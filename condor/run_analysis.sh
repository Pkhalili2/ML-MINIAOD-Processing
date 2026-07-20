#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 17 ]]; then
  echo "Usage: run_analysis.sh DATASET_TAG CHUNK_ID INPUT_LIST OUTPUT_DIR MAX_EVENTS CMSSW_VERSION SCRAM_ARCH ANALYSIS_CONFIG SAMPLE_LABEL IS_DATA JET_PT_MIN JET_ETA_MAX LEPTON_MODE MUON_PT_MIN MUON_ETA_MAX MUON_ISO_MAX MIN_DPHI [MUON_ISO_BRANCH=auto]"
  exit 2
fi

DATASET_TAG="$1"
CHUNK_ID="$2"
INPUT_LIST="$3"
OUTPUT_DIR="$4"
MAX_EVENTS="$5"
CMSSW_VERSION="$6"
SCRAM_ARCH="$7"
ANALYSIS_CONFIG="$8"
SAMPLE_LABEL="$9"
IS_DATA="${10}"
JET_PT_MIN="${11}"
JET_ETA_MAX="${12}"
LEPTON_MODE="${13}"
MUON_PT_MIN="${14}"
MUON_ETA_MAX="${15}"
MUON_ISO_MAX="${16}"
MIN_DPHI="${17}"
MUON_ISO_BRANCH="${18:-auto}"

JOBDIR="${_CONDOR_SCRATCH_DIR:-$(pwd)}"
REPORT="job_report_analysis_${DATASET_TAG}_${CHUNK_ID}.txt"
OUTPUT_TARBALL="analysis_outputs_${DATASET_TAG}_${CHUNK_ID}.tgz"
BUILD_CPUS="${BUILD_CPUS:-${_CONDOR_NPROCS:-1}}"
ANALYSIS_RETRIES="${ANALYSIS_RETRIES:-2}"
STAGED_OUTPUTS=()
FINALIZED_OUTPUT_TARBALL=0

cd "${JOBDIR}"
touch "${REPORT}"

reexec_args=("$@")
if [[ "${AK15_PREFETCH_XROOTD:-0}" == "1" && -z "${STARTED_SINGULARITY:-}" ]]; then
  transferred_input_list=""
  for candidate in "${INPUT_LIST}" "${JOBDIR}/${INPUT_LIST}" "$(basename "${INPUT_LIST}")"; do
    if [[ -f "${candidate}" ]]; then
      transferred_input_list="$(readlink -f "${candidate}")"
      break
    fi
  done
  if [[ -z "${transferred_input_list}" ]]; then
    echo "ERROR: could not find transferred input list for xrootd prefetch"
    exit 4
  fi
  if ! command -v xrdcp >/dev/null 2>&1; then
    echo "ERROR: xrdcp is unavailable on the worker host"
    exit 4
  fi

  prefetched_input_list="${JOBDIR}/prefetched_${DATASET_TAG}_${CHUNK_ID}.txt"
  : > "${prefetched_input_list}"
  prefetch_index=0
  while IFS= read -r source_path; do
    source_path="${source_path#${source_path%%[![:space:]]*}}"
    source_path="${source_path%${source_path##*[![:space:]]}}"
    [[ -n "${source_path}" && "${source_path}" != \#* ]] || continue
    if [[ "${source_path}" == root://* ]]; then
      local_path="${JOBDIR}/prefetched_$(printf '%04d' "${prefetch_index}").root"
      echo "Prefetching ${source_path} -> ${local_path}"
      timeout "${AK15_PREFETCH_TIMEOUT:-1800}" xrdcp -f "${source_path}" "${local_path}"
      if [[ ! -s "${local_path}" ]]; then
        echo "ERROR: xrdcp did not produce a nonempty local file"
        exit 4
      fi
      printf '%s\n' "${local_path}" >> "${prefetched_input_list}"
      prefetch_index=$((prefetch_index + 1))
    else
      printf '%s\n' "${source_path}" >> "${prefetched_input_list}"
    fi
  done < "${transferred_input_list}"
  if [[ ! -s "${prefetched_input_list}" ]]; then
    echo "ERROR: xrootd prefetch produced an empty input list"
    exit 4
  fi
  reexec_args[2]="${prefetched_input_list}"
fi

if [[ "${USE_SINGULARITY:-1}" == "1" && -z "${STARTED_SINGULARITY:-}" ]]; then
  CONTAINER_IMAGE="${CONTAINER_IMAGE:-/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel7}"
  container_runtime=""
  if command -v singularity >/dev/null 2>&1; then
    container_runtime="singularity"
  elif command -v apptainer >/dev/null 2>&1; then
    container_runtime="apptainer"
  fi

  if [[ -n "${container_runtime}" && -e "${CONTAINER_IMAGE}" ]]; then
    export STARTED_SINGULARITY=1
    export SINGULARITY_CACHEDIR="${JOBDIR}/singularity"
    export APPTAINER_CACHEDIR="${JOBDIR}/apptainer"
    script_path="./$(basename "$0")"
    if [[ ! -x "${script_path}" && -x "./condor/$(basename "$0")" ]]; then
      script_path="./condor/$(basename "$0")"
    fi
    if [[ ! -x "${script_path}" ]]; then
      echo "ERROR: could not find executable wrapper inside ${JOBDIR}"
      exit 2
    fi
    mounts=(-B "$(pwd -P)" -B /cvmfs)
    if [[ -n "${_CONDOR_SCRATCH_DIR:-}" && "$(cd "${_CONDOR_SCRATCH_DIR}" && pwd -P)" != "$(pwd -P)" ]]; then
      mounts+=(-B "${_CONDOR_SCRATCH_DIR}")
    fi
    if [[ -d /hdfs ]]; then
      mounts+=(-B /hdfs)
    fi
    exec "${container_runtime}" exec --no-home "${mounts[@]}" "${CONTAINER_IMAGE}" /bin/bash "${script_path}" "${reexec_args[@]}"
  fi
fi

exec > >(tee -a "${REPORT}") 2>&1

finalize_output_tarball() {
  local status="${1:-0}"
  local tar_status=0
  if [[ "${FINALIZED_OUTPUT_TARBALL}" == "1" ]]; then
    return 0
  fi
  FINALIZED_OUTPUT_TARBALL=1
  set +e
  cd "${JOBDIR}" 2>/dev/null || return 0
  if [[ "${#STAGED_OUTPUTS[@]}" -gt 0 ]]; then
    tar -czf "${OUTPUT_TARBALL}" "${STAGED_OUTPUTS[@]}"
    tar_status=$?
    if [[ "${tar_status}" != "0" ]]; then
      echo "ERROR: failed to create ${OUTPUT_TARBALL}"
      return 9
    fi
    tar -tzf "${OUTPUT_TARBALL}"
  elif [[ ! -f "${OUTPUT_TARBALL}" ]]; then
    tar -czf "${OUTPUT_TARBALL}" --files-from /dev/null
    echo "Created empty output transfer tarball: ${OUTPUT_TARBALL}"
  fi
  if [[ "${status}" != "0" ]]; then
    echo "Job exiting with status ${status}; logs above contain the payload failure."
  fi
}

trap 'status=$?; finalize_output_tarball "${status}" || status=$?; exit "${status}"' EXIT

resolve_input_list() {
  local candidate="$1"
  if [[ -f "${candidate}" ]]; then
    readlink -f "${candidate}"
    return 0
  fi
  if [[ -f "${JOBDIR}/${candidate}" ]]; then
    readlink -f "${JOBDIR}/${candidate}"
    return 0
  fi
  if [[ -f "$(basename "${candidate}")" ]]; then
    readlink -f "$(basename "${candidate}")"
    return 0
  fi
  return 1
}

copy_output() {
  local src="$1"
  local dest_name="$2"
  local dest="${OUTPUT_DIR%/}/${dest_name}"
  if ! mkdir -p "${OUTPUT_DIR}" 2>/dev/null || ! cp -f "${src}" "${dest}" 2>/dev/null; then
    echo "WARNING: could not copy ${src} directly to ${dest}; relying on Condor output transfer tarball."
    return 0
  fi
  echo "Copied ${src} -> ${dest}"
}

stage_output_for_transfer() {
  local src="$1"
  local stable_name="$2"
  cp -f "${src}" "${JOBDIR}/${stable_name}"
  STAGED_OUTPUTS+=("${stable_name}")
  echo "Staged ${src} for Condor output transfer as ${stable_name}"
}

run_with_retries() {
  local label="$1"
  shift
  local attempt=1
  local max_attempts=$((ANALYSIS_RETRIES + 1))
  local status=0
  while (( attempt <= max_attempts )); do
    echo "Starting ${label} attempt ${attempt}/${max_attempts}: $*"
    set +e
    "$@"
    status=$?
    set -e
    if [[ "${status}" == "0" ]]; then
      echo "${label} succeeded on attempt ${attempt}/${max_attempts}"
      return 0
    fi
    echo "WARNING: ${label} failed with status ${status} on attempt ${attempt}/${max_attempts}"
    if (( attempt < max_attempts )); then
      sleep "$((60 * attempt))"
    fi
    attempt=$((attempt + 1))
  done
  echo "ERROR: ${label} failed after ${max_attempts} attempts"
  return "${status}"
}

echo "AK15 physics-analysis Condor job"
echo "  host: $(hostname -f 2>/dev/null || hostname)"
echo "  dataset: ${DATASET_TAG}"
echo "  chunk: ${CHUNK_ID}"
echo "  input list: ${INPUT_LIST}"
echo "  output dir: ${OUTPUT_DIR}"
echo "  config: ${ANALYSIS_CONFIG}"
echo "  sample label: ${SAMPLE_LABEL}"
echo "  is data: ${IS_DATA}"
date -u

if [[ -f condor/package.tgz ]]; then
  tar -xzf condor/package.tgz
elif [[ -f package.tgz ]]; then
  tar -xzf package.tgz
else
  echo "ERROR: condor/package.tgz was not transferred"
  exit 4
fi

INPUT_LIST_PATH="$(resolve_input_list "${INPUT_LIST}")" || {
  echo "ERROR: could not find transferred input list '${INPUT_LIST}'"
  find . -maxdepth 4 -type f | sort
  exit 5
}

STAGED_INPUT_LIST="${JOBDIR}/staged_${DATASET_TAG}_${CHUNK_ID}.txt"
EXTRACTED_INPUT_LIST="${JOBDIR}/extracted_${DATASET_TAG}_${CHUNK_ID}.txt"
EXTRACTED_INPUT_DIR="${JOBDIR}/extracted_inputs_${DATASET_TAG}_${CHUNK_ID}"
while IFS= read -r line || [[ -n "${line}" ]]; do
  trimmed="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${line}")"
  if [[ -z "${trimmed}" || "${trimmed}" == \#* ]]; then
    echo "${line}" >> "${STAGED_INPUT_LIST}"
    continue
  fi
  raw="${trimmed#file:}"
  staged="${JOBDIR}/$(basename "${raw}")"
  if [[ "${raw}" == /* && -s "${staged}" ]]; then
    echo "file:${staged}" >> "${STAGED_INPUT_LIST}"
  else
    echo "${trimmed}" >> "${STAGED_INPUT_LIST}"
  fi
done < "${INPUT_LIST_PATH}"
INPUT_LIST_PATH="${STAGED_INPUT_LIST}"

if grep -E '(^|/)(root_outputs_.*\.tgz|.*\.tar\.gz|.*\.tgz)$' "${INPUT_LIST_PATH}" >/dev/null 2>&1; then
  mkdir -p "${EXTRACTED_INPUT_DIR}"
  : > "${EXTRACTED_INPUT_LIST}"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    trimmed="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${line}")"
    if [[ -z "${trimmed}" || "${trimmed}" == \#* ]]; then
      continue
    fi
    raw="${trimmed#file:}"
    case "${raw}" in
      *.tgz|*.tar.gz)
        tarball="${raw}"
        if [[ ! -s "${tarball}" && -s "${JOBDIR}/$(basename "${raw}")" ]]; then
          tarball="${JOBDIR}/$(basename "${raw}")"
        fi
        if [[ ! -s "${tarball}" ]]; then
          echo "ERROR: staged tarball is missing or empty: ${trimmed}"
          exit 5
        fi
        echo "Extracting Nano ROOT inputs from $(basename "${tarball}")"
        before_count="$(find "${EXTRACTED_INPUT_DIR}" -maxdepth 1 -type f -name 'nano_*.root' | wc -l)"
        if ! tar -xzf "${tarball}" -C "${EXTRACTED_INPUT_DIR}" --wildcards 'nano_*.root'; then
          echo "ERROR: failed to extract nano_*.root from ${tarball}"
          exit 5
        fi
        after_count="$(find "${EXTRACTED_INPUT_DIR}" -maxdepth 1 -type f -name 'nano_*.root' | wc -l)"
        if [[ "${after_count}" -le "${before_count}" ]]; then
          echo "ERROR: ${tarball} did not contain a nano_*.root file"
          exit 5
        fi
        ;;
      *)
        echo "${trimmed}" >> "${EXTRACTED_INPUT_LIST}"
        ;;
    esac
  done < "${INPUT_LIST_PATH}"
  find "${EXTRACTED_INPUT_DIR}" -maxdepth 1 -type f -name 'nano_*.root' -printf 'file:%p\n' | sort >> "${EXTRACTED_INPUT_LIST}"
  INPUT_LIST_PATH="${EXTRACTED_INPUT_LIST}"
fi

echo "Effective input list:"
cat "${INPUT_LIST_PATH}"

input_count="$(grep -v '^[[:space:]]*#' "${INPUT_LIST_PATH}" | grep -v '^[[:space:]]*$' | wc -l)"
if [[ "${input_count}" -lt 1 ]]; then
  echo "ERROR: input list is empty: ${INPUT_LIST_PATH}"
  exit 6
fi

source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH
scramv1 project CMSSW "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"
eval "$(scramv1 runtime -sh)"

cp -f "${JOBDIR}/PhysicsAnalysisTreeProducer.C" .
cp -f "${JOBDIR}/run_physics_analysis_tree.sh" .
if [[ -d "${JOBDIR}/config" ]]; then
  cp -a "${JOBDIR}/config" .
fi

analysis_file="analysis_${DATASET_TAG}_${CHUNK_ID}.root"
source_label="${SAMPLE_LABEL}_${CHUNK_ID}"

run_with_retries "physics analysis tree" \
  bash run_physics_analysis_tree.sh \
    "${INPUT_LIST_PATH}" \
    "${analysis_file}" \
    --config "${ANALYSIS_CONFIG}" \
    --sample "${source_label}" \
    --is-data "${IS_DATA}" \
    --max-events "${MAX_EVENTS}" \
    --jet-pt-min "${JET_PT_MIN}" \
    --jet-eta-max "${JET_ETA_MAX}" \
    --lepton-mode "${LEPTON_MODE}" \
    --muon-pt-min "${MUON_PT_MIN}" \
    --muon-eta-max "${MUON_ETA_MAX}" \
    --muon-iso-max "${MUON_ISO_MAX}" \
    --muon-iso-branch "${MUON_ISO_BRANCH}" \
    --min-dphi "${MIN_DPHI}"

if [[ ! -s "${analysis_file}" ]]; then
  echo "ERROR: physics analysis did not produce ${analysis_file}"
  exit 8
fi

stage_output_for_transfer "${analysis_file}" "${analysis_file}"
copy_output "${analysis_file}" "${analysis_file}"

echo "Final local ROOT outputs:"
ls -lh ./*.root 2>/dev/null || true
finalize_output_tarball 0
echo "Done."
date -u

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 12 ]]; then
  echo "Usage: run.sh DATASET_TAG CHUNK_ID INPUT_LIST MODE IS_SIGNAL MAX_EVENTS OUTPUT_DIR SAVE_NANO USE_X509 REQUIRE_HDFS CMSSW_VERSION SCRAM_ARCH [CONFIG_TYPE=mc|data] [SKIP_EVENTS=0] [AK15_LEADING_ONLY=0|1]"
  exit 2
fi

DATASET_TAG="$1"
CHUNK_ID="$2"
INPUT_LIST="$3"
MODE="$4"
IS_SIGNAL="$5"
MAX_EVENTS="$6"
OUTPUT_DIR="$7"
SAVE_NANO="$8"
USE_X509="$9"
REQUIRE_HDFS="${10}"
CMSSW_VERSION="${11}"
SCRAM_ARCH="${12}"
CONFIG_TYPE="${13:-mc}"
SKIP_EVENTS="${14:-0}"
AK15_LEADING_ONLY="${15:-0}"

case "${MODE}" in
  phase1|phase2|both) ;;
  *)
    echo "ERROR: MODE must be phase1, phase2, or both; got '${MODE}'"
    exit 2
    ;;
esac

case "${CONFIG_TYPE}" in
  mc)
    NANO_CONFIG_FILE="NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py"
    ;;
  data)
    NANO_CONFIG_FILE="NanoIncludingAK15_UL18NanoAODv2_OnlyNano_data_cfg.py"
    ;;
  *)
    echo "ERROR: CONFIG_TYPE must be mc or data; got '${CONFIG_TYPE}'"
    exit 2
    ;;
esac

case "${AK15_LEADING_ONLY}" in
  0|1) ;;
  *)
    echo "ERROR: AK15_LEADING_ONLY must be 0 or 1; got '${AK15_LEADING_ONLY}'"
    exit 2
    ;;
esac

JOBDIR="${_CONDOR_SCRATCH_DIR:-$(pwd)}"
REPORT="job_report_${DATASET_TAG}_${CHUNK_ID}.txt"
OUTPUT_TARBALL="root_outputs_${DATASET_TAG}_${CHUNK_ID}.tgz"
BUILD_CPUS="${BUILD_CPUS:-${_CONDOR_NPROCS:-1}}"
CMSRUN_RETRIES="${CMSRUN_RETRIES:-2}"
STAGED_OUTPUTS=()
DIRECT_OUTPUTS=()
FINALIZED_OUTPUT_TARBALL=0
TRANSFER_MARKER="condor_done_${DATASET_TAG}_${CHUNK_ID}.txt"
AK15_DIRECT_OUTPUT_TARBALL="${AK15_DIRECT_OUTPUT_TARBALL:-1}"
AK15_DIRECT_TARBALL_ONLY="${AK15_DIRECT_TARBALL_ONLY:-1}"
AK15_DIRECT_OUTPUT_FILES="${AK15_DIRECT_OUTPUT_FILES:-0}"
AK15_TRANSFER_STAGED_FILES="${AK15_TRANSFER_STAGED_FILES:-0}"

cd "${JOBDIR}"
touch "${REPORT}"

stage_x509_proxy() {
  if [[ "${USE_X509}" != "True" && "${USE_X509}" != "true" ]]; then
    return 0
  fi
  if [[ -z "${X509_USER_PROXY:-}" ]]; then
    echo "ERROR: USE_X509=True but X509_USER_PROXY is not set."
    exit 3
  fi
  if [[ ! -s "${X509_USER_PROXY}" ]]; then
    echo "ERROR: USE_X509=True but X509_USER_PROXY does not point to a readable proxy: ${X509_USER_PROXY}"
    exit 3
  fi

  local physical_jobdir
  physical_jobdir="$(pwd -P)"
  local staged_proxy="${physical_jobdir}/x509_proxy_${DATASET_TAG}_${CHUNK_ID}.pem"
  if [[ "$(readlink -f "${X509_USER_PROXY}")" != "${staged_proxy}" ]]; then
    cp "${X509_USER_PROXY}" "${staged_proxy}"
    chmod 600 "${staged_proxy}"
  fi
  export X509_USER_PROXY="${staged_proxy}"
  echo "Using staged X509 proxy: ${X509_USER_PROXY}"
}

stage_x509_proxy
: > "${TRANSFER_MARKER}"

reexec_args=("$@")
if [[ "${AK15_PREFETCH_XROOTD:-0}" == "1" && -z "${STARTED_SINGULARITY:-}" ]]; then
  prefetch_jobdir="$(pwd -P)"
  transferred_input_list=""
  for candidate in "${INPUT_LIST}" "${JOBDIR}/${INPUT_LIST}" "$(basename "${INPUT_LIST}")"; do
    if [[ -f "${candidate}" ]]; then
      transferred_input_list="$(readlink -f "${candidate}")"
      break
    fi
  done
  if [[ -z "${transferred_input_list}" ]]; then
    echo "ERROR: could not find the transferred input list for xrootd prefetch"
    exit 4
  fi
  command -v xrdcp >/dev/null 2>&1 || {
    echo "ERROR: xrdcp is unavailable on the worker host"
    exit 4
  }

  prefetched_input_list="${prefetch_jobdir}/prefetched_${DATASET_TAG}_${CHUNK_ID}.txt"
  : > "${prefetched_input_list}"
  prefetch_index=0
  while IFS= read -r source_path; do
    source_path="${source_path#${source_path%%[![:space:]]*}}"
    source_path="${source_path%${source_path##*[![:space:]]}}"
    [[ -n "${source_path}" && "${source_path}" != \#* ]] || continue
    if [[ "${source_path}" == root://* ]]; then
      local_path="${prefetch_jobdir}/prefetched_$(printf '%04d' "${prefetch_index}").root"
      echo "Prefetching ${source_path} -> ${local_path}"
      timeout "${AK15_PREFETCH_TIMEOUT:-1800}" xrdcp -f "${source_path}" "${local_path}"
      [[ -s "${local_path}" ]] || {
        echo "ERROR: xrdcp did not produce a nonempty local file"
        exit 4
      }
      printf '%s\n' "${local_path}" >> "${prefetched_input_list}"
      prefetch_index=$((prefetch_index + 1))
    else
      printf '%s\n' "${source_path}" >> "${prefetched_input_list}"
    fi
  done < "${transferred_input_list}"
  [[ -s "${prefetched_input_list}" ]] || {
    echo "ERROR: xrootd prefetch produced an empty input list"
    exit 4
  }
  reexec_args[2]="${prefetched_input_list}"
fi

local_output_path() {
  local path="$1"
  if [[ "${path}" == /nfs_scratch/* && ! -d /nfs_scratch && -d /mnt ]]; then
    printf '/mnt/%s\n' "${path#/nfs_scratch/}"
  else
    printf '%s\n' "${path}"
  fi
}

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

    physical_pwd="$(pwd -P)"
    export _CONDOR_SCRATCH_DIR="${physical_pwd}"
    script_path="${physical_pwd}/$(basename "$0")"
    if [[ ! -x "${script_path}" && -x "${physical_pwd}/condor/$(basename "$0")" ]]; then
      script_path="${physical_pwd}/condor/$(basename "$0")"
    fi
    if [[ ! -x "${script_path}" ]]; then
      echo "ERROR: could not find executable wrapper inside ${JOBDIR} (physical cwd: ${physical_pwd})"
      find "${physical_pwd}" -maxdepth 2 -type f | sort
      exit 2
    fi

    mounts=(-B "${physical_pwd}:${physical_pwd}:rw" -B /cvmfs)
    if [[ -n "${_CONDOR_SCRATCH_DIR:-}" && "$(cd "${_CONDOR_SCRATCH_DIR}" && pwd -P)" != "$(pwd -P)" ]]; then
      mounts+=(-B "${_CONDOR_SCRATCH_DIR}:${_CONDOR_SCRATCH_DIR}:rw")
    fi
    if [[ -d /hdfs ]]; then
      mounts+=(-B /hdfs)
    fi
    if [[ -d /nfs_scratch ]]; then
      mounts+=(-B /nfs_scratch:/mnt)
    fi
    if [[ -n "${X509_USER_PROXY:-}" && -e "${X509_USER_PROXY}" ]]; then
      proxy_dir="$(dirname "${X509_USER_PROXY}")"
      mounts+=(-B "${proxy_dir}:${proxy_dir}:ro")
    fi
    if [[ -d /etc/grid-security/certificates ]]; then
      mounts+=(-B /etc/grid-security/certificates)
    elif [[ -d /cvmfs/grid.cern.ch/etc/grid-security ]]; then
      mounts+=(-B /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security)
    fi

    exec "${container_runtime}" exec --no-home --pwd "${physical_pwd}" "${mounts[@]}" "${CONTAINER_IMAGE}" /bin/bash "${script_path}" "${reexec_args[@]}"
  else
    echo "WARNING: USE_SINGULARITY=1, but no Singularity/Apptainer runtime or container image was found."
    echo "         Continuing on the host OS; CMSSW_10_6_17 still requires an EL7-compatible environment."
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
    if [[ "${AK15_DIRECT_OUTPUT_FILES}" == "1" ]]; then
      echo "Direct output copy targets:"
      for copied in "${DIRECT_OUTPUTS[@]}"; do
        ls -lh "${copied}" 2>/dev/null || true
      done
      printf 'status=%s\ntag=%s\nchunk=%s\ndirect_outputs=%s\n' "${status}" "${DATASET_TAG}" "${CHUNK_ID}" "${DIRECT_OUTPUTS[*]}" > "${TRANSFER_MARKER}"
      copy_output "${TRANSFER_MARKER}" "${TRANSFER_MARKER}" || return 9
      copy_output "${REPORT}" "${REPORT}" || return 9
      tar -czf "${OUTPUT_TARBALL}" "${TRANSFER_MARKER}"
      tar_status=$?
      if [[ "${tar_status}" != "0" ]] || ! tar -tzf "${OUTPUT_TARBALL}" >/dev/null; then
        echo "ERROR: failed to create direct-output audit tarball ${OUTPUT_TARBALL}"
        return 9
      fi
      echo "Prepared direct ROOT outputs: ${DIRECT_OUTPUTS[*]}"
    elif [[ "${AK15_TRANSFER_STAGED_FILES}" == "1" ]]; then
      local missing=0
      for staged in "${STAGED_OUTPUTS[@]}"; do
        if [[ ! -s "${staged}" ]]; then
          echo "ERROR: expected staged output is missing or empty: ${staged}"
          missing=1
        fi
      done
      if [[ "${missing}" != "0" ]]; then
        return 9
      fi
      printf 'status=%s\ntag=%s\nchunk=%s\nstaged_outputs=%s\n' "${status}" "${DATASET_TAG}" "${CHUNK_ID}" "${STAGED_OUTPUTS[*]}" > "${TRANSFER_MARKER}"
      echo "Prepared staged ROOT files for Condor output transfer: ${STAGED_OUTPUTS[*]}"
    elif [[ "${AK15_DIRECT_OUTPUT_TARBALL}" == "1" && "${OUTPUT_DIR}" != root://* && "${OUTPUT_DIR}" != davs://* && "${OUTPUT_DIR}" != gsiftp://* ]]; then
      local effective_output_dir
      effective_output_dir="$(local_output_path "${OUTPUT_DIR%/}")"
      mkdir -p "${effective_output_dir}"
      local direct_tar="${effective_output_dir%/}/${OUTPUT_TARBALL}"
      local tmp_tar="${direct_tar}.tmp.$$"
      tar -czf "${tmp_tar}" "${STAGED_OUTPUTS[@]}"
      tar_status=$?
      if [[ "${tar_status}" != "0" ]]; then
        rm -f "${tmp_tar}"
        echo "ERROR: failed to create direct output tarball ${tmp_tar} (tar status ${tar_status})"
        return 9
      fi
      if ! tar -tzf "${tmp_tar}"; then
        rm -f "${tmp_tar}"
        echo "ERROR: direct output tarball failed validation: ${tmp_tar}"
        return 9
      fi
      mv -f "${tmp_tar}" "${direct_tar}"
      echo "Created direct output tarball: ${direct_tar}"
      printf 'status=%s\ntag=%s\nchunk=%s\ndirect_tarball=%s\n' "${status}" "${DATASET_TAG}" "${CHUNK_ID}" "${direct_tar}" > "${TRANSFER_MARKER}"
    else
      tar -czf "${OUTPUT_TARBALL}" "${STAGED_OUTPUTS[@]}"
      tar_status=$?
      if [[ "${tar_status}" != "0" ]]; then
        echo "ERROR: failed to create Condor output transfer tarball ${OUTPUT_TARBALL} (tar status ${tar_status})"
        return 9
      fi
      echo "Created Condor output transfer tarball: ${OUTPUT_TARBALL}"
      tar -tzf "${OUTPUT_TARBALL}"
      tar_status=$?
      if [[ "${tar_status}" != "0" ]]; then
        echo "ERROR: Condor output transfer tarball failed validation: ${OUTPUT_TARBALL} (tar status ${tar_status})"
        return 9
      fi
      printf 'status=%s\ntag=%s\nchunk=%s\ntransfer_tarball=%s\n' "${status}" "${DATASET_TAG}" "${CHUNK_ID}" "${OUTPUT_TARBALL}" > "${TRANSFER_MARKER}"
    fi
  elif [[ ! -f "${TRANSFER_MARKER}" ]]; then
    printf 'status=%s\ntag=%s\nchunk=%s\nno_staged_outputs=1\n' "${status}" "${DATASET_TAG}" "${CHUNK_ID}" > "${TRANSFER_MARKER}"
    echo "Created Condor transfer marker: ${TRANSFER_MARKER}"
  fi

  if [[ "${status}" != "0" ]]; then
    echo "Job exiting with status ${status}; logs above contain the payload failure."
  fi
}

trap 'status=$?; finalize_output_tarball "${status}" || status=$?; exit "${status}"' EXIT

echo "AK15 Condor job"
echo "  host: $(hostname -f 2>/dev/null || hostname)"
echo "  jobdir: ${JOBDIR}"
echo "  dataset: ${DATASET_TAG}"
echo "  chunk: ${CHUNK_ID}"
echo "  mode: ${MODE}"
echo "  config type: ${CONFIG_TYPE}"
echo "  nano config: ${NANO_CONFIG_FILE}"
echo "  input list: ${INPUT_LIST}"
echo "  output dir: ${OUTPUT_DIR}"
echo "  max events: ${MAX_EVENTS}"
echo "  skip events: ${SKIP_EVENTS}"
echo "  leading AK15 only: ${AK15_LEADING_ONLY}"
echo "  save nano: ${SAVE_NANO}"
echo "  use x509: ${USE_X509}"
echo "  require hdfs: ${REQUIRE_HDFS}"
date -u

if [[ -f condor/package.tgz ]]; then
  tar -xzf condor/package.tgz
elif [[ -f package.tgz ]]; then
  tar -xzf package.tgz
else
  echo "ERROR: condor/package.tgz was not transferred"
  exit 4
fi

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

INPUT_LIST_PATH="$(resolve_input_list "${INPUT_LIST}")" || {
  echo "ERROR: could not find transferred input list '${INPUT_LIST}'"
  find . -maxdepth 4 -type f | sort
  exit 5
}

input_count="$(grep -v '^[[:space:]]*#' "${INPUT_LIST_PATH}" | grep -v '^[[:space:]]*$' | wc -l)"
if [[ "${input_count}" -lt 1 ]]; then
  echo "ERROR: input list is empty: ${INPUT_LIST_PATH}"
  exit 6
fi
echo "Input files in this chunk: ${input_count}"

xrootd_url_parts() {
  local url="$1"
  local rest host path
  rest="${url#root://}"
  host="${rest%%/*}"
  path="${rest#*/}"
  printf 'root://%s %s\n' "${host}" "${path}"
}

xrootd_existing_size() {
  local url="$1"
  local base path
  read -r base path < <(xrootd_url_parts "${url}")
  xrdfs "${base}" stat "${path}" 2>/dev/null | awk '/Size:/ {print $2; exit}'
}

xrootd_remove_existing() {
  local url="$1"
  local base path
  read -r base path < <(xrootd_url_parts "${url}")
  xrdfs "${base}" rm "${path}"
}

copy_output() {
  local src="$1"
  local dest_name="$2"
  local effective_output_dir
  effective_output_dir="$(local_output_path "${OUTPUT_DIR%/}")"
  local dest="${effective_output_dir%/}/${dest_name}"

  if [[ "${AK15_DIRECT_OUTPUT_TARBALL}" == "1" && "${AK15_DIRECT_TARBALL_ONLY}" == "1" && "${OUTPUT_DIR}" != root://* && "${OUTPUT_DIR}" != davs://* && "${OUTPUT_DIR}" != gsiftp://* ]]; then
    echo "Skipping individual direct copy for ${src}; direct tarball mode will write ${OUTPUT_TARBALL}."
    return 0
  fi

  case "${OUTPUT_DIR}" in
    root://*)
      existing_size="$(xrootd_existing_size "${dest}" || true)"
      if [[ "${existing_size}" =~ ^[0-9]+$ ]]; then
        if [[ "${existing_size}" == "0" ]]; then
          echo "ERROR: preserving existing zero-byte xrootd output for inspection: ${dest}"
          return 9
        else
          echo "Output already exists and is nonempty; keeping existing file: ${dest} (${existing_size} bytes)"
          if [[ "${AK15_DIRECT_OUTPUT_FILES}" == "1" ]]; then
            DIRECT_OUTPUTS+=("${dest}")
          fi
          return 0
        fi
      fi
      if ! xrdcp "${src}" "${dest}"; then
        echo "ERROR: xrdcp failed for ${src} -> ${dest}"
        return 9
      fi
      ;;
    davs://*|gsiftp://*)
      gfal-copy -f "${src}" "${dest}"
      ;;
    *)
      if ! mkdir -p "${effective_output_dir}" 2>/dev/null || ! cp -f "${src}" "${dest}" 2>/dev/null; then
        if [[ "${AK15_DIRECT_OUTPUT_FILES}" == "1" ]]; then
          echo "ERROR: could not copy ${src} directly to ${dest}."
          return 9
        fi
        echo "WARNING: could not copy ${src} directly to ${dest}; relying on Condor output transfer tarball."
        return 0
      fi
      ;;
  esac
  echo "Copied ${src} -> ${dest}"
  if [[ "${AK15_DIRECT_OUTPUT_FILES}" == "1" ]]; then
    DIRECT_OUTPUTS+=("${dest}")
  fi
}

stage_output_for_transfer() {
  local src="$1"
  local stable_name="$2"
  cp -f "${src}" "${JOBDIR}/${stable_name}"
  STAGED_OUTPUTS+=("${stable_name}")
  echo "Staged ${src} for Condor output transfer as ${stable_name}"
}

write_output_tarball() {
  local finalize_status=0
  finalize_output_tarball 0 || finalize_status=$?
  if [[ "${finalize_status}" != "0" ]]; then
    echo "ERROR: output finalization failed with status ${finalize_status}"
    exit "${finalize_status}"
  fi
}

run_with_retries() {
  local label="$1"
  shift
  local attempt=1
  local max_attempts=$((CMSRUN_RETRIES + 1))
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
      sleep_seconds=$((60 * attempt))
      echo "Retrying ${label} after ${sleep_seconds} seconds..."
      sleep "${sleep_seconds}"
    fi
    attempt=$((attempt + 1))
  done

  echo "ERROR: ${label} failed after ${max_attempts} attempts"
  return "${status}"
}

source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH
export XRD_NETWORKSTACK=IPv4
export XRD_CONNECTIONWINDOW="${XRD_CONNECTIONWINDOW:-30}"
export XRD_REQUESTTIMEOUT="${XRD_REQUESTTIMEOUT:-1800}"

if [[ "${USE_X509}" == "True" || "${USE_X509}" == "true" ]]; then
  stage_x509_proxy
  if command -v voms-proxy-info >/dev/null 2>&1; then
    echo "Proxy identity on worker: $(voms-proxy-info -identity 2>/dev/null || true)"
    echo "Proxy seconds remaining on worker: $(voms-proxy-info -timeleft 2>/dev/null || true)"
    voms-proxy-info -exists -valid 1:00 || {
      echo "ERROR: USE_X509=True but no proxy with at least 1 hour remaining is available"
      exit 3
    }
  elif [[ -n "${X509_USER_PROXY:-}" && -s "${X509_USER_PROXY}" ]]; then
    echo "WARNING: voms-proxy-info is not available on this worker; using staged X509_USER_PROXY=${X509_USER_PROXY}."
  else
    echo "ERROR: USE_X509=True but voms-proxy-info is unavailable and X509_USER_PROXY is missing."
    exit 3
  fi
fi

scramv1 project CMSSW "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"
eval "$(scramv1 runtime -sh)"

cp -a "${JOBDIR}/MyAnalysis" .
cp -a "${JOBDIR}/JMEAnalysis" .
cp -f "${JOBDIR}/NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py" .
cp -f "${JOBDIR}/NanoIncludingAK15_UL18NanoAODv2_OnlyNano_data_cfg.py" .
cp -f "${JOBDIR}/AK15NanoFlatTreeProducer.C" .
cp -f "${JOBDIR}/run_ak15_nano_flat_tree.sh" .

scram b -j "${BUILD_CPUS}"

NANO_FILE=""
if [[ "${MODE}" == "phase1" || "${MODE}" == "both" ]]; then
  cms_inputs="$(
    grep -v '^[[:space:]]*#' "${INPUT_LIST_PATH}" |
    grep -v '^[[:space:]]*$' |
    paste -sd, -
  )"

  nano_stem="nano_${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}"
  echo "Running Stage 1 -> ${nano_stem}_Nano.root"
  run_with_retries "Stage 1 cmsRun" \
    cmsRun "${NANO_CONFIG_FILE}" \
    inputFiles="${cms_inputs}" \
    outputFile="${nano_stem}.root" \
    maxEvents="${MAX_EVENTS}" \
    skipEvents="${SKIP_EVENTS}" \
    ak15LeadingOnly="${AK15_LEADING_ONLY}"

  NANO_FILE="$(ls -t "${nano_stem}"*_Nano*.root 2>/dev/null | head -n 1 || true)"
  if [[ -z "${NANO_FILE}" || ! -s "${NANO_FILE}" ]]; then
    echo "ERROR: Stage 1 did not produce a NanoAOD output matching ${nano_stem}*_Nano*.root"
    exit 7
  fi

  if [[ "${MODE}" == "phase1" || "${SAVE_NANO}" == "1" ]]; then
    stage_output_for_transfer "${NANO_FILE}" "nano_${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}.root"
    if [[ "${AK15_DIRECT_OUTPUT_FILES}" == "1" ]]; then
      copy_output "${JOBDIR}/nano_${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}.root" "nano_${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}.root"
    else
      copy_output "${NANO_FILE}" "$(basename "${NANO_FILE}")"
    fi
  fi
fi

if [[ "${MODE}" == "phase2" || "${MODE}" == "both" ]]; then
  if [[ "${MODE}" == "both" ]]; then
    phase2_input="${NANO_FILE}"
    phase2_max_events="-1"
  else
    phase2_input="${INPUT_LIST_PATH}"
    phase2_max_events="${MAX_EVENTS}"
  fi

  flat_file="flat_${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}.root"
  source_label="${DATASET_TAG}_${CONFIG_TYPE}_${CHUNK_ID}"
  echo "Running Stage 2 -> ${flat_file}"
  run_with_retries "Stage 2 flat tree" \
    bash run_ak15_nano_flat_tree.sh \
    "${phase2_input}" \
    "${flat_file}" \
    "${IS_SIGNAL}" \
    "${phase2_max_events}" \
    "${source_label}"

  if [[ ! -s "${flat_file}" ]]; then
    echo "ERROR: Stage 2 did not produce ${flat_file}"
    exit 8
  fi
  stage_output_for_transfer "${flat_file}" "${flat_file}"
  copy_output "${flat_file}" "${flat_file}"
fi

echo "Final local ROOT outputs:"
ls -lh ./*.root 2>/dev/null || true
write_output_tarball
echo "Done."
date -u

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 12 ]]; then
  echo "Usage: run.sh DATASET_TAG CHUNK_ID INPUT_LIST MODE IS_SIGNAL MAX_EVENTS OUTPUT_DIR SAVE_NANO USE_X509 REQUIRE_HDFS CMSSW_VERSION SCRAM_ARCH"
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

case "${MODE}" in
  phase1|phase2|both) ;;
  *)
    echo "ERROR: MODE must be phase1, phase2, or both; got '${MODE}'"
    exit 2
    ;;
esac

JOBDIR="${_CONDOR_SCRATCH_DIR:-$(pwd)}"
REPORT="job_report_${DATASET_TAG}_${CHUNK_ID}.txt"
OUTPUT_TARBALL="root_outputs_${DATASET_TAG}_${CHUNK_ID}.tgz"
BUILD_CPUS="${BUILD_CPUS:-${_CONDOR_NPROCS:-1}}"
STAGED_OUTPUTS=()

cd "${JOBDIR}"

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

    script_path="$0"
    if [[ ! -x "${script_path}" ]]; then
      if [[ -x "./$(basename "$0")" ]]; then
        script_path="./$(basename "$0")"
      elif [[ -x "./condor/$(basename "$0")" ]]; then
        script_path="./condor/$(basename "$0")"
      fi
    fi

    mounts=(-B "$(pwd -P)" -B /cvmfs)
    if [[ -n "${_CONDOR_SCRATCH_DIR:-}" ]]; then
      mounts+=(-B "${_CONDOR_SCRATCH_DIR}")
    fi
    if [[ -d /hdfs ]]; then
      mounts+=(-B /hdfs)
    fi
    if [[ -d /etc/grid-security/certificates ]]; then
      mounts+=(-B /etc/grid-security/certificates)
    elif [[ -d /cvmfs/grid.cern.ch/etc/grid-security ]]; then
      mounts+=(-B /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security)
    fi

    exec "${container_runtime}" exec --no-home "${mounts[@]}" "${CONTAINER_IMAGE}" "${script_path}" "$@"
  else
    echo "WARNING: USE_SINGULARITY=1, but no Singularity/Apptainer runtime or container image was found."
    echo "         Continuing on the host OS; CMSSW_10_6_17 still requires an EL7-compatible environment."
  fi
fi

exec > >(tee -a "${REPORT}") 2>&1

echo "AK15 Condor job"
echo "  host: $(hostname -f 2>/dev/null || hostname)"
echo "  jobdir: ${JOBDIR}"
echo "  dataset: ${DATASET_TAG}"
echo "  chunk: ${CHUNK_ID}"
echo "  mode: ${MODE}"
echo "  input list: ${INPUT_LIST}"
echo "  output dir: ${OUTPUT_DIR}"
echo "  max events: ${MAX_EVENTS}"
echo "  save nano: ${SAVE_NANO}"
echo "  use x509: ${USE_X509}"
echo "  require hdfs: ${REQUIRE_HDFS}"
date -u

if [[ "${USE_X509}" == "True" || "${USE_X509}" == "true" ]]; then
  voms-proxy-info -exists -valid 1:00 || {
    echo "ERROR: USE_X509=True but no proxy with at least 1 hour remaining is available"
    exit 3
  }
fi

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

copy_output() {
  local src="$1"
  local dest_name="$2"
  local dest="${OUTPUT_DIR%/}/${dest_name}"

  case "${OUTPUT_DIR}" in
    root://*)
      xrdcp -f "${src}" "${dest}"
      ;;
    davs://*|gsiftp://*)
      gfal-copy -f "${src}" "${dest}"
      ;;
    *)
      if ! mkdir -p "${OUTPUT_DIR}" 2>/dev/null || ! cp -f "${src}" "${dest}" 2>/dev/null; then
        echo "WARNING: could not copy ${src} directly to ${dest}; relying on Condor output transfer tarball."
        return 0
      fi
      ;;
  esac
  echo "Copied ${src} -> ${dest}"
}

stage_output_for_transfer() {
  local src="$1"
  local stable_name="$2"
  cp -f "${src}" "${JOBDIR}/${stable_name}"
  STAGED_OUTPUTS+=("${stable_name}")
  echo "Staged ${src} for Condor output transfer as ${stable_name}"
}

write_output_tarball() {
  cd "${JOBDIR}"
  if [[ "${#STAGED_OUTPUTS[@]}" -gt 0 ]]; then
    tar -czf "${OUTPUT_TARBALL}" "${STAGED_OUTPUTS[@]}"
    echo "Created Condor output transfer tarball: ${OUTPUT_TARBALL}"
    tar -tzf "${OUTPUT_TARBALL}"
  else
    tar -czf "${OUTPUT_TARBALL}" --files-from /dev/null
    echo "Created empty Condor output transfer tarball: ${OUTPUT_TARBALL}"
  fi
}

source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH
export XRD_NETWORKSTACK=IPv4

scramv1 project CMSSW "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"
eval "$(scramv1 runtime -sh)"

cp -a "${JOBDIR}/MyAnalysis" .
cp -a "${JOBDIR}/JMEAnalysis" .
cp -f "${JOBDIR}/NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py" .
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

  nano_stem="nano_${DATASET_TAG}_${CHUNK_ID}"
  echo "Running Stage 1 -> ${nano_stem}_Nano.root"
  cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
    inputFiles="${cms_inputs}" \
    outputFile="${nano_stem}.root" \
    maxEvents="${MAX_EVENTS}"

  NANO_FILE="$(ls -t "${nano_stem}"*_Nano*.root 2>/dev/null | head -n 1 || true)"
  if [[ -z "${NANO_FILE}" || ! -s "${NANO_FILE}" ]]; then
    echo "ERROR: Stage 1 did not produce a NanoAOD output matching ${nano_stem}*_Nano*.root"
    exit 7
  fi

  if [[ "${MODE}" == "phase1" || "${SAVE_NANO}" == "1" ]]; then
    stage_output_for_transfer "${NANO_FILE}" "nano_${DATASET_TAG}_${CHUNK_ID}.root"
    copy_output "${NANO_FILE}" "$(basename "${NANO_FILE}")"
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

  flat_file="flat_${DATASET_TAG}_${CHUNK_ID}.root"
  source_label="${DATASET_TAG}_${CHUNK_ID}"
  echo "Running Stage 2 -> ${flat_file}"
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

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TAG=""
INPUT=""
OUTPUT_DIR=""
RETURN_DIR=""
FILES_PER_JOB="20"
LIMIT_FILES="0"
LIMIT_JOBS="0"
MAX_EVENTS="-1"
MAX_RETRIES="2"
REQUEST_DISK="8 GB"
CONFIG="config/analysis_muon_2018.json"
SAMPLE_LABEL=""
IS_DATA="0"
JET_PT_MIN="200"
JET_ETA_MAX="3"
LEPTON_MODE="muon"
MUON_PT_MIN="30"
MUON_ETA_MAX="2.5"
MUON_ISO_MAX="0.3"
MUON_ISO_BRANCH="auto"
MIN_DPHI="1.5"
USE_X509="0"
REQUIRE_HDFS="auto"
CMSSW_VERSION="CMSSW_10_6_17"
SCRAM_ARCH="slc7_amd64_gcc700"
INPUT_PREFIX="auto"
HDFS_XROOTD_PREFIX="${AK15_HDFS_XROOTD_PREFIX:-root://cmsxrootd.hep.wisc.edu//}"
PREFETCH_XROOTD="0"
DIRECT_OUTPUT_FILES="0"
STAGE_INPUT_FILES="auto"
DRY_RUN="0"
NO_SUBMIT="0"
CLEAR="1"

usage() {
  cat <<'EOF'
Usage:
  bash condor/submit_analysis_all.sh --tag TAG --input PHASE1_NANO_DIR_OR_GLOB --output-dir DIR [options]

Options:
  --files-per-job N          Default: 20
  --limit-files N            Use only first N input files
  --limit-jobs N             Use only first N jobs
  --max-events N             Analysis event limit per job. Default: -1
  --max-retries N            Condor retries after nonzero job exits. Default: 2
  --request-disk SIZE        Default: 8 GB
  --config PATH              Default: config/analysis_muon_2018.json
  --sample-label LABEL       Default: TAG
  --is-data 0|1              Default: 0
  --jet-pt-min X             Default: 200
  --jet-eta-max X            Default: 3
  --lepton-mode muon         Only muon is currently supported
  --muon-pt-min X            Default: 30
  --muon-eta-max X           Default: 2.5
  --muon-iso-max X           Default: 0.3
  --muon-iso-branch NAME     Default: auto
  --min-dphi X               Default: 1.5
  --use-x509                 Transfer current VOMS proxy
  --require-hdfs 0|1|auto    Default: auto
  --input-prefix auto|file|none|xrootd-wisc
  --hdfs-xrootd-prefix URL  Override the xrootd prefix used for /hdfs/store inputs.
  --prefetch-xrootd         Copy xrootd inputs to worker scratch before CMSSW starts.
  --direct-output-files 0|1 Copy compact ROOT outputs directly to OUTPUT_DIR.
  --stage-input-files 0|1|auto
                              Transfer local phase-1 ROOT files to the worker.
                              Default: auto for /nfs_scratch inputs.
  --dry-run                  Build submit ClassAd without submitting
  --no-submit                Prepare lists/package but do not call condor_submit
  --no-clear                 Keep old generated files for this tag
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --input) INPUT="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --return-dir) RETURN_DIR="$2"; shift 2 ;;
    --files-per-job) FILES_PER_JOB="$2"; shift 2 ;;
    --limit-files) LIMIT_FILES="$2"; shift 2 ;;
    --limit-jobs) LIMIT_JOBS="$2"; shift 2 ;;
    --max-events) MAX_EVENTS="$2"; shift 2 ;;
    --max-retries) MAX_RETRIES="$2"; shift 2 ;;
    --request-disk) REQUEST_DISK="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --sample-label) SAMPLE_LABEL="$2"; shift 2 ;;
    --is-data) IS_DATA="$2"; shift 2 ;;
    --jet-pt-min) JET_PT_MIN="$2"; shift 2 ;;
    --jet-eta-max) JET_ETA_MAX="$2"; shift 2 ;;
    --lepton-mode) LEPTON_MODE="$2"; shift 2 ;;
    --muon-pt-min) MUON_PT_MIN="$2"; shift 2 ;;
    --muon-eta-max) MUON_ETA_MAX="$2"; shift 2 ;;
    --muon-iso-max) MUON_ISO_MAX="$2"; shift 2 ;;
    --muon-iso-branch) MUON_ISO_BRANCH="$2"; shift 2 ;;
    --min-dphi) MIN_DPHI="$2"; shift 2 ;;
    --use-x509) USE_X509="1"; shift ;;
    --require-hdfs) REQUIRE_HDFS="$2"; shift 2 ;;
    --cmssw-version) CMSSW_VERSION="$2"; shift 2 ;;
    --scram-arch) SCRAM_ARCH="$2"; shift 2 ;;
    --input-prefix) INPUT_PREFIX="$2"; shift 2 ;;
    --hdfs-xrootd-prefix) HDFS_XROOTD_PREFIX="$2"; shift 2 ;;
    --prefetch-xrootd) PREFETCH_XROOTD="1"; shift ;;
    --direct-output-files) DIRECT_OUTPUT_FILES="$2"; shift 2 ;;
    --stage-input-files) STAGE_INPUT_FILES="$2"; shift 2 ;;
    --dry-run) DRY_RUN="1"; shift ;;
    --no-submit) NO_SUBMIT="1"; shift ;;
    --no-clear) CLEAR="0"; shift ;;
    --help|-h) usage; exit 0 ;;
    *)
      echo "ERROR: unknown option '$1'"
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${TAG}" || -z "${INPUT}" || -z "${OUTPUT_DIR}" ]]; then
  usage
  exit 2
fi

if [[ -z "${SAMPLE_LABEL}" ]]; then
  SAMPLE_LABEL="${TAG}"
fi
if [[ -z "${RETURN_DIR}" ]]; then
  case "${OUTPUT_DIR}" in
    /*) RETURN_DIR="${OUTPUT_DIR}" ;;
    *) RETURN_DIR="${REPO_ROOT}/condor/.returned/${TAG}" ;;
  esac
fi

cd "${REPO_ROOT}"
if [[ ! -f "${CONFIG}" ]]; then
  echo "ERROR: analysis config does not exist inside the project: ${CONFIG}"
  exit 2
fi

mkdir -p condor/.logs
mkdir -p "${RETURN_DIR}"
case "${OUTPUT_DIR}" in
  root://*|davs://*|gsiftp://*) ;;
  *) mkdir -p "${OUTPUT_DIR}" ;;
esac

if [[ "${DIRECT_OUTPUT_FILES}" != "0" && "${DIRECT_OUTPUT_FILES}" != "1" ]]; then
  echo "ERROR: --direct-output-files must be 0 or 1"
  exit 2
fi

make_args=(
  --tag "${TAG}"
  --input "${INPUT}"
  --mode phase2
  --config-type mc
  --is-signal 0
  --files-per-job "${FILES_PER_JOB}"
  --max-events "${MAX_EVENTS}"
  --output-dir "${OUTPUT_DIR}"
  --return-dir "${RETURN_DIR}"
  --save-nano 0
  --require-hdfs "${REQUIRE_HDFS}"
  --cmssw-version "${CMSSW_VERSION}"
  --scram-arch "${SCRAM_ARCH}"
  --input-prefix "${INPUT_PREFIX}"
  --hdfs-xrootd-prefix "${HDFS_XROOTD_PREFIX}"
)

if [[ "${LIMIT_FILES}" != "0" ]]; then
  make_args+=(--limit-files "${LIMIT_FILES}")
fi
if [[ "${LIMIT_JOBS}" != "0" ]]; then
  make_args+=(--limit-jobs "${LIMIT_JOBS}")
fi
if [[ "${USE_X509}" == "1" ]]; then
  make_args+=(--use-x509)
fi
if [[ "${CLEAR}" == "1" ]]; then
  make_args+=(--clear)
fi

python3 condor/make_filelists.py "${make_args[@]}"
bash condor/package_project.sh

JOB_TABLE="condor/.generated/${TAG}/job_table.txt"
if [[ ! -s "${JOB_TABLE}" ]]; then
  echo "ERROR: generated job table is empty: ${JOB_TABLE}"
  exit 3
fi

if [[ "${STAGE_INPUT_FILES}" == "auto" ]]; then
  case "${INPUT}" in
    /nfs_scratch/*|file:/nfs_scratch/*) STAGE_INPUT_FILES="1" ;;
    *) STAGE_INPUT_FILES="0" ;;
  esac
fi
if [[ "${STAGE_INPUT_FILES}" != "0" && "${STAGE_INPUT_FILES}" != "1" ]]; then
  echo "ERROR: --stage-input-files must be 0, 1, or auto"
  exit 2
fi

touch condor/.empty_transfer_input
JOB_TABLE_WITH_TRANSFERS="condor/.generated/${TAG}/job_table_with_transfers.txt"
while IFS= read -r row; do
  [[ -n "${row}" ]] || continue
  input_list="$(awk '{print $3}' <<< "${row}")"
  if [[ "${STAGE_INPUT_FILES}" == "1" ]]; then
    transfer_files="$(
      sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "${input_list}" |
      awk 'NF && $1 !~ /^#/ {print $1}' |
      sed -e 's#^file:##' |
      while IFS= read -r f; do
        case "${f}" in
          root://*|/store/*)
            echo "ERROR: cannot Condor-transfer remote input '${f}'" >&2
            exit 7
            ;;
          /*)
            if [[ ! -s "${f}" ]]; then
              echo "ERROR: staged input does not exist or is empty: ${f}" >&2
              exit 7
            fi
            printf '%s\n' "${f}"
            ;;
          *)
            echo "ERROR: staged input must be an absolute local file: ${f}" >&2
            exit 7
            ;;
        esac
      done |
      paste -sd, -
    )" || exit $?
    echo "${row} ${transfer_files}"
  else
    echo "${row} condor/.empty_transfer_input"
  fi
done < "${JOB_TABLE}" > "${JOB_TABLE_WITH_TRANSFERS}"
JOB_TABLE="${JOB_TABLE_WITH_TRANSFERS}"

echo
echo "Prepared $(wc -l < "${JOB_TABLE}") analysis jobs."
echo "Job table: ${JOB_TABLE}"
echo "Output dir: ${OUTPUT_DIR}"
echo "Analysis config: ${CONFIG}"
echo "Sample label: ${SAMPLE_LABEL}"
echo "Jet pT min: ${JET_PT_MIN}"
echo "Muon-only analysis mode: ${LEPTON_MODE}"
echo "Stage input files: ${STAGE_INPUT_FILES}"

if [[ "${NO_SUBMIT}" == "1" ]]; then
  echo "Not submitting because --no-submit was requested."
  exit 0
fi

submit_args=(
  JOB_TABLE="${JOB_TABLE}"
  AK15_MAX_RETRIES="${MAX_RETRIES}"
  AK15_REQUEST_DISK="${REQUEST_DISK}"
  AK15_PREFETCH_XROOTD="${PREFETCH_XROOTD}"
  AK15_DIRECT_OUTPUT_FILES="${DIRECT_OUTPUT_FILES}"
  ANALYSIS_CONFIG="${CONFIG}"
  SAMPLE_LABEL="${SAMPLE_LABEL}"
  IS_DATA_ANALYSIS="${IS_DATA}"
  JET_PT_MIN="${JET_PT_MIN}"
  JET_ETA_MAX="${JET_ETA_MAX}"
  LEPTON_MODE="${LEPTON_MODE}"
  MUON_PT_MIN="${MUON_PT_MIN}"
  MUON_ETA_MAX="${MUON_ETA_MAX}"
  MUON_ISO_MAX="${MUON_ISO_MAX}"
  MUON_ISO_BRANCH="${MUON_ISO_BRANCH}"
  MIN_DPHI="${MIN_DPHI}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  condor_submit "${submit_args[@]}" -dry-run "condor/.generated/${TAG}/analysis_dryrun.ad" condor/submit_analysis.sub
  echo "Wrote dry-run ClassAd: condor/.generated/${TAG}/analysis_dryrun.ad"
  exit 0
fi

condor_submit "${submit_args[@]}" condor/submit_analysis.sub

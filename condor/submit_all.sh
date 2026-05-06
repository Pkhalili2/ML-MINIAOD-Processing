#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TAG=""
INPUT=""
MODE="both"
IS_SIGNAL="1"
FILES_PER_JOB="20"
LIMIT_FILES="0"
LIMIT_JOBS="0"
MAX_EVENTS="-1"
OUTPUT_DIR=""
RETURN_DIR=""
SAVE_NANO="1"
USE_X509="0"
REQUIRE_HDFS="auto"
CMSSW_VERSION="CMSSW_10_6_17"
SCRAM_ARCH="slc7_amd64_gcc700"
XROOTD_PREFIX="root://cms-xrd-global.cern.ch//"
HDFS_XROOTD_PREFIX="root://cmsxrootd.hep.wisc.edu//"
INPUT_PREFIX="auto"
DRY_RUN="0"
NO_SUBMIT="0"
CLEAR="1"

usage() {
  cat <<'EOF'
Usage:
  bash condor/submit_all.sh --tag TAG --input INPUT [options]

Options:
  --mode phase1|phase2|both      Default: both
  --is-signal 0|1                Default: 1
  --files-per-job N              Default: 20
  --limit-files N                Use only the first N files
  --limit-jobs N                 Use only the first N generated jobs
  --max-events N                 Stage 1 maxEvents, or Stage 2 maxEvents in phase2 mode
  --output-dir PATH_OR_URL       Default: /nfs_scratch/$USER/ak15_condor_outputs/TAG
  --return-dir PATH              Submit-side directory for Condor-transferred ROOT tarballs
  --save-nano 0|1                Copy enriched NanoAOD outputs for phase1/both
  --use-x509                    Transfer your current VOMS proxy with the jobs
  --require-hdfs 0|1|auto        Default: auto
  --cmssw-version VERSION        Default: CMSSW_10_6_17
  --scram-arch ARCH              Default: slc7_amd64_gcc700
  --xrootd-prefix URL            Prefix for DAS /store files
  --hdfs-xrootd-prefix URL       Prefix for /hdfs/store files with --input-prefix xrootd-wisc
  --input-prefix auto|file|none|xrootd-wisc
  --dry-run                      Build the submit ClassAd without submitting
  --no-submit                    Prepare lists/package but do not call condor_submit
  --no-clear                     Keep old generated files for this tag
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --input) INPUT="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --is-signal) IS_SIGNAL="$2"; shift 2 ;;
    --files-per-job) FILES_PER_JOB="$2"; shift 2 ;;
    --limit-files) LIMIT_FILES="$2"; shift 2 ;;
    --limit-jobs) LIMIT_JOBS="$2"; shift 2 ;;
    --max-events) MAX_EVENTS="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --return-dir) RETURN_DIR="$2"; shift 2 ;;
    --save-nano) SAVE_NANO="$2"; shift 2 ;;
    --use-x509) USE_X509="1"; shift ;;
    --require-hdfs) REQUIRE_HDFS="$2"; shift 2 ;;
    --cmssw-version) CMSSW_VERSION="$2"; shift 2 ;;
    --scram-arch) SCRAM_ARCH="$2"; shift 2 ;;
    --xrootd-prefix) XROOTD_PREFIX="$2"; shift 2 ;;
    --hdfs-xrootd-prefix) HDFS_XROOTD_PREFIX="$2"; shift 2 ;;
    --input-prefix) INPUT_PREFIX="$2"; shift 2 ;;
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

if [[ -z "${TAG}" || -z "${INPUT}" ]]; then
  usage
  exit 2
fi

if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="${AK15_OUTPUT_BASE:-/nfs_scratch/${USER}/ak15_condor_outputs}/${TAG}"
fi
if [[ -z "${RETURN_DIR}" ]]; then
  case "${OUTPUT_DIR}" in
    /*) RETURN_DIR="${OUTPUT_DIR}" ;;
    *) RETURN_DIR="${REPO_ROOT}/condor/.returned/${TAG}" ;;
  esac
fi

cd "${REPO_ROOT}"
mkdir -p condor/.logs
mkdir -p "${RETURN_DIR}"
case "${OUTPUT_DIR}" in
  root://*|davs://*|gsiftp://*) ;;
  *) mkdir -p "${OUTPUT_DIR}" ;;
esac

make_args=(
  --tag "${TAG}"
  --input "${INPUT}"
  --mode "${MODE}"
  --is-signal "${IS_SIGNAL}"
  --files-per-job "${FILES_PER_JOB}"
  --max-events "${MAX_EVENTS}"
  --output-dir "${OUTPUT_DIR}"
  --return-dir "${RETURN_DIR}"
  --save-nano "${SAVE_NANO}"
  --require-hdfs "${REQUIRE_HDFS}"
  --cmssw-version "${CMSSW_VERSION}"
  --scram-arch "${SCRAM_ARCH}"
  --xrootd-prefix "${XROOTD_PREFIX}"
  --hdfs-xrootd-prefix "${HDFS_XROOTD_PREFIX}"
  --input-prefix "${INPUT_PREFIX}"
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

echo
echo "Prepared $(wc -l < "${JOB_TABLE}") jobs."
echo "Job table: ${JOB_TABLE}"
echo "Output dir: ${OUTPUT_DIR}"
echo "Condor transfer return dir: ${RETURN_DIR}"

if [[ "${NO_SUBMIT}" == "1" ]]; then
  echo "Not submitting because --no-submit was requested."
  exit 0
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  condor_submit JOB_TABLE="${JOB_TABLE}" -dry-run "condor/.generated/${TAG}/dryrun.ad" condor/submit.sub
  echo "Wrote dry-run ClassAd: condor/.generated/${TAG}/dryrun.ad"
  exit 0
fi

condor_submit JOB_TABLE="${JOB_TABLE}" condor/submit.sub

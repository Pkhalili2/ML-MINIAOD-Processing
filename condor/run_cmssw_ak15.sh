#!/usr/bin/env bash
set -euo pipefail

DATASET_TAG="${1:?missing DATASET_TAG}"
CHUNK_ID="${2:?missing CHUNK_ID}"
INPUT_LIST="${3:?missing INPUT_LIST}"
CMSSW_VERSION="${4:-CMSSW_10_6_17}"
SCRAM_ARCH="${5:-slc7_amd64_gcc700}"
IS_SIGNAL="${6:-0}"
FILL_ALL_EVENTS="${7:-1}"

JOBDIR="${_CONDOR_SCRATCH_DIR:-$(pwd)}"
OUTROOT="flat_${DATASET_TAG}_${CHUNK_ID}.root"

source /cvmfs/cms.cern.ch/cmsset_default.sh
if [[ -f /afs/hep.wisc.edu/cms/setup/bashrc ]]; then
  source /afs/hep.wisc.edu/cms/setup/bashrc
fi
export SCRAM_ARCH="${SCRAM_ARCH}"

cd "${JOBDIR}"
scramv1 project CMSSW "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"
eval "$(scramv1 runtime -sh)"

cd "${JOBDIR}"
tar -xzf MyAnalysis.tgz
tar -xJf JMEAnalysis.tar.xz

cd "${JOBDIR}/${CMSSW_VERSION}/src"
mkdir -p MyAnalysis
rsync -a --delete "${JOBDIR}/MyAnalysis/" "MyAnalysis/"

if [[ -d "${JOBDIR}/JMEAnalysis" ]]; then
  rsync -a "${JOBDIR}/JMEAnalysis/" "JMEAnalysis/"
fi

scram b -j 4

cd "${JOBDIR}"
cmsRun condor/NanoIncludingAK15_plusFlatTree_cfg.py \
  inputList="${JOBDIR}/${INPUT_LIST}" \
  flatOut="${JOBDIR}/${OUTROOT}" \
  maxEvents=-1 \
  isSignal="${IS_SIGNAL}" \
  fillAllEvents="${FILL_ALL_EVENTS}"

ls -lh "${OUTROOT}" || true
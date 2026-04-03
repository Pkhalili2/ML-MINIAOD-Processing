#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FILES_PER_JOB="${FILES_PER_JOB:-10}"

mkdir -p "${REPO_ROOT}/logs"
cd "${REPO_ROOT}"

tar -czf MyAnalysis.tgz MyAnalysis

if [[ ! -f JMEAnalysis.tar.xz ]]; then
  echo "Missing JMEAnalysis.tar.xz at repo top level"
  exit 1
fi

FILES_PER_JOB="${FILES_PER_JOB}" bash "${REPO_ROOT}/condor/make_filelists.sh"
bash "${REPO_ROOT}/condor/make_job_table.sh"
condor_submit "${REPO_ROOT}/condor/submit_ak15.sub"
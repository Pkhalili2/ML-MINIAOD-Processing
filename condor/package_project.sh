#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PACKAGE="${REPO_ROOT}/condor/package.tgz"

cd "${REPO_ROOT}"

required=(
  "MyAnalysis"
  "JMEAnalysis"
  "NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py"
  "AK15NanoFlatTreeProducer.C"
  "run_ak15_nano_flat_tree.sh"
  "scripts/count_events.py"
)

for path in "${required[@]}"; do
  if [[ ! -e "${path}" ]]; then
    echo "ERROR: required path '${path}' is missing"
    exit 1
  fi
done

tar \
  --exclude='*.root' \
  --exclude='*.so' \
  --exclude='*.pcm' \
  --exclude='*.d' \
  --exclude='__pycache__' \
  -czf "${PACKAGE}" \
  MyAnalysis \
  JMEAnalysis \
  NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  AK15NanoFlatTreeProducer.C \
  run_ak15_nano_flat_tree.sh \
  scripts/count_events.py

ls -lh "${PACKAGE}"

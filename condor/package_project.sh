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
  "NanoIncludingAK15_UL18NanoAODv2_OnlyNano_data_cfg.py"
  "AK15NanoFlatTreeProducer.C"
  "PhysicsAnalysisTreeProducer.C"
  "ReduceAK15NanoToLeading.C"
  "run_ak15_nano_flat_tree.sh"
  "run_reduce_ak15_nano_to_leading.sh"
  "condor/run.sh"
  "condor/run_analysis.sh"
  "condor/run_reduce_existing.sh"
  "run_physics_analysis_tree.sh"
  "config/analysis_muon_2018.json"
  "config/samples_2018.example.csv"
  "scripts/count_events.py"
  "scripts/sum_genweights.py"
  "scripts/prepare_sample_metadata.py"
  "scripts/make_weighted_plots.py"
  "scripts/collect_analysis_lumis.py"
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
  NanoIncludingAK15_UL18NanoAODv2_OnlyNano_data_cfg.py \
  AK15NanoFlatTreeProducer.C \
  PhysicsAnalysisTreeProducer.C \
  ReduceAK15NanoToLeading.C \
  run_ak15_nano_flat_tree.sh \
  run_reduce_ak15_nano_to_leading.sh \
  condor/run.sh \
  condor/run_analysis.sh \
  condor/run_reduce_existing.sh \
  run_physics_analysis_tree.sh \
  config \
  scripts/count_events.py \
  scripts/sum_genweights.py \
  scripts/prepare_sample_metadata.py \
  scripts/make_weighted_plots.py \
  scripts/collect_analysis_lumis.py

ls -lh "${PACKAGE}"

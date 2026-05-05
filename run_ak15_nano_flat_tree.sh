#!/bin/bash

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: bash run_ak15_nano_flat_tree.sh input_nano.root output_selected.root [isSignal=1] [maxEvents=-1] [sourceLabel]"
  exit 1
fi

input_file="$1"
output_file="$2"
is_signal="${3:-1}"
max_events="${4:--1}"
source_label="${5:-}"

check_path="$input_file"
case "$check_path" in
  @*) check_path="${check_path#@}" ;;
  file:*) check_path="${check_path#file:}" ;;
esac

case "$input_file" in
  root://*|davs://*|gsiftp://*) ;;
  *)
    if [ ! -f "$check_path" ]; then
      echo "ERROR: input file/list '$input_file' not found"
      exit 1
    fi
    ;;
esac

if ! command -v root >/dev/null 2>&1; then
  echo "ERROR: ROOT is not available. Run this inside CMSSW after:"
  echo "  source /cvmfs/cms.cern.ch/cmsset_default.sh"
  echo "  cmsenv"
  exit 1
fi

root -l -b -q "AK15NanoFlatTreeProducer.C+(\"${input_file}\",\"${output_file}\",${is_signal},${max_events},\"${source_label}\")"

echo
echo "Done. Output file:"
echo "${output_file}"

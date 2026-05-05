#!/bin/bash

set -e

if [ $# -lt 1 ]; then
  echo "Usage: bash run_nano_from_txt.sh one_file.txt [output_tag]"
  exit 1
fi

input_txt="$1"
tag="${2:-test}"

if [ ! -f "$input_txt" ]; then
  echo "ERROR: file '$input_txt' not found"
  exit 1
fi

input_file=$(grep -v '^[[:space:]]*#' "$input_txt" | grep -v '^[[:space:]]*$' | head -n 1)

if [ -z "$input_file" ]; then
  echo "ERROR: no valid input ROOT file found inside '$input_txt'"
  exit 1
fi

echo "Using input file:"
echo "$input_file"

cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles="$input_file" \
  outputFile="${tag}.root"

echo
echo "Done. Expected output file:"
echo "${tag}_Nano.root"

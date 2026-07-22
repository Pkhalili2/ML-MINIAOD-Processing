#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 INPUT.root OUTPUT.root [MAX_EVENTS]" >&2
  exit 2
fi

input=$1
output=$2
max_events=${3:--1}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

root -l -b -q \
  "${script_dir}/ReduceAK15NanoToLeading.C+(\"${input}\",\"${output}\",${max_events})"

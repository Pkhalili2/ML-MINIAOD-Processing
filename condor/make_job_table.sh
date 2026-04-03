#!/usr/bin/env bash
set -euo pipefail

DATASETS_FILE="${DATASETS_FILE:-condor/datasets.txt}"
FILL_ALL_EVENTS_DEFAULT="${FILL_ALL_EVENTS_DEFAULT:-1}"

mkdir -p logs
: > condor/job_table.txt

declare -A IS_SIGNAL_MAP
while read -r TAG IS_SIGNAL DSET; do
  [[ -z "${TAG}" ]] && continue
  [[ "${TAG}" =~ ^# ]] && continue
  IS_SIGNAL_MAP["${TAG}"]="${IS_SIGNAL}"
done < "${DATASETS_FILE}"

shopt -s nullglob
for f in filelists/chunks/*.txt; do
  base="$(basename "$f")"
  tag="${base%_*}"
  chunk="${base##*_}"
  chunk="${chunk%.txt}"
  echo "${tag} ${chunk} ${f} ${IS_SIGNAL_MAP[${tag}]} ${FILL_ALL_EVENTS_DEFAULT}" >> condor/job_table.txt
done

echo "Wrote $(wc -l < condor/job_table.txt) jobs."
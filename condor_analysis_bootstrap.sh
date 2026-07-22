#!/usr/bin/env bash
set -euo pipefail

tar -xzf package.tgz

if [[ "${AK15_DIRECT_OUTPUT_FILES:-0}" != "1" ]]; then
  exec bash condor/run_analysis.sh "$@"
fi

dataset_tag="$1"
chunk_id="$2"
output_dir="$4"
analysis_file="analysis_${dataset_tag}_${chunk_id}.root"
report="job_report_analysis_${dataset_tag}_${chunk_id}.txt"
marker="condor_done_analysis_${dataset_tag}_${chunk_id}.txt"

set +e
AK15_DIRECT_OUTPUT_FILES=0 bash condor/run_analysis.sh "$@"
status=$?
set -e

copy_xrootd_if_absent() {
  local src="$1"
  local dest="$2"
  local rest host path base existing_size
  rest="${dest#root://}"
  host="${rest%%/*}"
  path="${rest#*/}"
  base="root://${host}"
  existing_size="$(xrdfs "${base}" stat "${path}" 2>/dev/null | awk '/Size:/ {print $2; exit}' || true)"
  if [[ "${existing_size}" =~ ^[0-9]+$ ]]; then
    if [[ "${existing_size}" == "0" ]]; then
      echo "ERROR: preserving existing zero-byte xrootd output for inspection: ${dest}"
      return 9
    fi
    echo "Output already exists and is nonempty; keeping ${dest} (${existing_size} bytes)"
    return 0
  fi
  xrdcp "${src}" "${dest}"
}

if [[ "${output_dir}" != root://* ]]; then
  echo "ERROR: direct analysis output requires a root:// output directory"
  exit 9
fi

direct_outputs=()
if [[ "${status}" == "0" ]]; then
  if [[ ! -s "${analysis_file}" ]]; then
    echo "ERROR: successful analysis did not leave ${analysis_file} in worker scratch"
    status=8
  elif copy_xrootd_if_absent "${analysis_file}" "${output_dir%/}/${analysis_file}"; then
    direct_outputs+=("${output_dir%/}/${analysis_file}")
  else
    status=9
  fi
fi

printf 'status=%s\ntag=%s\nchunk=%s\ndirect_outputs=%s\n' \
  "${status}" "${dataset_tag}" "${chunk_id}" "${direct_outputs[*]}" > "${marker}"
copy_xrootd_if_absent "${marker}" "${output_dir%/}/${marker}" || status=9
if [[ -s "${report}" ]]; then
  copy_xrootd_if_absent "${report}" "${output_dir%/}/${report}" || status=9
fi

exit "${status}"

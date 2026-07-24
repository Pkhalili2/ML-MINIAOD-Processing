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
output_tarball="analysis_outputs_${dataset_tag}_${chunk_id}.tgz"
analysis_dest="${output_dir%/}/${analysis_file}"

write_audit_tarball() {
  local files=()
  set +e
  [[ -s "${marker}" ]] && files+=("${marker}")
  [[ -s "${report}" ]] && files+=("${report}")
  if [[ "${#files[@]}" -gt 0 ]]; then
    tar -czf "${output_tarball}" "${files[@]}"
  else
    tar -czf "${output_tarball}" --files-from /dev/null
  fi
}

trap 'final_status=$?; write_audit_tarball; exit "${final_status}"' EXIT

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
existing_analysis_size="$(
  rest="${analysis_dest#root://}"
  host="${rest%%/*}"
  path="${rest#*/}"
  xrdfs "root://${host}" stat "${path}" 2>/dev/null |
    awk '/Size:/ {print $2; exit}' || true
)"
payload_skipped=0
if [[ "${existing_analysis_size}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Direct analysis output already exists; skipping payload: ${analysis_dest} (${existing_analysis_size} bytes)"
  status=0
  payload_skipped=1
else
  set +e
  AK15_DIRECT_OUTPUT_FILES=0 bash condor/run_analysis.sh "$@"
  status=$?
  set -e
fi

if [[ "${status}" == "0" ]]; then
  if [[ "${payload_skipped}" == "1" ]]; then
    direct_outputs+=("${analysis_dest}")
  elif [[ ! -s "${analysis_file}" ]]; then
    echo "ERROR: successful analysis did not leave ${analysis_file} in worker scratch"
    status=8
  elif copy_xrootd_if_absent "${analysis_file}" "${analysis_dest}"; then
    direct_outputs+=("${analysis_dest}")
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

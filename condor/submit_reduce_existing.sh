#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "${script_dir}/.." && pwd)
tag=""
input_list=""
return_dir=""
max_events=-1
limit_files=0
max_retries=2
request_disk="8 GB"

usage() {
  cat <<'EOF'
Usage: bash condor/submit_reduce_existing.sh --tag TAG --input-list FILE --return-dir DIR [options]

Options:
  --max-events N     Default: -1
  --limit-files N    Default: all files
  --max-retries N    Default: 2
  --request-disk X   Default: 8 GB
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) tag=$2; shift 2 ;;
    --input-list) input_list=$2; shift 2 ;;
    --return-dir) return_dir=$2; shift 2 ;;
    --max-events) max_events=$2; shift 2 ;;
    --limit-files) limit_files=$2; shift 2 ;;
    --max-retries) max_retries=$2; shift 2 ;;
    --request-disk) request_disk=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown option $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${tag}" || -z "${input_list}" || -z "${return_dir}" ]]; then
  usage
  exit 2
fi

cd "${repo_root}"
[[ -s "${input_list}" ]] || {
  echo "ERROR: input list is missing or empty: ${input_list}" >&2
  exit 2
}
mkdir -p condor/.logs "${return_dir}"
generated="condor/.generated/${tag}"
mkdir -p "${generated}"
job_table="${generated}/reduce_job_table.txt"
: > "${job_table}"

index=0
while IFS= read -r source; do
  source=$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<< "${source}")
  [[ -n "${source}" && "${source}" != \#* ]] || continue
  if [[ "${limit_files}" != 0 && "${index}" -ge "${limit_files}" ]]; then
    break
  fi
  case "${source}" in
    /hdfs/store/*) source="root://cmsxrootd.hep.wisc.edu//${source#/hdfs/}" ;;
    /store/*) source="root://cmsxrootd.hep.wisc.edu//${source#/}" ;;
  esac
  chunk=$(printf '%04d' "${index}")
  one_input="${generated}/input_${chunk}.txt"
  printf '%s\n' "${source}" > "${one_input}"
  output_name="reduced_${tag}_${chunk}.root"
  printf '%s %s %s %s %s %s %s %s\n' \
    "${tag}" "${chunk}" "${one_input}" "${max_events}" \
    CMSSW_10_6_17 slc7_amd64_gcc700 "${output_name}" "${return_dir}" >> "${job_table}"
  index=$((index + 1))
done < "${input_list}"

[[ "${index}" -gt 0 ]] || {
  echo "ERROR: no inputs were selected" >&2
  exit 2
}

bash condor/package_project.sh
echo "Prepared ${index} reduction jobs in ${job_table}"
condor_submit \
  JOB_TABLE="${job_table}" \
  AK15_MAX_RETRIES="${max_retries}" \
  AK15_REQUEST_DISK="${request_disk}" \
  condor/submit_reduce_existing.sub

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash condor/hadd_by_size.sh INPUT_DIR OUTPUT_DIR PREFIX [MAX_SIZE]

Arguments:
  INPUT_DIR   Directory containing ROOT files to hadd.
  OUTPUT_DIR  Directory where consolidated ROOT files will be written.
  PREFIX      Output file prefix, e.g. flat_signal_8b or nano_signal_8b.
  MAX_SIZE    Approximate max input bytes per hadd group. Default: 6G.

Examples:
  bash condor/hadd_by_size.sh outputs/flat_ntuples outputs/hadd_flat flat_signal_8b 6G
  bash condor/hadd_by_size.sh outputs/nano_ntuples outputs/hadd_nano nano_signal_8b 10G
EOF
}

parse_size_bytes() {
  local value="$1"
  local number unit
  number="${value%[KkMmGgTt]}"
  unit="${value:${#number}}"
  if [[ -z "${number}" || ! "${number}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid size '${value}'" >&2
    exit 2
  fi

  case "${unit}" in
    "") echo "${number}" ;;
    K|k) echo $((number * 1024)) ;;
    M|m) echo $((number * 1024 * 1024)) ;;
    G|g) echo $((number * 1024 * 1024 * 1024)) ;;
    T|t) echo $((number * 1024 * 1024 * 1024 * 1024)) ;;
    *)
      echo "ERROR: invalid size suffix '${unit}'" >&2
      exit 2
      ;;
  esac
}

if [[ $# -lt 3 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 2
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"
PREFIX="$3"
MAX_SIZE="${4:-6G}"
MAX_BYTES="$(parse_size_bytes "${MAX_SIZE}")"

if [[ ! -d "${INPUT_DIR}" ]]; then
  echo "ERROR: input directory does not exist: ${INPUT_DIR}"
  exit 2
fi

if ! command -v hadd >/dev/null 2>&1; then
  echo "ERROR: hadd is not available. Run after cmsenv or in a ROOT environment."
  exit 2
fi

mkdir -p "${OUTPUT_DIR}"

shopt -s nullglob
inputs=("${INPUT_DIR}"/*.root)
shopt -u nullglob

if [[ "${#inputs[@]}" -eq 0 ]]; then
  echo "ERROR: no ROOT files found in ${INPUT_DIR}"
  exit 2
fi

group_files=()
group_bytes=0
group_index=0

run_hadd_group() {
  if [[ "${#group_files[@]}" -eq 0 ]]; then
    return 0
  fi

  local output
  output="${OUTPUT_DIR}/${PREFIX}_$(printf '%04d' "${group_index}").root"
  echo "hadd -> ${output}"
  printf '  %s\n' "${group_files[@]}"
  hadd -f "${output}" "${group_files[@]}"

  group_files=()
  group_bytes=0
  group_index=$((group_index + 1))
}

for input in "${inputs[@]}"; do
  size="$(stat -c '%s' "${input}")"
  if [[ "${#group_files[@]}" -gt 0 && $((group_bytes + size)) -gt "${MAX_BYTES}" ]]; then
    run_hadd_group
  fi
  group_files+=("${input}")
  group_bytes=$((group_bytes + size))
done

run_hadd_group

echo "Wrote ${group_index} consolidated file(s) to ${OUTPUT_DIR}"

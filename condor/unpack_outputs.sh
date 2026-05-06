#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: bash condor/unpack_outputs.sh OUTPUT_DIR [OUTPUT_DIR ...]"
  echo
  echo "Unpacks root_outputs_*.tgz files and sorts ROOT files into:"
  echo "  OUTPUT_DIR/nano_ntuples/"
  echo "  OUTPUT_DIR/flat_ntuples/"
  exit 2
fi

for outdir in "$@"; do
  if [[ ! -d "${outdir}" ]]; then
    echo "WARNING: skipping missing directory ${outdir}"
    continue
  fi

  mkdir -p "${outdir}/nano_ntuples" "${outdir}/flat_ntuples" "${outdir}/other_root"

  shopt -s nullglob
  tarballs=("${outdir}"/root_outputs_*.tgz)
  shopt -u nullglob

  if [[ "${#tarballs[@]}" -eq 0 ]]; then
    echo "No root_outputs_*.tgz files found in ${outdir}"
  fi

  for tarball in "${tarballs[@]}"; do
    echo "Unpacking ${tarball}"
    tmpdir="$(mktemp -d "${outdir}/.unpack.XXXXXX")"
    tar -xzf "${tarball}" -C "${tmpdir}"

    shopt -s nullglob
    for root_file in "${tmpdir}"/*.root; do
      name="$(basename "${root_file}")"
      case "${name}" in
        nano_*.root)
          mv -f "${root_file}" "${outdir}/nano_ntuples/${name}"
          ;;
        flat_*.root)
          mv -f "${root_file}" "${outdir}/flat_ntuples/${name}"
          ;;
        *)
          mv -f "${root_file}" "${outdir}/other_root/${name}"
          ;;
      esac
    done
    shopt -u nullglob

    rm -rf "${tmpdir}"
  done

  # Sort any ROOT files that were already unpacked at top level by older scripts.
  shopt -s nullglob
  for root_file in "${outdir}"/*.root; do
    name="$(basename "${root_file}")"
    case "${name}" in
      nano_*.root)
        mv -f "${root_file}" "${outdir}/nano_ntuples/${name}"
        ;;
      flat_*.root)
        mv -f "${root_file}" "${outdir}/flat_ntuples/${name}"
        ;;
      *)
        mv -f "${root_file}" "${outdir}/other_root/${name}"
        ;;
    esac
  done
  shopt -u nullglob

  echo "Organized ${outdir}:"
  find "${outdir}" -maxdepth 2 -type f -name '*.root' -printf '  %p\n' | sort
done

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 7 ]]; then
  echo "Usage: run_reduce_existing.sh TAG CHUNK INPUT_LIST MAX_EVENTS CMSSW_VERSION SCRAM_ARCH OUTPUT_NAME" >&2
  exit 2
fi

tag=$1
chunk=$2
input_list=$3
max_events=$4
cmssw_version=$5
scram_arch=$6
output_name=$7
jobdir=${_CONDOR_SCRATCH_DIR:-$(pwd)}
output_tarball="reduced_outputs_${tag}_${chunk}.tgz"

cd "${jobdir}"

resolve_file() {
  local candidate
  for candidate in "$1" "${jobdir}/$1" "$(basename "$1")"; do
    if [[ -f "${candidate}" ]]; then
      readlink -f "${candidate}"
      return 0
    fi
  done
  return 1
}

input_list_path=$(resolve_file "${input_list}") || {
  echo "ERROR: input list is missing: ${input_list}" >&2
  exit 3
}

mapfile -t sources < <(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "${input_list_path}" | grep -v '^#' | grep -v '^$')
if [[ ${#sources[@]} -ne 1 ]]; then
  echo "ERROR: each reduction job requires exactly one input; found ${#sources[@]}" >&2
  exit 3
fi

source_path=${sources[0]#file:}
if [[ "${source_path}" == root://* && -z "${STARTED_SINGULARITY:-}" ]]; then
  command -v xrdcp >/dev/null 2>&1 || {
    echo "ERROR: xrdcp is unavailable on the worker host" >&2
    exit 4
  }
  local_input="${jobdir}/input_${tag}_${chunk}.root"
  echo "Prefetching ${source_path}"
  timeout "${AK15_PREFETCH_TIMEOUT:-1800}" xrdcp -f "${source_path}" "${local_input}"
  [[ -s "${local_input}" ]] || {
    echo "ERROR: xrdcp did not produce a nonempty input" >&2
    exit 4
  }
  source_path="${local_input}"
fi

if [[ -z "${STARTED_SINGULARITY:-}" ]]; then
  container_image=${CONTAINER_IMAGE:-/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel7}
  runtime=""
  if command -v apptainer >/dev/null 2>&1; then
    runtime=apptainer
  elif command -v singularity >/dev/null 2>&1; then
    runtime=singularity
  fi
  if [[ -n "${runtime}" && -e "${container_image}" ]]; then
    export STARTED_SINGULARITY=1
    export SOURCE_PATH="${source_path}"
    exec "${runtime}" exec --no-home -B "${jobdir}" -B /cvmfs "${container_image}" \
      /bin/bash condor/run_reduce_existing.sh "$@"
  fi
fi

source_path=${SOURCE_PATH:-${source_path}}
source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=${scram_arch}
scramv1 project CMSSW "${cmssw_version}"
cd "${cmssw_version}/src"
eval "$(scramv1 runtime -sh)"

cp "${jobdir}/ReduceAK15NanoToLeading.C" .
cp "${jobdir}/run_reduce_ak15_nano_to_leading.sh" .
bash run_reduce_ak15_nano_to_leading.sh "${source_path}" "${output_name}" "${max_events}"
[[ -s "${output_name}" ]] || {
  echo "ERROR: reducer did not produce ${output_name}" >&2
  exit 5
}

root -l -b -q -e "TFile f(\"${output_name}\"); if (f.IsZombie() || !f.Get(\"Events\")) gSystem->Exit(6);"
cp "${output_name}" "${jobdir}/${output_name}"
cd "${jobdir}"
tar -czf "${output_tarball}" "${output_name}"
tar -tzf "${output_tarball}"

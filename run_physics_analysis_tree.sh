#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash run_physics_analysis_tree.sh INPUT_NANO_OR_LIST OUTPUT.root [options]

Options:
  --config PATH              JSON config. Default: config/analysis_muon_2018.json
  --sample LABEL             Sample label written to the output tree
  --is-data 0|1              Mark output as data. Default: 0
  --max-events N             Event limit. Default: -1
  --jet-pt-min X             Default from config, normally 200
  --jet-eta-max X            Default from config, normally 3
  --lepton-mode muon         Only muon is currently supported
  --muon-pt-min X            Default from config, normally 30
  --muon-eta-max X           Default from config, normally 2.5
  --muon-iso-max X           Default from config, normally 0.3
  --muon-iso-branch NAME     auto, Muon_pfRelIso04_all, Muon_pfRelIso03_all,
                             Muon_pfRelIso04_chg, or Muon_pfRelIso03_chg
  --muon-id none|medium|tight
                             Muon identification requirement. Default: none
  --ht-jet-pt-min X          AK4 jet pT threshold for reconstructed HT
  --ht-jet-eta-max X         AK4 jet abs(eta) limit for reconstructed HT
  --ht-jet-id-min N          Minimum NanoAOD Jet_jetId value for HT
  --min-dphi X               Minimum abs DeltaPhi(jet, muon). Default from config
  --lumi-mask PATH           CMS golden JSON or a run/lumi range text file
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"
shift 2

CONFIG="config/analysis_muon_2018.json"
SAMPLE_LABEL=""
IS_DATA="0"
MAX_EVENTS="-1"
JET_PT_MIN=""
JET_ETA_MAX=""
LEPTON_MODE=""
MUON_PT_MIN=""
MUON_ETA_MAX=""
MUON_ISO_MAX=""
MUON_ISO_BRANCH=""
MUON_ID=""
HT_JET_PT_MIN=""
HT_JET_ETA_MAX=""
HT_JET_ID_MIN=""
MIN_DPHI=""
LUMI_MASK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --sample) SAMPLE_LABEL="$2"; shift 2 ;;
    --is-data) IS_DATA="$2"; shift 2 ;;
    --max-events) MAX_EVENTS="$2"; shift 2 ;;
    --jet-pt-min) JET_PT_MIN="$2"; shift 2 ;;
    --jet-eta-max) JET_ETA_MAX="$2"; shift 2 ;;
    --lepton-mode) LEPTON_MODE="$2"; shift 2 ;;
    --muon-pt-min) MUON_PT_MIN="$2"; shift 2 ;;
    --muon-eta-max) MUON_ETA_MAX="$2"; shift 2 ;;
    --muon-iso-max) MUON_ISO_MAX="$2"; shift 2 ;;
    --muon-iso-branch) MUON_ISO_BRANCH="$2"; shift 2 ;;
    --muon-id) MUON_ID="$2"; shift 2 ;;
    --ht-jet-pt-min) HT_JET_PT_MIN="$2"; shift 2 ;;
    --ht-jet-eta-max) HT_JET_ETA_MAX="$2"; shift 2 ;;
    --ht-jet-id-min) HT_JET_ID_MIN="$2"; shift 2 ;;
    --min-dphi) MIN_DPHI="$2"; shift 2 ;;
    --lumi-mask) LUMI_MASK="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *)
      echo "ERROR: unknown option '$1'"
      usage
      exit 2
      ;;
  esac
done

if [[ ! -f "${CONFIG}" ]]; then
  echo "ERROR: config file not found: ${CONFIG}"
  exit 2
fi

config_assignments="$(
  python - "${CONFIG}" <<'PY'
from __future__ import print_function
import json
import re
import sys

path = sys.argv[1]
with open(path) as handle:
    cfg = json.load(handle)

def quote(value):
    value = str(value)
    return "'" + value.replace("'", "'\"'\"'") + "'"

def emit(shell_name, key, default):
    value = cfg.get(key, default)
    if isinstance(value, (dict, list)):
        raise SystemExit("Config key %s must be a scalar value" % key)
    if key in ("lepton_mode", "muon_iso_branch", "muon_id", "lumi_mask"):
        if not re.match(r"^[A-Za-z0-9_./:-]+$", str(value)):
            raise SystemExit("Config key %s contains unsafe characters: %r" % (key, value))
    print("%s=%s" % (shell_name, quote(value)))

emit("CFG_JET_PT_MIN", "jet_pt_min", 200.0)
emit("CFG_JET_ETA_MAX", "jet_eta_max", 3.0)
emit("CFG_LEPTON_MODE", "lepton_mode", "muon")
emit("CFG_MUON_PT_MIN", "muon_pt_min", 30.0)
emit("CFG_MUON_ETA_MAX", "muon_eta_max", 2.5)
emit("CFG_MUON_ISO_MAX", "muon_iso_max", 0.3)
emit("CFG_MUON_ISO_BRANCH", "muon_iso_branch", "auto")
emit("CFG_MUON_ID", "muon_id", "none")
emit("CFG_HT_JET_PT_MIN", "ht_jet_pt_min", 30.0)
emit("CFG_HT_JET_ETA_MAX", "ht_jet_eta_max", 2.4)
emit("CFG_HT_JET_ID_MIN", "ht_jet_id_min", 2)
emit("CFG_MIN_DPHI", "min_dphi", 1.5)
emit("CFG_LUMI_MASK", "lumi_mask", "")
PY
)"
eval "${config_assignments}"

JET_PT_MIN="${JET_PT_MIN:-${CFG_JET_PT_MIN}}"
JET_ETA_MAX="${JET_ETA_MAX:-${CFG_JET_ETA_MAX}}"
LEPTON_MODE="${LEPTON_MODE:-${CFG_LEPTON_MODE}}"
MUON_PT_MIN="${MUON_PT_MIN:-${CFG_MUON_PT_MIN}}"
MUON_ETA_MAX="${MUON_ETA_MAX:-${CFG_MUON_ETA_MAX}}"
MUON_ISO_MAX="${MUON_ISO_MAX:-${CFG_MUON_ISO_MAX}}"
MUON_ISO_BRANCH="${MUON_ISO_BRANCH:-${CFG_MUON_ISO_BRANCH}}"
MUON_ID="${MUON_ID:-${CFG_MUON_ID}}"
HT_JET_PT_MIN="${HT_JET_PT_MIN:-${CFG_HT_JET_PT_MIN}}"
HT_JET_ETA_MAX="${HT_JET_ETA_MAX:-${CFG_HT_JET_ETA_MAX}}"
HT_JET_ID_MIN="${HT_JET_ID_MIN:-${CFG_HT_JET_ID_MIN}}"
MIN_DPHI="${MIN_DPHI:-${CFG_MIN_DPHI}}"
LUMI_MASK="${LUMI_MASK:-${CFG_LUMI_MASK}}"

if [[ "${LEPTON_MODE}" != "muon" ]]; then
  echo "ERROR: only --lepton-mode muon is currently supported"
  exit 2
fi
if [[ "${MUON_ID}" != "none" && "${MUON_ID}" != "medium" && "${MUON_ID}" != "tight" ]]; then
  echo "ERROR: --muon-id must be none, medium, or tight"
  exit 2
fi

check_path="${INPUT_FILE}"
case "${check_path}" in
  @*) check_path="${check_path#@}" ;;
  file:*) check_path="${check_path#file:}" ;;
esac

case "${INPUT_FILE}" in
  root://*|davs://*|gsiftp://*) ;;
  *)
    if [[ ! -f "${check_path}" ]]; then
      echo "ERROR: input file/list '${INPUT_FILE}' not found"
      exit 1
    fi
    ;;
esac

if ! command -v root >/dev/null 2>&1; then
  echo "ERROR: ROOT is not available. Run this inside CMSSW after cmsenv."
  exit 1
fi

output_dir="$(dirname "${OUTPUT_FILE}")"
if [[ "${output_dir}" != "." ]]; then
  mkdir -p "${output_dir}"
fi

if [[ -z "${SAMPLE_LABEL}" ]]; then
  SAMPLE_LABEL="$(basename "${OUTPUT_FILE}" .root)"
fi

root_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

ROOT_INPUT="$(root_escape "${INPUT_FILE}")"
ROOT_OUTPUT="$(root_escape "${OUTPUT_FILE}")"
ROOT_SAMPLE="$(root_escape "${SAMPLE_LABEL}")"
ROOT_LEPTON_MODE="$(root_escape "${LEPTON_MODE}")"
ROOT_ISO_BRANCH="$(root_escape "${MUON_ISO_BRANCH}")"
ROOT_MUON_ID="$(root_escape "${MUON_ID}")"
ROOT_LUMI_MASK=""

if [[ "${IS_DATA}" == "1" && -n "${LUMI_MASK}" ]]; then
  if [[ ! -f "${LUMI_MASK}" ]]; then
    echo "ERROR: lumi mask not found: ${LUMI_MASK}"
    exit 2
  fi
  LUMI_MASK_RANGES="${OUTPUT_FILE%.root}.lumi_ranges.txt"
  python - "${LUMI_MASK}" "${LUMI_MASK_RANGES}" <<'PY'
from __future__ import print_function
import json
import sys

source, output = sys.argv[1:3]
with open(source) as handle:
    first = handle.read(1)
    handle.seek(0)
    if first == "{":
        payload = json.load(handle)
        with open(output, "w") as target:
            for run in sorted(payload, key=lambda value: int(value)):
                for first_lumi, last_lumi in payload[run]:
                    target.write("%s %s %s\n" % (run, first_lumi, last_lumi))
    else:
        with open(output, "w") as target:
            target.write(handle.read())
PY
  ROOT_LUMI_MASK="$(root_escape "${LUMI_MASK_RANGES}")"
fi

root -l -b -q "PhysicsAnalysisTreeProducer.C+(\"${ROOT_INPUT}\",\"${ROOT_OUTPUT}\",\"${ROOT_SAMPLE}\",${IS_DATA},${MAX_EVENTS},${JET_PT_MIN},${JET_ETA_MAX},\"${ROOT_LEPTON_MODE}\",${MUON_PT_MIN},${MUON_ETA_MAX},${MUON_ISO_MAX},${MIN_DPHI},\"${ROOT_ISO_BRANCH}\",\"${ROOT_LUMI_MASK}\",\"${ROOT_MUON_ID}\",${HT_JET_PT_MIN},${HT_JET_ETA_MAX},${HT_JET_ID_MIN})"

echo
echo "Done. Output file:"
echo "${OUTPUT_FILE}"

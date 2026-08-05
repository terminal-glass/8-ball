#!/usr/bin/env bash
# C10 profile step 5 — RAM Gate
# Model: starcoder2-7b  Lane: ubuntu/cpu
set -euo pipefail
PROFILE_STEP="5"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANE_JSON="${SCRIPT_DIR}/lane.json"
PROFILE_SIZES="${SCRIPT_DIR}/profile-sizes.csv"
MODEL_SLUG="starcoder2-7b"
TARGET_LANE="ubuntu/cpu"
if [[ ! -f "${LANE_JSON}" ]]; then
  echo "Missing lane metadata: ${LANE_JSON}" >&2
  exit 1
fi
echo "[profile-step-${PROFILE_STEP}] ${MODEL_SLUG} / ${TARGET_LANE} — RAM Gate"
python3 - "${LANE_JSON}" "${PROFILE_SIZES}" "${PROFILE_STEP}" <<'PY'
import csv, json, sys
lane = json.loads(open(sys.argv[1], encoding="utf-8").read())
step = sys.argv[3]
print(json.dumps({"step": step, "lane": lane.get("target_lane"), "install_path": lane.get("install_path")}, indent=2))
with open(sys.argv[2], encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
print(f"profile_sizes={len(rows)}")
PY

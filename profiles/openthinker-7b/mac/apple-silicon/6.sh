#!/usr/bin/env bash
# C10 profile step 6 — CPU Gate
# Model: openthinker-7b  Lane: mac/apple-silicon
set -euo pipefail
PROFILE_STEP="6"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANE_JSON="${SCRIPT_DIR}/lane.json"
PROFILE_SIZES="${SCRIPT_DIR}/profile-sizes.csv"
MODEL_SLUG="openthinker-7b"
TARGET_LANE="mac/apple-silicon"
if [[ ! -f "${LANE_JSON}" ]]; then
  echo "Missing lane metadata: ${LANE_JSON}" >&2
  exit 1
fi
echo "[profile-step-${PROFILE_STEP}] ${MODEL_SLUG} / ${TARGET_LANE} — CPU Gate"
python3 - "${LANE_JSON}" "${PROFILE_SIZES}" "${PROFILE_STEP}" <<'PY'
import csv, json, sys
lane = json.loads(open(sys.argv[1], encoding="utf-8").read())
step = sys.argv[3]
print(json.dumps({"step": step, "lane": lane.get("target_lane"), "install_path": lane.get("install_path")}, indent=2))
with open(sys.argv[2], encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
print(f"profile_sizes={len(rows)}")
PY

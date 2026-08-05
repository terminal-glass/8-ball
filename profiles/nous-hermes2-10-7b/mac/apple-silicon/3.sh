#!/usr/bin/env bash
# C10 profile step 3 — Deployment Lane
# Model: nous-hermes2-10-7b  Lane: mac/apple-silicon
set -euo pipefail
PROFILE_STEP="3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANE_JSON="${SCRIPT_DIR}/lane.json"
PROFILE_SIZES="${SCRIPT_DIR}/profile-sizes.csv"
MODEL_SLUG="nous-hermes2-10-7b"
TARGET_LANE="mac/apple-silicon"
if [[ ! -f "${LANE_JSON}" ]]; then
  echo "Missing lane metadata: ${LANE_JSON}" >&2
  exit 1
fi
echo "[profile-step-${PROFILE_STEP}] ${MODEL_SLUG} / ${TARGET_LANE} — Deployment Lane"
python3 - "${LANE_JSON}" "${PROFILE_SIZES}" "${PROFILE_STEP}" <<'PY'
import csv, json, sys
lane = json.loads(open(sys.argv[1], encoding="utf-8").read())
step = sys.argv[3]
print(json.dumps({"step": step, "lane": lane.get("target_lane"), "install_path": lane.get("install_path")}, indent=2))
with open(sys.argv[2], encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
print(f"profile_sizes={len(rows)}")
PY

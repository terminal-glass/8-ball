#!/usr/bin/env bash
# Host-safe shell baseline checks for canonical Ubuntu public installer scripts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LANE_DIR="${REPO_ROOT}/install/ubuntu/cpu"
CANONICAL_SCRIPTS=(
  trial-install.sh
  8.1.sh
  8.2.sh
  8.3.sh
)

fail() {
  echo "test-shell-baseline: $*" >&2
  exit 1
}

for script in "${CANONICAL_SCRIPTS[@]}"; do
  [[ -f "${LANE_DIR}/${script}" ]] || fail "missing canonical script: ${LANE_DIR}/${script}"
done

(
  cd "${LANE_DIR}"
  bash -n "${CANONICAL_SCRIPTS[@]}"
) || fail "bash -n syntax check failed"

for script in "${CANONICAL_SCRIPTS[@]}"; do
  path="${LANE_DIR}/${script}"
  if python3 - "${path}" <<'PY'
import sys
data = open(sys.argv[1], "rb").read()
if b"\xc3\xa5\xc3\xa7" in data:
    raise SystemExit(1)
if "åç".encode("utf-8") in data:
    raise SystemExit(1)
PY
  then
    :
  else
    fail "corrupt åç suffix found in ${path}"
  fi
done

COMMON_SH="${REPO_ROOT}/install/ubuntu/lib/ubuntu-common.sh"
grep -Fq 'TRIAL_LOG="${PHILO_ROOT}/trial-log.txt"' "${COMMON_SH}" \
  || fail "${COMMON_SH} must define TRIAL_LOG from PHILO_ROOT/trial-log.txt"

for script in trial-install.sh 8.1.sh; do
  path="${LANE_DIR}/${script}"
  if grep -Fq 'TRIAL_LOG="${PHILO_ROOT}/trial-log.txt"' "${path}"; then
    continue
  fi
  grep -Fq 'ubuntu-common.sh' "${path}" \
    || fail "${path} must set TRIAL_LOG or source install/ubuntu/lib/ubuntu-common.sh"
done

echo "test-shell-baseline: passed (${#CANONICAL_SCRIPTS[@]} scripts)"

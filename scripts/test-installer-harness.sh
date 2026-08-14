#!/usr/bin/env bash
# Offline-safe installer validation harness for 8-BALL 0.8 launch hardening.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/tmp/8ball-harness-philosopher}"
HARNESS_TMP="${HARNESS_TMP:-/tmp/8ball-harness}"
PASS=0
FAIL=0
SKIP=0

log() { printf '[harness] %s\n' "$*"; }
pass() { PASS=$((PASS + 1)); log "PASS: $*"; }
fail() { FAIL=$((FAIL + 1)); log "FAIL: $*"; }
skip() { SKIP=$((SKIP + 1)); log "NOT TESTED: $*"; }

run_bash_n() {
  local script="$1"
  if bash -n "${script}"; then
    pass "bash -n ${script#$REPO_ROOT/}"
  else
    fail "bash -n ${script#$REPO_ROOT/}"
  fi
}

main() {
  mkdir -p "${HARNESS_TMP}" "${PHILOSOPHER_ROOT}"
  log "8-BALL installer harness (offline portions)"

  for script in \
    "${REPO_ROOT}/install/ubuntu/trial-install.sh" \
    "${REPO_ROOT}/install/ubuntu/8.1.sh" \
    "${REPO_ROOT}/install/ubuntu/8.2.sh" \
    "${REPO_ROOT}/install/ubuntu/8.3.sh"; do
    run_bash_n "${script}"
  done

  if command -v shellcheck >/dev/null 2>&1; then
  log "Running shellcheck (warnings recorded separately)"
  shellcheck -S warning "${REPO_ROOT}/install/ubuntu/"*.sh "${REPO_ROOT}/install/shared/"*.sh 2>"${HARNESS_TMP}/shellcheck.txt" || true
  if [[ -s "${HARNESS_TMP}/shellcheck.txt" ]]; then
    log "ShellCheck warnings:"
    cat "${HARNESS_TMP}/shellcheck.txt"
  else
    pass "shellcheck no warnings on ubuntu/shared scripts"
  fi
  else
    skip "shellcheck not installed"
  fi

  if python3 "${REPO_ROOT}/install/shared/c10-hardware-resolve.py" plan >"${HARNESS_TMP}/plan.json"; then
    pass "c10-hardware-resolve.py plan"
    if python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d.get("candidates")' "${HARNESS_TMP}/plan.json"; then
      pass "hardware plan includes candidates"
    else
      fail "hardware plan missing candidates"
    fi
  else
    fail "c10-hardware-resolve.py plan"
  fi

  # MOTD model matching unit check
  if EIGHTBALL_REPO_ROOT="${REPO_ROOT}" bash -c '
    source "'"${REPO_ROOT}"'/install/shared/8ball-model-test.sh"
    eightball_validate_model_name "qwen3:1.7b"
  '; then
    pass "model name validation"
  else
    fail "model name validation"
  fi

  if [[ "${EUID:-$(id -u)}" -eq 0 ]] && command -v ollama >/dev/null 2>&1; then
    pass "root + ollama available for live tests"
    skip "live install/idempotency tests (run manually on VM)"
  else
    skip "first install / idempotent install (requires root + clean VM)"
    skip "Ollama already installed path"
    skip "existing swap / no swap"
    skip "low disk simulation"
    skip "model pull failure / inference failure"
    skip "manual --model override live"
    skip "MOTD READY state live"
    skip "Jets unsigned-in path live"
  fi

  skip "bulletin unavailable (requires install run)"
  skip "8.3 --no-motd path (requires install run)"

  log "Summary: PASS=${PASS} FAIL=${FAIL} NOT_TESTED=${SKIP}"
  [[ "${FAIL}" -eq 0 ]]
}

main "$@"

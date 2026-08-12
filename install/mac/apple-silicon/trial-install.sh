#!/usr/bin/env bash
# trial-install.sh — public 8-BALL macOS trial installer (Apple Silicon).
set -euo pipefail

EIGHTBALL_INSTALL_LANE="mac/apple-silicon"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/mac-apple-silicon.json"
MAC_EXPECTED_ARCH="arm64"
MAC_TARGET_LANE="mac/apple-silicon"
MAC_LOG_PREFIX="trial-install"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/macos-common.sh
source "${SCRIPT_DIR}/../lib/macos-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="trial-install.sh"
INSTALLER_SMOKE_PLATFORM="mac"
INSTALLER_SMOKE_CHECKS="- Verify macOS version and lane architecture
- Run foundation (8.1), model ladder (8.2), and optional completion card (8.3)
- Does not install software during --preflight"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

REQUESTED_MODEL=""
SKIP_MOTD=0
MANIFEST=""

usage() {
  cat <<'EOF'
Usage: trial-install.sh [options]

Public free/trial 8-BALL installer for macOS Apple Silicon (arm64).

Options:
  --model TAG       Request a specific Ollama tag (passed to 8.2.sh)
  --no-motd         Run 8.1 and 8.2 only
  --manifest PATH   Accepted for compatibility; macOS trial uses the Happy Nerds ladder
  -h, --help        Show this help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        REQUESTED_MODEL="$2"
        mac_validate_model_tag "${REQUESTED_MODEL}"
        shift 2
        ;;
      --no-motd)
        SKIP_MOTD=1
        shift
        ;;
      --manifest)
        MANIFEST="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

require_local_payload() {
  local name
  for name in 8.1.sh 8.2.sh 8.3.sh; do
    if [[ ! -f "${SCRIPT_DIR}/${name}" ]]; then
      echo "Missing required lane payload: ${SCRIPT_DIR}/${name}" >&2
      echo "This trial bundle must include its full lane scripts locally." >&2
      exit 1
    fi
  done
}

run_step() {
  local label="$1"
  shift
  mac_log "${label}"
  if ! "$@" >>"${LOG_FILE}" 2>&1; then
    echo "Step failed: ${label}" >&2
    tail -n 30 "${LOG_FILE}" >&2 || true
    exit 1
  fi
}

main() {
  installer_smoke_prologue "$@"
  parse_args "$@"
  mac_refuse_root
  mac_require_darwin
  mac_resolve_eightball_root
  mac_require_lane_architecture
  require_local_payload
  touch "${LOG_FILE}"

  local -a model_args=()
  if [[ -n "${REQUESTED_MODEL}" ]]; then
    model_args=(--model "${REQUESTED_MODEL}")
  fi

  mac_log "[1/3] Verifying macOS, Ollama app, and runtime observation"
  run_step "running 8.1.sh" "${SCRIPT_DIR}/8.1.sh"

  mac_log "[2/3] Running Happy Nerds trial ladder"
  run_step "running 8.2.sh" "${SCRIPT_DIR}/8.2.sh" "${model_args[@]}"

  if [[ "${SKIP_MOTD}" -eq 0 ]]; then
    mac_log "[3/3] Printing completion card and status helper"
    run_step "running 8.3.sh" "${SCRIPT_DIR}/8.3.sh"
  else
    mac_log "[3/3] Skipping completion card (--no-motd)"
  fi

  mac_log "Trial install complete. Log: ${LOG_FILE}"
  mac_log "Result: ${RESULT_FILE}"
  mac_log "Status: ${STATUS_BIN}"
}

main "$@"

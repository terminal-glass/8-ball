#!/usr/bin/env bash
# 8.3 — macOS completion card and user-level status helper.
set -euo pipefail

EIGHTBALL_INSTALL_LANE="mac/intel"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/mac-intel.json"
MAC_EXPECTED_ARCH="x86_64"
MAC_TARGET_LANE="mac/intel"
MAC_LOG_PREFIX="8.3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOTD_TEMPLATE="${SCRIPT_DIR}/assets/first-MOTD.txt"
# shellcheck source=../lib/macos-common.sh
source "${SCRIPT_DIR}/../lib/macos-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.3.sh"
INSTALLER_SMOKE_PLATFORM="mac"
INSTALLER_SMOKE_CHECKS="- Verify macOS user-level completion card prerequisites
- Would write a user-level status helper during a real install"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

main() {
  installer_smoke_prologue "$@"
  mac_refuse_root
  mac_require_darwin
  mac_resolve_eightball_root
  mac_validate_ollama_api

  if [[ ! -f "${MOTD_TEMPLATE}" ]]; then
    echo "Missing completion card template: ${MOTD_TEMPLATE}" >&2
    exit 1
  fi

  local selected_model="unknown"
  local model_status="UNKNOWN"
  local ollama_status="STOPPED"
  if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    ollama_status="RUNNING"
  fi
  if [[ -f "${RESULT_FILE}" ]]; then
    selected_model="$(awk -F': ' '$1 == "Model" {print $2; exit}' "${RESULT_FILE}")"
    if awk -F': ' '$1 == "Model test" && $2 == "PASSED"' "${RESULT_FILE}" >/dev/null; then
      model_status="READY"
    fi
  fi

  sed \
    -e "s/__OLLAMA_STATUS__/${ollama_status}/g" \
    -e "s/__MODEL_STATUS__/${model_status}/g" \
    -e "s/__SELECTED_MODEL__/${selected_model}/g" \
    -e "s|__EIGHTBALL_ROOT__|${EIGHTBALL_ROOT}|g" \
    "${MOTD_TEMPLATE}"

  mac_write_status_helper
  mac_log "Wrote status helper at ${STATUS_BIN}"
  mac_log "Jets are optional and require a separate 'ollama signin'; this installer does not activate them."
}

main "$@"

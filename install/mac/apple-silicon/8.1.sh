#!/usr/bin/env bash
# 8.1 — macOS foundation: Ollama app verification and runtime observation.
set -euo pipefail

EIGHTBALL_INSTALL_LANE="mac/apple-silicon"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/mac-apple-silicon.json"
MAC_EXPECTED_ARCH="arm64"
MAC_TARGET_LANE="mac/apple-silicon"
MAC_LOG_PREFIX="8.1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/macos-common.sh
source "${SCRIPT_DIR}/../lib/macos-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.1.sh"
INSTALLER_SMOKE_PLATFORM="mac"
INSTALLER_SMOKE_CHECKS="- Verify macOS version, architecture, and loopback Ollama API settings
- Would observe Ollama app lifecycle without installing during --preflight"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

main() {
  installer_smoke_prologue "$@"
  mac_refuse_root
  mac_require_darwin
  mac_resolve_eightball_root
  mac_validate_ollama_api
  mac_require_macos_version
  mac_require_lane_architecture

  mac_write_observation "${SCRIPT_DIR}"
  mac_log "Wrote runtime observation to ${OBSERVATION_FILE}"

  if ! mac_find_ollama_app; then
    mac_manual_ollama_install_message
    exit 1
  fi

  mac_launch_ollama_app
  mac_require_ollama_cli
  mac_wait_for_ollama_api
  mac_log "Foundation step complete for ${MAC_TARGET_LANE}"
}

main "$@"

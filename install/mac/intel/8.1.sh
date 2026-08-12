#!/usr/bin/env bash
# 8.1 — macOS foundation: Ollama app verification and runtime observation.
set -euo pipefail

EIGHTBALL_INSTALL_LANE="mac/intel"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/mac-intel.json"
MAC_EXPECTED_ARCH="x86_64"
MAC_TARGET_LANE="mac/intel"
MAC_LOG_PREFIX="8.1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/macos-common.sh
source "${SCRIPT_DIR}/../lib/macos-common.sh"

main() {
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

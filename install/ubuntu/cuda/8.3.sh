#!/usr/bin/env bash
# 8.3 — public 8-BALL login MOTD and remember helper (no network calls on login).
# Install lane: ubuntu/cuda
set -euo pipefail

EIGHTBALL_INSTALL_LANE="ubuntu/cuda"
EIGHTBALL_INSTALL_PROFILE="ubuntu/cuda"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cuda.json"
UBUNTU_LOG_PREFIX="8.3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOTD_TEMPLATE="${SCRIPT_DIR}/assets/first-MOTD.txt"

# shellcheck source=../lib/ubuntu-common.sh
source "${SCRIPT_DIR}/../lib/ubuntu-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.3.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Verify MOTD template presence
- Would install /etc/update-motd.d helper and remember script during a real install (requires root)"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

usage() {
  cat <<'EOF'
Usage: 8.3.sh [options]

Lane: ubuntu/cuda

Reads ${PHILOSOPHER_ROOT}/profiles/90-result.env written by 8.2.

Options:
  -h, --help    Show this help without mutating the host
EOF
}

main() {
  installer_smoke_prologue "$@"
  ubuntu_require_root
  ubuntu_ensure_state_root
  ubuntu_install_remember_helper
  ubuntu_install_motd "${MOTD_TEMPLATE}"
  ubuntu_log "Installed MOTD helper and remember command"
  ubuntu_log "Login MOTD performs no network calls"
}

main "$@"

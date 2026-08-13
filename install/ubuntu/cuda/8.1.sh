#!/usr/bin/env bash
# 8.1 — public 8-BALL foundation: Ollama install and local API verification.
# Install lane: ubuntu/cuda
set -euo pipefail

EIGHTBALL_INSTALL_LANE="ubuntu/cuda"
EIGHTBALL_INSTALL_PROFILE="ubuntu/cuda"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cuda.json"
UBUNTU_LOG_PREFIX="8.1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/ubuntu-common.sh
source "${SCRIPT_DIR}/../lib/ubuntu-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.1.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Verify Debian-family host identity
- Would install packages and Ollama and verify loopback API during a real install (requires root)"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

usage() {
  cat <<'EOF'
Usage: 8.1.sh [options]

Lane: ubuntu/cuda

Options:
  --yes                               Non-interactive confirmation for planned system changes
  --accept-ollama-install-risk        Development-only opt-in for unverified ollama.com/install.sh
  -h, --help                          Show this help without mutating the host
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes)
        export EIGHTBALL_NONINTERACTIVE_CONFIRM=1
        shift
        ;;
      --accept-ollama-install-risk)
        export EIGHTBALL_ACCEPT_OLLAMA_INSTALL_RISK=1
        shift
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

main() {
  installer_smoke_prologue "$@"
  parse_args "$@"
  ubuntu_require_root
  ubuntu_require_debian_family
  ubuntu_validate_ollama_api
  ubuntu_ensure_state_root
  ubuntu_resolve_profile_dir
  ubuntu_show_planned_changes
  ubuntu_require_noninteractive_confirm
  ubuntu_install_packages
  ubuntu_install_ollama_if_missing
  ubuntu_start_ollama
  ubuntu_wait_for_ollama
  ubuntu_log "Foundation step complete"
}

main "$@"

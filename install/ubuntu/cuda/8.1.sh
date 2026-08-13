#!/usr/bin/env bash
# Lane wrapper — delegates to canonical install/ubuntu/8.1.sh
set -euo pipefail
export EIGHTBALL_INSTALL_LANE="ubuntu/cuda"
export EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cuda.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALLER_SMOKE_SCRIPT_NAME="8.1.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Verify Debian-family host identity
- Would install packages and Ollama and verify loopback API during a real install (requires root)"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"
usage() { installer_smoke_usage; }
installer_smoke_prologue "$@"

exec "${SCRIPT_DIR}/../8.1.sh" "$@"

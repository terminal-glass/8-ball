#!/usr/bin/env bash
# Lane wrapper — delegates to canonical install/ubuntu/8.3.sh
# Supports -h|--help via canonical script delegation.
set -euo pipefail
export EIGHTBALL_INSTALL_LANE="ubuntu/cuda"
export EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cuda.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  exec "${SCRIPT_DIR}/../8.3.sh" --help
fi
exec "${SCRIPT_DIR}/../8.3.sh" "$@"

#!/usr/bin/env bash
# Backward-compatible entrypoint; use install/ubuntu/cpu/trial-install.sh directly.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/cpu/trial-install.sh" "$@"

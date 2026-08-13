#!/usr/bin/env bash
# Backward-compatible wrapper for install/ubuntu/cpu/8.2.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/cpu/8.2.sh" "$@"

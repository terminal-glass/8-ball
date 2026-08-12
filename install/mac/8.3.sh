#!/usr/bin/env bash
# install/mac/8.3.sh — dispatch to the canonical macOS lane by architecture.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$(uname -m 2>/dev/null || echo unknown)" in
  arm64)
    exec "${SCRIPT_DIR}/apple-silicon/8.3.sh" "$@"
    ;;
  x86_64)
    exec "${SCRIPT_DIR}/intel/8.3.sh" "$@"
    ;;
  *)
    echo "Unknown Mac architecture. Run install/mac/apple-silicon/8.3.sh or install/mac/intel/8.3.sh explicitly." >&2
    exit 1
    ;;
esac

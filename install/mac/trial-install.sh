#!/usr/bin/env bash
# install/mac/trial-install.sh — dispatch to the canonical macOS lane by architecture.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "8-BALL macOS installers must run as your normal user account." >&2
  exit 1
fi

if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Darwin" ]]; then
  echo "Use install/mac/apple-silicon on Apple Silicon or install/mac/intel on Intel Macs." >&2
  exit 1
fi

case "$(uname -m 2>/dev/null || echo unknown)" in
  arm64)
    exec "${SCRIPT_DIR}/apple-silicon/trial-install.sh" "$@"
    ;;
  x86_64)
    exec "${SCRIPT_DIR}/intel/trial-install.sh" "$@"
    ;;
  *)
    echo "Unknown Mac architecture. Run install/mac/apple-silicon or install/mac/intel explicitly." >&2
    exit 1
    ;;
esac

#!/usr/bin/env bash
# Adversarial fixture: --help prints apt-get usage (no smoke prologue).
set -euo pipefail
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: bad-help-apt.sh"
  echo "sudo apt-get install ollama"
  exit 0
fi
exit 1

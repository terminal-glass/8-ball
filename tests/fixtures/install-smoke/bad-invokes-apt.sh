#!/usr/bin/env bash
# Adversarial fixture: --preflight invokes apt-get then returns zero.
set -euo pipefail
if [[ "${1:-}" == "--preflight" ]]; then
  echo "lane: fixture/bad-invoke"
  echo "mode: preflight (no installation performed)"
  apt-get install -y curl
  exit 0
fi
exit 1

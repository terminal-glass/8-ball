#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/eight-ball.sh validate "$@"
python3 scripts/validate-install-lanes.py

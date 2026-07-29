#!/usr/bin/env bash
# Offline plan for recreating the candidate catalog from the Ollama library index.
# Does not fetch pages, download weights, or modify legacy data.
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash scripts/eight-ball.sh plan --fixture --offline --from-index "$@"

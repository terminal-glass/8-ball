#!/usr/bin/env bash
# Rebuild the candidate catalog from the six-family offline fixtures.
# Does not overwrite data/families or data/normalized.
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash scripts/eight-ball.sh all --source ollama --candidate --fixture --offline --sample "$@"

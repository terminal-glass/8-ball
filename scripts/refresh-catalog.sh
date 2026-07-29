#!/usr/bin/env bash
# Legacy pipeline: normalize committed data/families into data/normalized.
# For Ollama web recreate scaffolding, use:
#   bash scripts/plan-candidate-collect.sh
#   bash scripts/refresh-candidate-sample.sh
#   bash scripts/promote-candidate.sh
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash scripts/eight-ball.sh all "$@"

#!/usr/bin/env bash
# Dry-run promotion of candidate catalog into canonical data/normalized.
# Use: bash scripts/promote-candidate.sh --apply --confirm   # after review
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -eq 0 ]]; then
  exec bash scripts/eight-ball.sh promote --dry-run
fi
exec bash scripts/eight-ball.sh promote "$@"

#!/usr/bin/env bash
# Live Ollama metadata crawl into data/candidate/ (metadata pages only).
# Does not run ollama pull, download weights, or promote the canonical catalog.
set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="${LOG_DIR:-/tmp/eight-ball-live-crawl}"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/crawl-${STAMP}.log"

echo "Logging to $LOG"
exec > >(tee -a "$LOG") 2>&1

echo "=== eight-ball live candidate crawl started at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "--- collect (library index + all families) ---"
eight-ball collect --candidate --from-index

echo "--- normalize from latest manifest ---"
eight-ball normalize --source ollama --candidate

echo "--- generate ---"
eight-ball generate --candidate --source ollama

echo "--- validate ---"
eight-ball validate --candidate --source ollama

echo "--- report ---"
eight-ball report --candidate --source ollama

echo "--- compare vs legacy ---"
eight-ball compare

echo "--- promote dry-run (review gates expected) ---"
set +e
eight-ball promote --dry-run
promote_exit=$?
set -e
echo "promote dry-run exit: $promote_exit"

echo "=== live candidate crawl finished at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

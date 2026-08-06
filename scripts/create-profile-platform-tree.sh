#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

INDEX="profiles/c10-index.json"
PROFILES_DIR="profiles"

PLATFORM_LANES=(
  "ubuntu/cpu"
  "ubuntu/cuda"
  "mac/apple-silicon"
  "mac/intel"
  "windows/cpu"
  "windows/cuda"
  "cloud/digitalocean/cpu-droplet"
  "cloud/digitalocean/gpu-droplet"
  "cloud/aws-lightsail/cpu"
  "cloud/aws-lightsail/gpu"
)

if [[ ! -f "$INDEX" ]]; then
  echo "Missing C10 index: $INDEX (run scripts/generate-c10-profiles.py)" >&2
  exit 1
fi

mapfile -t MODEL_SLUGS < <(
  python3 - <<'PY'
import json
from pathlib import Path

rows = json.loads(Path("profiles/c10-index.json").read_text(encoding="utf-8")).get("rows", [])
for slug in sorted({row["model_slug"] for row in rows}):
    print(slug)
PY
)

if [[ "${#MODEL_SLUGS[@]}" -eq 0 ]]; then
  echo "No model slugs found in $INDEX" >&2
  exit 1
fi

mkdir -p "$PROFILES_DIR"
created=0
for slug in "${MODEL_SLUGS[@]}"; do
  model_dir="$PROFILES_DIR/$slug"
  mkdir -p "$model_dir"
  for lane in "${PLATFORM_LANES[@]}"; do
    mkdir -p "$model_dir/$lane"
    created=$((created + 1))
  done
done

echo "Platform tree ensured for ${#MODEL_SLUGS[@]} C10 models (${created} leaf lanes)."

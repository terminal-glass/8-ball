#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MANIFEST="data/generated/pages/install-manifest.json"
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

if [[ ! -f "$MANIFEST" ]]; then
  echo "Missing canonical manifest: $MANIFEST" >&2
  exit 1
fi

mapfile -t MODEL_SLUGS < <(
  python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(Path("data/generated/pages/install-manifest.json").read_text(encoding="utf-8"))
models = manifest.get("models", {})
slugs = sorted({entry.get("model_slug") or model_id for model_id, entry in models.items()})
for slug in slugs:
    print(slug)
PY
)

if [[ "${#MODEL_SLUGS[@]}" -eq 0 ]]; then
  echo "No model slugs found in $MANIFEST" >&2
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

echo "Platform tree created for ${#MODEL_SLUGS[@]} models (${created} leaf lanes)."

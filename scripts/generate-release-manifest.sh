#!/usr/bin/env bash
# Generate SHA-256 manifest for a tagged 8-BALL installer release.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="${1:-v0.8.0}"
OUT_DIR="${REPO_ROOT}/install/releases/${RELEASE}"
mkdir -p "${OUT_DIR}"

python3 - "${RELEASE}" "${OUT_DIR}/manifest.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

release, out_path = sys.argv[1:3]
repo = Path(out_path).resolve().parents[3]
scripts = {
    "trial-install.sh": repo / "install/ubuntu/trial-install.sh",
    "8.1.sh": repo / "install/ubuntu/8.1.sh",
    "8.2.sh": repo / "install/ubuntu/8.2.sh",
    "8.3.sh": repo / "install/ubuntu/8.3.sh",
}
checksums = {}
for name, path in scripts.items():
    if not path.is_file():
        raise SystemExit(f"Missing script for manifest: {path}")
    checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {
    "suite_version": release.lstrip("v"),
    "script_family": "8-BALL",
    "release_tag": release,
    "scripts": checksums,
}
Path(out_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out_path}")
PY

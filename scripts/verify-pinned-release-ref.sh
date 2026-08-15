#!/usr/bin/env bash
# Verify install/releases/*/manifest.json matches artifact bytes at an exact git ref.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF="${1:-}"
if [[ -z "${REF}" ]]; then
  REF="$(
    python3 - <<'PY'
import re
from pathlib import Path

text = Path("install/ubuntu/trial-install.sh").read_text(encoding="utf-8")
match = re.search(r'EIGHTBALL_RELEASE_REF="\$\{EIGHTBALL_RELEASE_REF:-([0-9a-f]+)\}"', text)
if not match:
    raise SystemExit("installer does not pin EIGHTBALL_RELEASE_REF")
print(match.group(1))
PY
  )"
fi

cd "${REPO_ROOT}"
if ! git cat-file -e "${REF}^{commit}" 2>/dev/null; then
  git fetch --depth 1 origin "${REF}"
fi

python3 - "${REF}" <<'PY'
import hashlib
import json
import subprocess
import sys

ref = sys.argv[1]
manifest = json.loads(
    subprocess.check_output(["git", "show", f"{ref}:install/releases/v0.8.0/manifest.json"])
)
mismatches = []
for rel_path, expected in manifest.get("artifacts", {}).items():
    data = subprocess.check_output(["git", "show", f"{ref}:{rel_path}"])
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        mismatches.append(rel_path)
print(f"runtime_ref={ref}")
print(f"artifacts_checked={len(manifest.get('artifacts', {}))}")
print(f"mismatches={len(mismatches)}")
print(
    "trial_install_in_manifest=",
    "install/ubuntu/trial-install.sh" in manifest.get("artifacts", {}),
)
rel = "install/shared/8ball-release.sh"
release_bytes = subprocess.check_output(["git", "show", f"{ref}:{rel}"])
print(f"8ball_release_expected={manifest['artifacts'][rel]}")
print(f"8ball_release_actual={hashlib.sha256(release_bytes).hexdigest()}")
if mismatches:
    for rel_path in mismatches[:10]:
        print(f"mismatch: {rel_path}")
    raise SystemExit(1)
PY

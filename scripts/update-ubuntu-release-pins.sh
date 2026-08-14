#!/usr/bin/env bash
# Regenerate trusted SHA-256 pins in install/ubuntu/lib/ubuntu-common.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON="${ROOT}/install/ubuntu/lib/ubuntu-common.sh"

python3 - "${COMMON}" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

common_path = Path(sys.argv[1])
root = common_path.parents[3]
text = common_path.read_text(encoding="utf-8")

def digest(lane: str, name: str) -> str:
    path = root / "install" / lane / name
    return hashlib.sha256(path.read_bytes()).hexdigest()

replacements = {
    "ubuntu/cpu": {
        "8.1.sh": digest("ubuntu/cpu", "8.1.sh"),
        "8.2.sh": digest("ubuntu/cpu", "8.2.sh"),
        "8.3.sh": digest("ubuntu/cpu", "8.3.sh"),
    },
    "ubuntu/cuda": {
        "8.1.sh": digest("ubuntu/cuda", "8.1.sh"),
        "8.2.sh": digest("ubuntu/cuda", "8.2.sh"),
        "8.3.sh": digest("ubuntu/cuda", "8.3.sh"),
    },
}

for lane, files in replacements.items():
    for name, value in files.items():
        key = f'{lane}/{name}'
        pattern = rf'(EIGHTBALL_RELEASE_SHA256\["{re.escape(key)}"\]=")[0-9a-f]{{64}}(")'
        text, count = re.subn(pattern, rf"\g<1>{value}\2", text)
        if count != 1:
            raise SystemExit(f"Failed to update hash for {key}")

common_path.write_text(text, encoding="utf-8")
print(f"Updated release SHA-256 pins in {common_path}")
PY

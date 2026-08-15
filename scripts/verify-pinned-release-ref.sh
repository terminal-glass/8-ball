#!/usr/bin/env bash
# Verify install/releases/*/manifest.json and runtime archive at an exact git ref.
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
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ref = sys.argv[1]
manifest_bytes = subprocess.check_output(
    ["git", "show", f"{ref}:install/releases/v0.8.0/manifest.json"]
)
manifest = json.loads(manifest_bytes)
archive_info = manifest.get("runtime_archive") or {}
archive_rel = archive_info.get("path")
archive_expected = archive_info.get("sha256")
if not archive_rel or not archive_expected:
    raise SystemExit("manifest missing runtime_archive.path or runtime_archive.sha256")

archive_bytes = subprocess.check_output(["git", "show", f"{ref}:{archive_rel}"])
archive_actual = hashlib.sha256(archive_bytes).hexdigest()
archive_mismatch = archive_actual != archive_expected

mismatches: list[str] = []
unsafe_paths: list[str] = []
archive_members: set[str] = set()
with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
    for member in tar.getmembers():
        if not member.isfile():
            continue
        name = member.name
        archive_members.add(name)
        if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
            unsafe_paths.append(name)

extracted_mismatches: list[str] = []
missing_in_archive: list[str] = []
rejected_members: list[str] = []
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "extracted"
    root.mkdir(parents=True, exist_ok=True)
    archive_path = Path(tmp) / "archive.tar.gz"
    archive_path.write_bytes(archive_bytes)
    repo_root = Path.cwd()
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "extract_runtime_archive",
        repo_root / "scripts/extract-runtime-archive.py",
    )
    if spec is None or spec.loader is None:
        raise SystemExit("could not load scripts/extract-runtime-archive.py")
    extract_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract_mod)
    try:
        extract_mod.extract_runtime_archive(archive_path, root)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    for rel_path, expected in manifest.get("artifacts", {}).items():
        if rel_path not in archive_members:
            missing_in_archive.append(rel_path)
            continue
        file_path = root / rel_path
        if not file_path.is_file():
            missing_in_archive.append(rel_path)
            continue
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual != expected:
            extracted_mismatches.append(rel_path)

    for rel_path, expected in manifest.get("artifacts", {}).items():
        data = subprocess.check_output(["git", "show", f"{ref}:{rel_path}"])
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            mismatches.append(rel_path)

print(f"runtime_ref={ref}")
print(f"artifacts_checked={len(manifest.get('artifacts', {}))}")
print(f"manifest_mismatches={len(mismatches)}")
print(f"archive_path={archive_rel}")
print(f"archive_sha_expected={archive_expected}")
print(f"archive_sha_actual={archive_actual}")
print(f"archive_sha_mismatch={str(archive_mismatch).lower()}")
print(f"archive_members={len(archive_members)}")
print(f"unsafe_paths={len(unsafe_paths)}")
print(f"missing_in_archive={len(missing_in_archive)}")
print(f"extracted_artifact_mismatches={len(extracted_mismatches)}")
print(
    "trial_install_in_archive=",
    "install/ubuntu/trial-install.sh" in archive_members,
)
rel = "install/shared/8ball-release.sh"
release_bytes = subprocess.check_output(["git", "show", f"{ref}:{rel}"])
print(f"8ball_release_expected={manifest['artifacts'][rel]}")
print(f"8ball_release_actual={hashlib.sha256(release_bytes).hexdigest()}")

if (
    mismatches
    or archive_mismatch
    or unsafe_paths
    or missing_in_archive
    or extracted_mismatches
    or "install/ubuntu/trial-install.sh" in archive_members
):
    for label, items in (
        ("manifest mismatch", mismatches),
        ("missing in archive", missing_in_archive),
        ("extracted mismatch", extracted_mismatches),
        ("unsafe path", unsafe_paths),
    ):
        for item in items[:5]:
            print(f"{label}: {item}")
    raise SystemExit(1)
PY

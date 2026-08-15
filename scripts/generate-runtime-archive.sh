#!/usr/bin/env bash
# Build a deterministic Ubuntu runtime archive for a tagged 8-BALL release.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="${1:-v0.8.0}"
OUT_DIR="${REPO_ROOT}/install/releases/${RELEASE}"
BUNDLE_CONFIG="${OUT_DIR}/runtime-bundle.json"
ARCHIVE_PATH="${OUT_DIR}/8ball-ubuntu-runtime.tar.gz"

python3 - "${RELEASE}" "${ARCHIVE_PATH}" "${BUNDLE_CONFIG}" "${REPO_ROOT}" <<'PY'
import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

release, archive_path, bundle_config_path, repo_root = sys.argv[1:5]
repo = Path(repo_root)
bundle = json.loads(Path(bundle_config_path).read_text(encoding="utf-8"))
pinned_manifest = repo / "install/releases" / release / "install-manifest.json"
if pinned_manifest in [repo / path for path in bundle.get("core_paths", [])]:
    if not pinned_manifest.is_file():
        raise SystemExit(f"Missing pinned install manifest: {pinned_manifest}")

archive_file = Path(archive_path)
archive_file.parent.mkdir(parents=True, exist_ok=True)


def collect_artifact_paths() -> list[str]:
    paths: list[str] = []
    for rel in bundle.get("ubuntu_scripts", []):
        path = repo / rel
        if not path.is_file():
            raise SystemExit(f"Missing ubuntu script for archive: {path}")
        paths.append(rel)
    for rel in bundle.get("shared_paths", []):
        path = repo / rel
        if not path.is_file():
            raise SystemExit(f"Missing shared artifact for archive: {path}")
        paths.append(rel)
    for rel in bundle.get("core_paths", []):
        path = repo / rel
        if not path.is_file():
            raise SystemExit(f"Missing core runtime artifact for archive: {path}")
        paths.append(rel)
    for slug in bundle.get("model_slugs", []):
        model_json = repo / "profiles" / slug / "model.json"
        if not model_json.is_file():
            raise SystemExit(f"Missing profile model.json for slug {slug}: {model_json}")
        paths.append(str(model_json.relative_to(repo)))
        sizes_dir = repo / "profiles" / slug / "sizes"
        if not sizes_dir.is_dir():
            raise SystemExit(f"Missing profile sizes for slug {slug}: {sizes_dir}")
        for size_path in sorted(sizes_dir.glob("*.json")):
            paths.append(str(size_path.relative_to(repo)))
        for lane in bundle.get("ubuntu_lanes", []):
            lane_json = repo / "profiles" / slug / lane / "lane.json"
            if not lane_json.is_file():
                raise SystemExit(f"Missing profile lane for slug {slug}: {lane_json}")
            paths.append(str(lane_json.relative_to(repo)))
    return sorted(set(paths))


def mode_for(rel_path: str) -> int:
    if rel_path.endswith(".sh") or rel_path.endswith(".py"):
        return 0o755
    return 0o644


artifact_paths = collect_artifact_paths()
for forbidden in (
    "install/ubuntu/trial-install.sh",
    f"install/releases/{release}/manifest.json",
    f"install/releases/{release}/8ball-ubuntu-runtime.tar.gz",
):
    if forbidden in artifact_paths:
        raise SystemExit(f"Forbidden archive member: {forbidden}")

buf = io.BytesIO()
with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for rel in artifact_paths:
            src = repo / rel
            data = src.read_bytes()
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mode = mode_for(rel)
            tar.addfile(info, io.BytesIO(data))

archive_bytes = buf.getvalue()
archive_file.write_bytes(archive_bytes)
digest = hashlib.sha256(archive_bytes).hexdigest()
print(f"Wrote {archive_file} ({len(artifact_paths)} files, {len(archive_bytes)} bytes)")
print(f"archive_sha256={digest}")
PY

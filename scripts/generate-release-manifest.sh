#!/usr/bin/env bash
# Generate SHA-256 manifest for a tagged 8-BALL installer release.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="${1:-v0.8.0}"
OUT_DIR="${REPO_ROOT}/install/releases/${RELEASE}"
BUNDLE_CONFIG="${OUT_DIR}/runtime-bundle.json"
ARCHIVE_PATH="${OUT_DIR}/8ball-ubuntu-runtime.tar.gz"
mkdir -p "${OUT_DIR}"

bash "${REPO_ROOT}/scripts/generate-runtime-archive.sh" "${RELEASE}"

python3 - "${RELEASE}" "${OUT_DIR}/manifest.json" "${BUNDLE_CONFIG}" "${ARCHIVE_PATH}" "${REPO_ROOT}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

release, out_path, bundle_config_path, archive_path, repo_root = sys.argv[1:6]
repo = Path(repo_root)
bundle = json.loads(Path(bundle_config_path).read_text(encoding="utf-8"))
pinned_manifest = repo / "install/releases" / release / "install-manifest.json"
if pinned_manifest in [repo / path for path in bundle.get("core_paths", [])]:
    if not pinned_manifest.is_file():
        raise SystemExit(f"Missing pinned install manifest: {pinned_manifest}")

archive_file = Path(archive_path)
if not archive_file.is_file():
    raise SystemExit(f"Missing runtime archive: {archive_file}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

artifacts: dict[str, str] = {}

for rel in bundle.get("ubuntu_scripts", []):
    path = repo / rel
    if not path.is_file():
        raise SystemExit(f"Missing ubuntu script for manifest: {path}")
    artifacts[rel] = sha256_file(path)

for rel in bundle.get("shared_paths", []):
    path = repo / rel
    if not path.is_file():
        raise SystemExit(f"Missing shared artifact for manifest: {path}")
    artifacts[rel] = sha256_file(path)

for rel in bundle.get("core_paths", []):
    path = repo / rel
    if not path.is_file():
        raise SystemExit(f"Missing core runtime artifact for manifest: {path}")
    artifacts[rel] = sha256_file(path)

for slug in bundle.get("model_slugs", []):
    model_json = repo / "profiles" / slug / "model.json"
    if not model_json.is_file():
        raise SystemExit(f"Missing profile model.json for slug {slug}: {model_json}")
    rel = str(model_json.relative_to(repo))
    artifacts[rel] = sha256_file(model_json)

    sizes_dir = repo / "profiles" / slug / "sizes"
    if not sizes_dir.is_dir():
        raise SystemExit(f"Missing profile sizes for slug {slug}: {sizes_dir}")
    for size_path in sorted(sizes_dir.glob("*.json")):
        rel = str(size_path.relative_to(repo))
        artifacts[rel] = sha256_file(size_path)

    for lane in bundle.get("ubuntu_lanes", []):
        lane_json = repo / "profiles" / slug / lane / "lane.json"
        if not lane_json.is_file():
            raise SystemExit(f"Missing profile lane for slug {slug}: {lane_json}")
        rel = str(lane_json.relative_to(repo))
        artifacts[rel] = sha256_file(lane_json)

scripts = {
    Path(rel).name: digest
    for rel, digest in artifacts.items()
    if rel.startswith("install/ubuntu/") and rel.endswith(".sh")
}

archive_rel = str(archive_file.relative_to(repo))
manifest = {
    "suite_version": release.lstrip("v"),
    "script_family": "8-BALL",
    "release_tag": release,
    "repository": "terminal-glass/8-ball",
    "runtime_bundle": str(Path(bundle_config_path).relative_to(repo)),
    "runtime_archive": {
        "path": archive_rel,
        "sha256": sha256_file(archive_file),
        "artifact_count": len(artifacts),
    },
    "scripts": scripts,
    "artifacts": artifacts,
}
Path(out_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out_path} ({len(artifacts)} artifacts)")
PY

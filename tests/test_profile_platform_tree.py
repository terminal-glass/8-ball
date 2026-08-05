from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from eight_ball.paths import GENERATED_INSTALL_MANIFEST_PATH, PROFILES_DIR, REPO_ROOT

PLATFORM_LANES = (
    "ubuntu/cpu",
    "ubuntu/cuda",
    "mac/apple-silicon",
    "mac/intel",
    "windows/cpu",
    "windows/cuda",
    "cloud/digitalocean/cpu-droplet",
    "cloud/digitalocean/gpu-droplet",
    "cloud/aws-lightsail/cpu",
    "cloud/aws-lightsail/gpu",
)

NON_MODEL_PROFILE_DIRS = frozenset(
    {
        "families",
        "models",
        "deployment-classes",
        "provider-assumptions",
    }
)


def _model_slugs_from_manifest() -> list[str]:
    manifest = json.loads(GENERATED_INSTALL_MANIFEST_PATH.read_text(encoding="utf-8"))
    models = manifest.get("models", {})
    return sorted({entry.get("model_slug") or model_id for model_id, entry in models.items()})


def _model_profile_dirs() -> list[Path]:
    return sorted(
        path
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in NON_MODEL_PROFILE_DIRS
    )


def test_platform_lane_skeleton_for_sample_models(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    for slug in ("qwen3-0-6b", "llama3-8b"):
        model_dir = profiles / slug
        model_dir.mkdir(parents=True)
        for lane in PLATFORM_LANES:
            (model_dir / lane).mkdir(parents=True)

        for lane in PLATFORM_LANES:
            assert (model_dir / lane).is_dir()
        assert not any(path.is_file() for path in model_dir.rglob("*"))


@pytest.mark.skipif(
    not GENERATED_INSTALL_MANIFEST_PATH.is_file(),
    reason="install manifest missing",
)
def test_profile_platform_tree_complete_in_working_tree() -> None:
    script = REPO_ROOT / "scripts" / "create-profile-platform-tree.sh"
    subprocess.run(["bash", str(script)], cwd=REPO_ROOT, check=True)

    model_dirs = _model_profile_dirs()
    expected_slugs = _model_slugs_from_manifest()
    assert len(model_dirs) == len(expected_slugs)

    missing: list[str] = []
    with_files: list[str] = []
    for model_dir in model_dirs:
        for lane in PLATFORM_LANES:
            lane_path = model_dir / lane
            if not lane_path.is_dir():
                missing.append(f"{model_dir.name}/{lane}")
        if any(path.is_file() for path in model_dir.rglob("*")):
            with_files.append(model_dir.name)

    assert not missing, f"Missing platform lanes: {missing[:10]}"
    assert not with_files, f"Model folders contain files: {with_files[:10]}"
    assert len(model_dirs) * len(PLATFORM_LANES) == 4370

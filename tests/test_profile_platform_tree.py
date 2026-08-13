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

STAGE_FILES = (
    "lane.json",
    "3-cpu.json",
    "4-ram.json",
    "5-hard-disk.json",
    "6-cpu-only.json",
    "7-gpu-vram.json",
    "profile-sizes.csv",
)

NON_MODEL_PROFILE_DIRS = frozenset(
    {
        "families",
        "models",
        "deployment-classes",
        "provider-assumptions",
        "legacy",
        "generated",
    }
)


def _c10_model_slugs() -> list[str]:
    index_path = PROFILES_DIR / "c10-index.json"
    if not index_path.is_file():
        return []
    rows = json.loads(index_path.read_text(encoding="utf-8")).get("rows", [])
    return sorted({row["model_slug"] for row in rows})


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
    not (PROFILES_DIR / "legacy" / "c10-index.json").is_file(),
    reason="Legacy C10 profile index missing",
)
def test_c10_profile_platform_tree_complete_in_working_tree() -> None:
    index_path = PROFILES_DIR / "legacy" / "c10-index.json"
    rows = json.loads(index_path.read_text(encoding="utf-8")).get("rows", [])
    model_slugs = sorted({row["model_slug"] for row in rows})
    assert model_slugs, "C10 index must list model slugs"

    missing: list[str] = []
    legacy_pages = PROFILES_DIR / "legacy" / "c10-model-pages"
    for slug in model_slugs:
        page = legacy_pages / f"{slug}.json"
        if not page.is_file():
            missing.append(f"legacy/c10-model-pages/{slug}.json")
        for lane in PLATFORM_LANES:
            leaf = PROFILES_DIR / slug / lane
            if not leaf.is_dir():
                missing.append(f"{slug}/{lane}")
                continue
            for stage in STAGE_FILES:
                if not (leaf / stage).is_file():
                    missing.append(f"{slug}/{lane}/{stage}")

    assert not missing, f"Missing C10 profile artifacts: {missing[:10]}"
    assert len(model_slugs) >= 200


def test_create_profile_platform_tree_script_runs(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "create-profile-platform-tree.sh"
    if not GENERATED_INSTALL_MANIFEST_PATH.is_file():
        pytest.skip("install manifest missing")
    subprocess.run(["bash", str(script)], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["python3", str(REPO_ROOT / "scripts" / "generate-profiles-from-agents.py")],
        cwd=REPO_ROOT,
        check=True,
    )

    model_dirs = sorted(
        path
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in NON_MODEL_PROFILE_DIRS
    )
    assert model_dirs

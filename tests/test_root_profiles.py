from __future__ import annotations

import json
import subprocess

import pytest

from eight_ball.paths import GENERATED_PROVIDER_ASSUMPTIONS_DIR, PROFILES_DIR, REPO_ROOT

FORBIDDEN_PROFILE_DIRS = (
    "families",
    "models",
    "deployment-classes",
    "provider-assumptions",
)
FORBIDDEN_PROFILE_FILES = (
    "index.csv",
    "environment.profile.example.env",
)
ALLOWED_PROFILE_ROOT_FILES = frozenset({"README.md", "c10-index.json", "manifest.json"})
INSTALL_LANES = (
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
    "5-hard_disk.json",
    "6-CPU_only.json",
    "7-video_card.json",
)


def test_generate_root_profiles_cli_removed() -> None:
    result = subprocess.run(
        ["python3", "-m", "eight_ball.cli", "generate-root-profiles"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr or "generate-root-profiles" in result.stderr


def test_root_profiles_module_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("eight_ball.generate.root_profiles")


def test_forbidden_profile_directories_absent() -> None:
    for name in FORBIDDEN_PROFILE_DIRS:
        assert not (PROFILES_DIR / name).exists(), f"Forbidden directory exists: profiles/{name}/"


def test_forbidden_profile_root_files_absent() -> None:
    for name in FORBIDDEN_PROFILE_FILES:
        assert not (PROFILES_DIR / name).is_file(), f"Forbidden file exists: profiles/{name}"


def test_provider_assumptions_live_under_data_generated() -> None:
    assert GENERATED_PROVIDER_ASSUMPTIONS_DIR.is_dir()
    for name in (
        "ubuntu-cpu.json",
        "ubuntu-cuda.json",
        "mac-apple-silicon.json",
        "mac-intel.json",
        "windows-cpu.json",
        "windows-cuda.json",
        "cloud-digitalocean-cpu-droplet.json",
        "cloud-digitalocean-gpu-droplet.json",
        "cloud-aws-lightsail-cpu.json",
        "cloud-aws-lightsail-gpu.json",
    ):
        assert (GENERATED_PROVIDER_ASSUMPTIONS_DIR / name).is_file()


def test_model_pages_and_directories_are_paired() -> None:
    model_pages = {
        path.stem
        for path in PROFILES_DIR.glob("*.json")
        if path.name not in {"c10-index.json", "manifest.json"}
    }
    model_dirs = {
        path.name
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in FORBIDDEN_PROFILE_DIRS
    }
    assert model_pages
    assert model_pages == model_dirs


def test_profiles_root_allowlist() -> None:
    for child in PROFILES_DIR.iterdir():
        if child.is_dir():
            assert child.name not in FORBIDDEN_PROFILE_DIRS
            continue
        if child.suffix == ".json" and child.name not in ALLOWED_PROFILE_ROOT_FILES:
            continue
        assert child.name in ALLOWED_PROFILE_ROOT_FILES, f"Unexpected profiles root file: {child.name}"


def test_c10_manifest_is_c10_only() -> None:
    manifest_path = PROFILES_DIR / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "c10.profiles-manifest.v1"
    paths = manifest.get("paths") or {}
    assert "profiles/families" not in json.dumps(paths)
    assert "profiles/models" not in json.dumps(paths)
    assert paths.get("provider_assumptions", "").startswith("data/generated/provider-assumptions")


def test_environment_profile_example_moved_out_of_profiles() -> None:
    assert not (PROFILES_DIR / "environment.profile.example.env").is_file()
    assert (REPO_ROOT / "docs/profile-runtime/environment.profile.example.env").is_file()


def test_c10_generator_does_not_erase_model_pages() -> None:
    marker = PROFILES_DIR / "gemma.json"
    assert marker.is_file()
    import os

    env = os.environ.copy()
    env["C10_BUILD_TIMESTAMP"] = "2026-08-06T08:00:00Z"
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "scripts/generate-c10-profiles.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert marker.is_file()
    assert (PROFILES_DIR / "gemma" / "ubuntu" / "cpu" / "lane.json").is_file()
    assert (PROFILES_DIR / "c10-index.json").is_file()


def test_lane_json_references_new_provider_assumption_path() -> None:
    lane = json.loads((PROFILES_DIR / "gemma/ubuntu/cpu/lane.json").read_text(encoding="utf-8"))
    assert lane["provider_assumption"].startswith("data/generated/provider-assumptions/")


def test_ram_stage_retains_size_ram_fit() -> None:
    ram = json.loads((PROFILES_DIR / "gemma/ubuntu/cpu/4-ram.json").read_text(encoding="utf-8"))
    assert isinstance(ram.get("size_ram_fit"), list) and ram["size_ram_fit"]
    for row in ram["size_ram_fit"]:
        if row.get("ram_fit_status") != "fit":
            assert row.get("fits") is False


def test_every_model_has_ten_lane_leaves_with_stage_files() -> None:
    model_pages = sorted(
        path.stem
        for path in PROFILES_DIR.glob("*.json")
        if path.name not in {"c10-index.json", "manifest.json"}
    )
    assert len(model_pages) >= 200
    for slug in model_pages[:5]:
        for lane in INSTALL_LANES:
            leaf = PROFILES_DIR / slug / lane
            assert leaf.is_dir(), slug
            for stage in STAGE_FILES:
                assert (leaf / stage).is_file(), f"{slug}/{lane}/{stage}"

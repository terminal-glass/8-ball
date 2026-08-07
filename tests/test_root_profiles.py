from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eight_ball.paths import PROFILES_DIR, REPO_ROOT

_C10_LANES_PATH = REPO_ROOT / "scripts" / "c10_lanes.py"
_SPEC = importlib.util.spec_from_file_location("c10_lanes", _C10_LANES_PATH)
assert _SPEC and _SPEC.loader
c10_lanes = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_lanes
_SPEC.loader.exec_module(c10_lanes)

FORBIDDEN_PROFILE_DIRS = (
    "families",
    "models",
    "deployment-classes",
    "provider-assumptions",
)
FORBIDDEN_PROFILE_FILES = (
    "environment.profile.example.env",
)
ALLOWED_PROFILE_ROOT_FILES = frozenset(
    {
        "README.md",
        "c10-index.json",
        "manifest.json",
        "lanes.json",
        "index.csv",
        "_lane-matrix-audit.json",
        "_lane-matrix-audit.csv",
    }
)
STAGE_FILES = c10_lanes.STAGE_PAYLOAD_FILES


def _lane_paths() -> list[str]:
    manifest = json.loads((PROFILES_DIR / "lanes.json").read_text(encoding="utf-8"))
    return [lane["profile_path"].rstrip("/") for lane in manifest["lanes"]]


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


def test_provider_assumptions_dir_absent() -> None:
    assert not (REPO_ROOT / "data/generated/provider-assumptions").exists()
    assert not (PROFILES_DIR / "provider-assumptions").exists()


def test_lanes_manifest_matches_canonical_contract() -> None:
    manifest = json.loads((PROFILES_DIR / "lanes.json").read_text(encoding="utf-8"))
    rows = c10_lanes.canonical_lane_rows_from_manifest(manifest)
    assert c10_lanes.lane_rows_match_canonical(rows)


def test_install_payload_contract_from_lanes_manifest() -> None:
    manifest = json.loads((PROFILES_DIR / "lanes.json").read_text(encoding="utf-8"))
    payload_count = 0
    readme_count = 0
    for lane in manifest["lanes"]:
        lane_dir = c10_lanes.install_lane_dir(lane)
        assert lane_dir.is_dir()
        readme_count += int((lane_dir / "README.md").is_file())
        for path in c10_lanes.payload_paths_for_lane(lane):
            assert path.is_file() and path.stat().st_size > 0, path
            payload_count += 1
    assert payload_count == c10_lanes.REQUIRED_INSTALL_PAYLOAD_FILE_COUNT
    assert readme_count == c10_lanes.REQUIRED_INSTALL_README_COUNT


def test_git_tracks_canonical_lane_payloads_when_staged() -> None:
    """Canonical lane payloads must not be gitignored; count from lanes.json paths."""
    manifest = json.loads((PROFILES_DIR / "lanes.json").read_text(encoding="utf-8"))
    for lane in manifest["lanes"]:
        for path in c10_lanes.payload_paths_for_lane(lane):
            rel = path.relative_to(REPO_ROOT).as_posix()
            assert path.is_file() and path.stat().st_size > 0
            ignore = subprocess.run(
                ["git", "check-ignore", "-q", "--", rel],
                cwd=REPO_ROOT,
            ).returncode
            assert ignore != 0, f"Canonical payload is gitignored: {rel}"


def test_model_pages_and_directories_are_paired() -> None:
    model_pages = {
        path.stem
        for path in PROFILES_DIR.glob("*.json")
        if path.name
        not in {"c10-index.json", "manifest.json", "lanes.json", "_lane-matrix-audit.json"}
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
        if child.suffix == ".csv" and child.name in {"index.csv", "_lane-matrix-audit.csv"}:
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
    assert "provider_assumptions" not in paths
    assert paths.get("lanes_manifest") == "profiles/lanes.json"


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


def test_lane_json_maps_to_install_path() -> None:
    lane = json.loads((PROFILES_DIR / "gemma/ubuntu/cpu/lane.json").read_text(encoding="utf-8"))
    assert lane["install_path"] == "install/ubuntu/cpu/"
    assert lane["lane_id"] == "ubuntu-cpu"
    assert "provider_assumption" not in lane


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
        if path.name
        not in {"c10-index.json", "manifest.json", "lanes.json", "_lane-matrix-audit.json"}
    )
    assert len(model_pages) >= 200
    lane_paths = _lane_paths()
    for slug in model_pages[:5]:
        for lane in lane_paths:
            leaf = PROFILES_DIR / slug / lane
            assert leaf.is_dir(), slug
            assert (leaf / "profile-sizes.csv").is_file()
            for stage in ("lane.json", *STAGE_FILES):
                assert (leaf / stage).is_file(), f"{slug}/{lane}/{stage}"

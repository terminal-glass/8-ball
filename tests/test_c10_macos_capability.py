from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_MACOS_PATH = REPO_ROOT / "scripts" / "c10_macos_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_macos_compatibility", _C10_MACOS_PATH)
assert _SPEC and _SPEC.loader
c10_macos = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_macos
_SPEC.loader.exec_module(c10_macos)


def test_arm64_selects_apple_silicon_lane_only() -> None:
    assert c10_macos.select_target_lane("arm64") == "mac/apple-silicon"
    normalized = c10_macos.normalize_observation({"architecture": "arm64"})
    assert normalized["target_lane"] == "mac/apple-silicon"
    assert normalized["cuda_status"] == "not_applicable"


def test_x86_64_selects_intel_lane_only() -> None:
    assert c10_macos.select_target_lane("x86_64") == "mac/intel"
    normalized = c10_macos.normalize_observation({"architecture": "x86_64"})
    assert normalized["target_lane"] == "mac/intel"


def test_unknown_architecture_selects_no_confident_lane() -> None:
    assert c10_macos.select_target_lane("aarch64") is None
    assert c10_macos.select_target_lane(None) is None
    normalized = c10_macos.normalize_observation({"architecture": "unknown"})
    assert normalized["target_lane"] == "unknown"


def test_apple_silicon_unified_memory_not_gpu_vram() -> None:
    normalized = c10_macos.normalize_observation(
        {
            "architecture": "arm64",
            "physical_memory_mb": 16384,
            "gpu_memory_mb": 8192,
        }
    )
    assert normalized["physical_memory_mb"] == 16384
    assert normalized["gpu_memory_mb"] is None


def test_missing_hardware_output_remains_null_or_unknown() -> None:
    normalized = c10_macos.normalize_observation({"architecture": "x86_64"})
    assert normalized["physical_memory_mb"] is None
    assert normalized["free_install_disk_mb"] is None
    assert normalized["cpu_threads"] is None
    assert normalized["gpu_name"] is None
    assert normalized["metal_status"] == "unknown"
    assert normalized["gpu_present"] == "unknown"


def test_mac_observation_does_not_change_catalog_model_fit() -> None:
    ram_path = REPO_ROOT / "profiles/llama3/mac/apple-silicon/4-ram.json"
    before = json.loads(ram_path.read_text(encoding="utf-8"))
    c10_macos.generate_macos_compatibility(REPO_ROOT)
    after = json.loads(ram_path.read_text(encoding="utf-8"))
    assert before == after


def test_taxonomy_has_eight_categories_and_five_bands() -> None:
    taxonomy = c10_macos.load_taxonomy(REPO_ROOT)
    assert len(taxonomy["categories"]) == 8
    assert len(taxonomy["runtime_menu_bands"]) == 5
    assert len(taxonomy["disk_gates"]) == 5


def test_canonical_mac_lanes_in_projection() -> None:
    projection = json.loads(
        (
            REPO_ROOT / "profiles/provider-compatibility/macos/lane-runtime-contract-projection.json"
        ).read_text(encoding="utf-8")
    )
    assert set(projection["lanes"]) == {"mac/apple-silicon", "mac/intel"}


def test_observe_helper_non_darwin_degrades_safely() -> None:
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/macos-observe-host.sh"), "/tmp"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["architecture"] == "unknown"
    assert payload["target_lane"] == "unknown"
    assert payload["cuda_status"] == "not_applicable"
    assert payload["observation_status"] == "non_darwin_host"


def test_macos_capability_report_trackable_path() -> None:
    report_path = REPO_ROOT / "data/generated/capability-catalog/macos/capability-report.json"
    assert report_path.is_file()
    assert c10_macos.REPORT_JSON == report_path


LEGACY_C5_INDEX = REPO_ROOT / "profiles" / "legacy" / "c5-root-export" / "index.csv"


def test_profiles_index_csv_unchanged() -> None:
    with LEGACY_C5_INDEX.open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_macos_validator_has_no_errors() -> None:
    errors = c10_macos.validate_macos_sources(REPO_ROOT)
    assert errors == []

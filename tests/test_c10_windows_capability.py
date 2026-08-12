from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_WINDOWS_PATH = REPO_ROOT / "scripts" / "c10_windows_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_windows_compatibility", _C10_WINDOWS_PATH)
assert _SPEC and _SPEC.loader
c10_windows = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_windows
_SPEC.loader.exec_module(c10_windows)


def test_taxonomy_category_counts() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    categories = taxonomy["categories"]
    assert len(categories) == 14
    assert sum(1 for c in categories if c["category_kind"] == "host_topology") == 6
    assert sum(1 for c in categories if c["category_kind"] == "lane_routing") == 2
    assert sum(1 for c in categories if c["category_kind"] == "gpu_reporting") == 6


def test_only_canonical_windows_lanes_referenced() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    lane_targets = {c["target_lane"] for c in taxonomy["categories"] if c.get("target_lane")}
    assert lane_targets == {"windows/cpu", "windows/cuda"}
    projection = json.loads(
        (
            REPO_ROOT / "profiles/provider-compatibility/windows/lane-runtime-contract-projection.json"
        ).read_text(encoding="utf-8")
    )
    assert set(projection["lanes"]) == {"windows/cpu", "windows/cuda"}


def test_no_windows_vm_physical_sublanes() -> None:
    windows_install = REPO_ROOT / "install" / "windows"
    for forbidden in ("vm", "physical", "hyperv", "wsl"):
        assert not (windows_install / forbidden).exists()


def test_runtime_menu_bands_match_pilot_policy() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    menu = c10_windows.load_pilot_menu(REPO_ROOT)
    bands = taxonomy["runtime_menu_bands"]
    assert len(bands) == 5
    expected = {tuple(band["ordered_pilot_candidates"]) for band in menu["bands"]}
    actual = {tuple(band["runtime_trial_candidates"]) for band in bands}
    assert actual == expected
    for band in bands:
        assert band["classification"] == "runtime_menu_band_only"
        assert band["source_script_path"] == c10_windows.WINDOWS_SOURCE_SCRIPT


def test_disk_gates_match_policy_mib() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    expected = {
        "qwen3:14b": 14336,
        "qwen3:8b": 9216,
        "qwen3:4b": 6144,
        "qwen3:1.7b": 4096,
        "qwen3:0.6b": 3072,
    }
    actual = {gate["candidate_ollama_ref"]: gate["required_free_disk_mib"] for gate in taxonomy["disk_gates"]}
    assert actual == expected
    for gate in taxonomy["disk_gates"]:
        assert gate["classification"] == "runtime_download_guard_only"
        assert gate["model_fit_proven"] is False


def test_nvidia_smi_required_for_cuda_lane() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    cuda = next(c for c in taxonomy["categories"] if c.get("target_lane") == "windows/cuda")
    commands = " ".join(cuda["runtime_evidence_commands"]).lower()
    assert "nvidia-smi" in commands
    assert cuda["windows_cuda_lane_eligible"] == "yes"
    assert cuda["windows_gpu_vram_source"] == "nvidia_smi"


def test_adapter_ram_cannot_become_verified_vram() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    unverified = next(
        c for c in taxonomy["categories"] if c["windows_gpu_reporting_category"] == "gpu_present_unverified"
    )
    assert "adapterram" in unverified["notes"].lower()
    assert unverified["windows_gpu_vram_source"] == "unknown"
    contract = json.loads(
        (
            REPO_ROOT / "profiles/provider-compatibility/windows/runtime-observation-contract.json"
        ).read_text(encoding="utf-8")
    )
    assert contract["adapter_ram_verified_vram_forbidden"] is True
    normalized = c10_windows.normalize_collector_output(
        {
            "EIGHTBALL_OS_FAMILY": "windows",
            "windows_gpu_vram_source": "unknown",
            "EIGHTBALL_GPU_VRAM_MB": 8192,
            "windows_cuda_lane_eligible": "no",
            "EIGHTBALL_GPU_PRESENT": "yes",
        }
    )
    assert normalized["EIGHTBALL_GPU_VRAM_MB"] == "unknown"


def test_wsl_not_native_windows() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    assert taxonomy["wsl_policy"]["native_windows_lane_eligible"] is False
    contract = json.loads(
        (
            REPO_ROOT / "profiles/provider-compatibility/windows/runtime-observation-contract.json"
        ).read_text(encoding="utf-8")
    )
    assert contract["wsl_native_windows_lane_forbidden"] is True
    schema = json.loads(
        (REPO_ROOT / "AGENTS/data-science/profile-mapping/windows/collector-output-schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["wsl_policy"]["native_windows_lane_eligible"] is False
    wsl = c10_windows.normalize_collector_output(
        {
            "EIGHTBALL_OS_FAMILY": "wsl",
            "windows_cuda_lane_eligible": "no",
            "native_windows_lane_eligible": False,
            "target_lane": "unknown",
        }
    )
    assert wsl["EIGHTBALL_OS_FAMILY"] == "wsl"
    assert wsl["native_windows_lane_eligible"] is False
    assert wsl["target_lane"] == "unknown"
    assert wsl["windows_cuda_lane_eligible"] == "no"


def test_wsl_with_nvidia_smi_still_excludes_native_windows_lanes() -> None:
    wsl = c10_windows.normalize_collector_output(
        {
            "EIGHTBALL_OS_FAMILY": "wsl",
            "windows_cuda_lane_eligible": "yes",
            "target_lane": "windows/cuda",
            "EIGHTBALL_GPU_VRAM_MB": 8192,
            "windows_gpu_vram_source": "nvidia_smi",
        }
    )
    assert wsl["target_lane"] == "unknown"
    assert wsl["native_windows_lane_eligible"] is False


def test_install_path_disk_free_gb_from_measured_bytes() -> None:
    assert c10_windows.compute_install_disk_free_gb(10 * 1024**3 + 900 * 1024**2) == 10
    assert c10_windows.compute_install_disk_free_gb(None) is None
    assert c10_windows.compute_install_disk_free_gb(-1) is None


def test_collector_normalization_keeps_unknown_disk_when_unresolved() -> None:
    normalized = c10_windows.normalize_collector_output(
        {
            "EIGHTBALL_OS_FAMILY": "windows",
            "EIGHTBALL_DISK_FREE_GB": None,
            "windows_cuda_lane_eligible": "no",
            "EIGHTBALL_GPU_PRESENT": "yes",
        }
    )
    assert normalized["EIGHTBALL_DISK_FREE_GB"] is None


def test_collector_safe_unknown_fallback_shape() -> None:
    normalized = c10_windows.normalize_collector_output({"EIGHTBALL_OS_FAMILY": "unknown"})
    assert normalized["target_lane"] == "unknown"
    assert normalized["EIGHTBALL_GPU_VRAM_MB"] == "unknown"


def test_collector_script_documents_wsl_and_install_disk() -> None:
    text = (REPO_ROOT / "AGENTS/data-science/profile-mapping/windows/collector-example.ps1").read_text(
        encoding="utf-8"
    )
    assert "Test-IsWslEnvironment" in text
    assert "Get-InstallPathFreeDiskGb" in text
    assert "$ErrorActionPreference = 'Stop'" not in text


def test_capacity_fields_remain_null_not_zero_or_empty() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    for record in taxonomy["categories"]:
        for field in (
            "windows_architecture",
            "visible_cpu_threads",
            "system_ram_gib",
            "install_path_free_disk_gib",
            "gpu_vendor",
            "gpu_model",
            "gpu_memory_gib",
        ):
            value = record.get(field)
            assert value not in (0, "", "0"), f"{record['id']}.{field} must not use placeholder"


def test_gpu_reporting_categories_present() -> None:
    taxonomy = c10_windows.load_taxonomy(REPO_ROOT)
    categories = {
        c["windows_gpu_reporting_category"]
        for c in taxonomy["categories"]
        if c["category_kind"] == "gpu_reporting"
    }
    assert categories == set(c10_windows.GPU_REPORTING_CATEGORIES)
    for record in taxonomy["categories"]:
        if record["category_kind"] == "gpu_reporting":
            assert record["model_fit_proven"] is False


def test_profiles_index_csv_unchanged() -> None:
    with (REPO_ROOT / "profiles/index.csv").open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_windows_validator_has_no_errors() -> None:
    errors = c10_windows.validate_windows_sources(REPO_ROOT)
    assert errors == []

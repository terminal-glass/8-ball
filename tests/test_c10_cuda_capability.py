from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_CUDA_PATH = REPO_ROOT / "scripts" / "c10_cuda_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_cuda_compatibility", _C10_CUDA_PATH)
assert _SPEC and _SPEC.loader
c10_cuda = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_cuda
_SPEC.loader.exec_module(c10_cuda)


def test_policy_supported_at_boundary_cc_5_driver_570() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(5.0, "570.12") == "supported"


def test_policy_unsupported_cc_5_driver_569() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(5.0, "569.99") == "unsupported"


def test_policy_supported_cc_6_3_driver_550() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(6.3, "550.54") == "supported"


def test_policy_unsupported_cc_below_5() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(4.9, "600") == "unsupported"


def test_policy_unknown_when_compute_capability_missing() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(None, "600") == "unknown"


def test_policy_unknown_when_driver_missing() -> None:
    assert c10_cuda.evaluate_ollama_nvidia_support(8.0, None) == "unknown"


def test_nvidia_smi_failure_produces_no_cuda_ready_lane() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(os_family="linux", nvidia_smi_csv="")
    assert payload["observation_status"] == "unavailable"
    assert payload["cuda_runtime_ready"] is False
    assert payload["target_lane"] == "unknown"
    assert payload["devices"] == []


def test_multi_gpu_retains_uuid_backed_records() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv=(
            "0, GPU-1111-aaaa, Tesla A, 570.00, 8192, 8.0\n"
            "1, GPU-2222-bbbb, Tesla B, 570.00, 16384, 8.6\n"
        ),
    )
    assert len(payload["devices"]) == 2
    assert payload["devices"][0]["gpu_uuid"] == "GPU-1111-aaaa"
    assert payload["devices"][1]["gpu_uuid"] == "GPU-2222-bbbb"
    assert payload["devices"][0]["gpu_index"] == 0
    assert payload["devices"][1]["gpu_index"] == 1


def test_driver_cuda_api_version_is_not_toolkit_version() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-3333, GPU C, 570.00, 8192, 8.0",
        nvidia_smi_header="CUDA Version: 12.4",
        nvcc_output="Cuda compilation tools, release 12.2, V12.2.140",
    )
    device = payload["devices"][0]
    assert device["driver_reported_cuda_api_max_version"] == "12.4"
    assert device["cuda_toolkit_version"] == "12.2"
    assert device["driver_reported_cuda_api_max_version"] != device["cuda_toolkit_version"]


def test_toolkit_null_without_nvcc() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-4444, GPU D, 570.00, 8192, 8.0",
        nvidia_smi_header="CUDA Version: 12.4",
    )
    assert payload["devices"][0]["cuda_toolkit_version"] is None


def test_cuda_visible_devices_numeric_does_not_resolve_uuid() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-aaaa, GPU A, 570.00, 8192, 8.0\n1, GPU-bbbb, GPU B, 570.00, 16384, 8.6",
        cuda_visible_devices="0",
    )
    assert payload["cuda_visible_devices_env"] == "0"
    assert payload["cuda_visible_resolved_uuid"] is None


def test_cuda_visible_devices_uuid_resolves_when_unambiguous() -> None:
    payload = c10_cuda.build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-aaaa, GPU A, 570.00, 8192, 8.0",
        cuda_visible_devices="GPU-aaaa",
    )
    assert payload["cuda_visible_resolved_uuid"] == "GPU-aaaa"


def test_lane_selection_requires_os_and_provider_context() -> None:
    assert c10_cuda.select_cuda_lane("linux", None, True) == "ubuntu/cuda"
    assert c10_cuda.select_cuda_lane("windows", None, True) == "windows/cuda"
    assert c10_cuda.select_cuda_lane("linux", "digitalocean", True) == "cloud/digitalocean/gpu-droplet"
    assert c10_cuda.select_cuda_lane("linux", "aws-lightsail", True) == "cloud/aws-lightsail/gpu"
    assert c10_cuda.select_cuda_lane("linux", None, False) is None
    assert c10_cuda.select_cuda_lane("macos", None, True) is None


def test_mac_lanes_are_never_cuda() -> None:
    for arch in ("arm64", "x86_64"):
        assert c10_cuda.select_cuda_lane("macos", None, True) is None
        assert c10_cuda.select_cuda_lane(arch, None, True) is None


def test_cuda_observation_does_not_change_catalog_model_fit() -> None:
    video_path = REPO_ROOT / "profiles/llama3/ubuntu/cuda/7-gpu-vram.json"
    before = json.loads(video_path.read_text(encoding="utf-8"))
    c10_cuda.generate_cuda_compatibility(REPO_ROOT)
    after = json.loads(video_path.read_text(encoding="utf-8"))
    assert before == after


def test_taxonomy_has_six_categories_and_four_cuda_lanes() -> None:
    taxonomy = c10_cuda.load_taxonomy(REPO_ROOT)
    assert len(taxonomy["categories"]) == 6
    lane_targets = {
        c["target_lane"] for c in taxonomy["categories"] if c["category_kind"] == "lane_routing"
    }
    assert lane_targets == set(c10_cuda.CANONICAL_LANES)


def test_canonical_cuda_lanes_in_projection() -> None:
    projection = json.loads(
        (REPO_ROOT / "profiles/provider-compatibility/cuda/lane-runtime-contract-projection.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(projection["lanes"]) == set(c10_cuda.CANONICAL_LANES)
    assert projection["mac_lanes_explicitly_excluded"] == list(c10_cuda.MAC_LANES)


def test_observe_linux_helper_degrades_safely() -> None:
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/cuda-observe-linux.sh")],
        capture_output=True,
        text=True,
        check=False,
        env={"CUDA_OBSERVE_OS_FAMILY": "linux", **dict(**__import__("os").environ)},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["observation_status"] in {"available", "unavailable"}
    assert payload["mac_lane_forbidden"] is True


def test_cuda_capability_report_trackable_path() -> None:
    report_path = REPO_ROOT / "data/generated/capability-catalog/cuda/capability-report.json"
    assert report_path.is_file()
    assert c10_cuda.REPORT_JSON == report_path


LEGACY_C5_INDEX = REPO_ROOT / "profiles" / "legacy" / "c5-root-export" / "index.csv"


def test_profiles_index_csv_unchanged() -> None:
    with LEGACY_C5_INDEX.open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_cuda_validator_has_no_errors() -> None:
    errors = c10_cuda.validate_cuda_sources(REPO_ROOT)
    assert errors == []


def test_policy_json_has_provenance() -> None:
    policy = c10_cuda.load_policy(REPO_ROOT)
    assert policy["source_url"] == "https://docs.ollama.com/gpu"
    assert policy["retrieval_date"] == "2026-08-12"
    assert policy["rules"]["minimum_driver_version"] == 550

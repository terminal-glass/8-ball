from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_UBUNTU_PATH = REPO_ROOT / "scripts" / "c10_ubuntu_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_ubuntu_compatibility", _C10_UBUNTU_PATH)
assert _SPEC and _SPEC.loader
c10_ubuntu = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_ubuntu
_SPEC.loader.exec_module(c10_ubuntu)


def test_taxonomy_has_exactly_ten_categories() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    categories = taxonomy["categories"]
    assert len(categories) == 10
    topology = [c for c in categories if c.get("host_topology")]
    gpu_states = [c for c in categories if c.get("gpu_runtime_state")]
    assert len(topology) == 6
    assert len(gpu_states) == 4


def test_topology_lane_combinations() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    pairs = {
        (c["host_topology"], c["target_lane"])
        for c in taxonomy["categories"]
        if c.get("host_topology")
    }
    assert pairs == set(c10_ubuntu.TOPOLOGY_LANES)


def test_gpu_runtime_states() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    states = {c["gpu_runtime_state"] for c in taxonomy["categories"] if c.get("gpu_runtime_state")}
    assert states == set(c10_ubuntu.GPU_RUNTIME_STATES)


def test_runtime_menu_bands_match_pilot_policy() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    menu = c10_ubuntu.load_pilot_menu(REPO_ROOT)
    bands = taxonomy["runtime_menu_bands"]
    assert len(bands) == 5
    expected = {tuple(b["ordered_pilot_candidates"]) for b in menu["bands"]}
    actual = {tuple(b["runtime_trial_candidates"]) for b in bands}
    assert actual == expected
    for band in bands:
        assert band["classification"] == "runtime_menu_band_only"
        assert band["model_fit_proven"] is False
        assert band["runtime_trial_required"] is True
        assert band["source_script_path"] == c10_ubuntu.UBUNTU_SOURCE_SCRIPT


def test_capacity_fields_remain_null_not_zero_or_empty() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    for record in taxonomy["categories"]:
        for field in c10_ubuntu.CAPACITY_FIELDS:
            value = record.get(field)
            assert value not in (0, "", "0"), f"{record['id']}.{field} must not use placeholder"


def test_provider_never_set_on_categories() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    for record in taxonomy["categories"]:
        assert record.get("provider") is None
        notes = record.get("notes", "").lower()
        assert "provider remains null" in notes or record.get("host_topology") != "virtual-machine"


def test_lspci_alone_does_not_mark_cuda_ready() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    for record in taxonomy["categories"]:
        if record.get("gpu_runtime_state") == "nvidia-cuda-ready":
            commands = " ".join(record["runtime_evidence_commands"]).lower()
            assert "nvidia-smi" in commands
        if record.get("gpu_runtime_state") == "gpu-present-not-cuda-ready":
            commands = " ".join(record["runtime_evidence_commands"]).lower()
            assert "nvidia-smi" in commands
            assert "lspci" in commands


def test_lane_projection_covers_both_ubuntu_lanes() -> None:
    projection = json.loads(
        (REPO_ROOT / "profiles/provider-compatibility/ubuntu/lane-runtime-contract-projection.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(projection["lanes"]) == {"ubuntu/cpu", "ubuntu/cuda"}
    for lane, entry in projection["lanes"].items():
        assert entry["model_fit_proven"] is False
        assert entry["runtime_trial_required"] is True
        assert entry["provider"] is None
        assert len(entry["topology_category_ids"]) == 3
        assert len(entry["gpu_state_category_ids"]) == 4
        assert len(entry["runtime_menu_band_ids"]) == 5


def test_stable_category_ids() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    ids = {c["id"] for c in taxonomy["categories"]}
    expected_topology = {
        "ubuntu-topology-bare-metal-cpu",
        "ubuntu-topology-bare-metal-cuda",
        "ubuntu-topology-virtual-machine-cpu",
        "ubuntu-topology-virtual-machine-cuda",
        "ubuntu-topology-unknown-cpu",
        "ubuntu-topology-unknown-cuda",
    }
    expected_gpu = {
        "ubuntu-gpu-state-nvidia-cuda-ready",
        "ubuntu-gpu-state-gpu-present-not-cuda-ready",
        "ubuntu-gpu-state-no-supported-gpu-detected",
        "ubuntu-gpu-state-gpu-state-unknown",
    }
    assert expected_topology | expected_gpu == ids


def test_runtime_menu_band_ids() -> None:
    taxonomy = c10_ubuntu.load_taxonomy(REPO_ROOT)
    band_ids = {b["ram_band_id"] for b in taxonomy["runtime_menu_bands"]}
    assert band_ids == {
        "ubuntu-ram-band-under-4gib",
        "ubuntu-ram-band-4-to-8gib",
        "ubuntu-ram-band-8-to-12gib",
        "ubuntu-ram-band-12-to-24gib",
        "ubuntu-ram-band-24gib-plus",
    }


def test_profiles_index_csv_unchanged() -> None:
    with (REPO_ROOT / "profiles/index.csv").open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_ubuntu_validator_has_no_errors() -> None:
    errors = c10_ubuntu.validate_ubuntu_sources(REPO_ROOT)
    assert errors == []


def test_observation_contract_forbids_provider_inference() -> None:
    contract = json.loads(
        (REPO_ROOT / "profiles/provider-compatibility/ubuntu/runtime-observation-contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["provider_inference_forbidden"] is True
    assert contract["lspci_cuda_ready_forbidden"] is True
    assert contract["per_device_gpu_evidence_required"] is True

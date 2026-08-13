from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_LIGHTSAIL_PATH = REPO_ROOT / "scripts" / "c10_lightsail_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_lightsail_compatibility", _C10_LIGHTSAIL_PATH)
assert _SPEC and _SPEC.loader
c10_lightsail = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_lightsail
_SPEC.loader.exec_module(c10_lightsail)


def test_lightsail_plan_inventory() -> None:
    cpu_plans, gpu_plans = c10_lightsail.load_lightsail_plans(REPO_ROOT)
    assert len(cpu_plans) == 11
    assert len(gpu_plans) == 3
    keys = {(p["provider"], p["product_line"], p["provider_plan_id"]) for p in cpu_plans + gpu_plans}
    assert len(keys) == 14


def test_plan_to_band_mapping_exact() -> None:
    menu = c10_lightsail.load_pilot_menu(REPO_ROOT)
    expected = {
        "lightsail-linux-gp-nano-0.5gb-ipv4": "fallback-under-4gb",
        "lightsail-linux-gp-micro-1gb-ipv4": "fallback-under-4gb",
        "lightsail-linux-gp-small-2gb-ipv4": "fallback-under-4gb",
        "lightsail-linux-gp-medium-4gb-ipv4": "pilot-4gb",
        "lightsail-linux-gp-large-8gb-ipv4": "pilot-8gb",
        "lightsail-linux-gp-xlarge-16gb-ipv4": "pilot-12gb",
        "lightsail-linux-gp-2xlarge-32gb-ipv4": "pilot-24gb-plus",
        "lightsail-linux-gp-4xlarge-64gb-ipv4": "pilot-24gb-plus",
        "lightsail-linux-gp-8xlarge-128gb-ipv4": "pilot-24gb-plus",
        "lightsail-linux-gp-12xlarge-192gb-ipv4": "pilot-24gb-plus",
        "lightsail-linux-gp-16xlarge-256gb-ipv4": "pilot-24gb-plus",
        "lightsail-research-gpu-xl": "pilot-12gb",
        "lightsail-research-gpu-2xl": "pilot-24gb-plus",
        "lightsail-research-gpu-4xl": "pilot-24gb-plus",
    }
    assert menu["plan_to_band"] == expected


def test_sub_4gb_plans_never_capacity_candidate() -> None:
    rows = c10_lightsail.load_csv_rows(REPO_ROOT / "profiles/provider-compatibility/aws-lightsail-cpu.csv")
    sub_4gb = {
        "lightsail-linux-gp-nano-0.5gb-ipv4",
        "lightsail-linux-gp-micro-1gb-ipv4",
        "lightsail-linux-gp-small-2gb-ipv4",
    }
    for row in rows:
        if row["provider_plan_id"] in sub_4gb:
            assert row["compatibility_status"] != "capacity-candidate"
            assert row["runtime_model_test_required"] == "true"


def test_gpu_plans_keep_unknown_vram() -> None:
    _, gpu_plans = c10_lightsail.load_lightsail_plans(REPO_ROOT)
    for plan in gpu_plans:
        assert plan["gpu_model"] is None
        assert plan["gpu_vram_gb"] is None
    rows = c10_lightsail.load_csv_rows(REPO_ROOT / "profiles/provider-compatibility/aws-lightsail-gpu.csv")
    assert rows
    assert all(row["gpu_vram_gate"] == "unknown" for row in rows)
    assert all(row["gpu_model"] == "" for row in rows)
    assert all(row["gpu_vram_gb"] == "" for row in rows)


def test_pilot_policy_disk_thresholds_only_for_qwen3_tags() -> None:
    rows = c10_lightsail.load_csv_rows(REPO_ROOT / "profiles/provider-compatibility/aws-lightsail-cpu.csv")
    pilot_rows = [row for row in rows if row["ollama_ref"] in c10_lightsail.PILOT_OLLAMA_REFS]
    non_pilot_rows = [row for row in rows if row["ollama_ref"] not in c10_lightsail.PILOT_OLLAMA_REFS]
    assert pilot_rows
    assert non_pilot_rows
    assert all(row["model_minimum_ram_gb"] == "" for row in rows)
    assert all(row["model_minimum_vram_gb"] == "" for row in rows)
    assert any(row["model_minimum_disk_free_gb"] != "" for row in pilot_rows)
    assert all(row["model_minimum_disk_free_gb"] == "" for row in non_pilot_rows)


def test_compatibility_row_counts() -> None:
    report = json.loads(
        (REPO_ROOT / "data/generated/aws-lightsail-capability-report.json").read_text(encoding="utf-8")
    )
    model_pages = c10_lightsail.load_model_pages(REPO_ROOT)
    size_count = sum(len(page["sizes"]) for page in model_pages.values())
    assert report["compatibility_row_counts"]["cloud/aws-lightsail/cpu"] == size_count * 11
    assert report["compatibility_row_counts"]["cloud/aws-lightsail/gpu"] == size_count * 3


LEGACY_C5_INDEX = REPO_ROOT / "profiles" / "legacy" / "c5-root-export" / "index.csv"


def test_profiles_index_csv_unchanged() -> None:
    with LEGACY_C5_INDEX.open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_lightsail_validator_has_no_errors() -> None:
    errors = c10_lightsail.validate_lightsail_sources(REPO_ROOT)
    assert errors == []

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_DO_PATH = REPO_ROOT / "scripts" / "c10_digitalocean_compatibility.py"
_SPEC = importlib.util.spec_from_file_location("c10_digitalocean_compatibility", _C10_DO_PATH)
assert _SPEC and _SPEC.loader
c10_do = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_do
_SPEC.loader.exec_module(c10_do)


def test_digitalocean_plan_inventory() -> None:
    catalog = c10_do.load_catalog(REPO_ROOT)
    cpu_plans = [p for p in catalog["plans"] if p["service_class"] == "cpu"]
    gpu_plans = [p for p in catalog["plans"] if p["service_class"] == "gpu"]
    assert len(cpu_plans) == 24
    assert len(gpu_plans) == 9
    assert catalog["plan_counts"]["total"] == 33


def test_selected_cpu_slugs_by_family() -> None:
    catalog = c10_do.load_catalog(REPO_ROOT)
    expected = {
        "basic": [
            "s-1vcpu-1gb",
            "s-1vcpu-2gb",
            "s-2vcpu-2gb",
            "s-4vcpu-8gb",
            "s-8vcpu-16gb",
            "s-8vcpu-32gb",
        ],
        "general-purpose": [
            "g-2vcpu-8gb",
            "g-4vcpu-16gb",
            "g-8vcpu-32gb",
            "g-16vcpu-64gb",
            "g-32vcpu-128gb",
            "g-40vcpu-160gb",
        ],
        "cpu-optimized": [
            "c-2vcpu-4gb",
            "c-4vcpu-8gb",
            "c-8vcpu-16gb",
            "c-16vcpu-32gb",
            "c-32vcpu-64gb",
            "c-48vcpu-96gb",
        ],
        "memory-optimized": [
            "m-2vcpu-16gb",
            "m-4vcpu-32gb",
            "m-8vcpu-64gb",
            "m-16vcpu-128gb",
            "m-24vcpu-192gb",
            "m-32vcpu-256gb",
        ],
    }
    assert catalog["selected_cpu_slugs_by_family"] == expected


def test_required_gpu_slugs_present() -> None:
    catalog = c10_do.load_catalog(REPO_ROOT)
    gpu_slugs = {p["provider_size_slug"] for p in catalog["plans"] if p["service_class"] == "gpu"}
    assert gpu_slugs == c10_do.REQUIRED_GPU_SLUGS


def test_gpu_memory_separate_from_system_ram() -> None:
    catalog = c10_do.load_catalog(REPO_ROOT)
    for plan in catalog["plans"]:
        if plan["service_class"] != "gpu":
            continue
        assert plan["gpu_memory_gib"] != plan["memory_gib"]
        assert plan["runtime_verification_required"] is True


def test_projection_classification_fields() -> None:
    rows = c10_do.load_csv_rows(REPO_ROOT / "profiles/provider-compatibility/digitalocean/cpu-plan-compatibility.csv")
    assert rows
    for row in rows:
        assert row["classification"] == "runtime_menu_band_only"
        assert row["model_fit_proven"] == "false"
        assert row["runtime_trial_required"] == "true"


def test_compatibility_row_counts() -> None:
    report = json.loads(
        (REPO_ROOT / "data/generated/digitalocean-capability-report.json").read_text(encoding="utf-8")
    )
    model_pages = c10_do.load_model_pages(REPO_ROOT)
    size_count = sum(len(page["sizes"]) for page in model_pages.values())
    assert report["compatibility_row_counts"]["cpu"] == size_count * 24
    assert report["compatibility_row_counts"]["gpu"] == size_count * 9


def test_profiles_index_csv_unchanged() -> None:
    with (REPO_ROOT / "profiles/index.csv").open(encoding="utf-8", newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    assert row_count == 2878


def test_digitalocean_validator_has_no_errors() -> None:
    errors = c10_do.validate_digitalocean_sources(REPO_ROOT)
    assert errors == []

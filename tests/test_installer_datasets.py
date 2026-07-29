from __future__ import annotations

import json
import sys
from pathlib import Path

from eight_ball.config import load_json
from eight_ball.export.installer_datasets import (
    P1_DIR,
    P2_DIR,
    P3_DIR,
    build_model_selection_index,
    build_p2_indexes,
    export_p3_catalog,
)
from eight_ball.paths import NORMALIZED_DIR

P2_TESTS_DIR = P2_DIR / "tests"


def _p1_dataset_paths() -> list[Path]:
    catalog = load_json(P1_DIR / "data" / "catalog.json")
    return [P1_DIR / "data" / entry["path"] for entry in catalog["datasets"]]


def test_p1_catalog_lists_existing_datasets():
    paths = _p1_dataset_paths()
    assert paths
    for path in paths:
        assert path.exists(), f"missing P1 dataset {path}"
        payload = load_json(path)
        assert isinstance(payload, list) and payload


def test_p1_provider_plans_have_positive_specs():
    for name in ("DO/droplets.json", "LS/lightsail-linux-ipv4.json"):
        for plan in load_json(P1_DIR / "data" / name):
            assert plan["ram_gb"] > 0
            assert plan["vcpu"] > 0
            assert plan["disk_gb"] > 0


def test_p1_overhead_reserves_cover_trial_components():
    components = {
        item["component"]
        for item in load_json(P1_DIR / "data" / "NC" / "overhead-reserves.json")
        if item.get("required")
    }
    assert "Ubuntu operating system" in components
    assert "Ollama service" in components


def test_p2_dataset_suite_passes():
    build_p2_indexes()
    sys.path.insert(0, str(P2_TESTS_DIR))
    try:
        import test_p2_datasets as suite

        for name in sorted(dir(suite)):
            if name.startswith("test_"):
                getattr(suite, name)()
    finally:
        sys.path.remove(str(P2_TESTS_DIR))


def test_p2_indexes_match_datasets():
    summary = build_p2_indexes()
    plans = load_json(P2_DIR / "indexes" / "plans.json")
    assert summary["total_plan_count"] == len(plans)
    assert summary["digitalocean_plan_count"] > 0
    assert summary["lightsail_bundle_count"] > 0
    providers = {item["provider_id"] for item in load_json(P2_DIR / "indexes" / "providers.json")}
    assert providers == {"digitalocean", "lightsail", "nocloudgpt"}


def test_model_selection_only_contains_fitting_local_defaults():
    selection = build_model_selection_index()
    assert selection["confidence"] == "estimated"
    profiles = selection["profiles"]
    assert profiles

    for profile_id, profile in profiles.items():
        budget = profile["model_ram_budget_gb"]
        for candidate in profile["candidates"]:
            assert candidate["availability"] in {"local", "both"}, profile_id
            assert candidate["download_size_bytes"] is not None
            assert candidate["confidence"] == "estimated"
            required = candidate["estimated_recommended_system_ram_gb"]
            assert required is not None and required <= budget
            identifier = candidate["ollama_identifier"]
            assert candidate["pull_command"] == f"ollama pull {identifier}"
            assert candidate["run_command"] == f"ollama run {identifier}"


def test_model_selection_orders_largest_first_and_caps():
    selection = build_model_selection_index()
    cap = selection["max_candidates_per_profile"]
    for profile in selection["profiles"].values():
        sizes = [c["download_size_bytes"] for c in profile["candidates"]]
        assert sizes == sorted(sizes, reverse=True)
        assert len(sizes) <= cap


def test_small_profile_budget_excludes_huge_models():
    selection = build_model_selection_index()
    small = selection["profiles"]["cpu-small"]
    for candidate in small["candidates"]:
        assert candidate["estimated_recommended_system_ram_gb"] <= small["model_ram_budget_gb"]
        assert candidate["download_size_bytes"] < 8_000_000_000


def test_p3_export_provenance_matches_catalog():
    provenance = export_p3_catalog()
    assert provenance["source_repository"] == "terminal-glass/8-ball"
    assert provenance["policy"]["metadata_only"] is True
    assert provenance["policy"]["model_payloads_included"] is False
    assert provenance["policy"]["installer_scripts_included"] is False

    counts = provenance["counts"]
    assert counts["families"] == len(load_json(NORMALIZED_DIR / "families.json"))
    assert counts["tags"] == len(load_json(NORMALIZED_DIR / "tags.json"))

    for name, meta in provenance["source_files"].items():
        assert (Path(meta["path"])).as_posix().endswith(name)

    selection_path = P3_DIR / "indexes" / "model-selection.json"
    assert selection_path.exists()
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    assert selection["catalog_version"] == provenance["catalog_version"]


def test_p3_export_contains_no_scripts():
    for path in P3_DIR.rglob("*"):
        assert path.suffix not in {".sh", ".bash"}, path

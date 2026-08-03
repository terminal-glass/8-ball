from __future__ import annotations

import pytest

from eight_ball.manifest_resolve import (
    format_sizing_log_lines,
    get_manifest_deployment,
    iter_manifest_fallback_deployments,
    load_install_manifest,
    resolve_manifest_selection,
    resolve_model_id,
    sizing_log_record,
)
from eight_ball.paths import GENERATED_INSTALL_MANIFEST_PATH


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not GENERATED_INSTALL_MANIFEST_PATH.is_file():
        pytest.skip("Committed install manifest missing")
    return load_install_manifest()


def test_resolve_qwen3_slug_deployment_type_3(manifest: dict) -> None:
    selection = resolve_manifest_selection(
        manifest,
        model_ref="qwen3-0-6b",
        deployment_type_id="3",
    )
    assert selection is not None
    assert selection.model_id == "qwen3-0.6b"
    assert selection.model_slug == "qwen3-0-6b"
    assert selection.deployment_type_id == "3"
    assert selection.ollama_identifier == "qwen3:0.6b"
    assert selection.fallback_used is False
    assert selection.fallback_reason is None


def test_resolve_qwen3_by_model_id_and_ollama_identifier(manifest: dict) -> None:
    by_id = resolve_manifest_selection(manifest, model_ref="qwen3-0.6b", deployment_type_id="3")
    by_tag = resolve_manifest_selection(manifest, model_ref="qwen3:0.6b", deployment_type_id="3")
    assert by_id is not None and by_tag is not None
    assert by_id.ollama_identifier == by_tag.ollama_identifier == "qwen3:0.6b"


def test_manifest_entry_lookup_contract(manifest: dict) -> None:
    model_id = resolve_model_id(manifest, "qwen3-0-6b")
    assert model_id == "qwen3-0.6b"
    deployment = manifest["models"][model_id]["deployments"]["3"]
    assert deployment["ollama_identifier"] == "qwen3:0.6b"
    assert deployment["helper_path"].endswith("models/qwen3-0-6b/3/info.json")


def test_get_manifest_deployment_matches_resolve(manifest: dict) -> None:
    deployment = get_manifest_deployment(manifest, "qwen3-0-6b", "3")
    assert deployment is not None
    assert deployment["selected_tag_id"] == "qwen3__0.6b"
    assert deployment["assessment"] == "full_gpu_fit"


def test_sizing_log_includes_required_fields(manifest: dict) -> None:
    selection = resolve_manifest_selection(
        manifest,
        model_ref="qwen3-0-6b",
        deployment_type_id="3",
    )
    assert selection is not None
    record = sizing_log_record(selection)
    for field in (
        "model_id",
        "model_slug",
        "deployment_type_id",
        "ollama_identifier",
        "assessment",
        "installed_storage_bytes_estimated",
        "min_system_ram_gb_estimated",
        "recommended_system_ram_gb_estimated",
        "min_vram_gb_estimated",
        "recommended_vram_gb_estimated",
        "cpu_suitability",
        "gpu_suitability",
        "pull_command",
        "run_command",
    ):
        assert field in record
        assert record[field] is not None or field in {"cpu_suitability", "gpu_suitability", "disk_estimate_gb"}

    lines = format_sizing_log_lines(selection)
    assert any("qwen3:0.6b" in line for line in lines)
    assert any(line.startswith("Installed storage") for line in lines)


def test_fallback_candidates_are_manifest_approved_only() -> None:
    manifest = {
        "schema_version": "c5.install-manifest.v1",
        "deployment_types": {},
        "models": {
            "big-model": {
                "model_id": "big-model",
                "model_slug": "big-model",
                "family_id": "demo",
                "family_slug": "demo",
                "default_tag_id": None,
                "deployments": {
                    "3": {
                        "model_id": "big-model",
                        "model_slug": "big-model",
                        "family_id": "demo",
                        "family_slug": "demo",
                        "deployment_type_id": "3",
                        "selected_tag_id": "big-model__latest",
                        "selected_tag": "latest",
                        "ollama_identifier": "big:latest",
                        "hardware_profile_id": "desktop-standard",
                        "runtime_policy_id": "interactive",
                        "assessment": "insufficient_memory",
                        "installed_storage_bytes_estimated": 50_000_000_000,
                        "min_system_ram_gb_estimated": 64,
                        "recommended_system_ram_gb_estimated": 96,
                        "min_vram_gb_estimated": 0,
                        "recommended_vram_gb_estimated": 0,
                        "cpu_suitability": "not_applicable",
                        "gpu_suitability": "not_applicable",
                        "pull_command": "ollama pull big:latest",
                        "run_command": "ollama run big:latest",
                        "helper_path": "data/generated/pages/models/big-model/3/info.json",
                    }
                },
            },
            "small-model": {
                "model_id": "small-model",
                "model_slug": "small-model",
                "family_id": "demo",
                "family_slug": "demo",
                "default_tag_id": None,
                "deployments": {
                    "3": {
                        "model_id": "small-model",
                        "model_slug": "small-model",
                        "family_id": "demo",
                        "family_slug": "demo",
                        "deployment_type_id": "3",
                        "selected_tag_id": "small-model__latest",
                        "selected_tag": "latest",
                        "ollama_identifier": "small:latest",
                        "hardware_profile_id": "cpu-small",
                        "runtime_policy_id": "interactive",
                        "assessment": "cpu_only_practical",
                        "installed_storage_bytes_estimated": 1_000_000_000,
                        "min_system_ram_gb_estimated": 2,
                        "recommended_system_ram_gb_estimated": 4,
                        "min_vram_gb_estimated": 0,
                        "recommended_vram_gb_estimated": 0,
                        "cpu_suitability": "not_applicable",
                        "gpu_suitability": "not_applicable",
                        "pull_command": "ollama pull small:latest",
                        "run_command": "ollama run small:latest",
                        "helper_path": "data/generated/pages/models/small-model/3/info.json",
                    }
                },
            },
        },
    }

    candidates = list(iter_manifest_fallback_deployments(manifest, "big-model", "3"))
    assert candidates
    assert candidates[0][2] == "model_fallback:big-model->small-model"

    selection = resolve_manifest_selection(manifest, model_ref="big-model", deployment_type_id="3")
    assert selection is not None
    assert selection.model_id == "small-model"
    assert selection.ollama_identifier == "small:latest"
    assert selection.fallback_used is True
    assert selection.fallback_reason == "model_fallback:big-model->small-model"

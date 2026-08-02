from __future__ import annotations

import json
from pathlib import Path

import pytest

from eight_ball.config import load_json, write_json
from eight_ball.generate.profiles import (
    DEPLOYMENT_TYPE_SPECS,
    generate_profile_artifacts,
)


def _write_minimal_projection(root: Path) -> None:
    root.mkdir(parents=True)
    write_json(
        root / "index" / "families.json",
        [
            {
                "id": "llama3",
                "name": "Llama 3",
                "aliases": [],
                "description": "Meta Llama 3",
                "catalog_source_id": "ollama-library",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "source_status": "live",
                "source_exception_explanation": None,
                "model_ids": ["llama3-8b"],
            },
            {
                "id": "kimi-k2.5",
                "name": "kimi-k2.5",
                "aliases": [],
                "description": "Retained stale record",
                "catalog_source_id": None,
                "source_url": "https://ollama.com/library/kimi-k2.5",
                "retrieved_at": "2026-07-16T05:12:39Z",
                "source_status": "stale_source_exception",
                "source_exception_explanation": "Retained stale source exception.",
                "model_ids": ["kimi-k2.5"],
            },
        ],
    )
    write_json(
        root / "index" / "models.json",
        [
            {
                "id": "llama3-8b",
                "family_id": "llama3",
                "ollama_name": "llama3-8b",
                "display_name": "Llama 3 8B",
                "description": "Llama 3 8B",
                "availability": "local",
                "default_tag": "llama3:8b",
                "catalog_source_id": "ollama-library",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "source_status": "live",
                "source_exception_explanation": None,
                "deployment_variants": [
                    {
                        "ollama_identifier": "llama3:8b",
                        "tag": "8b",
                        "parameter_count": 8000000000,
                        "parameter_unit": "8b",
                        "quantization": None,
                        "architecture": None,
                        "context_window_tokens": 8192,
                        "download_size_bytes": 4700000000,
                        "download_size_text": "4.7GB",
                        "availability": "local",
                        "pull_command": "ollama pull llama3:8b",
                        "run_command": "ollama run llama3:8b",
                        "alias_target": None,
                        "source_url": "https://ollama.com/library/llama3/tags",
                        "retrieved_at": "2026-08-01T12:00:00Z",
                    }
                ],
            },
            {
                "id": "kimi-k2.5",
                "family_id": "kimi-k2.5",
                "ollama_name": "kimi-k2.5",
                "display_name": "kimi-k2.5",
                "description": "Retained stale record",
                "availability": "cloud",
                "default_tag": "kimi-k2.5",
                "catalog_source_id": None,
                "source_url": "https://ollama.com/library/kimi-k2.5",
                "retrieved_at": "2026-07-16T05:12:39Z",
                "source_status": "stale_source_exception",
                "source_exception_explanation": "Retained stale source exception.",
                "deployment_variants": [],
            },
        ],
    )
    write_json(
        root / "manifest.json",
        {
            "canonical_catalog_version": "2026.08.01.test",
            "indexes": {
                "families": "index/families.json",
                "models": "index/models.json",
            },
            "counts": {
                "families": 2,
                "models": 2,
                "deployment_variants": 1,
            },
        },
    )


def test_generate_profile_artifacts_from_projection(tmp_path: Path) -> None:
    catalog_dir = tmp_path / "catalog"
    profiles_dir = tmp_path / "profiles"
    _write_minimal_projection(catalog_dir)

    summary = generate_profile_artifacts(catalog_dir=catalog_dir, profiles_dir=profiles_dir)

    assert summary["counts"]["families"] == 2
    assert summary["counts"]["models"] == 2
    assert summary["counts"]["deployment_variants"] == 1
    assert summary["counts"]["source_exception_families"] == 1

    family_meta = load_json(profiles_dir / "01-families" / "kimi-k2.5" / "metadata.json")
    assert family_meta["source_exception"] is True
    assert family_meta["installable"] is False
    assert family_meta["openwebui_docker_family"] is None

    model_meta = load_json(profiles_dir / "02-models" / "llama3" / "llama3-8b" / "metadata.json")
    assert model_meta["installable"] is None
    assert len(model_meta["deployment_variants"]) == 1
    assert "provenance" not in model_meta["deployment_variants"][0]

    for spec in DEPLOYMENT_TYPE_SPECS:
        assert (profiles_dir / "03-deployment-types" / spec["filename"]).exists()

    for filename in (
        "family-model-index.json",
        "deployment-types.json",
        "environment-artifact-index.json",
    ):
        path = profiles_dir / "generated" / filename
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))

    artifact_index = load_json(profiles_dir / "generated" / "environment-artifact-index.json")
    assert artifact_index["steps_completed"] == ["family", "model", "deployment_type"]
    assert artifact_index["steps_deferred"] == ["hard_disk", "ram", "cpu", "gpu"]


def test_generate_profile_artifacts_count_mismatch_raises(tmp_path: Path) -> None:
    catalog_dir = tmp_path / "catalog"
    _write_minimal_projection(catalog_dir)
    manifest = load_json(catalog_dir / "manifest.json")
    manifest["counts"]["families"] = 99
    write_json(catalog_dir / "manifest.json", manifest)

    with pytest.raises(ValueError, match="Family count mismatch"):
        generate_profile_artifacts(catalog_dir=catalog_dir, profiles_dir=tmp_path / "profiles")


def test_generate_profile_artifacts_uses_committed_p4_catalog() -> None:
    summary = generate_profile_artifacts()
    assert summary["counts"]["families"] == 234
    assert summary["counts"]["models"] == 437
    assert summary["counts"]["deployment_variants"] == 7271
    assert summary["counts"]["source_exception_families"] == 2

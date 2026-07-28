from __future__ import annotations

import pytest

from eight_ball.generate.indexes import build_indexes
from eight_ball.validate.catalog import ValidationError, validate_catalog


def _catalog_with_two_models_in_one_family() -> dict:
    """Synthetic catalog where one family has two models (future multi-model case)."""
    return {
        "publishers": [
            {
                "id": "ollama-library",
                "display_name": "Ollama Library",
                "aliases": ["ollama"],
                "official_url": "https://ollama.com/library",
            }
        ],
        "families": [
            {
                "id": "llama3",
                "publisher_id": "ollama-library",
                "name": "Llama 3",
                "aliases": [],
                "description": "Meta Llama 3",
                "primary_capabilities": {"chat": "true"},
                "ollama_url": "https://ollama.com/library/llama3",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-07-28T00:00:00Z",
            }
        ],
        "models": [
            {
                "id": "llama3-8b",
                "ollama_name": "llama3-8b",
                "display_name": "Llama 3 8B",
                "publisher_id": "ollama-library",
                "family_id": "llama3",
                "description": "8B parameter model",
                "availability": "local",
                "capabilities": {"chat": "true"},
                "default_tag": "llama3:8b",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-07-28T00:00:00Z",
                "validation_status": "needs_review",
            },
            {
                "id": "llama3-70b",
                "ollama_name": "llama3-70b",
                "display_name": "Llama 3 70B",
                "publisher_id": "ollama-library",
                "family_id": "llama3",
                "description": "70B parameter model",
                "availability": "local",
                "capabilities": {"chat": "true"},
                "default_tag": "llama3:70b",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-07-28T00:00:00Z",
                "validation_status": "needs_review",
            },
        ],
        "tags": [
            {
                "id": "llama3__8b",
                "ollama_identifier": "llama3:8b",
                "model_id": "llama3-8b",
                "tag": "8b",
                "parameter_count": 8_000_000_000,
                "parameter_unit": "8b",
                "quantization": None,
                "architecture": None,
                "context_window_tokens": 8192,
                "download_size_bytes": 4_700_000_000,
                "download_size_text": "4.7GB",
                "installed_storage_bytes_estimated": None,
                "availability": "local",
                "pull_command": "ollama pull llama3:8b",
                "run_command": "ollama run llama3:8b",
                "alias_target": None,
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-07-28T00:00:00Z",
                "provenance": {
                    "download_size_bytes": {
                        "value": 4_700_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/llama3",
                        "retrieved_at": "2026-07-28T00:00:00Z",
                    },
                    "parameter_count": {
                        "value": 8_000_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/llama3",
                        "retrieved_at": "2026-07-28T00:00:00Z",
                    },
                },
            },
            {
                "id": "llama3__70b",
                "ollama_identifier": "llama3:70b",
                "model_id": "llama3-70b",
                "tag": "70b",
                "parameter_count": 70_000_000_000,
                "parameter_unit": "70b",
                "quantization": None,
                "architecture": None,
                "context_window_tokens": 8192,
                "download_size_bytes": 40_000_000_000,
                "download_size_text": "40GB",
                "installed_storage_bytes_estimated": None,
                "availability": "local",
                "pull_command": "ollama pull llama3:70b",
                "run_command": "ollama run llama3:70b",
                "alias_target": None,
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-07-28T00:00:00Z",
                "provenance": {
                    "download_size_bytes": {
                        "value": 40_000_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/llama3",
                        "retrieved_at": "2026-07-28T00:00:00Z",
                    },
                    "parameter_count": {
                        "value": 70_000_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/llama3",
                        "retrieved_at": "2026-07-28T00:00:00Z",
                    },
                },
            },
        ],
    }


def test_by_family_index_uses_family_id_not_model_id(tmp_path, monkeypatch):
    from eight_ball.config import load_json

    catalog = _catalog_with_two_models_in_one_family()
    indexes_dir = tmp_path / "indexes"
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    monkeypatch.setattr("eight_ball.generate.indexes.INDEXES_DIR", indexes_dir)
    monkeypatch.setattr("eight_ball.validate.catalog.INDEXES_DIR", indexes_dir)
    monkeypatch.setattr("eight_ball.validate.catalog.GENERATED_DIR", generated_dir)

    build_indexes(catalog)
    by_family = load_json(indexes_dir / "by-family.json")
    by_model = load_json(indexes_dir / "by-model.json")

    assert set(by_family.keys()) == {"llama3"}
    assert set(by_model.keys()) == {"llama3-8b", "llama3-70b"}
    assert sorted(by_family["llama3"]) == ["llama3:70b", "llama3:8b"]
    assert sorted(by_model["llama3-8b"]) == ["llama3:8b"]
    assert sorted(by_model["llama3-70b"]) == ["llama3:70b"]

    report = validate_catalog(
        catalog,
        include_artifacts=True,
        generated_dir=generated_dir,
        indexes_dir=indexes_dir,
    )
    assert report["indexes"]["present"] is True
    assert report["indexes"]["families_indexed"] == 1
    assert report["indexes"]["models_indexed"] == 2


def test_by_family_index_fails_when_keyed_by_model_id(tmp_path, monkeypatch):
    from eight_ball.config import write_json

    catalog = _catalog_with_two_models_in_one_family()
    indexes_dir = tmp_path / "indexes"
    indexes_dir.mkdir()
    write_json(
        indexes_dir / "by-family.json",
        {"llama3-8b": ["llama3:8b"], "llama3-70b": ["llama3:70b"]},
    )
    write_json(
        indexes_dir / "by-model.json",
        {"llama3-8b": ["llama3:8b"], "llama3-70b": ["llama3:70b"]},
    )
    write_json(indexes_dir / "local-tags.json", ["llama3:70b", "llama3:8b"])
    write_json(indexes_dir / "cloud-tags.json", [])
    monkeypatch.setattr("eight_ball.validate.catalog.INDEXES_DIR", indexes_dir)
    monkeypatch.setattr("eight_ball.validate.catalog.GENERATED_DIR", tmp_path / "generated")

    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog, include_artifacts=True, indexes_dir=indexes_dir)
    assert any("by-family inconsistent for family llama3" in error for error in exc.value.errors)

from __future__ import annotations

import copy

import pytest

from eight_ball.config import load_json, write_json
from eight_ball.contributions.validate import validate_contribution_records
from eight_ball.generate.component_display import render_component_inventory
from eight_ball.generate.indexes import build_indexes
from eight_ball.history.changes import record_promotion
from eight_ball.report.unresolved import summarize_unresolved
from eight_ball.validate.catalog import ValidationError, validate_catalog


def _minimal_catalog() -> dict:
    return {
        "publishers": [
            {
                "id": "ollama-library",
                "display_name": "Ollama Library",
                "aliases": [],
                "official_url": "https://ollama.com/library",
            }
        ],
        "families": [
            {
                "id": "tiny",
                "publisher_id": "ollama-library",
                "name": "Tiny",
                "aliases": [],
                "description": "Tiny family",
                "primary_capabilities": {"chat": "true"},
                "ollama_url": "https://ollama.com/library/tiny",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
            }
        ],
        "models": [
            {
                "id": "tiny-local",
                "ollama_name": "tiny-local",
                "display_name": "Tiny Local",
                "publisher_id": "ollama-library",
                "family_id": "tiny",
                "description": "Local model",
                "availability": "local",
                "capabilities": {"chat": "true"},
                "default_tag": "tiny:latest",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
                "validation_status": "valid",
            }
        ],
        "tags": [
            {
                "id": "tiny__latest",
                "ollama_identifier": "tiny:latest",
                "model_id": "tiny-local",
                "tag": "latest",
                "parameter_count": 1_000_000_000,
                "parameter_unit": "1b",
                "quantization": None,
                "architecture": None,
                "context_window_tokens": None,
                "download_size_bytes": 700_000_000,
                "download_size_text": "700MB",
                "installed_storage_bytes_estimated": None,
                "availability": "local",
                "capabilities": {"chat": "true", "tool_use": "unknown"},
                "pull_command": "ollama pull tiny:latest",
                "run_command": "ollama run tiny:latest",
                "alias_target": None,
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
                "provenance": {
                    "download_size_bytes": {
                        "value": 700_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/tiny",
                        "retrieved_at": "2026-08-01T00:00:00Z",
                    },
                    "parameter_count": {
                        "value": 1_000_000_000,
                        "confidence": "observed",
                        "source_url": "https://ollama.com/library/tiny",
                        "retrieved_at": "2026-08-01T00:00:00Z",
                    },
                },
            },
            {
                "id": "tiny__cloud",
                "ollama_identifier": "tiny:cloud",
                "model_id": "tiny-local",
                "tag": "cloud",
                "parameter_count": None,
                "parameter_unit": None,
                "quantization": None,
                "architecture": None,
                "context_window_tokens": None,
                "download_size_bytes": None,
                "download_size_text": None,
                "installed_storage_bytes_estimated": None,
                "availability": "cloud_only",
                "capabilities": {"cloud": "true"},
                "pull_command": "ollama pull tiny:cloud",
                "run_command": "ollama run tiny:cloud",
                "alias_target": None,
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
                "provenance": {
                    "download_size_bytes": {
                        "value": None,
                        "confidence": "unknown",
                        "source_url": "https://ollama.com/library/tiny",
                        "retrieved_at": "2026-08-01T00:00:00Z",
                    },
                    "parameter_count": {
                        "value": None,
                        "confidence": "unknown",
                        "source_url": "https://ollama.com/library/tiny",
                        "retrieved_at": "2026-08-01T00:00:00Z",
                    },
                },
            },
        ],
    }


def test_invalid_tag_is_rejected():
    catalog = _minimal_catalog()
    catalog["tags"][0]["pull_command"] = "ollama pull other:tag"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog, include_artifacts=False)
    assert any("pull_command does not match exact tag" in error for error in exc.value.errors)


def test_unresolved_summary_keeps_nulls_and_decimal_units():
    catalog = _minimal_catalog()
    summary = summarize_unresolved(catalog, catalog_version="2026.08.01")
    assert summary["size_unit_policy"] == "decimal"
    assert summary["catalog_version"] == "2026.08.01"
    assert summary["counts"]["tag.quantization"] == 2
    assert summary["counts"]["tag.parameter_count"] == 1
    assert "not RAM or VRAM" in summary["si_note"]


def test_local_download_index_excludes_cloud_only(tmp_path):
    catalog = _minimal_catalog()
    summary = build_indexes(catalog, indexes_dir=tmp_path)
    local_download = load_json(tmp_path / "local-download-tags.json")
    cloud_only = load_json(tmp_path / "cloud-only-tags.json")
    assert local_download == ["tiny:latest"]
    assert cloud_only == ["tiny:cloud"]
    assert "tiny:cloud" not in local_download
    assert summary["cloud_only_tags"] == 1
    report = validate_catalog(
        catalog,
        include_artifacts=True,
        generated_dir=tmp_path / "generated",
        indexes_dir=tmp_path,
    )
    assert report["valid"] is True


def test_component_display_matches_source():
    from eight_ball.generate.component_display import load_component_inventory

    document = load_component_inventory()
    text = render_component_inventory(document)
    assert "Do not edit by hand." in text
    assert "Independent AI" in text
    assert "| Model catalog | catalog | required | local |" in text
    assert "unchosen" in text


def test_committed_contribution_records_match_catalog():
    errors = validate_contribution_records()
    assert errors == []


def test_contribution_validator_rejects_duplicate_component(tmp_path):
    from eight_ball.config import load_yaml
    from eight_ball.paths import CONFIG_DIR

    document = load_yaml(CONFIG_DIR / "components.yaml")
    document = copy.deepcopy(document)
    document["components"].append(copy.deepcopy(document["components"][0]))
    path = tmp_path / "components.yaml"
    path.write_text("schema: placeholder\n", encoding="utf-8")
    import yaml

    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    errors = validate_contribution_records(
        components_path=path,
        check_generated=False,
    )
    assert any("duplicate id catalog" in error for error in errors)


def test_promotion_preserves_removed_tags(tmp_path):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    history = tmp_path / "history"
    previous.mkdir()
    current.mkdir()
    write_json(
        previous / "tags.json",
        [{"ollama_identifier": "old:latest"}, {"ollama_identifier": "kept:latest"}],
    )
    write_json(previous / "families.json", [{"id": "old"}, {"id": "kept"}])
    write_json(previous / "models.json", [{"id": "old"}, {"id": "kept"}])
    write_json(previous / "catalog-meta.json", {"catalog_version": "2026.08.01"})
    write_json(current / "tags.json", [{"ollama_identifier": "kept:latest"}, {"ollama_identifier": "new:latest"}])
    write_json(current / "families.json", [{"id": "kept"}, {"id": "new"}])
    write_json(current / "models.json", [{"id": "kept"}, {"id": "new"}])
    write_json(current / "catalog-meta.json", {"catalog_version": "2026.08.02"})

    record = record_promotion(history_dir=history, archive_path=previous, new_dir=current)
    assert record["removed"] == ["old:latest"]
    assert record["added"] == ["new:latest"]
    stored = load_json(history / "catalog-changes.json")
    assert stored["changes"][0]["removed"] == ["old:latest"]

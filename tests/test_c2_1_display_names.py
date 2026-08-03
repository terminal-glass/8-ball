from __future__ import annotations

from eight_ball.config import load_json, write_json
from eight_ball.paths import P4_PUBLIC_CATALOG_DIR
from eight_ball.publish.display_names import (
    is_invalid_display_name,
    resolve_family_display_name,
    resolve_model_display_name,
)
from eight_ball.publish.public_catalog import build_public_catalog


def test_invalid_section_heading_names_are_rejected() -> None:
    for invalid in (
        "References",
        "Documentation",
        "Models",
        "Tags",
        "Library",
        "Cancel",
        "   ",
        "",
    ):
        assert is_invalid_display_name(invalid)


def test_valid_source_names_are_preserved() -> None:
    family = {"id": "llama3", "name": "Llama 3"}
    model = {
        "id": "llama3-8b",
        "family_id": "llama3",
        "display_name": "Llama 3 8B",
        "ollama_name": "llama3-8b",
    }
    assert resolve_family_display_name(family) == "Llama 3"
    assert resolve_model_display_name(model, family_display_name="Llama 3") == "Llama 3 8B"


def test_canonical_id_fallback_is_deterministic() -> None:
    family = {"id": "aya", "name": "References"}
    model = {
        "id": "aya-8b",
        "family_id": "aya",
        "display_name": "References",
        "ollama_name": "aya-8b",
    }
    assert resolve_family_display_name(family) == "aya"
    assert resolve_model_display_name(model, family_display_name="aya") == "aya-8b"


def test_public_catalog_corrects_contaminated_display_names(tmp_path) -> None:
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    write_json(
        normalized / "publishers.json",
        [{"id": "unknown", "display_name": "Unknown", "aliases": [], "official_url": None}],
    )
    write_json(
        normalized / "families.json",
        [
            {
                "id": "llama3",
                "catalog_source_id": "ollama-library",
                "publisher_id": "unknown",
                "name": "Llama 3",
                "aliases": [],
                "description": "Meta Llama 3",
                "primary_capabilities": {"text_generation": "true"},
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "review_reasons": [],
            },
            {
                "id": "aya",
                "catalog_source_id": "ollama-library",
                "publisher_id": "unknown",
                "name": "References",
                "aliases": [],
                "description": "Aya 23",
                "primary_capabilities": {"text_generation": "true"},
                "source_url": "https://ollama.com/library/aya",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "review_reasons": [],
            },
        ],
    )
    write_json(
        normalized / "models.json",
        [
            {
                "id": "llama3-8b",
                "ollama_name": "llama3-8b",
                "display_name": "Llama 3 8B",
                "publisher_id": "unknown",
                "family_id": "llama3",
                "catalog_source_id": "ollama-library",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "default_tag": "llama3:8b",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "validation_status": "valid",
                "review_reasons": [],
            },
            {
                "id": "aya-8b",
                "ollama_name": "aya-8b",
                "display_name": "References",
                "publisher_id": "unknown",
                "family_id": "aya",
                "catalog_source_id": "ollama-library",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "default_tag": "aya:8b",
                "source_url": "https://ollama.com/library/aya",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "validation_status": "needs_review",
                "review_reasons": [],
            },
        ],
    )
    write_json(
        normalized / "tags.json",
        [
            {
                "model_id": "llama3-8b",
                "family_id": "llama3",
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
                "capabilities": {"text_generation": "true"},
                "pull_command": "ollama pull llama3:8b",
                "run_command": "ollama run llama3:8b",
                "alias_target": None,
                "source_url": "https://ollama.com/library/llama3/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "provenance": {},
            },
            {
                "model_id": "aya-8b",
                "family_id": "aya",
                "ollama_identifier": "aya:8b",
                "tag": "8b",
                "parameter_count": 8000000000,
                "parameter_unit": "8b",
                "quantization": None,
                "architecture": None,
                "context_window_tokens": 8192,
                "download_size_bytes": 4700000000,
                "download_size_text": "4.7GB",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "pull_command": "ollama pull aya:8b",
                "run_command": "ollama run aya:8b",
                "alias_target": None,
                "source_url": "https://ollama.com/library/aya/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "provenance": {},
            },
        ],
    )
    write_json(normalized / "capabilities.json", [])
    write_json(
        normalized / "catalog-meta.json",
        {
            "catalog_version": "2026.08.01.test",
            "collection_date": "2026-08-01",
            "collection_id": "test",
            "collection_manifest": None,
            "catalog_source_id": "ollama-library",
        },
    )

    catalog = build_public_catalog(normalized_dir=normalized)
    families = {item["id"]: item for item in catalog["families"]}
    models = {item["id"]: item for item in catalog["models"]}

    assert catalog["manifest"]["counts"]["families"] == 2
    assert catalog["manifest"]["counts"]["models"] == 2
    assert families["llama3"]["name"] == "Llama 3"
    assert families["aya"]["name"] == "aya"
    assert models["llama3-8b"]["display_name"] == "Llama 3 8B"
    assert models["aya-8b"]["display_name"] == "aya-8b"
    assert "References" not in {families["aya"]["name"], models["aya-8b"]["display_name"]}


def test_committed_public_catalog_has_no_invalid_display_names() -> None:
    families = load_json(P4_PUBLIC_CATALOG_DIR / "index" / "families.json")
    models = load_json(P4_PUBLIC_CATALOG_DIR / "index" / "models.json")

    for family in families:
        assert not is_invalid_display_name(family.get("name"))
    for model in models:
        assert not is_invalid_display_name(model.get("display_name"))

    aya = next(item for item in families if item["id"] == "aya")
    assert aya["name"] == "aya"

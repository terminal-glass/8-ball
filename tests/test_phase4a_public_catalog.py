from __future__ import annotations

import json
from pathlib import Path

from eight_ball.config import load_json, write_json
from eight_ball.publish.public_catalog import (
    PUBLIC_CATALOG_GENERATOR_COMMAND,
    build_public_catalog,
    write_public_catalog,
)


def _write_minimal_canonical(root: Path) -> None:
    root.mkdir(parents=True)
    write_json(
        root / "publishers.json",
        [{"id": "meta", "display_name": "Meta", "aliases": [], "official_url": "https://ai.meta.com/"}],
    )
    write_json(
        root / "families.json",
        [
            {
                "id": "llama3",
                "catalog_source_id": "ollama-library",
                "publisher_id": "meta",
                "name": "Llama 3",
                "aliases": [],
                "description": "Meta Llama 3",
                "primary_capabilities": {"text_generation": "true", "chat": "true"},
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "provenance": {
                    "publisher_id": {
                        "value": "meta",
                        "confidence": "manual",
                        "source_url": "https://ollama.com/library/llama3",
                        "retrieved_at": "2026-08-01T12:00:00Z",
                    }
                },
                "review_reasons": [],
            },
            {
                "id": "kimi-k2.5",
                "catalog_source_id": "ollama-library",
                "publisher_id": "unknown",
                "name": "kimi-k2.5",
                "aliases": [],
                "description": "Retained stale record",
                "primary_capabilities": {"cloud": "true"},
                "source_url": "https://ollama.com/library/kimi-k2.5",
                "retrieved_at": "2026-07-16T05:12:39Z",
                "source_exception_retained": True,
                "review_reasons": ["unknown_publisher"],
            },
        ],
    )
    write_json(
        root / "models.json",
        [
            {
                "id": "llama3-8b",
                "ollama_name": "llama3-8b",
                "display_name": "Llama 3 8B",
                "publisher_id": "meta",
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
                "id": "kimi-k2.5",
                "ollama_name": "kimi-k2.5",
                "display_name": "kimi-k2.5",
                "publisher_id": "unknown",
                "family_id": "kimi-k2.5",
                "catalog_source_id": "ollama-library",
                "availability": "cloud",
                "capabilities": {"cloud": "true"},
                "default_tag": "kimi-k2.5:cloud",
                "source_url": "https://ollama.com/library/kimi-k2.5",
                "retrieved_at": "2026-07-16T05:12:39Z",
                "validation_status": "valid",
                "source_exception_retained": True,
                "review_reasons": ["unknown_publisher"],
            },
        ],
    )
    write_json(
        root / "tags.json",
        [
            {
                "id": "llama3__8b",
                "ollama_identifier": "llama3:8b",
                "model_id": "llama3-8b",
                "tag": "8b",
                "parameter_count": 8_000_000_000,
                "parameter_unit": "8b",
                "quantization": "Q4_0",
                "context_window_tokens": 8192,
                "download_size_bytes": 4_700_000_000,
                "download_size_text": "4.7GB",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "pull_command": "ollama pull llama3:8b",
                "run_command": "ollama run llama3:8b",
                "source_url": "https://ollama.com/library/llama3/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "provenance": {},
            },
            {
                "id": "llama3__latest",
                "ollama_identifier": "llama3:latest",
                "model_id": "llama3-8b",
                "tag": "latest",
                "parameter_count": 8_000_000_000,
                "parameter_unit": "8b",
                "quantization": "Q4_0",
                "context_window_tokens": 8192,
                "download_size_bytes": 4_700_000_000,
                "download_size_text": "4.7GB",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "pull_command": "ollama pull llama3:latest",
                "run_command": "ollama run llama3:latest",
                "alias_target": "llama3:8b",
                "source_url": "https://ollama.com/library/llama3/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
                "provenance": {},
            },
            {
                "id": "kimi-k2.5__cloud",
                "ollama_identifier": "kimi-k2.5:cloud",
                "model_id": "kimi-k2.5",
                "tag": "cloud",
                "parameter_count": None,
                "parameter_unit": None,
                "quantization": None,
                "context_window_tokens": 256000,
                "download_size_bytes": None,
                "download_size_text": None,
                "availability": "cloud_only",
                "capabilities": {"cloud": "true"},
                "pull_command": "ollama pull kimi-k2.5:cloud",
                "run_command": "ollama run kimi-k2.5:cloud",
                "source_url": "https://ollama.com/library/kimi-k2.5:cloud",
                "retrieved_at": "2026-07-16T05:07:45Z",
                "source_exception_retained": True,
                "provenance": {},
            },
        ],
    )
    write_json(root / "capabilities.json", [])
    write_json(
        root / "catalog-meta.json",
        {
            "catalog_version": "2026.08.01",
            "collection_date": "2026-08-01",
            "collection_id": "test-collection",
            "catalog_source_id": "ollama-library",
            "source_exception_families": ["kimi-k2.5"],
        },
    )


def test_public_catalog_is_deterministic_except_timestamp(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    first = build_public_catalog(normalized_dir=normalized)
    second = build_public_catalog(normalized_dir=normalized)
    first["manifest"].pop("generated_at")
    second["manifest"].pop("generated_at")
    assert first == second


def test_public_catalog_does_not_modify_canonical(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in normalized.glob("*.json")
    }
    build_public_catalog(normalized_dir=normalized)
    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in normalized.glob("*.json")
    }
    assert before == after


def test_source_exceptions_are_visible_but_not_indexable(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    catalog = build_public_catalog(normalized_dir=normalized)
    exception_family = next(item for item in catalog["families"] if item["id"] == "kimi-k2.5")
    assert exception_family["source_status"] == "stale_source_exception"
    assert exception_family["page"]["seo_eligible"] is False
    assert exception_family["source_exception_explanation"]
    assert catalog["manifest"]["counts"]["non_indexable_source_exception_families"] == 1


def test_deployment_variants_are_not_seo_pages(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    catalog = build_public_catalog(normalized_dir=normalized)
    model = next(item for item in catalog["models"] if item["id"] == "llama3-8b")
    assert len(model["deployment_variants"]) == 2
    assert all(variant["page"]["seo_eligible"] is False for variant in model["deployment_variants"])
    assert catalog["manifest"]["counts"]["deployment_variant_pages"] == 0


def test_publisher_verification_and_provenance_preserved(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    catalog = build_public_catalog(normalized_dir=normalized)
    llama3 = next(item for item in catalog["families"] if item["id"] == "llama3")
    assert llama3["publisher"]["verification_status"] == "verified"
    assert llama3["publisher"]["provenance"]["confidence"] == "manual"
    kimi = next(item for item in catalog["families"] if item["id"] == "kimi-k2.5")
    assert kimi["publisher"]["verification_status"] == "unknown"


def test_classifications_are_evidence_based(tmp_path):
    normalized = tmp_path / "normalized"
    _write_minimal_canonical(normalized)
    catalog = build_public_catalog(normalized_dir=normalized)
    model = next(item for item in catalog["models"] if item["id"] == "llama3-8b")
    assert model["classifications"]["local_private_suitable"] is True
    assert model["classifications"]["cloud_jet_suitable"] is False
    assert "text_generation" in model["classifications"]["capability_filters"]
    assert model["classifications"]["size_buckets"] == ["medium"]


def test_write_public_catalog_outputs_manifest_and_report(tmp_path):
    normalized = tmp_path / "normalized"
    output = tmp_path / "public"
    reports = tmp_path / "reports"
    _write_minimal_canonical(normalized)
    catalog = build_public_catalog(normalized_dir=normalized)
    paths = write_public_catalog(catalog, output_dir=output, reports_dir=reports)
    assert paths["manifest"].exists()
    manifest = load_json(paths["manifest"])
    assert manifest["generator_command"] == PUBLIC_CATALOG_GENERATOR_COMMAND
    assert json.loads(paths["families"].read_text(encoding="utf-8"))
    assert paths["report"].exists()


def test_full_canonical_projection_counts():
    catalog = build_public_catalog()
    counts = catalog["manifest"]["counts"]
    assert counts["families"] == 234
    assert counts["models"] == 437
    assert counts["deployment_variants"] == 7271
    assert counts["seo_eligible_family_pages"] == 232
    assert counts["seo_eligible_model_pages"] == 435
    assert counts["non_indexable_source_exception_families"] == 2

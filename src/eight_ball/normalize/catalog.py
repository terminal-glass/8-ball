from __future__ import annotations

from typing import Any

from eight_ball.config import capabilities_config, write_json
from eight_ball.normalize.legacy import (
    default_tag_for_variants,
    iter_legacy_family_files,
    load_legacy_family,
    map_capabilities,
    model_availability,
    tag_availability,
)
from eight_ball.normalize.parse import parse_context_length, parse_parameter_label
from eight_ball.paths import LEGACY_FAMILIES_DIR, NORMALIZED_DIR
from eight_ball.provenance import ProvenanceField


def _latest_source_timestamp(record: dict[str, Any], variants: list[dict[str, Any]]) -> str | None:
    timestamps = [record.get("generated_at_utc")]
    timestamps.extend(v.get("verified_at_utc") for v in variants)
    valid = [value for value in timestamps if value]
    return max(valid) if valid else None

DEFAULT_PUBLISHER_ID = "ollama-library"


def build_catalog(
    *,
    families_dir=LEGACY_FAMILIES_DIR,
    sample_only: bool = False,
) -> dict[str, Any]:
    publishers = [
        {
            "id": DEFAULT_PUBLISHER_ID,
            "display_name": "Ollama Library",
            "aliases": ["ollama"],
            "official_url": "https://ollama.com/library",
        }
    ]
    families: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    catalog_version = "unknown"
    latest_timestamp: str | None = None

    for path in iter_legacy_family_files(families_dir, sample_only=sample_only):
        record = load_legacy_family(path)
        catalog_version = record.get("catalog_version", catalog_version)
        variants = record.get("variants", [])
        family_timestamp = _latest_source_timestamp(record, variants)
        if family_timestamp and (latest_timestamp is None or family_timestamp > latest_timestamp):
            latest_timestamp = family_timestamp
        family = record["family"]
        slug = family["slug"]
        variants = record.get("variants", [])
        family_caps = map_capabilities(family.get("capabilities", []))
        families.append(
            {
                "id": slug,
                "publisher_id": DEFAULT_PUBLISHER_ID,
                "name": family.get("display_name", slug),
                "aliases": [],
                "description": family.get("updated_text") or family.get("description"),
                "primary_capabilities": family_caps,
                "ollama_url": family.get("ollama_url"),
                "source_url": family.get("ollama_url"),
                "retrieved_at": record.get("generated_at_utc"),
            }
        )
        model_id = slug
        models.append(
            {
                "id": model_id,
                "ollama_name": slug,
                "display_name": family.get("display_name", slug),
                "publisher_id": DEFAULT_PUBLISHER_ID,
                "family_id": slug,
                "description": family.get("updated_text") or family.get("description"),
                "availability": model_availability(variants),
                "capabilities": family_caps,
                "default_tag": default_tag_for_variants(variants),
                "source_url": family.get("ollama_url"),
                "retrieved_at": record.get("generated_at_utc"),
                "validation_status": "needs_review",
            }
        )
        for variant in variants:
            param_count = variant.get("parameter_count")
            param_label = variant.get("parameter_label")
            if param_count is None and param_label:
                parsed_count, parsed_label = parse_parameter_label(param_label)
                param_count = param_count or parsed_count
                param_label = param_label or parsed_label
            tags.append(
                {
                    "id": variant["exact_tag"].replace(":", "__"),
                    "ollama_identifier": variant["exact_tag"],
                    "model_id": model_id,
                    "tag": variant.get("tag_suffix", ""),
                    "parameter_count": param_count,
                    "parameter_unit": param_label,
                    "quantization": variant.get("quantization"),
                    "architecture": variant.get("architecture_type"),
                    "context_window_tokens": parse_context_length(variant.get("context_length")),
                    "download_size_bytes": variant.get("download_size_bytes"),
                    "download_size_text": variant.get("download_size_text"),
                    "installed_storage_bytes_estimated": None,
                    "availability": tag_availability(variant),
                    "pull_command": variant.get("pull_command"),
                    "run_command": variant.get("run_command"),
                    "alias_target": variant.get("alias_target"),
                    "source_url": variant.get("source_url"),
                    "retrieved_at": variant.get("verified_at_utc"),
                    "provenance": {
                        "download_size_bytes": ProvenanceField.observed(
                            variant.get("download_size_bytes"),
                            source_url=variant.get("source_url"),
                            retrieved_at=variant.get("verified_at_utc"),
                        ).to_dict(),
                        "parameter_count": (
                            ProvenanceField.observed(
                                param_count,
                                source_url=variant.get("source_url"),
                                retrieved_at=variant.get("verified_at_utc"),
                            ).to_dict()
                            if param_count is not None
                            else ProvenanceField.unknown("parameter count not published").to_dict()
                        ),
                    },
                }
            )

    return {
        "catalog_version": catalog_version,
        "generated_at": latest_timestamp,
        "publishers": publishers,
        "families": families,
        "models": models,
        "tags": tags,
        "capabilities": capabilities_config().get("capabilities", []),
    }


def normalize_legacy_catalog(*, sample_only: bool = False, families_dir=LEGACY_FAMILIES_DIR) -> dict[str, Any]:
    catalog = build_catalog(families_dir=families_dir, sample_only=sample_only)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(NORMALIZED_DIR / "publishers.json", catalog["publishers"])
    write_json(NORMALIZED_DIR / "families.json", catalog["families"])
    write_json(NORMALIZED_DIR / "models.json", catalog["models"])
    write_json(NORMALIZED_DIR / "tags.json", catalog["tags"])
    write_json(NORMALIZED_DIR / "capabilities.json", catalog["capabilities"])
    write_json(
        NORMALIZED_DIR / "catalog-meta.json",
        {
            "catalog_version": catalog["catalog_version"],
            "generated_at": catalog["generated_at"],
            "sample_only": sample_only,
        },
    )
    return catalog

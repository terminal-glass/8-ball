from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import NORMALIZED_DIR, P4_PUBLIC_CATALOG_DIR, REPO_ROOT, REPORTS_DIR
from eight_ball.provenance import utc_now_iso
from eight_ball.publish.classification import (
    CAPABILITY_FILTER_KEYS,
    CLOUD_AVAILABILITY,
    LOCAL_AVAILABILITY,
    PROMOTION_RECEIPT_PATH,
    PUBLIC_CATALOG_GENERATOR_COMMAND,
    PUBLIC_CATALOG_GENERATOR_VERSION,
    PUBLIC_CATALOG_SCHEMA_VERSION,
    SIZE_BUCKETS,
    SOURCE_EXCEPTION_EXPLANATION,
)
from eight_ball.publish.display_names import (
    resolve_family_display_name,
    resolve_model_display_name,
)

P4_DIR = P4_PUBLIC_CATALOG_DIR
NORMALIZED_FILES = (
    "publishers.json",
    "families.json",
    "models.json",
    "tags.json",
    "capabilities.json",
    "catalog-meta.json",
)


def _repo_head_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _relative_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_source_exception(record: dict[str, Any]) -> bool:
    return bool(record.get("source_exception_retained"))


def _source_status(record: dict[str, Any]) -> str:
    if _is_source_exception(record):
        return "stale_source_exception"
    return "live"


def _publisher_provenance(record: dict[str, Any]) -> dict[str, Any] | None:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return None
    publisher = provenance.get("publisher_id")
    if not isinstance(publisher, dict):
        return None
    return publisher


def _publisher_verification_status(
    record: dict[str, Any],
    *,
    publisher_id: str,
) -> str:
    if publisher_id == "unknown":
        return "unknown"
    review_reasons = set(record.get("review_reasons") or [])
    if "unknown_publisher" in review_reasons:
        return "unknown"
    if "publisher_mapping_needs_review" in review_reasons:
        return "unverified"
    publisher_provenance = _publisher_provenance(record)
    if publisher_provenance and publisher_provenance.get("confidence") == "manual":
        return "verified"
    if publisher_id != "unknown" and not review_reasons:
        return "verified"
    if publisher_provenance and publisher_provenance.get("confidence") == "derived":
        return "unverified"
    return "unknown"


def _publisher_projection(
    record: dict[str, Any],
    *,
    publishers_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    publisher_id = record.get("publisher_id", "unknown")
    publisher = publishers_by_id.get(publisher_id, {})
    verification_status = _publisher_verification_status(record, publisher_id=publisher_id)
    provenance = _publisher_provenance(record)
    return {
        "id": publisher_id,
        "display_name": publisher.get("display_name", publisher_id),
        "verification_status": verification_status,
        "provenance": provenance,
    }


def _capability_filters(capabilities: dict[str, str] | None) -> list[str]:
    capabilities = capabilities or {}
    return sorted(
        key
        for key in CAPABILITY_FILTER_KEYS
        if capabilities.get(key) == "true"
    )


def _size_bucket(parameter_count: int | None) -> str:
    if parameter_count is None:
        return "unknown"
    for bucket_id, lower, upper in SIZE_BUCKETS:
        if parameter_count < lower:
            continue
        if upper is None or parameter_count <= upper:
            return bucket_id
    return "unknown"


def _classify_tags(tags: list[dict[str, Any]]) -> dict[str, Any]:
    local_private_suitable = False
    cloud_jet_suitable = False
    capability_union: set[str] = set()
    size_buckets: set[str] = set()
    quantizations: set[str] = set()

    for tag in tags:
        availability = tag.get("availability", "unknown")
        if availability in LOCAL_AVAILABILITY and tag.get("download_size_bytes"):
            local_private_suitable = True
        if availability in CLOUD_AVAILABILITY:
            cloud_jet_suitable = True
        capability_union.update(_capability_filters(tag.get("capabilities")))
        size_buckets.add(_size_bucket(tag.get("parameter_count")))
        if tag.get("quantization"):
            quantizations.add(tag["quantization"])

    return {
        "local_private_suitable": local_private_suitable,
        "cloud_jet_suitable": cloud_jet_suitable,
        "capability_filters": sorted(capability_union),
        "size_buckets": sorted(size_buckets),
        "quantizations": sorted(quantizations),
        "unknown_fields": sorted(
            field
            for field, value in {
                "parameter_count": any(tag.get("parameter_count") is None for tag in tags),
                "download_size_bytes": any(
                    tag.get("download_size_bytes") is None
                    and tag.get("availability") not in {"cloud_only", "cloud"}
                    for tag in tags
                ),
                "context_window_tokens": any(
                    tag.get("context_window_tokens") is None for tag in tags
                ),
            }.items()
            if value
        ),
    }


def _deployment_variant(tag: dict[str, Any]) -> dict[str, Any]:
    return {
        "ollama_identifier": tag["ollama_identifier"],
        "tag": tag.get("tag"),
        "parameter_count": tag.get("parameter_count"),
        "parameter_unit": tag.get("parameter_unit"),
        "quantization": tag.get("quantization"),
        "architecture": tag.get("architecture"),
        "context_window_tokens": tag.get("context_window_tokens"),
        "download_size_bytes": tag.get("download_size_bytes"),
        "download_size_text": tag.get("download_size_text"),
        "availability": tag.get("availability"),
        "capabilities": tag.get("capabilities") or {},
        "pull_command": tag.get("pull_command"),
        "run_command": tag.get("run_command"),
        "alias_target": tag.get("alias_target"),
        "source_url": tag.get("source_url"),
        "retrieved_at": tag.get("retrieved_at"),
        "provenance": tag.get("provenance") or {},
        "page": {
            "page_type": "deployment_variant",
            "seo_eligible": False,
        },
        "classifications": {
            "local_private_suitable": (
                tag.get("availability") in LOCAL_AVAILABILITY
                and bool(tag.get("download_size_bytes"))
            ),
            "cloud_jet_suitable": tag.get("availability") in CLOUD_AVAILABILITY,
            "capability_filters": _capability_filters(tag.get("capabilities")),
            "size_bucket": _size_bucket(tag.get("parameter_count")),
            "quantization": tag.get("quantization"),
        },
    }


def _seo_eligible(record: dict[str, Any], *, page_type: str) -> bool:
    if page_type == "deployment_variant":
        return False
    return not _is_source_exception(record)


def build_public_catalog(
    *,
    normalized_dir: Path = NORMALIZED_DIR,
) -> dict[str, Any]:
    publishers = load_json(normalized_dir / "publishers.json")
    families = load_json(normalized_dir / "families.json")
    models = load_json(normalized_dir / "models.json")
    tags = load_json(normalized_dir / "tags.json")
    capabilities = load_json(normalized_dir / "capabilities.json")
    catalog_meta = load_json(normalized_dir / "catalog-meta.json")

    publishers_by_id = {item["id"]: item for item in publishers}
    models_by_family: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        models_by_family.setdefault(model["family_id"], []).append(model)
    tags_by_model: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        tags_by_model.setdefault(tag["model_id"], []).append(tag)

    family_projections: list[dict[str, Any]] = []
    model_projections: list[dict[str, Any]] = []

    classification_summary = {
        "local_private_suitable_models": 0,
        "cloud_jet_suitable_models": 0,
        "capability_filter_coverage": {key: 0 for key in CAPABILITY_FILTER_KEYS},
        "size_bucket_coverage": {bucket[0]: 0 for bucket in SIZE_BUCKETS},
        "size_bucket_coverage_unknown": 0,
        "models_with_unknown_parameter_count": 0,
    }

    for family in sorted(families, key=lambda item: item["id"]):
        family_models = sorted(
            models_by_family.get(family["id"], []),
            key=lambda item: item["id"],
        )
        family_tags = [
            tag
            for model in family_models
            for tag in tags_by_model.get(model["id"], [])
        ]
        family_classifications = _classify_tags(family_tags)
        for capability in family_classifications["capability_filters"]:
            classification_summary["capability_filter_coverage"][capability] += 1
        for bucket in family_classifications["size_buckets"]:
            if bucket == "unknown":
                classification_summary["size_bucket_coverage_unknown"] += 1
            else:
                classification_summary["size_bucket_coverage"][bucket] += 1

        family_display_name = resolve_family_display_name(family)
        family_projections.append(
            {
                "id": family["id"],
                "name": family_display_name,
                "aliases": family.get("aliases") or [],
                "description": family.get("description"),
                "catalog_source_id": family.get("catalog_source_id"),
                "source_url": family.get("source_url"),
                "retrieved_at": family.get("retrieved_at"),
                "primary_capabilities": family.get("primary_capabilities") or {},
                "publisher": _publisher_projection(family, publishers_by_id=publishers_by_id),
                "editorial_status": {
                    "technical_facts_authoritative": True,
                    "publisher_verification_status": _publisher_verification_status(
                        family,
                        publisher_id=family.get("publisher_id", "unknown"),
                    ),
                    "enrichment_backlog": list(family.get("review_reasons") or []),
                    "description_is_source_derived": bool(family.get("description")),
                },
                "source_status": _source_status(family),
                "source_exception_explanation": (
                    SOURCE_EXCEPTION_EXPLANATION if _is_source_exception(family) else None
                ),
                "page": {
                    "page_type": "family",
                    "seo_eligible": _seo_eligible(family, page_type="family"),
                },
                "classifications": family_classifications,
                "model_ids": [model["id"] for model in family_models],
            }
        )

        for model in family_models:
            model_tags = sorted(
                tags_by_model.get(model["id"], []),
                key=lambda item: item["ollama_identifier"],
            )
            model_classifications = _classify_tags(model_tags)
            if model_classifications["local_private_suitable"]:
                classification_summary["local_private_suitable_models"] += 1
            if model_classifications["cloud_jet_suitable"]:
                classification_summary["cloud_jet_suitable_models"] += 1
            if "unknown" in model_classifications["size_buckets"]:
                classification_summary["models_with_unknown_parameter_count"] += 1

            model_projections.append(
                {
                    "id": model["id"],
                    "family_id": model["family_id"],
                    "ollama_name": model.get("ollama_name"),
                    "display_name": resolve_model_display_name(
                        model,
                        family_display_name=family_display_name,
                    ),
                    "description": model.get("description"),
                    "availability": model.get("availability"),
                    "default_tag": model.get("default_tag"),
                    "capabilities": model.get("capabilities") or {},
                    "catalog_source_id": model.get("catalog_source_id"),
                    "source_url": model.get("source_url"),
                    "retrieved_at": model.get("retrieved_at"),
                    "validation_status": model.get("validation_status"),
                    "publisher": _publisher_projection(model, publishers_by_id=publishers_by_id),
                    "editorial_status": {
                        "technical_facts_authoritative": True,
                        "publisher_verification_status": _publisher_verification_status(
                            model,
                            publisher_id=model.get("publisher_id", "unknown"),
                        ),
                        "enrichment_backlog": list(model.get("review_reasons") or []),
                        "description_is_source_derived": bool(model.get("description")),
                    },
                    "source_status": _source_status(model),
                    "source_exception_explanation": (
                        SOURCE_EXCEPTION_EXPLANATION if _is_source_exception(model) else None
                    ),
                    "page": {
                        "page_type": "model",
                        "seo_eligible": _seo_eligible(model, page_type="model"),
                    },
                    "classifications": model_classifications,
                    "deployment_variants": [_deployment_variant(tag) for tag in model_tags],
                }
            )

    seo_eligible_families = sum(
        1 for item in family_projections if item["page"]["seo_eligible"]
    )
    seo_eligible_models = sum(
        1 for item in model_projections if item["page"]["seo_eligible"]
    )
    source_exception_families = sum(
        1 for item in family_projections if item["source_status"] == "stale_source_exception"
    )
    deployment_variant_count = sum(
        len(item["deployment_variants"]) for item in model_projections
    )

    source_files = {}
    for name in NORMALIZED_FILES:
        path = normalized_dir / name
        if path.exists():
            source_files[name] = {
                "path": _relative_repo_path(path),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }

    generated_at = utc_now_iso()
    manifest = {
        "schema_version": PUBLIC_CATALOG_SCHEMA_VERSION,
        "generator_version": PUBLIC_CATALOG_GENERATOR_VERSION,
        "generator_command": PUBLIC_CATALOG_GENERATOR_COMMAND,
        "generated_at": generated_at,
        "canonical_catalog_version": catalog_meta.get("catalog_version"),
        "promotion_receipt": PROMOTION_RECEIPT_PATH,
        "collection_date": catalog_meta.get("collection_date"),
        "collection_id": catalog_meta.get("collection_id"),
        "collection_manifest": catalog_meta.get("collection_manifest"),
        "catalog_source_id": catalog_meta.get("catalog_source_id"),
        "source_provenance": {
            "normalized_dir": _relative_repo_path(normalized_dir),
            "source_commit": _repo_head_commit(),
            "source_files": source_files,
        },
        "counts": {
            "families": len(family_projections),
            "models": len(model_projections),
            "deployment_variants": deployment_variant_count,
            "publishers": len(publishers),
            "capabilities": len(capabilities),
            "seo_eligible_family_pages": seo_eligible_families,
            "seo_eligible_model_pages": seo_eligible_models,
            "non_indexable_source_exception_families": source_exception_families,
            "deployment_variant_pages": 0,
        },
        "indexes": {
            "families": "index/families.json",
            "models": "index/models.json",
        },
        "classification_summary": classification_summary,
    }

    return {
        "manifest": manifest,
        "families": family_projections,
        "models": model_projections,
        "capabilities": capabilities,
        "publishers": publishers,
    }


def _publishing_report_lines(manifest: dict[str, Any]) -> list[str]:
    counts = manifest["counts"]
    summary = manifest["classification_summary"]
    lines = [
        "# Public Catalog Publishing Report",
        "",
        f"- Schema version: `{manifest['schema_version']}`",
        f"- Generator: `{manifest['generator_command']}` v{manifest['generator_version']}",
        f"- Generated at: {manifest['generated_at']}",
        f"- Canonical catalog version: `{manifest['canonical_catalog_version']}`",
        f"- Collection date: `{manifest.get('collection_date')}`",
        f"- Promotion receipt: `{manifest['promotion_receipt']}`",
        "",
        "## Page eligibility",
        f"- Family pages: **{counts['families']}** ({counts['seo_eligible_family_pages']} SEO-eligible)",
        f"- Model pages: **{counts['models']}** ({counts['seo_eligible_model_pages']} SEO-eligible)",
        f"- Deployment variants: **{counts['deployment_variants']}** (0 automatic SEO pages)",
        f"- Non-indexable source-exception families: **{counts['non_indexable_source_exception_families']}**",
        "",
        "## Classification coverage",
        f"- Local/private suitable models: {summary['local_private_suitable_models']}",
        f"- Cloud/Jet suitable models: {summary['cloud_jet_suitable_models']}",
        f"- Models with unknown parameter count: {summary['models_with_unknown_parameter_count']}",
        "",
        "### Capability filters (family count)",
    ]
    for key in CAPABILITY_FILTER_KEYS:
        lines.append(f"- `{key}`: {summary['capability_filter_coverage'][key]}")
    lines.extend(["", "### Size buckets (family count)"])
    for bucket_id, _, _ in SIZE_BUCKETS:
        lines.append(f"- `{bucket_id}`: {summary['size_bucket_coverage'][bucket_id]}")
    lines.append(f"- `unknown`: {summary['size_bucket_coverage_unknown']}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "- `AGENTS/data-science/P4-Public-Catalog/manifest.json`",
            "- `AGENTS/data-science/P4-Public-Catalog/index/families.json`",
            "- `AGENTS/data-science/P4-Public-Catalog/index/models.json`",
            "- `schemas/public-catalog-manifest.schema.json`",
            "- `AGENTS/data-science/P4-Public-Catalog/CONSUMPTION.md`",
            "- `AGENTS/data-science/P4-Public-Catalog/CLASSIFICATIONS.md`",
            "",
        ]
    )
    return lines


def write_public_catalog(
    catalog: dict[str, Any],
    *,
    output_dir: Path = P4_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_dir = output_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.json"
    families_path = index_dir / "families.json"
    models_path = index_dir / "models.json"
    report_path = reports_dir / "public-catalog-publishing.md"

    write_json(manifest_path, catalog["manifest"])
    write_json(families_path, catalog["families"])
    write_json(models_path, catalog["models"])

    report_path.write_text(
        "\n".join(_publishing_report_lines(catalog["manifest"])),
        encoding="utf-8",
    )

    return {
        "manifest": manifest_path,
        "families": families_path,
        "models": models_path,
        "report": report_path,
    }

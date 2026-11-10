from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from eight_ball.config import catalog_policy, load_json, write_json
from eight_ball.paths import NORMALIZED_DIR, REPORTS_DIR, SCHEMAS_DIR

UNRESOLVED_SCHEMA = "terminal-glass.8-ball.unresolved-fields/1"
SI_NOTE = (
    "Published sizes use decimal SI units (1 KB = 1000 bytes). "
    "download_size_bytes is disk size, not RAM or VRAM."
)

TAG_FIELDS = (
    "parameter_count",
    "quantization",
    "architecture",
    "context_window_tokens",
    "download_size_bytes",
    "download_size_text",
    "source_url",
    "retrieved_at",
)
MODEL_FIELDS = ("description", "source_url", "retrieved_at")
FAMILY_FIELDS = ("description", "source_url", "retrieved_at")


def collect_unresolved(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Return null observed fields. Null means unknown, not a guessed value."""
    rows: list[dict[str, str]] = []
    for family in catalog.get("families", []):
        for field in FAMILY_FIELDS:
            if family.get(field) is None:
                rows.append(
                    {
                        "entity": "family",
                        "id": str(family.get("id")),
                        "field": field,
                        "source_url": family.get("source_url") or "",
                    }
                )
    for model in catalog.get("models", []):
        for field in MODEL_FIELDS:
            if model.get(field) is None:
                rows.append(
                    {
                        "entity": "model",
                        "id": str(model.get("id")),
                        "field": field,
                        "source_url": model.get("source_url") or "",
                    }
                )
        for flag in model.get("unknown_field_flags") or []:
            rows.append(
                {
                    "entity": "model",
                    "id": str(model.get("id")),
                    "field": str(flag),
                    "source_url": model.get("source_url") or "",
                }
            )
    for tag in catalog.get("tags", []):
        for field in TAG_FIELDS:
            if tag.get(field) is None:
                rows.append(
                    {
                        "entity": "tag",
                        "id": str(tag.get("ollama_identifier") or tag.get("id")),
                        "field": field,
                        "source_url": tag.get("source_url") or "",
                    }
                )
    rows.sort(key=lambda row: (row["entity"], row["id"], row["field"]))
    return rows


def summarize_unresolved(
    catalog: dict[str, Any],
    *,
    catalog_version: str,
) -> dict[str, Any]:
    rows = collect_unresolved(catalog)
    counts: dict[str, int] = {}
    for row in rows:
        key = f"{row['entity']}.{row['field']}"
        counts[key] = counts.get(key, 0) + 1
    policy = catalog_policy().get("size_unit_policy")
    if policy != "decimal":
        raise ValueError(f"size_unit_policy must stay decimal, found {policy!r}")
    return {
        "schema": UNRESOLVED_SCHEMA,
        "catalog_version": catalog_version,
        "size_unit_policy": "decimal",
        "si_note": SI_NOTE,
        "total_unresolved_fields": len(rows),
        "counts": dict(sorted(counts.items())),
    }


def load_normalized_catalog(normalized_dir: Path = NORMALIZED_DIR) -> tuple[dict[str, Any], str]:
    catalog = {
        "families": load_json(normalized_dir / "families.json"),
        "models": load_json(normalized_dir / "models.json"),
        "tags": load_json(normalized_dir / "tags.json"),
    }
    meta_path = normalized_dir / "catalog-meta.json"
    version = "unknown"
    if meta_path.exists():
        meta = load_json(meta_path)
        version = str(meta.get("catalog_version") or "unknown")
    return catalog, version


def unresolved_summary_from_disk(normalized_dir: Path = NORMALIZED_DIR) -> dict[str, Any]:
    catalog, version = load_normalized_catalog(normalized_dir)
    return summarize_unresolved(catalog, catalog_version=version)


def validate_unresolved_summary(summary: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMAS_DIR / "unresolved-field-report.schema.json")
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(summary), key=lambda e: list(e.path))]


def write_unresolved_summary(
    path: Path | None = None,
    *,
    normalized_dir: Path = NORMALIZED_DIR,
) -> dict[str, Any]:
    summary = unresolved_summary_from_disk(normalized_dir)
    errors = validate_unresolved_summary(summary)
    if errors:
        raise ValueError("; ".join(errors))
    target = path or REPORTS_DIR / "unresolved-fields-summary.json"
    write_json(target, summary)
    return summary

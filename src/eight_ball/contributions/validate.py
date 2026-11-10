from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from eight_ball.config import catalog_policy, load_json, load_yaml
from eight_ball.generate.component_display import render_component_inventory
from eight_ball.paths import (
    CONFIG_DIR,
    HISTORY_DIR,
    NORMALIZED_DIR,
    REPO_ROOT,
    REPORTS_DIR,
    SCHEMAS_DIR,
)
from eight_ball.report.unresolved import unresolved_summary_from_disk

INVENTORY_DOC = REPO_ROOT / "docs" / "component-inventory.md"
SUMMARY_PATH = REPORTS_DIR / "unresolved-fields-summary.json"


def _schema_errors(instance: object, schema_name: str, label: str) -> list[str]:
    schema = load_json(SCHEMAS_DIR / schema_name)
    validator = Draft202012Validator(schema)
    return [
        f"{label}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


def validate_contribution_records(
    *,
    components_path: Path | None = None,
    changes_path: Path | None = None,
    inventory_doc_path: Path | None = None,
    summary_path: Path | None = None,
    normalized_dir: Path | None = None,
    check_generated: bool = True,
) -> list[str]:
    """Reject invalid contribution records and drifted generated display."""
    errors: list[str] = []
    if catalog_policy().get("size_unit_policy") != "decimal":
        errors.append("config/catalog-policy.yaml size_unit_policy must be decimal")

    components_path = components_path or CONFIG_DIR / "components.yaml"
    changes_path = changes_path or HISTORY_DIR / "catalog-changes.json"
    inventory_doc_path = inventory_doc_path or INVENTORY_DOC
    summary_path = summary_path or SUMMARY_PATH
    normalized_dir = normalized_dir or NORMALIZED_DIR

    try:
        components = load_yaml(components_path)
    except OSError as exc:
        return [f"component inventory unreadable: {exc}"]
    errors.extend(_schema_errors(components, "component-inventory.schema.json", "components"))
    if isinstance(components, dict):
        seen: set[str] = set()
        for item in components.get("components") or []:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if item_id in seen:
                errors.append(f"components: duplicate id {item_id}")
            if isinstance(item_id, str):
                seen.add(item_id)
            source_path = item.get("source_path")
            if source_path and not (REPO_ROOT / source_path).exists():
                errors.append(f"components: {item_id} source_path missing: {source_path}")
        meta_path = normalized_dir / "catalog-meta.json"
        if meta_path.exists() and isinstance(components.get("catalog_version"), str):
            meta = load_json(meta_path)
            if components["catalog_version"] != meta.get("catalog_version"):
                errors.append(
                    "components: catalog_version "
                    f"{components['catalog_version']} does not match "
                    f"data/normalized catalog {meta.get('catalog_version')}"
                )
        if check_generated and inventory_doc_path.exists() and not errors:
            expected = render_component_inventory(components)
            actual = inventory_doc_path.read_text(encoding="utf-8")
            if actual != expected:
                errors.append(
                    "docs/component-inventory.md drifted from config/components.yaml. "
                    "Regenerate it; do not hand-edit the display."
                )
        elif check_generated and not inventory_doc_path.exists():
            errors.append("docs/component-inventory.md is missing. Generate it from config/components.yaml.")

    if not changes_path.exists():
        errors.append("data/history/catalog-changes.json is missing")
    else:
        changes = load_json(changes_path)
        errors.extend(_schema_errors(changes, "catalog-change.schema.json", "catalog-changes"))
        versions = [
            row.get("catalog_version")
            for row in changes.get("changes", [])
            if isinstance(row, dict)
        ]
        meta_path = normalized_dir / "catalog-meta.json"
        if meta_path.exists():
            current = load_json(meta_path).get("catalog_version")
            if current not in versions:
                errors.append(
                    f"catalog-changes: missing history row for canonical version {current}"
                )

    if check_generated:
        if not summary_path.exists():
            errors.append("reports/unresolved-fields-summary.json is missing")
        else:
            summary = load_json(summary_path)
            errors.extend(
                _schema_errors(summary, "unresolved-field-report.schema.json", "unresolved-summary")
            )
            if not errors:
                fresh = unresolved_summary_from_disk(normalized_dir)
            if summary != fresh:
                errors.append(
                    "reports/unresolved-fields-summary.json does not match "
                    "data/normalized/. Regenerate the unresolved-field report."
                )

    errors.extend(_capability_evidence_errors(normalized_dir))
    errors.extend(_alignment_errors())
    return errors


def _capability_evidence_errors(normalized_dir: Path) -> list[str]:
    from eight_ball.evidence.capabilities import evidence_errors, load_evidence_registry

    path = normalized_dir / "capability-evidence.json"
    if not path.exists():
        return ["data/normalized/capability-evidence.json is missing"]
    registry = load_evidence_registry(path)
    tags = {row["ollama_identifier"] for row in load_json(normalized_dir / "tags.json")}
    errors = evidence_errors(registry, known_tags=tags)
    meta_path = normalized_dir / "catalog-meta.json"
    if meta_path.exists() and registry.get("catalog_version") != load_json(meta_path).get("catalog_version"):
        errors.append("capability-evidence catalog_version does not match the canonical catalog")
    return errors


def _alignment_errors() -> list[str]:
    from eight_ball.osamp.alignment import alignment_errors, load_alignment, render_alignment

    document = load_alignment()
    errors = alignment_errors(document)
    path = REPO_ROOT / "docs" / "osamp-alignment.md"
    if not path.exists():
        return errors + ["docs/osamp-alignment.md is missing. Generate it from config/osamp-alignment.yaml."]
    if not errors and path.read_text(encoding="utf-8") != render_alignment(document):
        errors.append("docs/osamp-alignment.md drifted from config/osamp-alignment.yaml.")
    return errors

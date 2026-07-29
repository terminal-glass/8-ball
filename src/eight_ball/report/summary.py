from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.normalize.capabilities import CAPABILITY_KEYS, capability_coverage_summary
from eight_ball.normalize.provenance_fields import (
    missing_provenance_fields,
    provenance_confidence_counts,
)
from eight_ball.normalize.publishers import infer_publisher_id, publisher_mapping_needs_review
from eight_ball.paths import GENERATED_DIR, NORMALIZED_DIR, REPORTS_DIR
from eight_ball.provenance import utc_now_iso


def _capability_conflicts(
    families: list[dict[str, Any]],
    models: list[dict[str, Any]],
    tags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flag contradictions only.

    Tags and models may add capabilities beyond family badge evidence. That is
    expected under Phase 3 isolation and is not a conflict. A conflict is when
    family evidence says true and a child record says false.
    """
    family_caps = {family["id"]: family.get("primary_capabilities", {}) for family in families}
    model_by_id = {model["id"]: model for model in models}
    conflicts: list[dict[str, Any]] = []
    seen_model_conflicts: set[tuple[str, str]] = set()

    for model in models:
        family_id = model.get("family_id")
        model_caps = model.get("capabilities", {}) or {}
        for cap_id in CAPABILITY_KEYS:
            family_value = family_caps.get(family_id, {}).get(cap_id, "unknown")
            model_value = model_caps.get(cap_id, "unknown")
            if family_value == "true" and model_value == "false":
                key = (model["id"], cap_id)
                if key in seen_model_conflicts:
                    continue
                seen_model_conflicts.add(key)
                conflicts.append(
                    {
                        "model_id": model["id"],
                        "capability": cap_id,
                        "family_value": family_value,
                        "model_value": model_value,
                        "kind": "model_contradicts_family",
                    }
                )

    for tag in tags:
        family_id = tag["ollama_identifier"].split(":", 1)[0]
        model_id = tag["model_id"]
        tag_caps = tag.get("capabilities", {}) or {}
        for cap_id in CAPABILITY_KEYS:
            family_value = family_caps.get(family_id, {}).get(cap_id, "unknown")
            model_value = (model_by_id.get(model_id) or {}).get("capabilities", {}).get(
                cap_id, "unknown"
            )
            tag_value = tag_caps.get(cap_id, "unknown")
            if family_value == "true" and tag_value == "false":
                conflicts.append(
                    {
                        "ollama_identifier": tag["ollama_identifier"],
                        "capability": cap_id,
                        "family_value": family_value,
                        "model_value": model_value,
                        "tag_value": tag_value,
                        "kind": "tag_contradicts_family",
                    }
                )
    return conflicts


def coverage_summary(
    catalog: dict[str, Any] | None = None,
    *,
    normalized_dir: Path = NORMALIZED_DIR,
) -> dict[str, Any]:
    if catalog is None:
        catalog = {
            "publishers": load_json(normalized_dir / "publishers.json"),
            "families": load_json(normalized_dir / "families.json"),
            "models": load_json(normalized_dir / "models.json"),
            "tags": load_json(normalized_dir / "tags.json"),
        }
    tags = catalog["tags"]
    models = catalog["models"]
    families = catalog["families"]
    total = len(tags)
    unknown_params = sum(1 for t in tags if t.get("parameter_count") is None)
    unknown_sizes = sum(1 for t in tags if t.get("download_size_bytes") is None)
    unknown_quants = sum(1 for t in tags if t.get("quantization") is None)
    unknown_context = sum(1 for t in tags if t.get("context_window_tokens") is None)
    unknown_architectures = sum(1 for t in tags if t.get("architecture") is None)
    cloud_tags = sum(1 for t in tags if t.get("availability") in {"cloud", "cloud_only", "both"})
    local_tags = sum(1 for t in tags if t.get("availability") in {"local", "both"})
    manual_review = sum(1 for m in models if m.get("validation_status") == "needs_review")

    publisher_counts = Counter(family.get("publisher_id", "unknown") for family in families)
    unknown_publishers = publisher_counts.get("unknown", 0)

    publisher_review_needed = 0
    for family in families:
        inference = infer_publisher_id(
            family_slug=family["id"],
            display_name=family.get("name"),
            description=family.get("description"),
        )
        if publisher_mapping_needs_review(inference):
            publisher_review_needed += 1

    model_capability_coverage = capability_coverage_summary(models, "capabilities")
    tag_capability_coverage = capability_coverage_summary(tags, "capabilities")
    provenance_counts = provenance_confidence_counts(tags)

    review_reason_counts: Counter[str] = Counter()
    unknown_field_flag_counts: Counter[str] = Counter()
    for model in models:
        for reason in model.get("review_reasons", []):
            review_reason_counts[reason] += 1
        for flag in model.get("unknown_field_flags", []):
            unknown_field_flag_counts[flag] += 1
    for family in families:
        for reason in family.get("review_reasons", []):
            review_reason_counts[reason] += 1
        for flag in family.get("unknown_field_flags", []):
            unknown_field_flag_counts[flag] += 1

    missing_provenance_records = [
        {
            "id": tag["id"],
            "ollama_identifier": tag["ollama_identifier"],
            "missing_fields": missing_provenance_fields(tag.get("provenance")),
        }
        for tag in tags
        if missing_provenance_fields(tag.get("provenance"))
    ]

    capability_conflicts = _capability_conflicts(families, models, tags)

    unknown_capability_fields = 0
    for tag in tags:
        for cap_id in CAPABILITY_KEYS:
            if (tag.get("capabilities") or {}).get(cap_id) == "unknown":
                unknown_capability_fields += 1

    return {
        "publishers": len(catalog["publishers"]),
        "families": len(families),
        "models": len(models),
        "tags": total,
        "local_tags": local_tags,
        "cloud_tags": cloud_tags,
        "unknown_parameter_count": unknown_params,
        "unknown_download_size": unknown_sizes,
        "unknown_quantization": unknown_quants,
        "unknown_context_window": unknown_context,
        "unknown_architecture": unknown_architectures,
        "unknown_parameter_count_rate": round(unknown_params / total, 4) if total else 0,
        "unknown_download_size_rate": round(unknown_sizes / total, 4) if total else 0,
        "manual_review_count": manual_review,
        "publisher_counts": dict(sorted(publisher_counts.items())),
        "unknown_publisher_families": unknown_publishers,
        "unknown_publisher_rate": round(unknown_publishers / len(families), 4) if families else 0,
        "publisher_mappings_needing_review": publisher_review_needed,
        "model_capability_coverage": model_capability_coverage,
        "tag_capability_coverage": tag_capability_coverage,
        "unknown_capability_field_count": unknown_capability_fields,
        "provenance_confidence_counts": provenance_counts,
        "missing_provenance_record_count": len(missing_provenance_records),
        "capability_conflict_count": len(capability_conflicts),
        "review_reason_counts": dict(sorted(review_reason_counts.items())),
        "unknown_field_flag_counts": dict(sorted(unknown_field_flag_counts.items())),
    }


def _deployment_count_from_generated(*, generated_dir: Path = GENERATED_DIR) -> int:
    path = generated_dir / "deployment_recommendations.json"
    if not path.exists():
        return 0
    return len(load_json(path))


def _input_identifier(*, normalized_dir: Path = NORMALIZED_DIR) -> str:
    meta_path = normalized_dir / "catalog-meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        if meta.get("candidate"):
            return "data/candidate/normalized"
        if meta.get("sample_only"):
            return "tests/fixtures/families"
        return "data/families"
    return "unknown"


def write_reports(
    *,
    validation_report: dict[str, Any] | None = None,
    generation_summary: dict[str, Any] | None = None,
    normalized_dir: Path = NORMALIZED_DIR,
    generated_dir: Path = GENERATED_DIR,
    report_path: Path | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage = coverage_summary(normalized_dir=normalized_dir)
    deployment_count = 0
    if generation_summary and "deployment_combinations" in generation_summary:
        deployment_count = generation_summary["deployment_combinations"]
    else:
        deployment_count = _deployment_count_from_generated(generated_dir=generated_dir)
    coverage["deployment_combinations"] = deployment_count
    coverage["input_identifier"] = _input_identifier(normalized_dir=normalized_dir)
    coverage["report_generated_at"] = utc_now_iso()
    if validation_report is not None:
        coverage["validation_valid"] = validation_report.get("valid", False)
        coverage["validation_error_count"] = validation_report.get("error_count", 0)
    write_json(REPORTS_DIR / "coverage-summary.json", coverage)
    if validation_report is not None:
        write_json(REPORTS_DIR / "validation-report.json", validation_report)

    lines = [
        "# 8-BALL Catalog Report",
        "",
        f"- Report generated at: {coverage['report_generated_at']}",
        f"- Input identifier: {coverage['input_identifier']}",
        "",
        "## Coverage",
        f"- Publishers: {coverage['publishers']}",
        f"- Families: {coverage['families']}",
        f"- Models: {coverage['models']}",
        f"- Tags: {coverage['tags']}",
        f"- Local tags: {coverage['local_tags']}",
        f"- Cloud-related tags: {coverage['cloud_tags']}",
        f"- Unknown parameter count: {coverage['unknown_parameter_count']}",
        f"- Unknown download size: {coverage['unknown_download_size']}",
        f"- Unknown quantizations: {coverage['unknown_quantization']}",
        f"- Unknown context windows: {coverage['unknown_context_window']}",
        f"- Unknown architectures: {coverage['unknown_architecture']}",
        f"- Manual review count: {coverage['manual_review_count']}",
        f"- Deployment combinations: {deployment_count}",
        "",
        "## Publisher coverage",
        f"- Unknown publisher families: {coverage['unknown_publisher_families']}",
        f"- Publisher mappings needing review: {coverage['publisher_mappings_needing_review']}",
        f"- Publisher counts: {coverage['publisher_counts']}",
        "",
        "## Capability coverage",
        f"- Unknown capability field count (tag-level): {coverage['unknown_capability_field_count']}",
        f"- Capability conflicts: {coverage['capability_conflict_count']}",
        "",
        "## Provenance coverage",
        f"- Tag provenance confidence counts: {coverage['provenance_confidence_counts']}",
        f"- Records missing field-level provenance: {coverage['missing_provenance_record_count']}",
        "",
        "## Review coverage",
        f"- Actionable review reason counts: {coverage['review_reason_counts']}",
        f"- Unknown field flag counts: {coverage['unknown_field_flag_counts']}",
    ]
    if validation_report is not None:
        lines.extend(
            [
                "",
                "## Validation",
                f"- Valid: {validation_report.get('valid', False)}",
                f"- Errors: {validation_report.get('error_count', 0)}",
                f"- Warnings: {validation_report.get('warning_count', 0)}",
            ]
        )
    report_path = report_path or REPORTS_DIR / "catalog-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path

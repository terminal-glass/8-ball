from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import NORMALIZED_DIR, REPORTS_DIR


def coverage_summary(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    if catalog is None:
        catalog = {
            "publishers": load_json(NORMALIZED_DIR / "publishers.json"),
            "families": load_json(NORMALIZED_DIR / "families.json"),
            "models": load_json(NORMALIZED_DIR / "models.json"),
            "tags": load_json(NORMALIZED_DIR / "tags.json"),
        }
    tags = catalog["tags"]
    total = len(tags)
    unknown_params = sum(1 for t in tags if t.get("parameter_count") is None)
    unknown_sizes = sum(1 for t in tags if t.get("download_size_bytes") is None)
    cloud_tags = sum(1 for t in tags if t.get("availability") in {"cloud", "cloud_only", "both"})
    local_tags = sum(1 for t in tags if t.get("availability") in {"local", "both"})
    return {
        "publishers": len(catalog["publishers"]),
        "families": len(catalog["families"]),
        "models": len(catalog["models"]),
        "tags": total,
        "local_tags": local_tags,
        "cloud_tags": cloud_tags,
        "unknown_parameter_count_rate": round(unknown_params / total, 4) if total else 0,
        "unknown_download_size_rate": round(unknown_sizes / total, 4) if total else 0,
    }


def write_reports(
    *,
    validation_report: dict[str, Any] | None = None,
    generation_summary: dict[str, Any] | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage = coverage_summary()
    if generation_summary:
        coverage["deployment_combinations"] = generation_summary.get("deployment_combinations", 0)
    write_json(REPORTS_DIR / "coverage-summary.json", coverage)
    if validation_report is not None:
        write_json(REPORTS_DIR / "validation-report.json", validation_report)

    lines = [
        "# 8-BALL Catalog Report",
        "",
        "## Coverage",
        f"- Publishers: {coverage['publishers']}",
        f"- Families: {coverage['families']}",
        f"- Models: {coverage['models']}",
        f"- Tags: {coverage['tags']}",
        f"- Local tags: {coverage['local_tags']}",
        f"- Cloud-related tags: {coverage['cloud_tags']}",
        f"- Unknown parameter rate: {coverage['unknown_parameter_count_rate']:.2%}",
        f"- Unknown download size rate: {coverage['unknown_download_size_rate']:.2%}",
    ]
    if generation_summary:
        lines.append(f"- Deployment combinations: {generation_summary['deployment_combinations']}")
    if validation_report is not None:
        lines.extend(
            [
                "",
                "## Validation",
                f"- Valid: {validation_report.get('valid', False)}",
                f"- Errors: {validation_report.get('error_count', 0)}",
            ]
        )
    report_path = REPORTS_DIR / "catalog-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path

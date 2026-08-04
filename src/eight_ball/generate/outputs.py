from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from eight_ball.agents_csv.import_collection import HardwareImportError, import_hardware_collection
from eight_ball.config import load_json, write_json
from eight_ball.estimate.hardware import estimate_installed_storage_bytes
from eight_ball.generate.deployments import generate_deployments
from eight_ball.generate.indexes import build_indexes
from eight_ball.generate.pages import generate_pages
from eight_ball.paths import GENERATED_DIR, INDEXES_DIR, NORMALIZED_DIR


def generate_outputs(
    *,
    normalized_dir: Path = NORMALIZED_DIR,
    generated_dir: Path = GENERATED_DIR,
    indexes_dir: Path = INDEXES_DIR,
    skip_hardware_import: bool = False,
) -> dict[str, Any]:
    if not skip_hardware_import:
        hardware_report = import_hardware_collection(
            normalized_dir=normalized_dir,
            write_outputs=True,
        )
        if not hardware_report.ok:
            raise HardwareImportError(hardware_report.errors)
    tags = load_json(normalized_dir / "tags.json")
    for tag in tags:
        tag["installed_storage_bytes_estimated"] = estimate_installed_storage_bytes(tag)
    write_json(normalized_dir / "tags.json", tags)

    deployments = generate_deployments(tags)
    generated_dir.mkdir(parents=True, exist_ok=True)
    write_json(generated_dir / "publishers.json", load_json(normalized_dir / "publishers.json"))
    write_json(generated_dir / "families.json", load_json(normalized_dir / "families.json"))
    write_json(generated_dir / "models.json", load_json(normalized_dir / "models.json"))
    write_json(generated_dir / "tags.json", tags)
    write_json(generated_dir / "capabilities.json", load_json(normalized_dir / "capabilities.json"))
    write_json(generated_dir / "deployment_recommendations.json", deployments)
    _write_deployments_csv(generated_dir / "deployment_recommendations.csv", deployments)
    index_summary = build_indexes(
        {
            "families": load_json(normalized_dir / "families.json"),
            "models": load_json(normalized_dir / "models.json"),
            "tags": tags,
        },
        indexes_dir=indexes_dir,
    )
    families = load_json(normalized_dir / "families.json")
    models = load_json(normalized_dir / "models.json")
    page_summary = generate_pages(
        families=families,
        models=models,
        tags=tags,
        deployments=deployments,
        output_root=generated_dir / "pages",
    )
    return {
        "tags": len(tags),
        "deployment_combinations": len(deployments),
        "indexes": index_summary,
        "pages": page_summary,
    }


def _write_deployments_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

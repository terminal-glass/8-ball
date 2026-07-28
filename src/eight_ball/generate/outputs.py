from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.estimate.hardware import estimate_installed_storage_bytes
from eight_ball.generate.deployments import generate_deployments
from eight_ball.generate.indexes import build_indexes
from eight_ball.paths import GENERATED_DIR, NORMALIZED_DIR


def generate_outputs() -> dict[str, Any]:
    tags = load_json(NORMALIZED_DIR / "tags.json")
    for tag in tags:
        tag["installed_storage_bytes_estimated"] = estimate_installed_storage_bytes(tag)
    write_json(NORMALIZED_DIR / "tags.json", tags)

    deployments = generate_deployments(tags)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(GENERATED_DIR / "publishers.json", load_json(NORMALIZED_DIR / "publishers.json"))
    write_json(GENERATED_DIR / "families.json", load_json(NORMALIZED_DIR / "families.json"))
    write_json(GENERATED_DIR / "models.json", load_json(NORMALIZED_DIR / "models.json"))
    write_json(GENERATED_DIR / "tags.json", tags)
    write_json(GENERATED_DIR / "capabilities.json", load_json(NORMALIZED_DIR / "capabilities.json"))
    write_json(GENERATED_DIR / "deployment_recommendations.json", deployments)
    _write_deployments_csv(GENERATED_DIR / "deployment_recommendations.csv", deployments)
    index_summary = build_indexes(
        {
            "families": load_json(NORMALIZED_DIR / "families.json"),
            "models": load_json(NORMALIZED_DIR / "models.json"),
            "tags": tags,
        }
    )
    return {
        "tags": len(tags),
        "deployment_combinations": len(deployments),
        "indexes": index_summary,
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

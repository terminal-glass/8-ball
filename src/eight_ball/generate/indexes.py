from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import write_json
from eight_ball.paths import INDEXES_DIR, NORMALIZED_DIR


def build_indexes(
    catalog: dict[str, Any] | None = None,
    *,
    indexes_dir: Path | None = None,
) -> dict[str, Any]:
    if catalog is None:
        from eight_ball.config import load_json

        catalog = {
            "families": load_json(NORMALIZED_DIR / "families.json"),
            "models": load_json(NORMALIZED_DIR / "models.json"),
            "tags": load_json(NORMALIZED_DIR / "tags.json"),
        }

    tags = catalog["tags"]
    models = catalog["models"]
    model_to_family = {model["id"]: model["family_id"] for model in models}

    by_family: dict[str, list[str]] = {}
    by_model: dict[str, list[str]] = {}
    local_tags: list[str] = []
    cloud_tags: list[str] = []

    for tag in tags:
        ollama_id = tag["ollama_identifier"]
        model_id = tag["model_id"]
        family_id = model_to_family.get(model_id)
        if family_id is None:
            raise KeyError(f"tag {tag['id']} references unknown model {model_id}")
        by_model.setdefault(model_id, []).append(ollama_id)
        by_family.setdefault(family_id, []).append(ollama_id)
        availability = tag.get("availability")
        if availability in {"local", "both"}:
            local_tags.append(ollama_id)
        if availability in {"cloud", "cloud_only", "both"}:
            cloud_tags.append(ollama_id)

    target_dir = indexes_dir or INDEXES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    indexes = {
        "by-family": by_family,
        "by-model": by_model,
        "local-tags": sorted(local_tags),
        "cloud-tags": sorted(cloud_tags),
    }
    for name, payload in indexes.items():
        write_json(target_dir / f"{name}.json", payload)
    return {
        "families_indexed": len(by_family),
        "models_indexed": len(by_model),
        "local_tags": len(local_tags),
        "cloud_tags": len(cloud_tags),
    }

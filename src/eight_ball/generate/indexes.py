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
    by_capability: dict[str, list[str]] = {}
    local_tags: list[str] = []
    local_download_tags: list[str] = []
    cloud_tags: list[str] = []
    cloud_only_tags: list[str] = []
    download_sizes: list[dict[str, Any]] = []

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
            local_download_tags.append(ollama_id)
        if availability in {"cloud", "cloud_only", "both"}:
            cloud_tags.append(ollama_id)
        if availability == "cloud_only":
            cloud_only_tags.append(ollama_id)
        if tag.get("download_size_bytes") is not None:
            download_sizes.append(
                {
                    "ollama_identifier": ollama_id,
                    "download_size_bytes": tag["download_size_bytes"],
                }
            )
        for capability_id, value in (tag.get("capabilities") or {}).items():
            if value == "true":
                by_capability.setdefault(capability_id, []).append(ollama_id)

    target_dir = indexes_dir or INDEXES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    download_sizes.sort(key=lambda row: (row["download_size_bytes"], row["ollama_identifier"]))
    indexes = {
        "by-family": by_family,
        "by-model": by_model,
        "by-capability": {key: sorted(value) for key, value in sorted(by_capability.items())},
        "local-tags": sorted(local_tags),
        "local-download-tags": sorted(local_download_tags),
        "cloud-tags": sorted(cloud_tags),
        "cloud-only-tags": sorted(cloud_only_tags),
        "download-size-bytes": download_sizes,
    }
    for name, payload in indexes.items():
        write_json(target_dir / f"{name}.json", payload)
    return {
        "families_indexed": len(by_family),
        "models_indexed": len(by_model),
        "local_tags": len(local_tags),
        "local_download_tags": len(local_download_tags),
        "cloud_tags": len(cloud_tags),
        "cloud_only_tags": len(cloud_only_tags),
    }

from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import load_json
from eight_ball.manager.suitability import assess_suitability
from eight_ball.paths import NORMALIZED_DIR


def load_catalog(normalized_dir: Path | None = None) -> dict[str, Any]:
    root = normalized_dir or NORMALIZED_DIR
    return {
        "publishers": load_json(root / "publishers.json"),
        "families": load_json(root / "families.json"),
        "models": load_json(root / "models.json"),
        "tags": load_json(root / "tags.json"),
        "catalog_meta": load_json(root / "catalog-meta.json") if (root / "catalog-meta.json").exists() else {},
    }


def browse(
    catalog: dict[str, Any],
    *,
    query: str = "",
    availability: str | None = None,
    capability: str | None = None,
    local_downloads_only: bool = False,
    hardware: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    families = {row["id"]: row for row in catalog["families"]}
    models = {row["id"]: row for row in catalog["models"]}
    needle = query.casefold()
    rows: list[dict[str, Any]] = []
    for tag in catalog["tags"]:
        if local_downloads_only and tag.get("availability") not in {"local", "both"}:
            continue
        if availability is not None and tag.get("availability") != availability:
            continue
        capabilities = tag.get("capabilities") or {}
        if capability is not None and capabilities.get(capability) != "true":
            continue
        model = models.get(tag["model_id"], {})
        family = families.get(model.get("family_id"), {})
        haystack = " ".join(
            [
                str(model.get("display_name") or ""),
                str(family.get("name") or ""),
                str(tag.get("ollama_identifier") or ""),
            ]
        ).casefold()
        if needle and needle not in haystack:
            continue
        rows.append(display_record(tag, model, family, hardware))
    rows.sort(key=lambda row: row["exact_tag"])
    return rows


def display_record(
    tag: dict[str, Any],
    model: dict[str, Any],
    family: dict[str, Any],
    hardware: dict[str, Any] | None = None,
) -> dict[str, Any]:
    suitability = assess_suitability(tag, hardware)
    evidence = tag.get("capability_evidence") or []
    return {
        "display_name": model.get("display_name"),
        "family": family.get("name"),
        "exact_tag": tag.get("ollama_identifier"),
        "availability": tag.get("availability"),
        "download_size_bytes": tag.get("download_size_bytes"),
        "download_size_text": suitability["download_size_text"],
        "estimated_runtime_memory_bytes": suitability["estimated_runtime_memory_bytes"],
        "runtime_memory_evidence": suitability["evidence_level"],
        "download_size_used_as_memory": False,
        "capabilities": tag.get("capabilities") or {},
        "capability_evidence": evidence,
        "capability_evidence_status": "recorded" if evidence else "untested",
        "source_url": tag.get("source_url"),
        "retrieved_at": tag.get("retrieved_at"),
        "license_status": "unknown",
        "suitability": suitability["classification"],
        "suitability_reason": suitability["reason"],
        "evidence_level": suitability["evidence_level"],
        "actions": ["download"] if suitability["local_download"] else [],
    }

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from eight_ball.config import capabilities_config
from eight_ball.paths import LEGACY_FAMILIES_DIR, SAMPLE_FAMILIES


def iter_legacy_family_files(
    families_dir: Path = LEGACY_FAMILIES_DIR,
    *,
    sample_only: bool = False,
) -> Iterable[Path]:
    for path in sorted(families_dir.glob("*.json")):
        if sample_only and path.stem not in SAMPLE_FAMILIES:
            continue
        yield path


def load_legacy_family(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def map_capabilities(
  family_caps: list[str],
  variant_caps: list[str] | None = None,
) -> dict[str, str]:
    cfg = capabilities_config()
    mapping = cfg.get("legacy_capability_map", {})
    canonical = {item["id"]: "unknown" for item in cfg.get("capabilities", [])}
    tokens = list(family_caps) + list(variant_caps or [])
    for token in tokens:
        key = mapping.get(token, token)
        if key in canonical:
            canonical[key] = "true"
    return canonical


def tag_availability(variant: dict[str, Any]) -> str:
    local = bool(variant.get("local_available"))
    cloud = bool(variant.get("cloud_available"))
    cloud_only = bool(variant.get("cloud_only"))
    if cloud_only:
        return "cloud_only"
    if local and cloud:
        return "both"
    if cloud:
        return "cloud"
    if local:
        return "local"
    return "unknown"


def model_availability(variants: list[dict[str, Any]]) -> str:
    values = {tag_availability(v) for v in variants}
    if values == {"cloud_only"} or values == {"cloud"}:
        return "cloud"
    if "cloud" in values or "both" in values or "cloud_only" in values:
        if "local" in values or "both" in values:
            return "both"
        return "cloud"
    if values <= {"local"}:
        return "local"
    return "unknown"


def default_tag_for_variants(variants: list[dict[str, Any]]) -> str | None:
    for variant in variants:
        if variant.get("is_default_alias"):
            return variant.get("exact_tag")
    for variant in variants:
        if variant.get("tag_suffix") in {"latest", "v1.6"}:
            return variant.get("exact_tag")
    return variants[0]["exact_tag"] if variants else None

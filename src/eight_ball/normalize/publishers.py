from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from eight_ball.config import publishers_config

DEFAULT_CATALOG_SOURCE_ID = "ollama-library"


@dataclass(frozen=True)
class PublisherInference:
    publisher_id: str
    confidence: str
    method: str
    notes: str | None = None


def _slug_prefixes(publisher: dict[str, Any]) -> list[str]:
    return [value.lower() for value in publisher.get("slug_prefixes", [])]


def _text_patterns(publisher: dict[str, Any]) -> list[str]:
    return [value.lower() for value in publisher.get("text_patterns", [])]


def _publisher_registry() -> dict[str, dict[str, Any]]:
    config = publishers_config()
    return {item["id"]: item for item in config.get("publishers", [])}


def catalog_source_records() -> list[dict[str, Any]]:
    return list(publishers_config().get("catalog_sources", []))


def default_catalog_source_id() -> str:
    return publishers_config().get("default_catalog_source_id", DEFAULT_CATALOG_SOURCE_ID)


def default_publisher_id() -> str:
    return publishers_config().get("default_publisher_id", "unknown")


def build_publisher_records(*, publisher_ids: set[str]) -> list[dict[str, Any]]:
    registry = _publisher_registry()
    records: list[dict[str, Any]] = []
    for publisher_id in sorted(publisher_ids):
        publisher = registry.get(publisher_id)
        if publisher is None:
            continue
        records.append(
            {
                "id": publisher["id"],
                "display_name": publisher["display_name"],
                "aliases": publisher.get("aliases", []),
                "official_url": publisher.get("official_url"),
            }
        )
    return records


def infer_publisher_id(
    *,
    family_slug: str,
    display_name: str | None = None,
    description: str | None = None,
    updated_text: str | None = None,
) -> PublisherInference:
    config = publishers_config()
    overrides = config.get("family_overrides", {})
    if family_slug in overrides:
        publisher_id = overrides[family_slug]
        return PublisherInference(
            publisher_id=publisher_id,
            confidence="manual",
            method="family_override",
            notes=f"config family_overrides[{family_slug}]",
        )

    slug = family_slug.lower()
    haystack = " ".join(
        part
        for part in [family_slug, display_name or "", description or "", updated_text or ""]
        if part
    ).lower()

    for publisher in config.get("publishers", []):
        publisher_id = publisher["id"]
        if publisher_id == "unknown":
            continue
        for prefix in _slug_prefixes(publisher):
            if slug == prefix or slug.startswith((f"{prefix}-", prefix)):
                return PublisherInference(
                    publisher_id=publisher_id,
                    confidence="derived",
                    method="slug_prefix",
                    notes=f"matched slug prefix {prefix}",
                )

    for publisher in config.get("publishers", []):
        publisher_id = publisher["id"]
        if publisher_id == "unknown":
            continue
        for pattern in _text_patterns(publisher):
            if pattern and pattern in haystack:
                return PublisherInference(
                    publisher_id=publisher_id,
                    confidence="derived",
                    method="text_pattern",
                    notes=f"matched text pattern {pattern}",
                )

    return PublisherInference(
        publisher_id=default_publisher_id(),
        confidence="unknown",
        method="default",
        notes="no publisher pattern matched",
    )


def slug_token_match(slug: str, token: str) -> bool:
    token = token.lower()
    slug = slug.lower()
    if slug == token:
        return True
    return bool(re.match(rf"^{re.escape(token)}([._-]|$)", slug))

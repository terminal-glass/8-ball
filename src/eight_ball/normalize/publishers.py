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
    review_status: str = "needs_review"
    provenance_type: str = "inferred"
    evidence_url: str | None = None


def _slug_prefixes(publisher: dict[str, Any]) -> list[str]:
    return [value.lower() for value in publisher.get("slug_prefixes", [])]


def _text_patterns(publisher: dict[str, Any]) -> list[str]:
    return [value.lower() for value in publisher.get("text_patterns", [])]


def _publisher_registry() -> dict[str, dict[str, Any]]:
    config = publishers_config()
    return {item["id"]: item for item in config.get("publishers", [])}


def _community_slug_prefixes() -> list[str]:
    return [value.lower() for value in publishers_config().get("community_slug_prefixes", [])]


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


def slug_token_match(slug: str, token: str) -> bool:
    token = token.lower()
    slug = slug.lower()
    if slug == token:
        return True
    return bool(re.match(rf"^{re.escape(token)}([._-]|$)", slug))


def _is_community_slug(slug: str) -> bool:
    for prefix in _community_slug_prefixes():
        if slug_token_match(slug, prefix):
            return True
    return False


def _text_pattern_match(haystack: str, pattern: str) -> bool:
    if not pattern:
        return False
    return bool(re.search(rf"\b{re.escape(pattern)}\b", haystack, flags=re.IGNORECASE))


def _inference_from_publisher(
    publisher: dict[str, Any],
    *,
    method: str,
    notes: str,
    confidence: str = "derived",
) -> PublisherInference:
    return PublisherInference(
        publisher_id=publisher["id"],
        confidence=confidence,
        method=method,
        notes=notes,
        review_status=publisher.get("review_status", "needs_review"),
        provenance_type=publisher.get("provenance_type", "inferred"),
        evidence_url=publisher.get("evidence_url"),
    )


def _override_entry(overrides: dict[str, Any], family_slug: str) -> dict[str, Any] | None:
    entry = overrides.get(family_slug)
    if entry is None:
        return None
    if isinstance(entry, str):
        return {"publisher_id": entry}
    return entry


def infer_publisher_id(
    *,
    family_slug: str,
    display_name: str | None = None,
    description: str | None = None,
    updated_text: str | None = None,
) -> PublisherInference:
    config = publishers_config()
    registry = _publisher_registry()
    overrides = config.get("family_overrides", {})

    override = _override_entry(overrides, family_slug)
    if override is not None:
        publisher_id = override["publisher_id"]
        return PublisherInference(
            publisher_id=publisher_id,
            confidence="manual",
            method="family_override",
            notes=f"config family_overrides[{family_slug}]",
            review_status=override.get("review_status", "approved"),
            provenance_type=override.get("provenance_type", "manual"),
            evidence_url=override.get("evidence_url"),
        )

    slug = family_slug.lower()
    if _is_community_slug(slug):
        unknown = registry.get(default_publisher_id(), {})
        return PublisherInference(
            publisher_id=default_publisher_id(),
            confidence="unknown",
            method="community_slug",
            notes="community or derived slug prefix blocked publisher inference",
            review_status=unknown.get("review_status", "needs_review"),
            provenance_type="unknown",
        )

    haystack = " ".join(
        part
        for part in [family_slug, display_name or "", description or "", updated_text or ""]
        if part
    )

    for publisher in config.get("publishers", []):
        publisher_id = publisher["id"]
        if publisher_id == "unknown":
            continue
        for prefix in _slug_prefixes(publisher):
            if slug_token_match(slug, prefix):
                return _inference_from_publisher(
                    publisher,
                    method="slug_prefix",
                    notes=f"matched slug prefix {prefix}",
                )

    lowered_haystack = haystack.lower()
    for publisher in config.get("publishers", []):
        publisher_id = publisher["id"]
        if publisher_id == "unknown":
            continue
        for pattern in _text_patterns(publisher):
            if _text_pattern_match(lowered_haystack, pattern):
                return _inference_from_publisher(
                    publisher,
                    method="text_pattern",
                    notes=f"matched text pattern {pattern}",
                )

    unknown = registry.get(default_publisher_id(), {})
    return PublisherInference(
        publisher_id=default_publisher_id(),
        confidence="unknown",
        method="default",
        notes="no publisher pattern matched",
        review_status=unknown.get("review_status", "needs_review"),
        provenance_type="unknown",
    )


def publisher_mapping_needs_review(inference: PublisherInference) -> bool:
    return inference.review_status == "needs_review"

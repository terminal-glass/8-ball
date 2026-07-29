from __future__ import annotations

from typing import Any

from eight_ball.collect.parse_ollama import ParsedTag
from eight_ball.provenance import ProvenanceField

TAG_PROVENANCE_FIELDS = (
    "download_size_bytes",
    "parameter_count",
    "context_window_tokens",
    "quantization",
    "availability",
    "capabilities",
)

# Normalized values must not be labeled observed; raw text is observed separately.
DERIVED_TAG_PROVENANCE_FIELDS = (
    "download_size_bytes",
    "parameter_count",
    "context_window_tokens",
    "quantization",
    "availability",
    "capabilities",
)
DERIVED_PROVENANCE_CONFIDENCES = frozenset({"derived", "unknown"})


def observed_or_unknown(
    value: Any,
    *,
    source_url: str | None,
    retrieved_at: str | None,
    unknown_note: str,
) -> dict[str, Any]:
    if value is None:
        return ProvenanceField.unknown(unknown_note).to_dict()
    return ProvenanceField.observed(
        value,
        source_url=source_url,
        retrieved_at=retrieved_at,
    ).to_dict()


def derived_or_unknown(
    value: Any,
    *,
    source_url: str | None,
    retrieved_at: str | None,
    unknown_note: str,
    notes: str | None = None,
) -> dict[str, Any]:
    if value is None:
        return ProvenanceField.unknown(unknown_note).to_dict()
    return ProvenanceField.derived(
        value,
        source_url=source_url,
        retrieved_at=retrieved_at,
        notes=notes,
    ).to_dict()


def build_tag_provenance(
    *,
    tag: dict[str, Any],
    parsed_tag: ParsedTag,
    source_url: str | None,
    retrieved_at: str | None,
    capabilities: dict[str, str],
) -> dict[str, Any]:
    return {
        "download_size_text": observed_or_unknown(
            parsed_tag.download_size_text,
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="download size text not published",
        ),
        "download_size_bytes": derived_or_unknown(
            tag.get("download_size_bytes"),
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="download size not published",
            notes="derived from published download size text",
        ),
        "parameter_count": derived_or_unknown(
            tag.get("parameter_count"),
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="parameter count not published",
            notes="derived from tag suffix parameter label when present",
        ),
        "context_window_tokens": derived_or_unknown(
            tag.get("context_window_tokens"),
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="context window not published",
            notes="derived from published context window text",
        ),
        "quantization": derived_or_unknown(
            tag.get("quantization"),
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="quantization not published",
            notes="derived from tag suffix when present",
        ),
        "availability": derived_or_unknown(
            tag.get("availability"),
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="availability not determined",
            notes="derived from download size and structured cloud badge metadata",
        ),
        "capabilities": derived_or_unknown(
            capabilities,
            source_url=source_url,
            retrieved_at=retrieved_at,
            unknown_note="capabilities not determined",
            notes="derived from family badges plus tag input capabilities",
        ),
    }


def build_family_provenance(
    *,
    publisher_inference: Any,
    catalog_source_id: str,
    source_url: str | None,
    retrieved_at: str | None,
) -> dict[str, Any]:
    confidence = getattr(publisher_inference, "confidence", "unknown")
    if confidence == "unknown":
        publisher_provenance = ProvenanceField.unknown(
            getattr(publisher_inference, "notes", "publisher not identified")
        ).to_dict()
    elif confidence == "manual":
        publisher_provenance = ProvenanceField.manual(
            getattr(publisher_inference, "publisher_id", None),
            source_url=getattr(publisher_inference, "evidence_url", None) or source_url,
            retrieved_at=retrieved_at,
            notes=getattr(publisher_inference, "notes", None),
        ).to_dict()
    else:
        publisher_provenance = ProvenanceField.derived(
            getattr(publisher_inference, "publisher_id", None),
            source_url=getattr(publisher_inference, "evidence_url", None) or source_url,
            retrieved_at=retrieved_at,
            notes=getattr(publisher_inference, "notes", None),
        ).to_dict()
    return {
        "publisher_id": publisher_provenance,
        "catalog_source_id": ProvenanceField.observed(
            catalog_source_id,
            source_url=source_url,
            retrieved_at=retrieved_at,
        ).to_dict(),
    }


def provenance_confidence_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"observed": 0, "derived": 0, "estimated": 0, "manual": 0, "unknown": 0}
    for record in records:
        provenance = record.get("provenance", {}) or {}
        for field in provenance.values():
            confidence = field.get("confidence", "unknown")
            counts[confidence] = counts.get(confidence, 0) + 1
    return counts


def missing_provenance_fields(provenance: dict[str, Any] | None) -> list[str]:
    if not provenance:
        return list(TAG_PROVENANCE_FIELDS)
    return [field for field in TAG_PROVENANCE_FIELDS if field not in provenance]

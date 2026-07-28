from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

Confidence = Literal["observed", "derived", "estimated", "manual", "unknown"]


@dataclass
class ProvenanceField:
    value: Any
    confidence: Confidence
    source_url: str | None = None
    retrieved_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "notes": self.notes,
        }

    @classmethod
    def observed(
        cls,
        value: Any,
        *,
        source_url: str | None = None,
        retrieved_at: str | None = None,
        notes: str | None = None,
    ) -> ProvenanceField:
        return cls(value, "observed", source_url, retrieved_at, notes)

    @classmethod
    def derived(
        cls,
        value: Any,
        *,
        source_url: str | None = None,
        retrieved_at: str | None = None,
        notes: str | None = None,
    ) -> ProvenanceField:
        return cls(value, "derived", source_url, retrieved_at, notes)

    @classmethod
    def estimated(
        cls,
        value: Any,
        *,
        source_url: str | None = None,
        retrieved_at: str | None = None,
        notes: str | None = None,
    ) -> ProvenanceField:
        return cls(value, "estimated", source_url, retrieved_at, notes)

    @classmethod
    def manual(
        cls,
        value: Any,
        *,
        source_url: str | None = None,
        retrieved_at: str | None = None,
        notes: str | None = None,
    ) -> ProvenanceField:
        return cls(value, "manual", source_url, retrieved_at, notes)

    @classmethod
    def unknown(cls, notes: str | None = None) -> ProvenanceField:
        return cls(None, "unknown", notes=notes)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

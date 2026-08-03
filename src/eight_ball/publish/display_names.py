from __future__ import annotations

from typing import Any

INVALID_DISPLAY_NAMES: frozenset[str] = frozenset(
    {
        "references",
        "documentation",
        "models",
        "tags",
        "library",
        "cancel",
    }
)


def is_invalid_display_name(value: object | None) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return True
    normalized = value.strip()
    if not normalized:
        return True
    return normalized.casefold() in INVALID_DISPLAY_NAMES


def _first_valid_display_name(candidates: list[object | None]) -> str | None:
    for candidate in candidates:
        if not is_invalid_display_name(candidate):
            assert isinstance(candidate, str)
            return candidate.strip()
    return None


def resolve_family_display_name(family: dict[str, Any]) -> str:
    """Resolve a family display name from canonical metadata without inventing names."""
    resolved = _first_valid_display_name(
        [
            family.get("name"),
        ]
    )
    if resolved is not None:
        return resolved
    return family["id"]


def resolve_model_display_name(
    model: dict[str, Any],
    *,
    family_display_name: str | None = None,
) -> str:
    """Resolve a model display name from canonical metadata without inventing names."""
    resolved = _first_valid_display_name(
        [
            model.get("display_name"),
            model.get("ollama_name"),
            family_display_name if family_display_name != model.get("family_id") else None,
        ]
    )
    if resolved is not None:
        return resolved
    return model["id"]


def resolve_projection_family_display_name(family: dict[str, Any]) -> str:
    """Resolve a family display name from a P4 projection record."""
    resolved = _first_valid_display_name(
        [
            family.get("name"),
        ]
    )
    if resolved is not None:
        return resolved
    return family["id"]


def resolve_projection_model_display_name(
    model: dict[str, Any],
    *,
    family_display_name: str | None = None,
) -> str:
    """Resolve a model display name from a P4 projection record."""
    resolved = _first_valid_display_name(
        [
            model.get("display_name"),
            model.get("ollama_name"),
            family_display_name if family_display_name != model.get("family_id") else None,
        ]
    )
    if resolved is not None:
        return resolved
    return model["id"]

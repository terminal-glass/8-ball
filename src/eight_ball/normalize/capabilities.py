from __future__ import annotations

from typing import Any

from eight_ball.normalize.legacy import map_capabilities

CAPABILITY_KEYS = (
    "chat",
    "text_generation",
    "coding",
    "reasoning",
    "vision",
    "embeddings",
    "tool_use",
    "structured_output",
    "multilingual",
    "audio",
    "cloud",
)


def merge_capability_maps(*maps: dict[str, str]) -> dict[str, str]:
    merged = {cap_id: "unknown" for cap_id in CAPABILITY_KEYS}
    for capability_map in maps:
        for cap_id, value in capability_map.items():
            if cap_id not in merged:
                continue
            if value == "true":
                merged[cap_id] = "true"
            elif value == "false" and merged[cap_id] == "unknown":
                merged[cap_id] = "false"
    return merged


def capabilities_from_tokens(tokens: list[str]) -> dict[str, str]:
    return map_capabilities(tokens)


def refine_capabilities(
    base: dict[str, str],
    tokens: list[str],
) -> dict[str, str]:
    return merge_capability_maps(base, capabilities_from_tokens(tokens))


def tag_tokens_from_input_capabilities(input_capabilities: list[str]) -> list[str]:
    tokens: set[str] = set()
    for item in input_capabilities:
        lowered = item.lower()
        if "image" in lowered or lowered == "vision":
            tokens.add("vision")
        if "embed" in lowered:
            tokens.add("embedding")
        if "text" in lowered:
            tokens.add("text")
        if "audio" in lowered:
            tokens.add("audio")
        if "tool" in lowered:
            tokens.add("tools")
        if "cloud" in lowered:
            tokens.add("cloud")
    return sorted(tokens)


def family_tokens_from_badges(badges: list[str]) -> list[str]:
    return sorted({badge.lower() for badge in badges if badge})


def capability_coverage_summary(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    totals = {cap_id: {"true": 0, "false": 0, "unknown": 0} for cap_id in CAPABILITY_KEYS}
    for record in records:
        capability_map = record.get(field, {}) or {}
        for cap_id in CAPABILITY_KEYS:
            value = capability_map.get(cap_id, "unknown")
            if value not in {"true", "false", "unknown"}:
                value = "unknown"
            totals[cap_id][value] += 1
    return totals

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import (
    CANDIDATE_NORMALIZED_DIR,
    NORMALIZED_DIR,
    REPORTS_DIR,
)

_CAPABILITY_KEYS = (
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


@dataclass
class CatalogComparison:
    legacy_tag_count: int
    candidate_tag_count: int
    shared_tags: int
    legacy_only_tags: list[str]
    candidate_only_tags: list[str]
    legacy_family_count: int
    candidate_family_count: int
    legacy_only_families: list[str]
    candidate_only_families: list[str]
    legacy_model_count: int
    candidate_model_count: int
    legacy_only_models: list[str]
    candidate_only_models: list[str]
    families_compared: int
    size_deltas: list[dict[str, Any]] = field(default_factory=list)
    parameter_deltas: list[dict[str, Any]] = field(default_factory=list)
    quantization_deltas: list[dict[str, Any]] = field(default_factory=list)
    context_deltas: list[dict[str, Any]] = field(default_factory=list)
    capability_deltas: list[dict[str, Any]] = field(default_factory=list)
    availability_deltas: list[dict[str, Any]] = field(default_factory=list)
    alias_target_deltas: list[dict[str, Any]] = field(default_factory=list)
    manual_review_items: list[dict[str, Any]] = field(default_factory=list)
    parse_failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_tag_count": self.legacy_tag_count,
            "candidate_tag_count": self.candidate_tag_count,
            "shared_tags": self.shared_tags,
            "legacy_only_count": len(self.legacy_only_tags),
            "candidate_only_count": len(self.candidate_only_tags),
            "legacy_only_tags": self.legacy_only_tags,
            "candidate_only_tags": self.candidate_only_tags,
            "legacy_family_count": self.legacy_family_count,
            "candidate_family_count": self.candidate_family_count,
            "legacy_only_families": self.legacy_only_families,
            "candidate_only_families": self.candidate_only_families,
            "legacy_model_count": self.legacy_model_count,
            "candidate_model_count": self.candidate_model_count,
            "legacy_only_models": self.legacy_only_models,
            "candidate_only_models": self.candidate_only_models,
            "families_compared": self.families_compared,
            "size_deltas": self.size_deltas,
            "parameter_deltas": self.parameter_deltas,
            "quantization_deltas": self.quantization_deltas,
            "context_deltas": self.context_deltas,
            "capability_deltas": self.capability_deltas,
            "availability_deltas": self.availability_deltas,
            "alias_target_deltas": self.alias_target_deltas,
            "manual_review_items": self.manual_review_items,
            "parse_failures": self.parse_failures,
        }


def _load_tags(path: Path) -> dict[str, dict[str, Any]]:
    return {tag["ollama_identifier"]: tag for tag in load_json(path)}


def _load_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in load_json(path)}


def _filter_by_family(
    items: dict[str, dict[str, Any]],
    family_filter: set[str] | None,
    *,
    family_key: str,
) -> dict[str, dict[str, Any]]:
    if not family_filter:
        return items
    return {
        key: value
        for key, value in items.items()
        if value.get(family_key) in family_filter or key.split(":", 1)[0] in family_filter
    }


def _capability_delta(
    legacy_caps: dict[str, str] | None,
    candidate_caps: dict[str, str] | None,
) -> dict[str, str] | None:
    legacy_caps = legacy_caps or {}
    candidate_caps = candidate_caps or {}
    delta: dict[str, str] = {}
    for key in _CAPABILITY_KEYS:
        legacy_value = legacy_caps.get(key, "unknown")
        candidate_value = candidate_caps.get(key, "unknown")
        if legacy_value != candidate_value:
            delta[key] = f"{legacy_value} -> {candidate_value}"
    return delta or None


def compare_catalogs(
    *,
    legacy_dir: Path = NORMALIZED_DIR,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    family_filter: set[str] | None = None,
    parse_failures: list[dict[str, Any]] | None = None,
) -> CatalogComparison:
    legacy_tags = _load_tags(legacy_dir / "tags.json")
    candidate_tags = _load_tags(candidate_dir / "tags.json")
    legacy_families = _load_by_id(legacy_dir / "families.json")
    candidate_families = _load_by_id(candidate_dir / "families.json")
    legacy_models = _load_by_id(legacy_dir / "models.json")
    candidate_models = _load_by_id(candidate_dir / "models.json")

    if family_filter:
        legacy_tags = {
            key: value
            for key, value in legacy_tags.items()
            if key.split(":", 1)[0] in family_filter
        }
        candidate_tags = {
            key: value
            for key, value in candidate_tags.items()
            if key.split(":", 1)[0] in family_filter
        }
        legacy_families = {
            key: value for key, value in legacy_families.items() if key in family_filter
        }
        candidate_families = {
            key: value for key, value in candidate_families.items() if key in family_filter
        }
        legacy_models = _filter_by_family(legacy_models, family_filter, family_key="family_id")
        candidate_models = _filter_by_family(candidate_models, family_filter, family_key="family_id")

    legacy_ids = set(legacy_tags)
    candidate_ids = set(candidate_tags)
    shared = legacy_ids & candidate_ids
    legacy_only = sorted(legacy_ids - candidate_ids)
    candidate_only = sorted(candidate_ids - legacy_ids)

    legacy_family_ids = set(legacy_families)
    candidate_family_ids = set(candidate_families)
    legacy_only_families = sorted(legacy_family_ids - candidate_family_ids)
    candidate_only_families = sorted(candidate_family_ids - legacy_family_ids)

    legacy_model_ids = set(legacy_models)
    candidate_model_ids = set(candidate_models)
    legacy_only_models = sorted(legacy_model_ids - candidate_model_ids)
    candidate_only_models = sorted(candidate_model_ids - legacy_model_ids)

    size_deltas: list[dict[str, Any]] = []
    parameter_deltas: list[dict[str, Any]] = []
    quantization_deltas: list[dict[str, Any]] = []
    context_deltas: list[dict[str, Any]] = []
    capability_deltas: list[dict[str, Any]] = []
    availability_deltas: list[dict[str, Any]] = []
    alias_target_deltas: list[dict[str, Any]] = []
    manual_review_items: list[dict[str, Any]] = []

    for tag_id in sorted(shared):
        legacy_tag = legacy_tags[tag_id]
        candidate_tag = candidate_tags[tag_id]

        legacy_size = legacy_tag.get("download_size_bytes")
        candidate_size = candidate_tag.get("download_size_bytes")
        if legacy_size != candidate_size:
            size_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_download_size_bytes": legacy_size,
                    "candidate_download_size_bytes": candidate_size,
                }
            )

        legacy_params = (
            legacy_tag.get("parameter_count"),
            legacy_tag.get("parameter_unit"),
        )
        candidate_params = (
            candidate_tag.get("parameter_count"),
            candidate_tag.get("parameter_unit"),
        )
        if legacy_params != candidate_params:
            parameter_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_parameter_count": legacy_params[0],
                    "legacy_parameter_unit": legacy_params[1],
                    "candidate_parameter_count": candidate_params[0],
                    "candidate_parameter_unit": candidate_params[1],
                }
            )

        if legacy_tag.get("quantization") != candidate_tag.get("quantization"):
            quantization_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_quantization": legacy_tag.get("quantization"),
                    "candidate_quantization": candidate_tag.get("quantization"),
                }
            )

        if legacy_tag.get("context_window_tokens") != candidate_tag.get("context_window_tokens"):
            context_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_context_window_tokens": legacy_tag.get("context_window_tokens"),
                    "candidate_context_window_tokens": candidate_tag.get("context_window_tokens"),
                }
            )

        if legacy_tag.get("availability") != candidate_tag.get("availability"):
            availability_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_availability": legacy_tag.get("availability"),
                    "candidate_availability": candidate_tag.get("availability"),
                }
            )

        if legacy_tag.get("alias_target") != candidate_tag.get("alias_target"):
            alias_target_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_alias_target": legacy_tag.get("alias_target"),
                    "candidate_alias_target": candidate_tag.get("alias_target"),
                }
            )

        tag_cap_delta = _capability_delta(
            legacy_tag.get("capabilities"),
            candidate_tag.get("capabilities"),
        )
        if tag_cap_delta:
            capability_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "model_id": candidate_tag.get("model_id"),
                    "capability_changes": tag_cap_delta,
                }
            )

    review_seen: set[tuple[str, str]] = set()

    def _add_review_item(item: dict[str, Any]) -> None:
        key = (item.get("kind", ""), item.get("id", ""))
        if key in review_seen:
            return
        review_seen.add(key)
        manual_review_items.append(item)

    for model_id, candidate_model in sorted(candidate_models.items()):
        if candidate_model.get("validation_status") == "needs_review":
            reasons = candidate_model.get("review_reasons") or ["candidate model marked needs_review"]
            _add_review_item(
                {
                    "kind": "model",
                    "id": model_id,
                    "family_id": candidate_model.get("family_id"),
                    "reason": "; ".join(sorted(set(reasons))),
                }
            )

    for family_id in sorted(candidate_family_ids):
        family = candidate_families[family_id]
        family_reasons = list(family.get("review_reasons") or [])
        if family_reasons:
            _add_review_item(
                {
                    "kind": "family",
                    "id": family_id,
                    "reason": "; ".join(sorted(set(family_reasons))),
                }
            )

    families = {tag_id.split(":", 1)[0] for tag_id in legacy_ids | candidate_ids}
    return CatalogComparison(
        legacy_tag_count=len(legacy_tags),
        candidate_tag_count=len(candidate_tags),
        shared_tags=len(shared),
        legacy_only_tags=legacy_only,
        candidate_only_tags=candidate_only,
        legacy_family_count=len(legacy_families),
        candidate_family_count=len(candidate_families),
        legacy_only_families=legacy_only_families,
        candidate_only_families=candidate_only_families,
        legacy_model_count=len(legacy_models),
        candidate_model_count=len(candidate_models),
        legacy_only_models=legacy_only_models,
        candidate_only_models=candidate_only_models,
        families_compared=len(families),
        size_deltas=size_deltas,
        parameter_deltas=parameter_deltas,
        quantization_deltas=quantization_deltas,
        context_deltas=context_deltas,
        capability_deltas=capability_deltas,
        availability_deltas=availability_deltas,
        alias_target_deltas=alias_target_deltas,
        manual_review_items=manual_review_items,
        parse_failures=list(parse_failures or []),
    )


def write_comparison_report(
    comparison: CatalogComparison,
    *,
    output_path: Path | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path or REPORTS_DIR / "candidate-comparison.md"
    write_json(REPORTS_DIR / "candidate-comparison.json", comparison.to_dict())

    lines = [
        "# Candidate vs Legacy Catalog Comparison",
        "",
        "## Summary",
        f"- Legacy tags (in scope): {comparison.legacy_tag_count}",
        f"- Candidate tags (in scope): {comparison.candidate_tag_count}",
        f"- Shared tag identifiers: {comparison.shared_tags}",
        f"- Legacy-only tags: {len(comparison.legacy_only_tags)}",
        f"- Candidate-only tags: {len(comparison.candidate_only_tags)}",
        f"- Legacy families: {comparison.legacy_family_count}",
        f"- Candidate families: {comparison.candidate_family_count}",
        f"- Legacy-only families: {len(comparison.legacy_only_families)}",
        f"- Candidate-only families: {len(comparison.candidate_only_families)}",
        f"- Legacy models: {comparison.legacy_model_count}",
        f"- Candidate models: {comparison.candidate_model_count}",
        f"- Legacy-only models: {len(comparison.legacy_only_models)}",
        f"- Candidate-only models: {len(comparison.candidate_only_models)}",
        f"- Families compared: {comparison.families_compared}",
        f"- Download size mismatches: {len(comparison.size_deltas)}",
        f"- Parameter mismatches: {len(comparison.parameter_deltas)}",
        f"- Quantization mismatches: {len(comparison.quantization_deltas)}",
        f"- Context mismatches: {len(comparison.context_deltas)}",
        f"- Capability mismatches: {len(comparison.capability_deltas)}",
        f"- Availability mismatches: {len(comparison.availability_deltas)}",
        f"- Alias target mismatches: {len(comparison.alias_target_deltas)}",
        f"- Manual review items: {len(comparison.manual_review_items)}",
        f"- Parse failures: {len(comparison.parse_failures)}",
        "",
    ]

    def _section(title: str, items: list, formatter) -> None:
        if not items:
            return
        lines.extend([f"## {title}", ""])
        for item in items[:50]:
            lines.append(formatter(item))
        if len(items) > 50:
            lines.append(f"- ... and {len(items) - 50} more (see JSON report)")
        lines.append("")

    _section(
        "Candidate-only tags (sample)",
        comparison.candidate_only_tags,
        lambda tag: f"- `{tag}`",
    )
    _section(
        "Legacy-only tags (sample)",
        comparison.legacy_only_tags,
        lambda tag: f"- `{tag}`",
    )
    _section(
        "Download size mismatches (sample)",
        comparison.size_deltas,
        lambda row: (
            f"- `{row['ollama_identifier']}`: legacy={row['legacy_download_size_bytes']} "
            f"candidate={row['candidate_download_size_bytes']}"
        ),
    )
    _section(
        "Capability mismatches (sample)",
        comparison.capability_deltas,
        lambda row: f"- `{row['ollama_identifier']}`: {row['capability_changes']}",
    )
    _section(
        "Manual review items (sample)",
        comparison.manual_review_items,
        lambda row: f"- {row['kind']} `{row.get('id', '')}`: {row['reason']}",
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

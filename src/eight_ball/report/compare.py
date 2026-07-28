from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import (
    CANDIDATE_NORMALIZED_DIR,
    NORMALIZED_DIR,
    REPORTS_DIR,
)


@dataclass
class CatalogComparison:
    legacy_tag_count: int
    candidate_tag_count: int
    shared_tags: int
    legacy_only_tags: list[str]
    candidate_only_tags: list[str]
    families_compared: int
    size_deltas: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_tag_count": self.legacy_tag_count,
            "candidate_tag_count": self.candidate_tag_count,
            "shared_tags": self.shared_tags,
            "legacy_only_count": len(self.legacy_only_tags),
            "candidate_only_count": len(self.candidate_only_tags),
            "legacy_only_tags": self.legacy_only_tags[:100],
            "candidate_only_tags": self.candidate_only_tags[:100],
            "families_compared": self.families_compared,
            "size_deltas": self.size_deltas[:100],
        }


def _load_tags(path: Path) -> dict[str, dict[str, Any]]:
    return {tag["ollama_identifier"]: tag for tag in load_json(path)}


def compare_catalogs(
    *,
    legacy_dir: Path = NORMALIZED_DIR,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    family_filter: set[str] | None = None,
) -> CatalogComparison:
    legacy_tags = _load_tags(legacy_dir / "tags.json")
    candidate_tags = _load_tags(candidate_dir / "tags.json")

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

    legacy_ids = set(legacy_tags)
    candidate_ids = set(candidate_tags)
    shared = legacy_ids & candidate_ids
    legacy_only = sorted(legacy_ids - candidate_ids)
    candidate_only = sorted(candidate_ids - legacy_ids)

    size_deltas: list[dict[str, Any]] = []
    for tag_id in sorted(shared):
        legacy_size = legacy_tags[tag_id].get("download_size_bytes")
        candidate_size = candidate_tags[tag_id].get("download_size_bytes")
        if legacy_size != candidate_size:
            size_deltas.append(
                {
                    "ollama_identifier": tag_id,
                    "legacy_download_size_bytes": legacy_size,
                    "candidate_download_size_bytes": candidate_size,
                }
            )

    families = {tag_id.split(":", 1)[0] for tag_id in legacy_ids | candidate_ids}
    return CatalogComparison(
        legacy_tag_count=len(legacy_tags),
        candidate_tag_count=len(candidate_tags),
        shared_tags=len(shared),
        legacy_only_tags=legacy_only,
        candidate_only_tags=candidate_only,
        families_compared=len(families),
        size_deltas=size_deltas,
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
        f"- Families compared: {comparison.families_compared}",
        f"- Download size mismatches: {len(comparison.size_deltas)}",
        "",
    ]
    if comparison.candidate_only_tags:
        lines.extend(["## Candidate-only tags (sample)", ""])
        lines.extend(f"- `{tag}`" for tag in comparison.candidate_only_tags[:20])
        lines.append("")
    if comparison.legacy_only_tags:
        lines.extend(["## Legacy-only tags (sample)", ""])
        lines.extend(f"- `{tag}`" for tag in comparison.legacy_only_tags[:20])
        lines.append("")
    if comparison.size_deltas:
        lines.extend(["## Download size mismatches (sample)", ""])
        for row in comparison.size_deltas[:20]:
            lines.append(
                f"- `{row['ollama_identifier']}`: legacy={row['legacy_download_size_bytes']} "
                f"candidate={row['candidate_download_size_bytes']}"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

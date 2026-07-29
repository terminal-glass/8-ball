from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.collect.parse_ollama import parse_library_index
from eight_ball.config import write_json
from eight_ball.normalize.publishers import infer_publisher_id
from eight_ball.paths import (
    FIXTURES_DIR,
    LEGACY_FAMILIES_DIR,
    REPORTS_DIR,
    SAMPLE_FAMILIES,
    SNAPSHOTS_DIR,
)
from eight_ball.provenance import utc_now_iso


def resolve_library_index_path(*, fixture: bool = False, offline: bool = True) -> Path | None:
    if fixture:
        path = FIXTURES_DIR / "snapshots" / "ollama-library-index.html"
        return path if path.exists() else None
    for candidate in (
        SNAPSHOTS_DIR / "ollama-library-index.html",
        FIXTURES_DIR / "snapshots" / "ollama-library-index.html",
    ):
        if candidate.exists():
            return candidate
    if offline:
        return None
    return None


def discover_family_slugs_from_index(
    index_path: Path | None = None,
    *,
    fixture: bool = False,
    offline: bool = True,
) -> list[str]:
    path = index_path or resolve_library_index_path(fixture=fixture, offline=offline)
    if path is None:
        return []
    html = path.read_text(encoding="utf-8")
    return [entry.slug for entry in parse_library_index(html)]


def _legacy_family_slugs(families_dir: Path = LEGACY_FAMILIES_DIR) -> set[str]:
    if not families_dir.exists():
        return set()
    return {path.stem for path in families_dir.glob("*.json")}


def build_recreate_plan(
    *,
    fixture: bool = False,
    offline: bool = True,
    sample_only: bool = False,
    family_slugs: list[str] | None = None,
    index_path: Path | None = None,
) -> dict[str, Any]:
    """Build an offline recreate plan without network access.

    The plan lists which families would be collected/normalized, how they
    compare to legacy observations, and a low-noise publisher preview.
    """
    resolved_index = index_path or resolve_library_index_path(fixture=fixture, offline=offline)
    discovered = discover_family_slugs_from_index(
        resolved_index,
        fixture=fixture,
        offline=offline,
    )
    legacy = _legacy_family_slugs()

    if family_slugs:
        selected = list(family_slugs)
        selection_mode = "explicit"
    elif sample_only:
        selected = list(SAMPLE_FAMILIES)
        selection_mode = "sample"
    else:
        selected = discovered
        selection_mode = "from_index"

    selected_set = set(selected)
    index_only = sorted(selected_set - legacy)
    legacy_only = sorted(legacy - selected_set)
    shared = sorted(selected_set & legacy)

    publisher_preview: dict[str, int] = {}
    needs_review = 0
    unknown_publishers = 0
    for slug in selected:
        inference = infer_publisher_id(family_slug=slug)
        publisher_preview[inference.publisher_id] = publisher_preview.get(inference.publisher_id, 0) + 1
        if inference.publisher_id == "unknown":
            unknown_publishers += 1
        elif inference.review_status == "needs_review":
            needs_review += 1

    # Each selected family needs family page + tags page; plus one library index.
    estimated_page_fetches = 1 + (2 * len(selected))

    plan = {
        "generated_at": utc_now_iso(),
        "mode": "metadata_recreate_plan",
        "offline": offline,
        "fixture": fixture,
        "selection_mode": selection_mode,
        "index_path": str(resolved_index) if resolved_index else None,
        "index_family_count": len(discovered),
        "selected_family_count": len(selected),
        "selected_families": selected,
        "legacy_family_count": len(legacy),
        "shared_with_legacy_count": len(shared),
        "index_only_families": index_only,
        "legacy_only_families": legacy_only,
        "estimated_page_fetches": estimated_page_fetches,
        "publisher_preview": {
            "counts": dict(sorted(publisher_preview.items())),
            "unknown_publisher_count": unknown_publishers,
            "inferred_needs_review_count": needs_review,
            "notes": (
                "Preview uses slug/override inference only. "
                "Description-based text matches require collected family pages."
            ),
        },
        "safety": {
            "downloads_model_weights": False,
            "runs_ollama_pull": False,
            "writes_legacy_families": False,
            "candidate_output": "data/candidate/normalized",
            "promote_required_for_canonical": True,
        },
        "recommended_next_commands": _recommended_commands(
            selection_mode=selection_mode,
            fixture=fixture,
            offline=offline,
            selected=selected,
        ),
    }
    return plan


def _recommended_commands(
    *,
    selection_mode: str,
    fixture: bool,
    offline: bool,
    selected: list[str],
) -> list[str]:
    if selection_mode == "sample" or (fixture and selection_mode != "explicit"):
        return [
            "eight-ball all --source ollama --candidate --fixture --offline --sample",
            "eight-ball compare --sample",
            "eight-ball promote --dry-run",
        ]
    if selection_mode == "from_index" and offline:
        return [
            "eight-ball collect --source ollama --candidate --offline --from-index",
            "eight-ball normalize --source ollama --candidate --offline --from-index",
            "eight-ball validate --candidate --source ollama",
            "eight-ball compare",
            "eight-ball promote --dry-run",
        ]
    if selection_mode == "explicit":
        families = ",".join(selected[:6]) + (",..." if len(selected) > 6 else "")
        return [
            f"eight-ball all --source ollama --candidate --offline --families {families}",
            "eight-ball promote --dry-run",
        ]
    return [
        "# Live full recreate (explicit; metadata pages only):",
        "eight-ball collect --source ollama --candidate --from-index",
        "eight-ball normalize --source ollama --candidate --from-index",
        "eight-ball validate --candidate --source ollama",
        "eight-ball compare",
        "eight-ball promote --dry-run",
    ]


def write_recreate_plan(plan: dict[str, Any], output_path: Path | None = None) -> Path:
    path = output_path or (REPORTS_DIR / "candidate-collect-plan.json")
    write_json(path, plan)
    return path


def render_recreate_plan_markdown(plan: dict[str, Any]) -> str:
    publisher_counts = plan["publisher_preview"]["counts"]
    publisher_lines = "\n".join(
        f"- `{publisher_id}`: {count}" for publisher_id, count in publisher_counts.items()
    )
    index_only = plan["index_only_families"]
    legacy_only = plan["legacy_only_families"]
    commands = "\n".join(f"- `{cmd}`" for cmd in plan["recommended_next_commands"])
    return f"""# Candidate Catalog Recreate Plan

Generated: {plan["generated_at"]}

## Selection

- Mode: `{plan["selection_mode"]}`
- Index families: {plan["index_family_count"]}
- Selected families: {plan["selected_family_count"]}
- Legacy families: {plan["legacy_family_count"]}
- Shared with legacy: {plan["shared_with_legacy_count"]}
- Estimated metadata page fetches: {plan["estimated_page_fetches"]}
- Index path: `{plan["index_path"]}`

## Coverage deltas

- Index-only families ({len(index_only)}): {", ".join(f"`{slug}`" for slug in index_only[:30]) or "_none_"}{" ..." if len(index_only) > 30 else ""}
- Legacy-only families ({len(legacy_only)}): {", ".join(f"`{slug}`" for slug in legacy_only[:30]) or "_none_"}{" ..." if len(legacy_only) > 30 else ""}

## Publisher preview (low-noise)

- Unknown publishers: {plan["publisher_preview"]["unknown_publisher_count"]}
- Inferred mappings needing review: {plan["publisher_preview"]["inferred_needs_review_count"]}

{publisher_lines}

{plan["publisher_preview"]["notes"]}

## Safety

- Downloads model weights: `{plan["safety"]["downloads_model_weights"]}`
- Runs `ollama pull`: `{plan["safety"]["runs_ollama_pull"]}`
- Writes legacy families: `{plan["safety"]["writes_legacy_families"]}`
- Candidate output: `{plan["safety"]["candidate_output"]}`
- Promote required for canonical catalog: `{plan["safety"]["promote_required_for_canonical"]}`

## Recommended next commands

{commands}
"""


def write_recreate_plan_markdown(plan: dict[str, Any], output_path: Path | None = None) -> Path:
    path = output_path or (REPORTS_DIR / "candidate-collect-plan.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_recreate_plan_markdown(plan), encoding="utf-8")
    return path

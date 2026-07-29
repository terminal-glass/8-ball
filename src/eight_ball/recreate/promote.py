from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import CANDIDATE_NORMALIZED_DIR, HISTORY_DIR, NORMALIZED_DIR
from eight_ball.provenance import utc_now_iso
from eight_ball.recreate.protect import (
    assert_candidate_output_path,
    assert_not_touching_legacy_families,
    assert_promote_target_is_normalized,
)
from eight_ball.report.compare import compare_catalogs
from eight_ball.validate.catalog import ValidationError, validate_catalog

NORMALIZED_FILES = (
    "publishers.json",
    "families.json",
    "models.json",
    "tags.json",
    "capabilities.json",
    "catalog-meta.json",
)


def _catalog_version(normalized_dir: Path) -> str:
    meta_path = normalized_dir / "catalog-meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        version = meta.get("catalog_version")
        if isinstance(version, str) and version:
            return version
    return utc_now_iso()[:10]


def archive_normalized_catalog(
    *,
    source_dir: Path = NORMALIZED_DIR,
    history_dir: Path = HISTORY_DIR,
    catalog_version: str | None = None,
) -> Path:
    """Copy the current canonical normalized catalog into data/history/<version>/."""
    assert_promote_target_is_normalized(source_dir)
    version = catalog_version or _catalog_version(source_dir)
    target = history_dir / version
    if target.exists():
        stamp = utc_now_iso().replace(":", "").replace("-", "")
        target = history_dir / f"{version}.{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    for name in NORMALIZED_FILES:
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, target / name)
    write_json(
        target / "archive-meta.json",
        {
            "archived_at": utc_now_iso(),
            "source_dir": str(source_dir),
            "catalog_version": version,
            "files": [name for name in NORMALIZED_FILES if (source_dir / name).exists()],
        },
    )
    return target


def _count_entities(normalized_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, key in (
        ("publishers.json", "publishers"),
        ("families.json", "families"),
        ("models.json", "models"),
        ("tags.json", "tags"),
    ):
        path = normalized_dir / name
        if path.exists():
            payload = load_json(path)
            counts[key] = len(payload) if isinstance(payload, list) else 0
        else:
            counts[key] = 0
    return counts


def _review_counts(candidate_dir: Path) -> dict[str, int]:
    families = load_json(candidate_dir / "families.json")
    models = load_json(candidate_dir / "models.json")
    return {
        "families": sum(bool(item.get("review_reasons")) for item in families),
        "models": sum(
            item.get("validation_status") == "needs_review"
            or bool(item.get("review_reasons"))
            for item in models
        ),
    }


def _validate_candidate(candidate_dir: Path) -> dict[str, Any]:
    try:
        report = validate_catalog(
            include_artifacts=False,
            normalized_dir=candidate_dir,
        )
    except ValidationError as exc:
        return {
            "valid": False,
            "error_count": len(exc.errors),
            "warning_count": len(exc.warnings),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
    return report


def _promotion_gates(
    *,
    candidate_dir: Path,
    target_dir: Path,
    allow_review_items: bool,
    allow_removals: bool,
) -> tuple[dict[str, Any], list[str]]:
    validation = _validate_candidate(candidate_dir)
    review_counts = _review_counts(candidate_dir)
    blockers: list[str] = []

    if not validation["valid"]:
        blockers.append(
            f"candidate validation failed with {validation['error_count']} error(s)"
        )

    comparison_summary: dict[str, Any] | None = None
    if validation["valid"]:
        comparison = compare_catalogs(
            legacy_dir=target_dir,
            candidate_dir=candidate_dir,
        )
        comparison_summary = {
            "legacy_only_families": len(comparison.legacy_only_families),
            "legacy_only_models": len(comparison.legacy_only_models),
            "legacy_only_tags": len(comparison.legacy_only_tags),
            "candidate_only_families": len(comparison.candidate_only_families),
            "candidate_only_models": len(comparison.candidate_only_models),
            "candidate_only_tags": len(comparison.candidate_only_tags),
        }
        removal_count = sum(
            comparison_summary[key]
            for key in (
                "legacy_only_families",
                "legacy_only_models",
                "legacy_only_tags",
            )
        )
        if removal_count and not allow_removals:
            blockers.append(
                "candidate would remove canonical records "
                f"({comparison_summary['legacy_only_families']} families, "
                f"{comparison_summary['legacy_only_models']} models, "
                f"{comparison_summary['legacy_only_tags']} tags); "
                "review the comparison and pass --allow-removals to acknowledge"
            )

    review_count = review_counts["families"] + review_counts["models"]
    if review_count and not allow_review_items:
        blockers.append(
            "candidate has unresolved actionable review records "
            f"({review_counts['families']} families, {review_counts['models']} models); "
            "resolve them or pass --allow-review-items to acknowledge"
        )

    gates = {
        "validation": validation,
        "review_records": review_counts,
        "comparison": comparison_summary,
        "allow_review_items": allow_review_items,
        "allow_removals": allow_removals,
    }
    return gates, blockers


def _stage_promoted_catalog(candidate_dir: Path, target_dir: Path) -> Path:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=".normalized-stage-",
            dir=target_dir.parent,
        )
    )
    try:
        for name in NORMALIZED_FILES:
            shutil.copy2(candidate_dir / name, stage / name)
        promoted_meta = load_json(stage / "catalog-meta.json")
        promoted_meta["candidate"] = False
        promoted_meta["promoted_at"] = utc_now_iso()
        promoted_meta["promoted_from"] = str(candidate_dir)
        write_json(stage / "catalog-meta.json", promoted_meta)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return stage


def _replace_normalized_catalog(*, staged_dir: Path, target_dir: Path) -> None:
    rollback = target_dir.parent / f".normalized-rollback-{staged_dir.name.removeprefix('.normalized-stage-')}"
    moved_current = False
    try:
        if target_dir.exists():
            target_dir.rename(rollback)
            moved_current = True
        staged_dir.rename(target_dir)
    except Exception:
        if moved_current and rollback.exists() and not target_dir.exists():
            rollback.rename(target_dir)
        raise
    finally:
        if staged_dir.exists():
            shutil.rmtree(staged_dir, ignore_errors=True)
    if rollback.exists():
        shutil.rmtree(rollback, ignore_errors=True)


def promote_candidate_catalog(
    *,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    target_dir: Path = NORMALIZED_DIR,
    history_dir: Path = HISTORY_DIR,
    dry_run: bool = True,
    apply: bool = False,
    allow_review_items: bool = False,
    allow_removals: bool = False,
) -> dict[str, Any]:
    """Promote a reviewed candidate catalog into the canonical normalized tree.

    Default is dry-run. Apply requires dry_run=False and apply=True.
    Legacy data/families is never modified.
    """
    assert_candidate_output_path(candidate_dir)
    assert_promote_target_is_normalized(target_dir)
    assert_not_touching_legacy_families(target_dir)

    missing = [name for name in NORMALIZED_FILES if not (candidate_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Candidate catalog incomplete; missing: " + ", ".join(missing)
        )

    candidate_meta = load_json(candidate_dir / "catalog-meta.json")
    if not candidate_meta.get("candidate"):
        raise ValueError("Refusing to promote catalog that is not marked candidate=true")

    gates, blockers = _promotion_gates(
        candidate_dir=candidate_dir,
        target_dir=target_dir,
        allow_review_items=allow_review_items,
        allow_removals=allow_removals,
    )
    result: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "dry_run": dry_run or not apply,
        "applied": False,
        "eligible": not blockers,
        "candidate_dir": str(candidate_dir),
        "target_dir": str(target_dir),
        "candidate_counts": _count_entities(candidate_dir),
        "current_counts": _count_entities(target_dir),
        "candidate_version": candidate_meta.get("catalog_version"),
        "archive_path": None,
        "gates": gates,
        "blockers": blockers,
        "notes": [],
    }

    if result["dry_run"]:
        if blockers:
            result["notes"].append(
                "Dry-run blocked. Resolve or explicitly acknowledge every blocker before apply."
            )
        else:
            result["notes"].append(
                "Dry-run passed. Re-run with --apply --confirm to archive and promote."
            )
        result["notes"].append("Legacy data/families remains untouched.")
        return result

    if blockers:
        raise ValueError("Promotion blocked: " + "; ".join(blockers))

    staged_dir = _stage_promoted_catalog(candidate_dir, target_dir)
    archive_path = archive_normalized_catalog(
        source_dir=target_dir,
        history_dir=history_dir,
        catalog_version=_catalog_version(target_dir),
    )
    result["archive_path"] = str(archive_path)

    try:
        _replace_normalized_catalog(staged_dir=staged_dir, target_dir=target_dir)
    except Exception:
        shutil.rmtree(staged_dir, ignore_errors=True)
        raise

    result["applied"] = True
    result["dry_run"] = False
    result["notes"].append(f"Archived previous canonical catalog to {archive_path}")
    result["notes"].append(f"Promoted candidate catalog to {target_dir}")
    result["notes"].append("Legacy data/families remains untouched.")
    return result

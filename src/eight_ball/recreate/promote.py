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
from eight_ball.report.compare import CatalogComparison, compare_catalogs
from eight_ball.report.source_exceptions import (
    SOURCE_EXCEPTION_RETENTION_POLICY,
    known_source_exception_slugs,
)
from eight_ball.validate.catalog import ValidationError, validate_catalog

NORMALIZED_FILES = (
    "publishers.json",
    "families.json",
    "models.json",
    "tags.json",
    "capabilities.json",
    "catalog-meta.json",
)

_ENRICHMENT_REVIEW_REASONS = frozenset(
    {
        "unknown_publisher",
        "publisher_mapping_needs_review",
        "missing_family_description",
    }
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


def _review_counts(candidate_dir: Path) -> dict[str, Any]:
    families = load_json(candidate_dir / "families.json")
    models = load_json(candidate_dir / "models.json")

    def _is_enrichment_only(reasons: list[str]) -> bool:
        return bool(reasons) and all(reason in _ENRICHMENT_REVIEW_REASONS for reason in reasons)

    enrichment_families = sum(
        1 for item in families if _is_enrichment_only(list(item.get("review_reasons") or []))
    )
    enrichment_models = sum(
        1 for item in models if _is_enrichment_only(list(item.get("review_reasons") or []))
    )
    structural_families = sum(
        1
        for item in families
        if item.get("review_reasons")
        and not _is_enrichment_only(list(item.get("review_reasons") or []))
    )
    structural_models = sum(
        1
        for item in models
        if item.get("validation_status") == "needs_review"
        and not _is_enrichment_only(list(item.get("review_reasons") or []))
    )
    return {
        "enrichment_backlog": {
            "families": enrichment_families,
            "models": enrichment_models,
        },
        "structural": {
            "families": structural_families,
            "models": structural_models,
        },
        # Backward-compatible aggregate for reports that still read review_records.
        "families": enrichment_families + structural_families,
        "models": enrichment_models + structural_models,
    }


def _regrouped_legacy_model_ids(
    *,
    legacy_dir: Path,
    candidate_dir: Path,
) -> set[str]:
    legacy_models = {model["id"] for model in load_json(legacy_dir / "models.json")}
    candidate_model_ids = {model["id"] for model in load_json(candidate_dir / "models.json")}
    candidate_tag_ids = {
        tag["ollama_identifier"] for tag in load_json(candidate_dir / "tags.json")
    }
    legacy_tags = load_json(legacy_dir / "tags.json")
    regrouped: set[str] = set()
    for model_id in sorted(legacy_models - candidate_model_ids):
        model_tags = [
            tag["ollama_identifier"]
            for tag in legacy_tags
            if tag.get("model_id") == model_id
        ]
        if model_tags and all(tag_id in candidate_tag_ids for tag_id in model_tags):
            regrouped.add(model_id)
    return regrouped


def _adjusted_removal_summary(
    comparison: CatalogComparison,
    *,
    legacy_dir: Path,
    candidate_dir: Path,
    source_exception_families: set[str],
) -> dict[str, Any]:
    regrouped_models = _regrouped_legacy_model_ids(
        legacy_dir=legacy_dir,
        candidate_dir=candidate_dir,
    )
    legacy_models = load_json(legacy_dir / "models.json")
    legacy_model_families = {
        model["id"]: model.get("family_id") for model in legacy_models
    }
    retained_families = sorted(
        family
        for family in comparison.legacy_only_families
        if family in source_exception_families
    )
    retained_tags = sorted(
        tag_id
        for tag_id in comparison.legacy_only_tags
        if tag_id.split(":", 1)[0] in source_exception_families
    )
    blocking_families = [
        family
        for family in comparison.legacy_only_families
        if family not in source_exception_families
    ]
    blocking_models = [
        model_id
        for model_id in comparison.legacy_only_models
        if model_id not in regrouped_models
        and legacy_model_families.get(model_id) not in source_exception_families
    ]
    blocking_tags = [
        tag_id
        for tag_id in comparison.legacy_only_tags
        if tag_id.split(":", 1)[0] not in source_exception_families
    ]
    return {
        "source_exception_families": retained_families,
        "digest_regrouped_models": sorted(regrouped_models),
        "source_exception_tags": retained_tags,
        "blocking_removals": {
            "families": blocking_families,
            "models": blocking_models,
            "tags": blocking_tags,
        },
        "blocking_removal_count": (
            len(blocking_families) + len(blocking_models) + len(blocking_tags)
        ),
        "retention_policy": SOURCE_EXCEPTION_RETENTION_POLICY,
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
    source_exception_families = known_source_exception_slugs()
    blockers: list[str] = []

    if not validation["valid"]:
        blockers.append(
            f"candidate validation failed with {validation['error_count']} error(s)"
        )

    comparison_summary: dict[str, Any] | None = None
    adjusted_removals: dict[str, Any] | None = None
    if validation["valid"]:
        comparison = compare_catalogs(
            legacy_dir=target_dir,
            candidate_dir=candidate_dir,
        )
        adjusted_removals = _adjusted_removal_summary(
            comparison,
            legacy_dir=target_dir,
            candidate_dir=candidate_dir,
            source_exception_families=source_exception_families,
        )
        comparison_summary = {
            "legacy_only_families": len(comparison.legacy_only_families),
            "legacy_only_models": len(comparison.legacy_only_models),
            "legacy_only_tags": len(comparison.legacy_only_tags),
            "candidate_only_families": len(comparison.candidate_only_families),
            "candidate_only_models": len(comparison.candidate_only_models),
            "candidate_only_tags": len(comparison.candidate_only_tags),
            "adjusted_removals": adjusted_removals,
        }
        blocking = adjusted_removals["blocking_removals"]
        removal_count = adjusted_removals["blocking_removal_count"]
        if removal_count and not allow_removals:
            blockers.append(
                "candidate would remove canonical records "
                f"({len(blocking['families'])} families, "
                f"{len(blocking['models'])} models, "
                f"{len(blocking['tags'])} tags) after excluding source exceptions "
                "and digest regrouping; review the comparison and pass "
                "--allow-removals to acknowledge"
            )

    structural_review_count = (
        review_counts["structural"]["families"] + review_counts["structural"]["models"]
    )
    if structural_review_count and not allow_review_items:
        blockers.append(
            "candidate has unresolved structural review records "
            f"({review_counts['structural']['families']} families, "
            f"{review_counts['structural']['models']} models); "
            "resolve them or pass --allow-review-items to acknowledge"
        )

    gates = {
        "validation": validation,
        "review_records": review_counts,
        "comparison": comparison_summary,
        "allow_review_items": allow_review_items,
        "allow_removals": allow_removals,
        "source_exception_retention_policy": SOURCE_EXCEPTION_RETENTION_POLICY,
    }
    return gates, blockers


def _retain_source_exception_records(
    staged_dir: Path,
    *,
    legacy_dir: Path,
    source_exception_families: set[str],
) -> list[str]:
    if not source_exception_families:
        return []

    retained: list[str] = []
    families = load_json(staged_dir / "families.json")
    models = load_json(staged_dir / "models.json")
    tags = load_json(staged_dir / "tags.json")
    existing_family_ids = {family["id"] for family in families}
    existing_model_ids = {model["id"] for model in models}
    existing_tag_ids = {tag["ollama_identifier"] for tag in tags}

    legacy_families = {item["id"]: item for item in load_json(legacy_dir / "families.json")}
    legacy_models = {item["id"]: item for item in load_json(legacy_dir / "models.json")}
    legacy_tags = {
        item["ollama_identifier"]: item
        for item in load_json(legacy_dir / "tags.json")
    }

    for family_id in sorted(source_exception_families):
        if family_id in existing_family_ids:
            continue
        legacy_family = legacy_families.get(family_id)
        if legacy_family is None:
            continue
        legacy_family = dict(legacy_family)
        legacy_family["source_exception_retained"] = True
        families.append(legacy_family)
        retained.append(f"family:{family_id}")

    for model_id, legacy_model in sorted(legacy_models.items()):
        if legacy_model.get("family_id") not in source_exception_families:
            continue
        if model_id in existing_model_ids:
            continue
        retained_model = dict(legacy_model)
        retained_model["source_exception_retained"] = True
        models.append(retained_model)
        retained.append(f"model:{model_id}")

    for tag_id, legacy_tag in sorted(legacy_tags.items()):
        family_slug = tag_id.split(":", 1)[0]
        if family_slug not in source_exception_families:
            continue
        if tag_id in existing_tag_ids:
            continue
        retained_tag = dict(legacy_tag)
        retained_tag["source_exception_retained"] = True
        tags.append(retained_tag)
        retained.append(f"tag:{tag_id}")

    write_json(staged_dir / "families.json", families)
    write_json(staged_dir / "models.json", models)
    write_json(staged_dir / "tags.json", tags)
    return retained


def _stage_promoted_catalog(
    candidate_dir: Path,
    target_dir: Path,
    *,
    source_exception_families: set[str],
) -> Path:
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
        retained = _retain_source_exception_records(
            stage,
            legacy_dir=target_dir,
            source_exception_families=source_exception_families,
        )
        promoted_meta = load_json(stage / "catalog-meta.json")
        promoted_meta["candidate"] = False
        promoted_meta["promoted_at"] = utc_now_iso()
        promoted_meta["promoted_from"] = str(candidate_dir)
        if retained:
            promoted_meta["source_exception_retained"] = retained
            promoted_meta["source_exception_retention_policy"] = (
                SOURCE_EXCEPTION_RETENTION_POLICY
            )
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
            shutil.move(str(target_dir), str(rollback))
            moved_current = True
        shutil.move(str(staged_dir), str(target_dir))
    except Exception:
        if moved_current and rollback.exists() and not target_dir.exists():
            shutil.move(str(rollback), str(target_dir))
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
        "notes": [SOURCE_EXCEPTION_RETENTION_POLICY],
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

    staged_dir = _stage_promoted_catalog(
        candidate_dir,
        target_dir,
        source_exception_families=known_source_exception_slugs(),
    )
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

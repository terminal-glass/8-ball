from __future__ import annotations

import shutil
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


def promote_candidate_catalog(
    *,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    target_dir: Path = NORMALIZED_DIR,
    history_dir: Path = HISTORY_DIR,
    dry_run: bool = True,
    apply: bool = False,
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

    result: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "dry_run": dry_run or not apply,
        "applied": False,
        "candidate_dir": str(candidate_dir),
        "target_dir": str(target_dir),
        "candidate_counts": _count_entities(candidate_dir),
        "current_counts": _count_entities(target_dir),
        "candidate_version": candidate_meta.get("catalog_version"),
        "archive_path": None,
        "notes": [],
    }

    if result["dry_run"]:
        result["notes"].append(
            "Dry-run only. Re-run with --apply --confirm to archive and promote."
        )
        result["notes"].append("Legacy data/families remains untouched.")
        return result

    archive_path = archive_normalized_catalog(
        source_dir=target_dir,
        history_dir=history_dir,
        catalog_version=_catalog_version(target_dir),
    )
    result["archive_path"] = str(archive_path)

    target_dir.mkdir(parents=True, exist_ok=True)
    for name in NORMALIZED_FILES:
        shutil.copy2(candidate_dir / name, target_dir / name)

    # Clear candidate marker on the promoted canonical copy.
    promoted_meta = load_json(target_dir / "catalog-meta.json")
    promoted_meta["candidate"] = False
    promoted_meta["promoted_at"] = utc_now_iso()
    promoted_meta["promoted_from"] = str(candidate_dir)
    write_json(target_dir / "catalog-meta.json", promoted_meta)

    result["applied"] = True
    result["dry_run"] = False
    result["notes"].append(f"Archived previous canonical catalog to {archive_path}")
    result["notes"].append(f"Promoted candidate catalog to {target_dir}")
    result["notes"].append("Legacy data/families remains untouched.")
    return result

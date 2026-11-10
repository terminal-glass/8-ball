from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import HISTORY_DIR
from eight_ball.provenance import utc_now_iso

CHANGE_SCHEMA = "terminal-glass.8-ball.catalog-change/1"


def empty_history() -> dict[str, Any]:
    return {"schema": CHANGE_SCHEMA, "changes": []}


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_history()
    return load_json(path)


def _identifiers(normalized_dir: Path) -> set[str]:
    tags_path = normalized_dir / "tags.json"
    if not tags_path.exists():
        return set()
    return {str(tag["ollama_identifier"]) for tag in load_json(tags_path)}


def _counts(normalized_dir: Path) -> dict[str, int]:
    def _len(name: str) -> int:
        path = normalized_dir / name
        if not path.exists():
            return 0
        return len(load_json(path))

    return {
        "families": _len("families.json"),
        "models": _len("models.json"),
        "tags": _len("tags.json"),
    }


def _version(normalized_dir: Path) -> str:
    meta_path = normalized_dir / "catalog-meta.json"
    if not meta_path.exists():
        return "unknown"
    return str(load_json(meta_path).get("catalog_version") or "unknown")


def record_promotion(
    *,
    history_dir: Path = HISTORY_DIR,
    archive_path: Path,
    new_dir: Path,
) -> dict[str, Any]:
    """Append removed and added tags after a canonical promotion.

    The previous catalog stays in ``archive_path``. This log does not delete it.
    """
    previous = _identifiers(archive_path)
    current = _identifiers(new_dir)
    record = {
        "catalog_version": _version(new_dir),
        "changed_at": utc_now_iso(),
        "action": "promoted",
        "source_note": (
            f"Promoted into {new_dir.name}. Previous canonical snapshot archived at "
            f"{archive_path.name}. Public data/normalized remains the source of truth."
        ),
        "counts": _counts(new_dir),
        "removed": sorted(previous - current),
        "added": sorted(current - previous),
    }
    path = history_dir / "catalog-changes.json"
    history = load_history(path)
    history.setdefault("schema", CHANGE_SCHEMA)
    history.setdefault("changes", [])
    history["changes"].append(record)
    write_json(path, history)
    return record

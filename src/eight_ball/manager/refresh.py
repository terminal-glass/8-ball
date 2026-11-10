from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.provenance import utc_now_iso
from eight_ball.validate.catalog import ValidationError, validate_catalog

FORBIDDEN_SUFFIXES = {".gguf", ".bin", ".blob", ".safetensors"}


class RefreshRejected(Exception):
    """A snapshot was not adopted. The current catalog stays in place."""


def adopt_snapshot(
    candidate_dir: Path,
    store_dir: Path,
    metadata: dict[str, str],
) -> dict[str, Any]:
    """Validate, then atomically point current.json at the new snapshot.

    Failure leaves current.json and last-known-good.json unchanged.
    This function never installs or switches a model.
    """
    required = ("source_repository", "source_ref", "source_sha", "schema_version", "catalog_version")
    missing = [key for key in required if not metadata.get(key)]
    receipt: dict[str, Any] = {
        "source_repository": metadata.get("source_repository"),
        "source_ref": metadata.get("source_ref"),
        "source_sha": metadata.get("source_sha"),
        "schema_version": metadata.get("schema_version"),
        "catalog_version": metadata.get("catalog_version"),
        "import_time": utc_now_iso(),
        "snapshot_hash": None,
        "validation_result": "rejected",
        "install_performed": False,
        "models_switched": False,
    }
    if missing:
        receipt["errors"] = [f"missing import metadata: {', '.join(missing)}"]
        _write_rejection(store_dir, receipt)
        return {"ok": False, "current_unchanged": True, "receipt": receipt}

    payload_errors = _reject_payloads(candidate_dir)
    try:
        catalog = {
            "publishers": load_json(candidate_dir / "publishers.json"),
            "families": load_json(candidate_dir / "families.json"),
            "models": load_json(candidate_dir / "models.json"),
            "tags": load_json(candidate_dir / "tags.json"),
        }
        meta_path = candidate_dir / "catalog-meta.json"
        if meta_path.exists():
            catalog["catalog_meta"] = load_json(meta_path)
        validate_catalog(catalog, include_artifacts=False)
        validation_errors: list[str] = []
    except (OSError, ValidationError, KeyError) as exc:
        validation_errors = [str(exc)]
    errors = payload_errors + validation_errors
    snapshot_hash = _tree_hash(candidate_dir)
    receipt["snapshot_hash"] = snapshot_hash
    if errors:
        receipt["errors"] = errors
        _write_rejection(store_dir, receipt)
        return {"ok": False, "current_unchanged": True, "receipt": receipt}

    destination = store_dir / "snapshots" / snapshot_hash
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(candidate_dir, destination)
    pointer = {
        "snapshot_hash": snapshot_hash,
        "catalog_version": metadata["catalog_version"],
        "source_repository": metadata["source_repository"],
        "source_ref": metadata["source_ref"],
        "source_sha": metadata["source_sha"],
        "schema_version": metadata["schema_version"],
        "import_time": receipt["import_time"],
        "validation_result": "passed",
        "install_performed": False,
        "models_switched": False,
    }
    _atomic_json(store_dir / "current.json", pointer)
    _atomic_json(store_dir / "last-known-good.json", pointer)
    receipt["validation_result"] = "passed"
    return {"ok": True, "current_unchanged": False, "receipt": receipt, "pointer": pointer}


def current_pointer(store_dir: Path) -> dict[str, Any] | None:
    path = store_dir / "current.json"
    if not path.exists():
        return None
    return load_json(path)


def last_known_good(store_dir: Path) -> dict[str, Any] | None:
    path = store_dir / "last-known-good.json"
    if not path.exists():
        return None
    return load_json(path)


def _reject_payloads(candidate_dir: Path) -> list[str]:
    errors: list[str] = []
    if not candidate_dir.is_dir():
        return ["candidate snapshot directory is missing"]
    for path in candidate_dir.rglob("*"):
        if path.is_file() and path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            errors.append(f"snapshot contains a forbidden payload: {path.name}")
    return errors


def _tree_hash(candidate_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in candidate_dir.rglob("*") if path.is_file())
    for path in files:
        rel = path.relative_to(candidate_dir).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, payload)
    os.replace(temporary, path)


def _write_rejection(store_dir: Path, receipt: dict[str, Any]) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)
    stamp = receipt["import_time"].replace(":", "")
    _atomic_json(store_dir / "rejections" / f"{stamp}.json", receipt)

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, load_yaml, write_json
from eight_ball.paths import MANIFESTS_DIR, RAW_DIR, REPO_ROOT

PARSER_VERSION = "1.0.0"
COLLECTION_STATE_NAME = "collection-state.json"


class ManifestVerificationError(RuntimeError):
    pass


@dataclass
class SnapshotEntry:
    source_url: str
    retrieved_at: str
    http_status: int
    checksum_sha256: str
    parser_version: str
    snapshot_location: str
    content_bytes: int
    snapshot_kind: str
    family_slug: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "http_status": self.http_status,
            "checksum_sha256": self.checksum_sha256,
            "parser_version": self.parser_version,
            "snapshot_location": self.snapshot_location,
            "content_bytes": self.content_bytes,
            "snapshot_kind": self.snapshot_kind,
        }
        if self.family_slug is not None:
            payload["family_slug"] = self.family_slug
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


@dataclass
class CollectionManifest:
    collection_id: str
    entries: list[SnapshotEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "parser_version": PARSER_VERSION,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def find_entry(
        self,
        snapshot_kind: str,
        *,
        family_slug: str | None = None,
    ) -> SnapshotEntry | None:
        for entry in self.entries:
            if entry.snapshot_kind != snapshot_kind:
                continue
            if family_slug is not None and entry.family_slug != family_slug:
                continue
            return entry
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_collection_id() -> str:
    return uuid.uuid4().hex


def checksum_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def checksum_text(content: str) -> str:
    return checksum_bytes(content.encode("utf-8"))


def relative_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def resolve_repo_path(location: str) -> Path:
    path = Path(location)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def snapshot_policy() -> dict[str, Any]:
    return load_yaml(REPO_ROOT / "config" / "snapshot-policy.yaml")


def collection_state_path() -> Path:
    return RAW_DIR / COLLECTION_STATE_NAME


def begin_collection() -> CollectionManifest:
    return CollectionManifest(collection_id=new_collection_id())


def record_snapshot(
    *,
    source_url: str,
    content: str,
    http_status: int,
    snapshot_path: Path,
    snapshot_kind: str,
    family_slug: str | None = None,
    retrieved_at: str | None = None,
    notes: str | None = None,
) -> SnapshotEntry:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    snapshot_path.write_bytes(encoded)
    return SnapshotEntry(
        source_url=source_url,
        retrieved_at=retrieved_at or utc_now_iso(),
        http_status=http_status,
        checksum_sha256=checksum_bytes(encoded),
        parser_version=PARSER_VERSION,
        snapshot_location=relative_repo_path(snapshot_path),
        content_bytes=len(encoded),
        snapshot_kind=snapshot_kind,
        family_slug=family_slug,
        notes=notes,
    )


def write_manifest(manifest: CollectionManifest, *, candidate: bool = False) -> Path:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = "candidate-" if candidate else "collection-"
    path = MANIFESTS_DIR / f"{prefix}{manifest.collection_id}.json"
    write_json(path, manifest.to_dict())
    write_json(RAW_DIR / "latest-manifest.json", {"path": relative_repo_path(path), **manifest.to_dict()})
    return path


def load_manifest(path: Path) -> CollectionManifest:
    data = load_json(path)
    entries = [
        SnapshotEntry(
            source_url=item["source_url"],
            retrieved_at=item["retrieved_at"],
            http_status=item["http_status"],
            checksum_sha256=item["checksum_sha256"],
            parser_version=item["parser_version"],
            snapshot_location=item["snapshot_location"],
            content_bytes=item["content_bytes"],
            snapshot_kind=item["snapshot_kind"],
            family_slug=item.get("family_slug"),
            notes=item.get("notes"),
        )
        for item in data.get("entries", [])
    ]
    return CollectionManifest(collection_id=data["collection_id"], entries=entries)


def latest_manifest_path(*, candidate: bool = False) -> Path | None:
    prefix = "candidate-" if candidate else "collection-"
    if not MANIFESTS_DIR.exists():
        return None
    matches = sorted(MANIFESTS_DIR.glob(f"{prefix}*.json"))
    return matches[-1] if matches else None


def load_latest_manifest(*, candidate: bool = False) -> CollectionManifest:
    path = latest_manifest_path(candidate=candidate)
    if path is None:
        raise FileNotFoundError("No collection manifest found under data/manifests/")
    return load_manifest(path)


def verify_snapshot_file(path: Path, expected_checksum: str) -> None:
    if not path.exists():
        raise ManifestVerificationError(f"Snapshot missing at {path}")
    actual = checksum_bytes(path.read_bytes())
    if actual != expected_checksum:
        raise ManifestVerificationError(
            f"Checksum mismatch for {path}: expected {expected_checksum}, got {actual}"
        )


def read_verified_snapshot(entry: SnapshotEntry) -> str:
    path = resolve_repo_path(entry.snapshot_location)
    verify_snapshot_file(path, entry.checksum_sha256)
    return path.read_text(encoding="utf-8")


def load_collection_state() -> dict[str, Any]:
    path = collection_state_path()
    if not path.exists():
        return {"completed": {}}
    return load_json(path)


def save_collection_state(state: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    write_json(collection_state_path(), state)


def state_key(entry: SnapshotEntry) -> str:
    slug = entry.family_slug or "library"
    return f"{entry.snapshot_kind}:{slug}"


def mark_collection_complete(state: dict[str, Any], entry: SnapshotEntry) -> None:
    state.setdefault("completed", {})[state_key(entry)] = {
        "checksum_sha256": entry.checksum_sha256,
        "snapshot_location": entry.snapshot_location,
        "retrieved_at": entry.retrieved_at,
    }


def get_collection_state_entry(
    state: dict[str, Any],
    *,
    snapshot_kind: str,
    family_slug: str | None,
) -> dict[str, Any] | None:
    key = f"{snapshot_kind}:{family_slug or 'library'}"
    return state.get("completed", {}).get(key)


def is_collection_complete(state: dict[str, Any], *, snapshot_kind: str, family_slug: str | None) -> bool:
    return get_collection_state_entry(
        state,
        snapshot_kind=snapshot_kind,
        family_slug=family_slug,
    ) is not None


def verify_content_checksum(content: str, expected_checksum: str, *, label: str) -> None:
    actual = checksum_text(content)
    if actual != expected_checksum:
        raise ManifestVerificationError(
            f"Checksum mismatch for {label}: expected {expected_checksum}, got {actual}"
        )

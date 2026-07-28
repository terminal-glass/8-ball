from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eight_ball.config import load_yaml, write_json
from eight_ball.paths import MANIFESTS_DIR, REPO_ROOT

PARSER_VERSION = "1.0.0"


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
            "entries": [entry.to_dict() for entry in self.entries],
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def checksum_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def relative_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def snapshot_policy() -> dict[str, Any]:
    return load_yaml(REPO_ROOT / "config" / "snapshot-policy.yaml")


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
    return path


def load_manifest(path: Path) -> CollectionManifest:
    from eight_ball.config import load_json

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

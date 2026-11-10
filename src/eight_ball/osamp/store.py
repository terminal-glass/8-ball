from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.manager.secrets import write_private_file


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class HoldStore:
    """Durable local hold. Accepted commitments stay. Expired noise is dropped."""

    def __init__(self, path: Path, home: Path):
        self.path = path
        self.home = home
        self.seen_nonces: list[str] = []
        self.held: list[dict[str, Any]] = []
        self.commitments: list[dict[str, Any]] = []
        if path.exists():
            self._load(path)

    def save(self) -> None:
        payload = {
            "seen_nonces": self.seen_nonces,
            "held": self.held,
            "commitments": self.commitments,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        write_json(temporary, payload)
        write_private_file(self.path, temporary.read_bytes(), home=self.home)
        temporary.unlink(missing_ok=True)

    def remember_nonce(self, nonce: str) -> None:
        if nonce not in self.seen_nonces:
            self.seen_nonces.append(nonce)

    def drop_expired(self, now: datetime) -> None:
        self.held = [item for item in self.held if not _expired(item.get("expires_at"), now)]

    def _load(self, path: Path) -> None:
        payload = load_json(path)
        self.seen_nonces = list(payload.get("seen_nonces") or [])
        self.held = list(payload.get("held") or [])
        self.commitments = list(payload.get("commitments") or [])


def _expired(value: str | None, now: datetime) -> bool:
    if not value:
        return False
    return parse_time(value) <= now

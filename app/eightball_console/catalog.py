"""Read-only access to the 8-Ball catalog (profiles/, data/normalized/, config/)."""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


class Catalog:
    def __init__(self, root: Path, commit: str = "") -> None:
        self.root = Path(root)
        self._commit = commit

    @property
    def available(self) -> bool:
        return (self.root / "profiles").is_dir()

    @property
    def commit(self) -> str:
        if self._commit:
            return self._commit
        marker = self.root / "CATALOG_COMMIT"
        if marker.is_file():
            self._commit = marker.read_text().strip()
        elif (self.root / ".git").exists():
            try:
                self._commit = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                              capture_output=True, text=True, timeout=5).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                self._commit = ""
        return self._commit or "unknown"

    def family(self, slug: str) -> dict[str, Any] | None:
        if not _safe_slug(slug):
            return None
        p = self.root / "profiles" / slug / "model.json"
        return _load(p) if p.is_file() else None

    def sizes(self, slug: str) -> list[dict[str, Any]]:
        return list(_sizes(str(self.root), slug)) if _safe_slug(slug) else []

    def size_for_ref(self, ref: str) -> dict[str, Any] | None:
        if ":" not in ref:
            ref = ref + ":latest"
        fam = ref.split(":", 1)[0].split("/")[-1]
        for s in self.sizes(fam):
            if s.get("ollama_ref") == ref:
                return s
        return None

    def known_ref(self, ref: str) -> bool:
        return self.size_for_ref(ref) is not None


def _safe_slug(slug: str) -> bool:
    return bool(slug) and all(c.isalnum() or c in "-._" for c in slug) and not slug.startswith(".")


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


@lru_cache(maxsize=512)
def _sizes(root: str, slug: str) -> tuple[dict[str, Any], ...]:
    d = Path(root) / "profiles" / slug / "sizes"
    if not d.is_dir():
        return ()
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            doc = _load(f)
        except (OSError, ValueError):
            continue
        if doc.get("ollama_ref"):
            out.append(doc)
    return tuple(out)

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import requests

from eight_ball.config import catalog_policy, sources_config, write_json
from eight_ball.paths import RAW_DIR, REPO_ROOT, SNAPSHOTS_DIR


class CollectionError(RuntimeError):
    pass


def _request(url: str) -> requests.Response:
    policy = catalog_policy()
    headers = {"User-Agent": policy.get("user_agent", "eight-ball/0.1")}
    timeout = policy.get("request_timeout_seconds", 30)
    retries = policy.get("maximum_retries", 3)
    backoff = policy.get("retry_backoff_seconds", [2, 5, 10])
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = backoff[min(attempt, len(backoff) - 1)]
            import time

            time.sleep(delay)
    raise CollectionError(f"Failed to fetch {url}: {last_error}") from last_error


def _cache_path(url: str, suffix: str = ".html") -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return RAW_DIR / f"{digest}{suffix}"


def collect_ollama_library(*, offline: bool = False) -> dict[str, Any]:
    url = sources_config()["official_sources"]["ollama_library"]["url"]
    cache = _cache_path(url)
    snapshot = SNAPSHOTS_DIR / "ollama-library-index.html"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    if offline:
        if snapshot.exists():
            content = snapshot.read_text(encoding="utf-8")
            try:
                source = str(snapshot.relative_to(REPO_ROOT))
            except ValueError:
                source = str(snapshot)
        elif cache.exists():
            content = cache.read_text(encoding="utf-8")
            try:
                source = str(cache.relative_to(REPO_ROOT))
            except ValueError:
                source = str(cache)
        else:
            raise CollectionError(
                "Offline mode requires cached snapshot at "
                f"{snapshot} or raw cache at {cache}"
            )
    else:
        response = _request(url)
        content = response.text
        cache.write_text(content, encoding="utf-8")
        policy = catalog_policy()
        max_bytes = policy.get("maximum_source_snapshot_bytes", 2_000_000)
        if len(content.encode("utf-8")) <= max_bytes:
            snapshot.write_text(content, encoding="utf-8")
        source = url

    manifest = {
        "source_url": url,
        "retrieved_from": source,
        "content_bytes": len(content.encode("utf-8")),
        "note": "Library index snapshot stored for offline normalization tests.",
    }
    write_json(RAW_DIR / "ollama-library-manifest.json", manifest)
    return manifest


def collect_family_snapshot(
    family_slug: str,
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    url = f"https://ollama.com/library/{family_slug}"
    cache = _cache_path(url)
    snapshot = SNAPSHOTS_DIR / f"{family_slug}.html"
    if offline and fixture_dir:
        fixture = fixture_dir / "snapshots" / f"{family_slug}.html"
        if fixture.exists():
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
            return {"family_slug": family_slug, "source_url": url, "retrieved_from": str(fixture)}
    if offline:
        if snapshot.exists():
            return {"family_slug": family_slug, "source_url": url, "retrieved_from": str(snapshot)}
        raise CollectionError(f"No offline snapshot for family {family_slug}")
    response = _request(url)
    content = response.text
    cache.write_text(content, encoding="utf-8")
    policy = catalog_policy()
    if len(content.encode("utf-8")) <= policy.get("maximum_source_snapshot_bytes", 2_000_000):
        snapshot.write_text(content, encoding="utf-8")
    return {"family_slug": family_slug, "source_url": url, "bytes": len(content.encode("utf-8"))}

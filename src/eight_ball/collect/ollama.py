from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from eight_ball.collect.manifest import (
    PARSER_VERSION,
    CollectionManifest,
    record_snapshot,
    relative_repo_path,
    snapshot_policy,
    utc_now_iso,
    write_manifest,
)
from eight_ball.config import catalog_policy, sources_config, write_json
from eight_ball.paths import FIXTURES_DIR, RAW_DIR, SNAPSHOTS_DIR


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
            time.sleep(delay)
    raise CollectionError(f"Failed to fetch {url}: {last_error}") from last_error


def _cache_path(url: str, suffix: str = ".html") -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return RAW_DIR / f"{digest}{suffix}"


def _collection_id() -> str:
    return utc_now_iso().replace(":", "").replace("-", "")


def _resolve_snapshot_path(
    *,
    family_slug: str | None,
    snapshot_kind: str,
    offline: bool,
    fixture_dir: Path | None,
) -> tuple[Path, str | None]:
    if offline and fixture_dir:
        if snapshot_kind == "library_index":
            fixture_name = "ollama-library-index.html"
        elif snapshot_kind == "family_tags":
            fixture_name = f"{family_slug}-tags.html"
        else:
            fixture_name = f"{family_slug}.html"
        fixture = fixture_dir / "snapshots" / fixture_name
        if fixture.exists():
            return fixture, relative_repo_path(fixture)
    if snapshot_kind == "library_index":
        return SNAPSHOTS_DIR / "ollama-library-index.html", None
    if snapshot_kind == "family_tags":
        return SNAPSHOTS_DIR / f"{family_slug}-tags.html", None
    return SNAPSHOTS_DIR / f"{family_slug}.html", None


def _store_response(
    *,
    manifest: CollectionManifest,
    source_url: str,
    content: str,
    http_status: int,
    snapshot_path: Path,
    snapshot_kind: str,
    family_slug: str | None = None,
    retrieved_at: str | None = None,
    notes: str | None = None,
) -> None:
    cache = _cache_path(source_url)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(content, encoding="utf-8")

    policy = snapshot_policy()
    max_bytes = policy.get("maximum_ephemeral_snapshot_bytes", 2_000_000)
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes and snapshot_path.parent != FIXTURES_DIR:
        entry = record_snapshot(
            source_url=source_url,
            content=content,
            http_status=http_status,
            snapshot_path=snapshot_path,
            snapshot_kind=snapshot_kind,
            family_slug=family_slug,
            retrieved_at=retrieved_at,
            notes=notes,
        )
        manifest.entries.append(entry)
    else:
        manifest.entries.append(
            record_snapshot(
                source_url=source_url,
                content=content,
                http_status=http_status,
                snapshot_path=cache,
                snapshot_kind=snapshot_kind,
                family_slug=family_slug,
                retrieved_at=retrieved_at,
                notes=notes or "stored in raw cache only; exceeds ephemeral snapshot limit",
            )
        )


def collect_ollama_library(
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    candidate: bool = False,
) -> CollectionManifest:
    url = sources_config()["official_sources"]["ollama_library"]["url"]
    snapshot_path, fixture_source = _resolve_snapshot_path(
        family_slug=None,
        snapshot_kind="library_index",
        offline=offline,
        fixture_dir=fixture_dir,
    )
    manifest = CollectionManifest(collection_id=_collection_id())
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    if offline:
        if fixture_source and snapshot_path.exists():
            content = snapshot_path.read_text(encoding="utf-8")
            manifest.entries.append(
                record_snapshot(
                    source_url=url,
                    content=content,
                    http_status=200,
                    snapshot_path=snapshot_path,
                    snapshot_kind="library_index",
                    retrieved_at="2026-01-01T00:00:00Z",
                    notes=f"offline fixture {fixture_source}",
                )
            )
        elif snapshot_path.exists():
            content = snapshot_path.read_text(encoding="utf-8")
            manifest.entries.append(
                record_snapshot(
                    source_url=url,
                    content=content,
                    http_status=200,
                    snapshot_path=snapshot_path,
                    snapshot_kind="library_index",
                    notes="offline cached snapshot",
                )
            )
        else:
            cache = _cache_path(url)
            if not cache.exists():
                raise CollectionError(
                    "Offline mode requires cached snapshot at "
                    f"{snapshot_path} or raw cache at {cache}"
                )
            content = cache.read_text(encoding="utf-8")
            manifest.entries.append(
                record_snapshot(
                    source_url=url,
                    content=content,
                    http_status=200,
                    snapshot_path=cache,
                    snapshot_kind="library_index",
                    notes="offline raw cache",
                )
            )
    else:
        response = _request(url)
        _store_response(
            manifest=manifest,
            source_url=url,
            content=response.text,
            http_status=response.status_code,
            snapshot_path=snapshot_path,
            snapshot_kind="library_index",
        )

    write_manifest(manifest, candidate=candidate)
    write_json(
        RAW_DIR / "ollama-library-manifest.json",
        {
            "collection_id": manifest.collection_id,
            "parser_version": PARSER_VERSION,
            "entries": [entry.to_dict() for entry in manifest.entries],
        },
    )
    return manifest


def collect_family_snapshot(
    family_slug: str,
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    candidate: bool = False,
    manifest: CollectionManifest | None = None,
    include_tags_page: bool = True,
) -> CollectionManifest:
    manifest = manifest or CollectionManifest(collection_id=_collection_id())
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    pages = [("family", f"https://ollama.com/library/{family_slug}")]
    if include_tags_page:
        pages.append(("family_tags", f"https://ollama.com/library/{family_slug}/tags"))

    for snapshot_kind, url in pages:
        snapshot_path, fixture_source = _resolve_snapshot_path(
            family_slug=family_slug,
            snapshot_kind=snapshot_kind,
            offline=offline,
            fixture_dir=fixture_dir,
        )
        if offline:
            if not snapshot_path.exists():
                raise CollectionError(f"No offline snapshot for {family_slug} ({snapshot_kind})")
            content = snapshot_path.read_text(encoding="utf-8")
            manifest.entries.append(
                record_snapshot(
                    source_url=url,
                    content=content,
                    http_status=200,
                    snapshot_path=snapshot_path,
                    snapshot_kind=snapshot_kind,
                    family_slug=family_slug,
                    retrieved_at="2026-01-01T00:00:00Z" if fixture_source else None,
                    notes=f"offline fixture {fixture_source}" if fixture_source else "offline cached snapshot",
                )
            )
            continue

        response = _request(url)
        _store_response(
            manifest=manifest,
            source_url=url,
            content=response.text,
            http_status=response.status_code,
            snapshot_path=snapshot_path,
            snapshot_kind=snapshot_kind,
            family_slug=family_slug,
        )
        delay = catalog_policy().get("request_delay_seconds", 1)
        if delay:
            time.sleep(delay)

    write_manifest(manifest, candidate=candidate)
    return manifest


def collect_families(
    family_slugs: list[str],
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    candidate: bool = False,
) -> CollectionManifest:
    manifest = CollectionManifest(collection_id=_collection_id())
    for slug in family_slugs:
        collect_family_snapshot(
            slug,
            offline=offline,
            fixture_dir=fixture_dir,
            candidate=candidate,
            manifest=manifest,
        )
    write_manifest(manifest, candidate=candidate)
    return manifest

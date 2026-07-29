from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from eight_ball.collect.manifest import (
    CollectionManifest,
    begin_collection,
    get_collection_state_entry,
    load_collection_state,
    mark_collection_complete,
    record_snapshot,
    relative_repo_path,
    save_collection_state,
    snapshot_policy,
    verify_content_checksum,
    write_manifest,
)
from eight_ball.config import catalog_policy, sources_config
from eight_ball.paths import FIXTURES_DIR, RAW_DIR, SNAPSHOTS_DIR


class CollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResumedSnapshot:
    content: str
    retrieved_at: str


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


def _append_entry(
    manifest: CollectionManifest,
    *,
    source_url: str,
    content: str,
    http_status: int,
    snapshot_path: Path,
    snapshot_kind: str,
    family_slug: str | None = None,
    retrieved_at: str | None = None,
    notes: str | None = None,
    state: dict | None = None,
) -> None:
    cache = _cache_path(source_url)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(content, encoding="utf-8")

    policy = snapshot_policy()
    max_bytes = policy.get("maximum_ephemeral_snapshot_bytes", 2_000_000)
    encoded = content.encode("utf-8")
    target_path = snapshot_path
    if len(encoded) > max_bytes or snapshot_path.parent == FIXTURES_DIR:
        target_path = cache
        notes = notes or "stored in raw cache only; exceeds ephemeral snapshot limit"

    entry = record_snapshot(
        source_url=source_url,
        content=content,
        http_status=http_status,
        snapshot_path=target_path,
        snapshot_kind=snapshot_kind,
        family_slug=family_slug,
        retrieved_at=retrieved_at,
        notes=notes,
    )
    manifest.entries.append(entry)
    if state is not None:
        mark_collection_complete(state, entry)


def _should_skip_live_fetch(
    *,
    resume: bool,
    state: dict,
    snapshot_kind: str,
    family_slug: str | None,
    snapshot_path: Path,
    source_url: str,
) -> ResumedSnapshot | None:
    if not resume:
        return None
    state_entry = get_collection_state_entry(
        state,
        snapshot_kind=snapshot_kind,
        family_slug=family_slug,
    )
    if state_entry is None:
        return None

    expected_checksum = state_entry["checksum_sha256"]
    retrieved_at = state_entry["retrieved_at"]
    label = f"{snapshot_kind}:{family_slug or 'library'}"

    if snapshot_path.exists():
        content = snapshot_path.read_text(encoding="utf-8")
    else:
        cache = _cache_path(source_url)
        if not cache.exists():
            return None
        content = cache.read_text(encoding="utf-8")

    verify_content_checksum(content, expected_checksum, label=label)
    return ResumedSnapshot(content=content, retrieved_at=retrieved_at)


def collect_ollama_library(
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    candidate: bool = False,
    manifest: CollectionManifest | None = None,
    write: bool = True,
    resume: bool = False,
    state: dict | None = None,
) -> CollectionManifest:
    url = sources_config()["official_sources"]["ollama_library"]["url"]
    snapshot_path, fixture_source = _resolve_snapshot_path(
        family_slug=None,
        snapshot_kind="library_index",
        offline=offline,
        fixture_dir=fixture_dir,
    )
    manifest = manifest or begin_collection()
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    state = state if state is not None else load_collection_state()

    if offline:
        if not snapshot_path.exists():
            cache = _cache_path(url)
            if not cache.exists():
                raise CollectionError(
                    "Offline mode requires cached snapshot at "
                    f"{snapshot_path} or raw cache at {cache}"
                )
            snapshot_path = cache
        content = snapshot_path.read_text(encoding="utf-8")
        _append_entry(
            manifest,
            source_url=url,
            content=content,
            http_status=200,
            snapshot_path=snapshot_path,
            snapshot_kind="library_index",
            retrieved_at="2026-01-01T00:00:00Z" if fixture_source else None,
            notes=f"offline fixture {fixture_source}" if fixture_source else "offline cached snapshot",
            state=state,
        )
    else:
        resumed = _should_skip_live_fetch(
            resume=resume,
            state=state,
            snapshot_kind="library_index",
            family_slug=None,
            snapshot_path=snapshot_path,
            source_url=url,
        )
        if resumed is not None:
            content = resumed.content
            http_status = 200
            notes = "resume: reused cached snapshot"
            retrieved_at = resumed.retrieved_at
        else:
            response = _request(url)
            content = response.text
            http_status = response.status_code
            notes = None
            retrieved_at = None
        _append_entry(
            manifest,
            source_url=url,
            content=content,
            http_status=http_status,
            snapshot_path=snapshot_path,
            snapshot_kind="library_index",
            retrieved_at=retrieved_at,
            notes=notes,
            state=state,
        )

    if write:
        write_manifest(manifest, candidate=candidate)
        save_collection_state(state)
    return manifest


def collect_family_snapshot(
    family_slug: str,
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    manifest: CollectionManifest | None = None,
    include_tags_page: bool = True,
    write: bool = False,
    resume: bool = False,
    state: dict | None = None,
) -> CollectionManifest:
    manifest = manifest or begin_collection()
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    state = state if state is not None else load_collection_state()

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
            _append_entry(
                manifest,
                source_url=url,
                content=content,
                http_status=200,
                snapshot_path=snapshot_path,
                snapshot_kind=snapshot_kind,
                family_slug=family_slug,
                retrieved_at="2026-01-01T00:00:00Z" if fixture_source else None,
                notes=f"offline fixture {fixture_source}" if fixture_source else "offline cached snapshot",
                state=state,
            )
            continue

        resumed = _should_skip_live_fetch(
            resume=resume,
            state=state,
            snapshot_kind=snapshot_kind,
            family_slug=family_slug,
            snapshot_path=snapshot_path,
            source_url=url,
        )
        if resumed is not None:
            content = resumed.content
            http_status = 200
            notes = "resume: reused cached snapshot"
            retrieved_at = resumed.retrieved_at
        else:
            response = _request(url)
            content = response.text
            http_status = response.status_code
            notes = None
            retrieved_at = None
        _append_entry(
            manifest,
            source_url=url,
            content=content,
            http_status=http_status,
            snapshot_path=snapshot_path,
            snapshot_kind=snapshot_kind,
            family_slug=family_slug,
            retrieved_at=retrieved_at,
            notes=notes,
            state=state,
        )
        delay = catalog_policy().get("request_delay_seconds", 1)
        if delay:
            time.sleep(delay)

    if write:
        save_collection_state(state)
    return manifest


def collect_families(
    family_slugs: list[str],
    *,
    offline: bool = False,
    fixture_dir: Path | None = None,
    candidate: bool = False,
    manifest: CollectionManifest | None = None,
    resume: bool = False,
    state: dict | None = None,
) -> CollectionManifest:
    manifest = manifest or begin_collection()
    state = state if state is not None else load_collection_state()
    for slug in family_slugs:
        collect_family_snapshot(
            slug,
            offline=offline,
            fixture_dir=fixture_dir,
            manifest=manifest,
            resume=resume,
            state=state,
        )
    write_manifest(manifest, candidate=candidate)
    save_collection_state(state)
    return manifest

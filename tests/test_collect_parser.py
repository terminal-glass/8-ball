from __future__ import annotations

from pathlib import Path

from eight_ball.collect.manifest import checksum_bytes
from eight_ball.collect.parse_ollama import (
    parse_family_tags_page,
    parse_library_index,
)
from eight_ball.normalize.ollama_web import normalize_ollama_snapshots

FIXTURE_SNAPSHOTS = Path("tests/fixtures/snapshots")


def test_parse_library_index_fixture():
    html = (FIXTURE_SNAPSHOTS / "ollama-library-index.html").read_text(encoding="utf-8")
    entries = parse_library_index(html)
    slugs = {entry.slug for entry in entries}
    assert "tinyllama" in slugs
    assert "llama3" in slugs
    assert len(entries) >= 200


def test_parse_family_tags_fixture_tinyllama():
    html = (FIXTURE_SNAPSHOTS / "tinyllama-tags.html").read_text(encoding="utf-8")
    tags = parse_family_tags_page(html, "tinyllama")
    assert len(tags) == 36
    identifiers = {tag.ollama_identifier for tag in tags}
    assert "tinyllama:latest" in identifiers
    assert "tinyllama:1.1b-chat-v0.6-q4_K_M" in identifiers
    latest = next(tag for tag in tags if tag.ollama_identifier == "tinyllama:latest")
    assert latest.download_size_bytes == 638_000_000
    assert latest.context_window_tokens == 2000
    assert latest.is_latest is True


def test_parse_family_tags_fixture_llama3_has_multiple_models():
    html = (FIXTURE_SNAPSHOTS / "llama3-tags.html").read_text(encoding="utf-8")
    tags = parse_family_tags_page(html, "llama3")
    assert len(tags) >= 60
    param_labels = {tag.parameter_label for tag in tags if tag.parameter_label}
    assert "8b" in param_labels
    assert "70b" in param_labels


def test_normalize_ollama_snapshots_writes_candidate_catalog(tmp_path, monkeypatch):
    from eight_ball.config import load_json

    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_snapshots(
        family_slugs=["tinyllama", "llama3"],
        snapshot_dir=FIXTURE_SNAPSHOTS,
        retrieved_at="2026-07-28T12:00:00Z",
    )
    assert catalog["families"][0]["id"] == "tinyllama"
    assert len(catalog["tags"]) > 0

    models = load_json(candidate_dir / "models.json")
    families = {model["family_id"] for model in models}
    assert "llama3" in families
    llama3_models = [model for model in models if model["family_id"] == "llama3"]
    assert len(llama3_models) >= 2

    meta = load_json(candidate_dir / "catalog-meta.json")
    assert meta["candidate"] is True
    assert meta["source"] == "ollama_web"


def test_snapshot_checksum_is_stable():
    content = (FIXTURE_SNAPSHOTS / "tinyllama.html").read_bytes()
    assert checksum_bytes(content) == checksum_bytes(content)


def test_manifest_fixture_pipeline_offline(tmp_path, monkeypatch):
    from eight_ball.collect.ollama import collect_families, collect_ollama_library

    snapshots = tmp_path / "snapshots"
    manifests = tmp_path / "manifests"
    snapshots.mkdir()
    manifests.mkdir()
    monkeypatch.setattr("eight_ball.collect.ollama.SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr("eight_ball.collect.manifest.MANIFESTS_DIR", manifests)

    for name in ["ollama-library-index.html", "tinyllama.html", "tinyllama-tags.html"]:
        target = snapshots / name
        target.write_text((FIXTURE_SNAPSHOTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    collect_ollama_library(offline=True, fixture_dir=FIXTURE_SNAPSHOTS, candidate=True)
    manifest = collect_families(
        ["tinyllama"],
        offline=True,
        fixture_dir=FIXTURE_SNAPSHOTS,
        candidate=True,
    )
    assert manifest.entries
    assert all(entry.checksum_sha256 for entry in manifest.entries)
    assert all(entry.parser_version for entry in manifest.entries)


def test_gemini_fixture_is_cloud_family():
    from eight_ball.collect.parse_ollama import parse_family_page

    family = parse_family_page(
        (FIXTURE_SNAPSHOTS / "gemini-3-flash-preview.html").read_text(encoding="utf-8"),
        "gemini-3-flash-preview",
    )
    tags = parse_family_tags_page(
        (FIXTURE_SNAPSHOTS / "gemini-3-flash-preview-tags.html").read_text(encoding="utf-8"),
        "gemini-3-flash-preview",
    )
    assert family.is_cloud_family is True
    assert tags[0].download_size_bytes is None


def test_compare_sample_families(tmp_path, monkeypatch):
    from eight_ball.report.compare import compare_catalogs

    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.compare.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    normalize_ollama_snapshots(
        family_slugs=["tinyllama"],
        snapshot_dir=FIXTURE_SNAPSHOTS,
        retrieved_at="2026-07-28T12:00:00Z",
    )
    comparison = compare_catalogs(
        candidate_dir=candidate_dir,
        family_filter={"tinyllama"},
    )
    assert comparison.candidate_tag_count == 36
    assert comparison.shared_tags > 0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eight_ball.collect.manifest import (
    CollectionManifest,
    SnapshotEntry,
    begin_collection,
    load_manifest,
    verify_snapshot_file,
)
from eight_ball.collect.ollama import collect_families, collect_ollama_library
from eight_ball.collect.parse_ollama import ParseError, parse_family_tags_page
from eight_ball.normalize.ollama_web import (
    _input_capabilities_to_legacy,
    _resolve_model_id_map,
    normalize_ollama_from_manifest,
    normalize_ollama_snapshots,
)
from eight_ball.normalize.parse import parse_size_text_to_bytes
from eight_ball.report.compare import compare_catalogs

FIXTURE_SNAPSHOTS = Path("tests/fixtures/snapshots")
FIXTURE_MANIFEST = Path("tests/fixtures/manifests/six-family-sample.json")


def test_parse_size_4_1gb_decimal():
    assert parse_size_text_to_bytes("4.1GB") == 4_100_000_000


def test_text_input_does_not_map_to_tools():
    from eight_ball.collect.parse_ollama import ParsedTag
    from eight_ball.normalize.legacy import map_capabilities

    tags = [
        ParsedTag(
            ollama_identifier="tinyllama:latest",
            family_slug="tinyllama",
            tag_suffix="latest",
            input_capabilities=["Text"],
        )
    ]
    legacy_tokens = _input_capabilities_to_legacy(tags)
    assert "tools" not in legacy_tokens
    assert "text" in legacy_tokens
    caps = map_capabilities(legacy_tokens)
    assert caps["tool_use"] != "true"
    assert caps["text_generation"] == "true"


def test_latest_alias_merges_into_parameter_model():
    from eight_ball.collect.parse_ollama import ParsedTag, apply_alias_targets

    tags = [
        ParsedTag(
            ollama_identifier="tinyllama:latest",
            family_slug="tinyllama",
            tag_suffix="latest",
            digest="abc123456789",
            is_latest=True,
        ),
        ParsedTag(
            ollama_identifier="tinyllama:1.1b",
            family_slug="tinyllama",
            tag_suffix="1.1b",
            digest="abc123456789",
            parameter_label="1.1b",
        ),
    ]
    apply_alias_targets(tags)
    model_map = _resolve_model_id_map("tinyllama", tags)
    assert model_map["tinyllama:latest"] == model_map["tinyllama:1.1b"]
    assert model_map["tinyllama:latest"] == "tinyllama-1.1b"


def test_parse_malformed_tags_page_raises():
    html = (FIXTURE_SNAPSHOTS / "malformed-tags.html").read_text(encoding="utf-8")
    with pytest.raises(ParseError, match="zero tag records"):
        parse_family_tags_page(html, "malformed")


def test_shared_manifest_preserves_library_index(tmp_path, monkeypatch):
    snapshots = tmp_path / "snapshots"
    manifests = tmp_path / "manifests"
    snapshots.mkdir()
    manifests.mkdir()
    monkeypatch.setattr("eight_ball.collect.ollama.SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr("eight_ball.collect.manifest.MANIFESTS_DIR", manifests)

    for name in ["ollama-library-index.html", "tinyllama.html", "tinyllama-tags.html"]:
        target = snapshots / name
        target.write_text((FIXTURE_SNAPSHOTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    manifest = begin_collection()
    collect_ollama_library(
        offline=True,
        fixture_dir=Path("tests/fixtures"),
        candidate=True,
        manifest=manifest,
        write=False,
    )
    collect_families(
        ["tinyllama"],
        offline=True,
        fixture_dir=Path("tests/fixtures"),
        candidate=True,
        manifest=manifest,
    )
    kinds = {entry.snapshot_kind for entry in manifest.entries}
    assert "library_index" in kinds
    assert "family" in kinds
    assert "family_tags" in kinds
    assert len(manifest.entries) == 3


def test_normalize_from_manifest_verifies_checksums(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_from_manifest(
        FIXTURE_MANIFEST,
        family_slugs=["tinyllama"],
    )
    assert catalog["families"][0]["retrieved_at"] == "2026-01-01T00:00:00Z"
    models = json.loads((candidate_dir / "models.json").read_text(encoding="utf-8"))
    tinyllama_models = [model for model in models if model["family_id"] == "tinyllama"]
    assert len(tinyllama_models) == 1
    assert tinyllama_models[0]["id"] == "tinyllama-1.1b"


def test_manifest_checksum_mismatch_raises(tmp_path):
    manifest = CollectionManifest(
        collection_id="test",
        entries=[
            SnapshotEntry(
                source_url="https://example.com",
                retrieved_at="2026-01-01T00:00:00Z",
                http_status=200,
                checksum_sha256="0" * 64,
                parser_version="1.0.0",
                snapshot_location="tests/fixtures/snapshots/tinyllama.html",
                content_bytes=1,
                snapshot_kind="family",
                family_slug="tinyllama",
            )
        ],
    )
    entry = manifest.entries[0]
    with pytest.raises(Exception, match="Checksum mismatch"):
        verify_snapshot_file(Path(entry.snapshot_location), entry.checksum_sha256)


def test_compare_includes_capability_and_model_deltas(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.compare.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    normalize_ollama_snapshots(
        family_slugs=["tinyllama"],
        snapshot_dir=FIXTURE_SNAPSHOTS,
        retrieved_at="2026-07-28T12:00:00Z",
    )
    comparison = compare_catalogs(candidate_dir=candidate_dir, family_filter={"tinyllama"})
    payload = comparison.to_dict()
    assert "capability_deltas" in payload
    assert "legacy_only_models" in payload
    assert "manual_review_items" in payload
    assert len(payload["legacy_only_tags"]) == len(comparison.legacy_only_tags)


def test_cli_normalize_ollama_requires_family_selection():
    from eight_ball.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["normalize", "--source", "ollama"])
    assert exc.value.code == 2


def test_fixture_manifest_includes_library_index():
    manifest = load_manifest(FIXTURE_MANIFEST)
    assert manifest.find_entry("library_index") is not None
    assert len(manifest.entries) == 13

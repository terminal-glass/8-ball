from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.normalize.ollama_web import normalize_ollama_from_manifest
from eight_ball.report.reconcile import (
    build_candidate_mapping,
    discover_source_exceptions,
    reconcile_candidate_catalog,
    write_reconciliation_reports,
)

FIXTURE_MANIFEST = Path("tests/fixtures/manifests/six-family-sample.json")


def test_build_candidate_mapping_groups_models_and_tags(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama", "llama3"])

    mapping = build_candidate_mapping(
        candidate_dir=candidate_dir,
        manifest=__import__("eight_ball.collect.manifest", fromlist=["load_manifest"]).load_manifest(
            FIXTURE_MANIFEST
        ),
    )
    assert mapping.normalized_family_count == 2
    assert mapping.tag_count > 0
    assert mapping.model_count > 0
    tinyllama = next(row for row in mapping.families if row["family_id"] == "tinyllama")
    assert tinyllama["model_count"] >= 1
    assert tinyllama["tag_count"] >= 1
    assert all("model_id" in model for model in tinyllama["models"])
    assert all("tags" in model for model in tinyllama["models"])


def test_discover_source_exceptions_flags_parse_failures(tmp_path, monkeypatch):
    from eight_ball.collect.manifest import CollectionManifest, SnapshotEntry, load_manifest

    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    catalog = normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    manifest = load_manifest(FIXTURE_MANIFEST)
    exceptions = discover_source_exceptions(
        manifest,
        normalized_family_ids={family["id"] for family in catalog["families"]},
    )
    # Collected families with valid snapshots but not normalized should not be parse failures.
    assert all(item["family_slug"] != "llama3" for item in exceptions)

    malformed = CollectionManifest(
        collection_id="malformed",
        entries=[
            SnapshotEntry(
                source_url="https://ollama.com/library/malformed",
                retrieved_at="2026-01-01T00:00:00Z",
                http_status=200,
                checksum_sha256=__import__(
                    "eight_ball.collect.manifest", fromlist=["checksum_text"]
                ).checksum_text(
                    Path("tests/fixtures/snapshots/malformed-tags.html").read_text(encoding="utf-8")
                ),
                parser_version="1.0.0",
                snapshot_location="tests/fixtures/snapshots/malformed-tags.html",
                content_bytes=1,
                snapshot_kind="family",
                family_slug="malformed",
            ),
            SnapshotEntry(
                source_url="https://ollama.com/library/malformed/tags",
                retrieved_at="2026-01-01T00:00:00Z",
                http_status=200,
                checksum_sha256=__import__(
                    "eight_ball.collect.manifest", fromlist=["checksum_text"]
                ).checksum_text(
                    Path("tests/fixtures/snapshots/malformed-tags.html").read_text(encoding="utf-8")
                ),
                parser_version="1.0.0",
                snapshot_location="tests/fixtures/snapshots/malformed-tags.html",
                content_bytes=1,
                snapshot_kind="family_tags",
                family_slug="malformed",
            ),
        ],
    )
    malformed_exceptions = discover_source_exceptions(malformed, normalized_family_ids=set())
    assert len(malformed_exceptions) == 1
    assert malformed_exceptions[0]["reason"] == "static_html_parse_failure"


def test_reconcile_classifies_legacy_only_models_as_regrouping_not_absence(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    legacy_dir = tmp_path / "legacy" / "normalized"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", legacy_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.REPORTS_DIR", reports_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    legacy_dir.mkdir(parents=True)
    for name in ("families.json", "models.json", "tags.json", "catalog-meta.json"):
        source = Path("data/normalized") / name
        target = legacy_dir / name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        legacy_dir=legacy_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    assert report.legacy_comparison["legacy_only_models"] > 0
    assert report.legacy_comparison["legacy_only_models_likely_regrouped"] > 0
    assert "disposition_counts" in report.legacy_comparison
    paths = write_reconciliation_reports(report, output_dir=reports_dir)
    assert paths["markdown"].exists()
    assert paths["review_queue"].exists()
    assert paths["source_exceptions"].exists()


def test_reconcile_includes_configured_source_exceptions(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", Path("data/normalized"))
    monkeypatch.setattr("eight_ball.report.reconcile.REPORTS_DIR", reports_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    slugs = {item["family_slug"] for item in report.source_exceptions}
    assert "kimi-k2.5" in slugs
    assert "minimax-m2.5" in slugs


def test_reconcile_requires_manifest_or_latest_pointer(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.RAW_DIR", tmp_path / "raw")
    with pytest.raises(FileNotFoundError):
        reconcile_candidate_catalog(candidate_dir=candidate_dir)

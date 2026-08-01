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
    assert mapping.parseable_source_families == 2
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
    assert report.legacy_model_evidence["legacy_only_model_count"] > 0
    assert report.legacy_model_evidence["explained_by_digest_regrouping"] > 0
    assert report.legacy_comparison["disposition_counts"]["regrouped"] > 0
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


def test_reconcile_includes_promotion_review_and_grouping_integrity(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", Path("data/normalized"))
    monkeypatch.setattr("eight_ball.report.reconcile.REPORTS_DIR", reports_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama", "llama3"])
    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    assert report.collection_stats["snapshot_count"] > 0
    assert report.grouping_integrity["valid"] is True
    assert report.grouping_integrity["deployment_variant_tags"] > 0
    assert report.promotion_review["eligible"] is False
    assert report.promotion_review["blocker_interpretations"]
    assert report.live_counts["normalized_candidate_families"] > 0
    assert len(report.candidate_only_items) >= 0
    assert "candidate_only_new_live" in report.classified_items
    kinds = {item["kind"] for item in report.review_queue}
    assert "source_exception" in kinds
    assert "publisher_mapping" not in kinds
    paths = write_reconciliation_reports(report, output_dir=reports_dir)
    assert paths["promotion_review"].exists()


def test_reconcile_requires_manifest_or_latest_pointer(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.RAW_DIR", tmp_path / "raw")
    with pytest.raises(FileNotFoundError):
        reconcile_candidate_catalog(candidate_dir=candidate_dir)


def test_live_count_contract_uses_distinct_inventory_fields(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", Path("data/normalized"))

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    counts = report.live_counts
    assert counts["source_indexed_families"] >= counts["parseable_source_families"]
    assert counts["source_exception_families"] == len(report.source_exceptions)
    assert counts["source_indexed_families"] == report.collection_stats["source_indexed_families"]
    assert counts["normalized_candidate_families"] == counts["parseable_source_families"]
    assert counts["tags"] > 0
    assert counts["deployment_combinations"] > 0
    assert "index_families" not in counts


def test_regrouping_evidence_totals_align_with_dispositions(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    legacy_dir = tmp_path / "legacy" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", legacy_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    legacy_dir.mkdir(parents=True)
    for name in ("families.json", "models.json", "tags.json", "catalog-meta.json"):
        target = legacy_dir / name
        target.write_text((Path("data/normalized") / name).read_text(encoding="utf-8"), encoding="utf-8")

    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        legacy_dir=legacy_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    evidence = report.legacy_model_evidence
    dispositions = report.legacy_comparison["disposition_counts"]
    assert dispositions["regrouped"] == len(report.regrouped_items)
    assert evidence["legacy_only_model_count"] == (
        evidence["explained_by_digest_regrouping"]
        + evidence["explained_by_source_exception"]
        + evidence["unexplained_model_count"]
    )


def test_source_exception_retention_policy_documented(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", Path("data/normalized"))

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    slugs = {item["family_slug"] for item in report.source_exceptions}
    assert slugs >= {"kimi-k2.5", "minimax-m2.5"}
    assert report.to_dict()["source_exception_retention_policy"]
    assert all(
        item["disposition"] == "source_unparseable"
        for item in report.source_exceptions
        if item["family_slug"] in {"kimi-k2.5", "minimax-m2.5"}
    )


def test_publisher_enrichment_backlog_does_not_block_promotion(tmp_path, monkeypatch):
    from eight_ball.config import write_json

    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.reconcile.NORMALIZED_DIR", Path("data/normalized"))

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])
    families = __import__("eight_ball.config", fromlist=["load_json"]).load_json(
        candidate_dir / "families.json"
    )
    families[0]["review_reasons"] = ["publisher_mapping_needs_review"]
    write_json(candidate_dir / "families.json", families)
    models = __import__("eight_ball.config", fromlist=["load_json"]).load_json(
        candidate_dir / "models.json"
    )
    for model in models:
        model["review_reasons"] = ["publisher_mapping_needs_review"]
        model["validation_status"] = "valid"
    write_json(candidate_dir / "models.json", models)

    report = reconcile_candidate_catalog(
        candidate_dir=candidate_dir,
        manifest_path=FIXTURE_MANIFEST,
    )
    assert report.enrichment_backlog
    assert not any(
        "unresolved actionable review records" in blocker
        for blocker in report.promotion_review.get("blockers", [])
    )
    assert not any(
        "unresolved structural review records" in blocker
        for blocker in report.promotion_review.get("blockers", [])
    )

from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.collect.manifest import (
    checksum_text,
    verify_content_checksum,
)
from eight_ball.collect.ollama import ResumedSnapshot, _should_skip_live_fetch
from eight_ball.collect.parse_ollama import ParseError, parse_library_index
from eight_ball.normalize.ollama_web import normalize_ollama_from_manifest
from eight_ball.normalize.publishers import infer_publisher_id
from eight_ball.report.compare import compare_catalogs

FIXTURE_SNAPSHOTS = Path("tests/fixtures/snapshots")
FIXTURE_MANIFEST = Path("tests/fixtures/manifests/six-family-sample.json")


def test_parse_empty_library_index_raises():
    html = (FIXTURE_SNAPSHOTS / "malformed-index.html").read_text(encoding="utf-8")
    with pytest.raises(ParseError, match="zero family records"):
        parse_library_index(html)


def test_resume_verifies_checksum(tmp_path):
    snapshot_path = tmp_path / "tinyllama.html"
    content = "<html>cached</html>"
    snapshot_path.write_text(content, encoding="utf-8")
    state = {
        "completed": {
            "family:tinyllama": {
                "checksum_sha256": checksum_text(content),
                "snapshot_location": str(snapshot_path),
                "retrieved_at": "2026-01-01T00:00:00Z",
            }
        }
    }
    resumed = _should_skip_live_fetch(
        resume=True,
        state=state,
        snapshot_kind="family",
        family_slug="tinyllama",
        snapshot_path=snapshot_path,
        source_url="https://ollama.com/library/tinyllama",
    )
    assert isinstance(resumed, ResumedSnapshot)
    assert resumed.content == content
    assert resumed.retrieved_at == "2026-01-01T00:00:00Z"


def test_resume_checksum_mismatch_raises(tmp_path):
    snapshot_path = tmp_path / "tinyllama.html"
    snapshot_path.write_text("<html>tampered</html>", encoding="utf-8")
    state = {
        "completed": {
            "family:tinyllama": {
                "checksum_sha256": "0" * 64,
                "snapshot_location": str(snapshot_path),
                "retrieved_at": "2026-01-01T00:00:00Z",
            }
        }
    }
    with pytest.raises(Exception, match="Checksum mismatch"):
        _should_skip_live_fetch(
            resume=True,
            state=state,
            snapshot_kind="family",
            family_slug="tinyllama",
            snapshot_path=snapshot_path,
            source_url="https://ollama.com/library/tinyllama",
        )


def test_verify_content_checksum_helper():
    content = "fixture"
    digest = checksum_text(content)
    verify_content_checksum(content, digest, label="fixture")
    with pytest.raises(Exception, match="Checksum mismatch"):
        verify_content_checksum("changed", digest, label="fixture")


def test_publisher_inference_for_sample_families():
    assert infer_publisher_id(family_slug="llama3").publisher_id == "meta"
    assert infer_publisher_id(family_slug="codestral").publisher_id == "mistral-ai"
    assert infer_publisher_id(family_slug="gemini-3-flash-preview").publisher_id == "google"
    assert infer_publisher_id(family_slug="nomic-embed-text").publisher_id == "nomic-ai"
    assert infer_publisher_id(family_slug="llava").publisher_id == "llava-project"


def test_candidate_catalog_has_catalog_source_and_publishers(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_from_manifest(
        FIXTURE_MANIFEST,
        family_slugs=["llama3", "llava", "nomic-embed-text"],
    )
    assert catalog["catalog_source_id"] == "ollama-library"
    publisher_ids = {publisher["id"] for publisher in catalog["publishers"]}
    assert "ollama-library" not in publisher_ids
    assert {"meta", "llava-project", "nomic-ai"} <= publisher_ids

    families = {family["id"]: family for family in catalog["families"]}
    assert families["llama3"]["catalog_source_id"] == "ollama-library"
    assert families["llama3"]["publisher_id"] == "meta"
    assert "provenance" in families["llama3"]

    tags = catalog["tags"]
    llama_tag = next(tag for tag in tags if tag["ollama_identifier"] == "llama3:latest")
    assert "capabilities" in llama_tag
    assert "context_window_tokens" in llama_tag["provenance"]
    assert llama_tag["provenance"]["capabilities"]["confidence"] == "derived"


def test_tag_capabilities_refine_family_defaults(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_from_manifest(
        FIXTURE_MANIFEST,
        family_slugs=["llava"],
    )
    family = next(item for item in catalog["families"] if item["id"] == "llava")
    tag = next(item for item in catalog["tags"] if item["ollama_identifier"] == "llava:latest")
    assert family["primary_capabilities"].get("vision") == "true"
    assert tag["capabilities"].get("vision") == "true"


def test_compare_manual_review_items_are_deduplicated(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    monkeypatch.setattr("eight_ball.report.compare.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama", "llama3"])
    comparison = compare_catalogs(family_filter={"tinyllama", "llama3"})
    model_items = [item for item in comparison.manual_review_items if item["kind"] == "model"]
    model_ids = [item["id"] for item in model_items]
    assert len(model_ids) == len(set(model_ids))
    assert len(model_items) < comparison.candidate_tag_count

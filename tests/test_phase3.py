from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.collect.manifest import (
    checksum_text,
)
from eight_ball.collect.ollama import ResumedSnapshot, _should_skip_live_fetch
from eight_ball.collect.parse_ollama import ParsedTag, ParseError, parse_library_index
from eight_ball.normalize.ollama_web import (
    build_candidate_catalog,
    normalize_ollama_from_manifest,
    normalize_ollama_snapshots,
)
from eight_ball.normalize.publishers import infer_publisher_id, slug_token_match
from eight_ball.report.compare import compare_catalogs
from eight_ball.validate.catalog import ValidationError, validate_catalog

FIXTURE_SNAPSHOTS = Path("tests/fixtures/snapshots")
FIXTURE_MANIFEST = Path("tests/fixtures/manifests/six-family-sample.json")


def test_parse_empty_library_index_raises():
    html = (FIXTURE_SNAPSHOTS / "malformed-index.html").read_text(encoding="utf-8")
    with pytest.raises(ParseError, match="zero family records"):
        parse_library_index(html)


def test_slug_token_match_rejects_false_positives():
    assert slug_token_match("llama3", "llama3")
    assert not slug_token_match("llamax", "llama")
    assert not slug_token_match("philosopher", "phi")
    assert not slug_token_match("mistrallite", "mistral")
    assert infer_publisher_id(family_slug="llamax").publisher_id == "unknown"
    assert infer_publisher_id(family_slug="philosopher").publisher_id == "unknown"
    assert infer_publisher_id(family_slug="mistrallite").publisher_id == "unknown"


def test_slug_token_match_allows_digit_glued_versions():
    assert slug_token_match("phi3", "phi")
    assert slug_token_match("phi4-mini", "phi")
    assert slug_token_match("gemma2", "gemma")
    assert slug_token_match("granite3.1-dense", "granite")
    assert slug_token_match("dolphin3", "dolphin")


def test_digit_glued_official_slugs_infer_publishers_needing_review():
    phi3 = infer_publisher_id(family_slug="phi3")
    assert phi3.publisher_id == "microsoft"
    assert phi3.method == "slug_prefix"
    assert phi3.review_status == "needs_review"

    gemma2 = infer_publisher_id(family_slug="gemma2")
    assert gemma2.publisher_id == "google"
    assert gemma2.review_status == "needs_review"

    granite = infer_publisher_id(family_slug="granite3-moe")
    assert granite.publisher_id == "ibm"
    assert granite.review_status == "needs_review"

    assert infer_publisher_id(family_slug="codegemma").publisher_id == "google"
    assert infer_publisher_id(family_slug="devstral").publisher_id == "mistral-ai"
    assert infer_publisher_id(family_slug="llama-guard3").publisher_id == "meta"


def test_community_slug_blocks_base_publisher_inference():
    assert infer_publisher_id(family_slug="dolphin-llama3").publisher_id == "unknown"
    assert infer_publisher_id(family_slug="dolphin3").publisher_id == "unknown"


def test_derivative_markers_block_base_publisher_inference():
    assert infer_publisher_id(family_slug="mistral-openorca").publisher_id == "unknown"
    assert infer_publisher_id(family_slug="llama2-uncensored").publisher_id == "unknown"
    assert infer_publisher_id(family_slug="llama3-chatqa").publisher_id == "unknown"


def test_bare_text_name_drops_do_not_assign_publishers():
    assert (
        infer_publisher_id(
            family_slug="cogito",
            description="Based on Qwen architecture",
        ).publisher_id
        == "unknown"
    )
    assert (
        infer_publisher_id(
            family_slug="acme",
            description="uses granite backbone",
        ).publisher_id
        == "unknown"
    )
    assert (
        infer_publisher_id(
            family_slug="demo",
            description="Microsoft Phi research release",
        ).publisher_id
        == "microsoft"
    )


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


def test_publisher_inference_for_sample_families():
    llama3 = infer_publisher_id(family_slug="llama3")
    assert llama3.publisher_id == "meta"
    assert llama3.confidence == "manual"
    assert llama3.review_status == "approved"
    assert infer_publisher_id(family_slug="codestral").publisher_id == "mistral-ai"
    assert infer_publisher_id(family_slug="gemini-3-flash-preview").publisher_id == "google"
    assert infer_publisher_id(family_slug="nomic-embed-text").publisher_id == "nomic-ai"
    assert infer_publisher_id(family_slug="llava").publisher_id == "llava-project"


def test_capabilities_do_not_leak_between_tags():
    from eight_ball.collect.parse_ollama import ParsedFamilyPage

    family = ParsedFamilyPage(
        slug="demo",
        display_name="demo",
        capability_badges=[],
    )
    tags = [
        ParsedTag(
            ollama_identifier="demo:vision",
            family_slug="demo",
            tag_suffix="vision",
            input_capabilities=["Image"],
        ),
        ParsedTag(
            ollama_identifier="demo:text",
            family_slug="demo",
            tag_suffix="text",
            input_capabilities=["Text"],
        ),
    ]
    catalog = build_candidate_catalog(
        families=[family],
        tags_by_family={"demo": tags},
        retrieved_at="2026-07-28T12:00:00Z",
        retrieved_at_by_family={"demo": {"family": "2026-07-28T12:00:00Z", "tags": "2026-07-28T12:00:00Z"}},
    )
    by_id = {tag["ollama_identifier"]: tag for tag in catalog["tags"]}
    assert catalog["families"][0]["primary_capabilities"].get("vision") != "true"
    assert by_id["demo:vision"]["capabilities"].get("vision") == "true"
    assert by_id["demo:text"]["capabilities"].get("vision") != "true"
    assert by_id["demo:text"]["capabilities"].get("text_generation") == "true"


def test_per_snapshot_timestamps_use_family_and_tags_pages_separately():
    from eight_ball.collect.parse_ollama import ParsedFamilyPage

    family = ParsedFamilyPage(slug="demo", display_name="demo")
    tags = [
        ParsedTag(
            ollama_identifier="demo:latest",
            family_slug="demo",
            tag_suffix="latest",
            input_capabilities=["Text"],
            download_size_text="1.0GB",
            download_size_bytes=1_000_000_000,
        )
    ]
    catalog = build_candidate_catalog(
        families=[family],
        tags_by_family={"demo": tags},
        retrieved_at="2026-07-28T12:00:00Z",
        retrieved_at_by_family={
            "demo": {
                "family": "2026-07-01T10:00:00Z",
                "tags": "2026-07-02T11:00:00Z",
            }
        },
    )
    assert catalog["families"][0]["retrieved_at"] == "2026-07-01T10:00:00Z"
    assert catalog["tags"][0]["retrieved_at"] == "2026-07-02T11:00:00Z"
    assert (
        catalog["families"][0]["provenance"]["catalog_source_id"]["retrieved_at"]
        == "2026-07-01T10:00:00Z"
    )
    assert catalog["tags"][0]["provenance"]["download_size_bytes"]["retrieved_at"] == "2026-07-02T11:00:00Z"


def test_per_snapshot_timestamps_from_manifest_fixture(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_from_manifest(
        FIXTURE_MANIFEST,
        family_slugs=["tinyllama"],
    )
    family = catalog["families"][0]
    tag = catalog["tags"][0]
    assert family["retrieved_at"] == "2026-01-01T00:00:00Z"
    assert tag["retrieved_at"] == "2026-01-01T00:00:00Z"
    assert family["provenance"]["catalog_source_id"]["retrieved_at"] == family["retrieved_at"]
    assert tag["provenance"]["download_size_bytes"]["retrieved_at"] == tag["retrieved_at"]


def test_tag_provenance_marks_normalized_values_as_derived(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    catalog = normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["llama3"])
    tag = next(tag for tag in catalog["tags"] if tag["ollama_identifier"] == "llama3:latest")
    assert tag["provenance"]["download_size_text"]["confidence"] == "observed"
    assert tag["provenance"]["download_size_bytes"]["confidence"] == "derived"
    assert tag["provenance"]["parameter_count"]["confidence"] in {"derived", "unknown"}
    assert tag["provenance"]["context_window_tokens"]["confidence"] == "derived"


def test_candidate_validation_rejects_invalid_capability_and_missing_provenance(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])

    from eight_ball.config import load_json, write_json

    tags = load_json(candidate_dir / "tags.json")
    tags[0]["capabilities"]["not_a_real_capability"] = "true"
    del tags[0]["provenance"]["quantization"]
    write_json(candidate_dir / "tags.json", tags)

    with pytest.raises(ValidationError):
        validate_catalog(normalized_dir=candidate_dir, include_artifacts=False)


def test_candidate_validation_rejects_observed_confidence_on_derived_fields(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama"])

    from eight_ball.config import load_json, write_json

    tags = load_json(candidate_dir / "tags.json")
    tags[0]["provenance"]["download_size_bytes"]["confidence"] = "observed"
    write_json(candidate_dir / "tags.json", tags)

    with pytest.raises(ValidationError) as excinfo:
        validate_catalog(normalized_dir=candidate_dir, include_artifacts=False)
    assert any("must be derived or unknown" in error for error in excinfo.value.errors)


def test_manual_override_models_are_valid_not_noisy_review(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    catalog = normalize_ollama_from_manifest(
        FIXTURE_MANIFEST,
        family_slugs=["llama3", "codestral", "tinyllama"],
    )
    reviewed_models = [model for model in catalog["models"] if model["validation_status"] == "needs_review"]
    assert reviewed_models == []
    assert all(model.get("unknown_field_flags") == [] for model in catalog["models"])
    assert all("publisher_inferred" not in model.get("review_reasons", []) for model in catalog["models"])


def test_inferred_publisher_mapping_needs_review_without_unknown_flag():
    inference = infer_publisher_id(family_slug="phi3")
    assert inference.publisher_id == "microsoft"
    assert inference.review_status == "needs_review"


def test_capability_conflicts_ignore_expected_tag_extensions(tmp_path, monkeypatch):
    from eight_ball.report.summary import coverage_summary

    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)
    catalog = normalize_ollama_from_manifest(FIXTURE_MANIFEST)
    coverage = coverage_summary(catalog, normalized_dir=candidate_dir)
    assert coverage["capability_conflict_count"] == 0


def test_normalize_skips_families_with_unparseable_tags(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    tinyllama_family = (FIXTURE_SNAPSHOTS / "tinyllama.html").read_text(encoding="utf-8")
    tinyllama_tags = (FIXTURE_SNAPSHOTS / "tinyllama-tags.html").read_text(encoding="utf-8")
    (snapshots / "tinyllama.html").write_text(tinyllama_family, encoding="utf-8")
    (snapshots / "tinyllama-tags.html").write_text(tinyllama_tags, encoding="utf-8")
    (snapshots / "broken.html").write_text("<html><body>no tags</body></html>", encoding="utf-8")
    (snapshots / "broken-tags.html").write_text("<html><body>no tags</body></html>", encoding="utf-8")

    catalog = normalize_ollama_snapshots(
        family_slugs=["tinyllama", "broken"],
        snapshot_dir=snapshots,
        retrieved_at="2026-08-01T00:00:00Z",
    )
    assert len(catalog["parse_failures"]) == 1
    assert catalog["parse_failures"][0]["family_slug"] == "broken"
    assert len(catalog["families"]) == 1
    assert catalog["families"][0]["id"] == "tinyllama"


def test_compare_manual_review_items_are_deduplicated(tmp_path, monkeypatch):
    candidate_dir = tmp_path / "candidate" / "normalized"
    monkeypatch.setattr("eight_ball.normalize.ollama_web.CANDIDATE_NORMALIZED_DIR", candidate_dir)

    normalize_ollama_from_manifest(FIXTURE_MANIFEST, family_slugs=["tinyllama", "llama3"])
    comparison = compare_catalogs(
        candidate_dir=candidate_dir,
        family_filter={"tinyllama", "llama3"},
    )
    model_items = [item for item in comparison.manual_review_items if item["kind"] == "model"]
    model_ids = [item["id"] for item in model_items]
    assert len(model_ids) == len(set(model_ids))
    assert len(model_items) < comparison.candidate_tag_count

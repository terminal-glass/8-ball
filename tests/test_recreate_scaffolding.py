from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.cli import main
from eight_ball.config import load_json, write_json
from eight_ball.recreate.plan import build_recreate_plan
from eight_ball.recreate.promote import promote_candidate_catalog
from eight_ball.recreate.protect import assert_candidate_output_path, protected_legacy_paths


def _write_catalog(
    root: Path,
    *,
    family_id: str = "llama3",
    candidate: bool,
    needs_review: bool = False,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    model_id = f"{family_id}-8b"
    ollama_identifier = f"{family_id}:latest"
    provenance = {
        field: {"confidence": "derived"}
        for field in (
            "download_size_bytes",
            "parameter_count",
            "context_window_tokens",
            "quantization",
            "availability",
            "capabilities",
        )
    }
    for name, payload in {
        "publishers.json": [
            {
                "id": "meta",
                "display_name": "Meta",
                "official_url": "https://ai.meta.com/",
            }
        ],
        "families.json": [
            {
                "id": family_id,
                "publisher_id": "meta",
                "name": family_id,
                "source_url": f"https://ollama.com/library/{family_id}",
                "retrieved_at": "2026-07-29T01:00:00Z",
                "primary_capabilities": {"text_generation": "true"},
                "review_reasons": ["publisher_mapping_needs_review"]
                if needs_review
                else [],
            }
        ],
        "models.json": [
            {
                "id": model_id,
                "ollama_name": family_id,
                "display_name": family_id,
                "publisher_id": "meta",
                "family_id": family_id,
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "default_tag": ollama_identifier,
                "source_url": f"https://ollama.com/library/{family_id}",
                "retrieved_at": "2026-07-29T01:00:00Z",
                "validation_status": "needs_review" if needs_review else "valid",
                "review_reasons": ["publisher_mapping_needs_review"]
                if needs_review
                else [],
            }
        ],
        "tags.json": [
            {
                "id": f"{family_id}__latest",
                "ollama_identifier": ollama_identifier,
                "model_id": model_id,
                "tag": "latest",
                "parameter_count": 8_000_000_000,
                "parameter_unit": "8b",
                "quantization": None,
                "context_window_tokens": 8192,
                "download_size_bytes": 4_000_000_000,
                "download_size_text": "4.0GB",
                "availability": "local",
                "capabilities": {"text_generation": "true"},
                "pull_command": f"ollama pull {ollama_identifier}",
                "run_command": f"ollama run {ollama_identifier}",
                "source_url": f"https://ollama.com/library/{family_id}/tags",
                "retrieved_at": "2026-07-29T01:00:00Z",
                "provenance": provenance,
            }
        ],
        "capabilities.json": [],
        "catalog-meta.json": {
            "catalog_version": "2026.07.29",
            "candidate": candidate,
            "catalog_source_id": "ollama-library",
        },
    }.items():
        write_json(root / name, payload)


def _allow_tmp_promote_target(monkeypatch) -> None:
    monkeypatch.setattr(
        "eight_ball.recreate.promote.assert_promote_target_is_normalized",
        lambda path: None,
    )


def test_protected_legacy_paths_include_families_and_normalized():
    paths = {path.name for path in protected_legacy_paths()}
    assert "families" in paths
    assert "normalized" in paths


def test_assert_candidate_output_rejects_legacy_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "eight_ball.recreate.protect.protected_legacy_paths",
        lambda: [tmp_path / "data" / "normalized"],
    )
    with pytest.raises(PermissionError):
        assert_candidate_output_path(tmp_path / "data" / "normalized")


def test_recreate_plan_from_fixture_index():
    plan = build_recreate_plan(fixture=True, offline=True, sample_only=False)
    assert plan["selection_mode"] == "from_index"
    assert plan["index_family_count"] >= 6
    assert plan["selected_family_count"] == plan["index_family_count"]
    assert plan["estimated_page_fetches"] == 1 + 2 * plan["selected_family_count"]
    assert plan["safety"]["downloads_model_weights"] is False
    assert plan["safety"]["writes_legacy_families"] is False
    assert "unknown" in plan["publisher_preview"]["counts"] or plan["publisher_preview"][
        "unknown_publisher_count"
    ] >= 0


def test_recreate_plan_sample_is_small():
    plan = build_recreate_plan(fixture=True, offline=True, sample_only=True)
    assert plan["selection_mode"] == "sample"
    assert plan["selected_family_count"] == 6


def test_recreate_plan_deduplicates_explicit_families():
    plan = build_recreate_plan(
        fixture=True,
        offline=True,
        family_slugs=["llama3", "llama3", "tinyllama"],
    )
    assert plan["selected_families"] == ["llama3", "tinyllama"]
    assert plan["selected_family_count"] == 2


def test_recreate_plan_does_not_silently_use_fixture_index(tmp_path, monkeypatch):
    monkeypatch.setattr("eight_ball.recreate.plan.SNAPSHOTS_DIR", tmp_path)
    with pytest.raises(ValueError, match="No families selected"):
        build_recreate_plan(fixture=False, offline=True)


def test_cli_plan_writes_reports(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr("eight_ball.cli.REPORTS_DIR", reports)
    monkeypatch.setattr("eight_ball.recreate.plan.REPORTS_DIR", reports)
    assert main(["plan", "--fixture", "--offline", "--from-index"]) == 0
    assert (reports / "candidate-collect-plan.json").exists()
    assert (reports / "candidate-collect-plan.md").exists()
    plan = load_json(reports / "candidate-collect-plan.json")
    assert plan["selected_family_count"] >= 6


def test_promote_dry_run_does_not_modify_normalized(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    history = tmp_path / "history"
    _write_catalog(candidate, candidate=True)
    _write_catalog(target, candidate=False)
    _allow_tmp_promote_target(monkeypatch)

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        history_dir=history,
        dry_run=True,
        apply=False,
    )
    assert result["dry_run"] is True
    assert result["applied"] is False
    assert result["eligible"] is True
    assert load_json(target / "families.json")[0]["id"] == "llama3"
    assert not history.exists() or not any(history.iterdir())


def test_promote_blocks_invalid_candidate(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    history = tmp_path / "history"
    _write_catalog(candidate, candidate=True)
    _write_catalog(target, candidate=False)
    _allow_tmp_promote_target(monkeypatch)
    tags = load_json(candidate / "tags.json")
    tags[0]["model_id"] = "missing-model"
    write_json(candidate / "tags.json", tags)

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        history_dir=history,
        dry_run=True,
        apply=False,
    )
    assert result["eligible"] is False
    assert result["gates"]["validation"]["valid"] is False
    assert "validation failed" in result["blockers"][0]


def test_promote_does_not_block_publisher_enrichment_backlog(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    _write_catalog(candidate, candidate=True, needs_review=True)
    _write_catalog(target, candidate=False)
    _allow_tmp_promote_target(monkeypatch)

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        dry_run=True,
        apply=False,
    )
    assert result["eligible"] is True
    assert result["gates"]["review_records"]["enrichment_backlog"] == {
        "families": 1,
        "models": 1,
    }
    assert result["gates"]["review_records"]["structural"] == {
        "families": 0,
        "models": 0,
    }
    assert not any("unresolved actionable review" in item for item in result["blockers"])
    assert not any("unresolved structural review" in item for item in result["blockers"])


def test_promote_blocks_unresolved_review_records(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    _write_catalog(candidate, candidate=True, needs_review=True)
    _write_catalog(target, candidate=False)
    _allow_tmp_promote_target(monkeypatch)
    models = load_json(candidate / "models.json")
    models[0]["validation_status"] = "needs_review"
    models[0]["review_reasons"] = ["structural_data_gap"]
    write_json(candidate / "models.json", models)

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        dry_run=True,
        apply=False,
    )
    assert result["eligible"] is False
    assert result["gates"]["review_records"]["structural"] == {"families": 0, "models": 1}
    assert any("unresolved structural review" in item for item in result["blockers"])


def test_promote_blocks_unacknowledged_removals(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    _write_catalog(candidate, family_id="llama3", candidate=True)
    _write_catalog(target, family_id="tinyllama", candidate=False)
    _allow_tmp_promote_target(monkeypatch)

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        dry_run=True,
        apply=False,
    )
    assert result["eligible"] is False
    assert result["gates"]["comparison"]["legacy_only_families"] == 1
    assert any("--allow-removals" in item for item in result["blockers"])


def test_promote_apply_archives_and_replaces(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    history = tmp_path / "history"
    _write_catalog(candidate, family_id="new", candidate=True)
    _write_catalog(target, family_id="old", candidate=False)
    _allow_tmp_promote_target(monkeypatch)
    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        history_dir=history,
        dry_run=False,
        apply=True,
        allow_removals=True,
    )
    assert result["applied"] is True
    assert Path(result["archive_path"]).exists()
    assert load_json(target / "families.json")[0]["id"] == "new"
    assert load_json(target / "catalog-meta.json")["candidate"] is False


def test_promote_restores_canonical_if_atomic_swap_fails(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    history = tmp_path / "history"
    _write_catalog(candidate, candidate=True)
    _write_catalog(target, candidate=False)
    _allow_tmp_promote_target(monkeypatch)
    original_rename = Path.rename

    def fail_stage_rename(path: Path, target_path: Path):
        if path.name.startswith(".normalized-stage-"):
            raise OSError("simulated swap failure")
        return original_rename(path, target_path)

    monkeypatch.setattr(Path, "rename", fail_stage_rename)
    with pytest.raises(OSError, match="simulated swap failure"):
        promote_candidate_catalog(
            candidate_dir=candidate,
            target_dir=target,
            history_dir=history,
            dry_run=False,
            apply=True,
        )
    assert load_json(target / "families.json")[0]["id"] == "llama3"


def test_cli_promote_apply_requires_confirm():
    assert main(["promote", "--apply"]) == 2

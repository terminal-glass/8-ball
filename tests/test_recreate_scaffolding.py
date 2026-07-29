from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.cli import main
from eight_ball.config import load_json, write_json
from eight_ball.recreate.plan import build_recreate_plan
from eight_ball.recreate.promote import promote_candidate_catalog
from eight_ball.recreate.protect import assert_candidate_output_path, protected_legacy_paths


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
    candidate.mkdir()
    target.mkdir()
    for name, payload in {
        "publishers.json": [{"id": "meta", "display_name": "Meta"}],
        "families.json": [{"id": "llama3", "publisher_id": "meta", "name": "llama3"}],
        "models.json": [
            {
                "id": "llama3-8b",
                "ollama_name": "llama3",
                "display_name": "llama3",
                "publisher_id": "meta",
                "family_id": "llama3",
            }
        ],
        "tags.json": [
            {
                "id": "llama3__latest",
                "ollama_identifier": "llama3:latest",
                "model_id": "llama3-8b",
                "tag": "latest",
            }
        ],
        "capabilities.json": [],
        "catalog-meta.json": {
            "catalog_version": "2026.07.29",
            "candidate": True,
            "catalog_source_id": "ollama-library",
        },
    }.items():
        write_json(candidate / name, payload)
    write_json(target / "families.json", [{"id": "legacy-family"}])
    monkeypatch.setattr(
        "eight_ball.recreate.promote.assert_promote_target_is_normalized",
        lambda path: None,
    )

    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        history_dir=history,
        dry_run=True,
        apply=False,
    )
    assert result["dry_run"] is True
    assert result["applied"] is False
    assert load_json(target / "families.json") == [{"id": "legacy-family"}]
    assert not history.exists() or not any(history.iterdir())


def test_promote_apply_archives_and_replaces(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    target = tmp_path / "normalized"
    history = tmp_path / "history"
    candidate.mkdir()
    target.mkdir()
    write_json(target / "families.json", [{"id": "old"}])
    write_json(
        target / "catalog-meta.json",
        {"catalog_version": "2026.07.16", "candidate": False},
    )
    for name, payload in {
        "publishers.json": [],
        "families.json": [{"id": "new", "publisher_id": "meta", "name": "new"}],
        "models.json": [],
        "tags.json": [],
        "capabilities.json": [],
        "catalog-meta.json": {
            "catalog_version": "2026.07.29",
            "candidate": True,
            "catalog_source_id": "ollama-library",
        },
    }.items():
        write_json(candidate / name, payload)

    monkeypatch.setattr(
        "eight_ball.recreate.promote.assert_promote_target_is_normalized",
        lambda path: None,
    )
    result = promote_candidate_catalog(
        candidate_dir=candidate,
        target_dir=target,
        history_dir=history,
        dry_run=False,
        apply=True,
    )
    assert result["applied"] is True
    assert Path(result["archive_path"]).exists()
    assert load_json(target / "families.json")[0]["id"] == "new"
    assert load_json(target / "catalog-meta.json")["candidate"] is False


def test_cli_promote_apply_requires_confirm():
    assert main(["promote", "--apply"]) == 2

from __future__ import annotations

from eight_ball.collect.ollama import collect_ollama_library
from eight_ball.generate.outputs import generate_outputs
from eight_ball.normalize.catalog import normalize_legacy_catalog
from eight_ball.paths import FIXTURES_DIR
from eight_ball.validate.catalog import validate_catalog


def test_offline_fixture_pipeline(tmp_path, monkeypatch):
    normalized = tmp_path / "normalized"
    generated = tmp_path / "generated"
    snapshots = tmp_path / "snapshots"
    raw = tmp_path / "raw"
    snapshots.mkdir()
    raw.mkdir()
    (snapshots / "ollama-library-index.html").write_text(
        (FIXTURES_DIR / "snapshots" / "ollama-library-index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr("eight_ball.paths.NORMALIZED_DIR", normalized)
    monkeypatch.setattr("eight_ball.paths.GENERATED_DIR", generated)
    monkeypatch.setattr("eight_ball.paths.SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr("eight_ball.paths.RAW_DIR", raw)
    monkeypatch.setattr("eight_ball.collect.ollama.SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr("eight_ball.collect.ollama.RAW_DIR", raw)
    monkeypatch.setattr(
        "eight_ball.normalize.catalog.LEGACY_FAMILIES_DIR",
        FIXTURES_DIR / "families",
    )
    monkeypatch.setattr("eight_ball.normalize.catalog.NORMALIZED_DIR", normalized)
    monkeypatch.setattr("eight_ball.generate.outputs.NORMALIZED_DIR", normalized)
    monkeypatch.setattr("eight_ball.generate.outputs.GENERATED_DIR", generated)
    monkeypatch.setattr("eight_ball.validate.catalog.NORMALIZED_DIR", normalized)

    collect_ollama_library(offline=True)
    normalize_legacy_catalog(sample_only=False, families_dir=FIXTURES_DIR / "families")
    validate_catalog()
    summary = generate_outputs()
    assert summary["tags"] > 0
    assert summary["deployment_combinations"] == summary["tags"] * 8 * 3

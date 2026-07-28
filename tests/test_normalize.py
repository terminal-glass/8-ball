from __future__ import annotations

from pathlib import Path

from eight_ball.normalize.catalog import build_catalog


def test_sample_catalog_normalization():
    fixture_dir = Path("tests/fixtures/families")
    catalog = build_catalog(families_dir=fixture_dir, sample_only=False)
    assert len(catalog["families"]) == 6
    assert len(catalog["models"]) == 6
    assert catalog["tags"]
    slugs = {family["id"] for family in catalog["families"]}
    assert slugs == {
        "tinyllama",
        "llama3",
        "codestral",
        "llava",
        "nomic-embed-text",
        "gemini-3-flash-preview",
    }


def test_cloud_model_availability():
    fixture_dir = Path("tests/fixtures/families")
    catalog = build_catalog(families_dir=fixture_dir, sample_only=False)
    gemini = next(m for m in catalog["models"] if m["id"] == "gemini-3-flash-preview")
    assert gemini["availability"] in {"cloud", "both"}

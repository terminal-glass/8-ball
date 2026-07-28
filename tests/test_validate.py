from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.normalize.catalog import build_catalog
from eight_ball.validate.catalog import ValidationError, validate_catalog


def test_validate_sample_catalog():
    catalog = build_catalog(families_dir=Path("tests/fixtures/families"), sample_only=False)
    report = validate_catalog(catalog)
    assert report["valid"] is True
    assert report["counts"]["tags"] > 0


def test_duplicate_tag_detection():
    catalog = build_catalog(families_dir=Path("tests/fixtures/families"), sample_only=False)
    catalog["tags"].append(dict(catalog["tags"][0]))
    with pytest.raises(ValidationError):
        validate_catalog(catalog)

"""Committed metadata exports for downstream installer-authoring work.

These exports are metadata only. This repository never generates installer
scripts; it publishes validated catalog data that separate installer
repositories may read.
"""

from eight_ball.export.installer_datasets import (
    build_p2_indexes,
    export_p3_catalog,
)

__all__ = [
    "build_p2_indexes",
    "export_p3_catalog",
]

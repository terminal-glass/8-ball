"""Catalog recreate scaffolding: plan, protect, archive, and promote.

This module does not download model weights and does not run a live crawl by
itself. It defines the safe workflow for rebuilding candidate catalogs from
official Ollama metadata snapshots and promoting them only after review.
"""

from __future__ import annotations

from eight_ball.recreate.plan import build_recreate_plan, write_recreate_plan
from eight_ball.recreate.promote import (
    archive_normalized_catalog,
    promote_candidate_catalog,
)
from eight_ball.recreate.protect import (
    assert_candidate_output_path,
    protected_legacy_paths,
)

__all__ = [
    "archive_normalized_catalog",
    "assert_candidate_output_path",
    "build_recreate_plan",
    "promote_candidate_catalog",
    "protected_legacy_paths",
    "write_recreate_plan",
]

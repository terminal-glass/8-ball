from __future__ import annotations

PUBLIC_CATALOG_SCHEMA_VERSION = "1.0.0"
PUBLIC_CATALOG_GENERATOR_VERSION = "1.0.0"
PUBLIC_CATALOG_GENERATOR_COMMAND = "eight-ball publish-catalog"

PROMOTION_RECEIPT_PATH = "reports/catalog-promotion-receipt.md"

CAPABILITY_FILTER_KEYS = (
    "chat",
    "text_generation",
    "coding",
    "reasoning",
    "vision",
    "embeddings",
    "tool_use",
    "structured_output",
    "multilingual",
    "audio",
    "cloud",
)

LOCAL_AVAILABILITY = frozenset({"local", "both"})
CLOUD_AVAILABILITY = frozenset({"cloud", "cloud_only", "both"})

SIZE_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("micro", 0, 999_999_999),
    ("small", 1_000_000_000, 7_999_999_999),
    ("medium", 8_000_000_000, 30_999_999_999),
    ("large", 31_000_000_000, 70_999_999_999),
    ("xlarge", 71_000_000_000, None),
)

SOURCE_EXCEPTION_EXPLANATION = (
    "Retained from prior canonical catalog because the current static HTML parser "
    "cannot normalize this family's live tags. This is a stale source exception, "
    "not evidence of live removal."
)

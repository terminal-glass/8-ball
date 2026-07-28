from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
SCHEMAS_DIR = REPO_ROOT / "schemas"
DATA_DIR = REPO_ROOT / "data"
LEGACY_FAMILIES_DIR = DATA_DIR / "families"
RAW_DIR = DATA_DIR / "raw"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
NORMALIZED_DIR = DATA_DIR / "normalized"
CANDIDATE_DIR = DATA_DIR / "candidate"
CANDIDATE_NORMALIZED_DIR = CANDIDATE_DIR / "normalized"
CANDIDATE_GENERATED_DIR = CANDIDATE_DIR / "generated"
CANDIDATE_INDEXES_DIR = CANDIDATE_DIR / "indexes"
MANIFESTS_DIR = DATA_DIR / "manifests"
GENERATED_DIR = DATA_DIR / "generated"
REPORTS_DIR = REPO_ROOT / "reports"
INDEXES_DIR = REPO_ROOT / "indexes"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

SAMPLE_FAMILIES = (
    "tinyllama",
    "llama3",
    "codestral",
    "llava",
    "nomic-embed-text",
    "gemini-3-flash-preview",
)

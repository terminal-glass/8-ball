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
HISTORY_DIR = DATA_DIR / "history"
CANDIDATE_DIR = DATA_DIR / "candidate"
CANDIDATE_NORMALIZED_DIR = CANDIDATE_DIR / "normalized"
CANDIDATE_GENERATED_DIR = CANDIDATE_DIR / "generated"
CANDIDATE_INDEXES_DIR = CANDIDATE_DIR / "indexes"
MANIFESTS_DIR = DATA_DIR / "manifests"
GENERATED_DIR = DATA_DIR / "generated"
REPORTS_DIR = REPO_ROOT / "reports"
INDEXES_DIR = REPO_ROOT / "indexes"
DATA_SCIENCE_DIR = REPO_ROOT / "AGENTS" / "data-science"
P4_PUBLIC_CATALOG_DIR = DATA_SCIENCE_DIR / "P4-Public-Catalog"
PROFILES_DIR = REPO_ROOT / "profiles"
PROFILES_FAMILIES_DIR = PROFILES_DIR / "01-families"
PROFILES_MODELS_DIR = PROFILES_DIR / "02-models"
PROFILES_DEPLOYMENT_TYPES_DIR = PROFILES_DIR / "03-deployment-types"
PROFILES_GENERATED_DIR = PROFILES_DIR / "generated"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

SAMPLE_FAMILIES = (
    "tinyllama",
    "llama3",
    "codestral",
    "llava",
    "nomic-embed-text",
    "gemini-3-flash-preview",
)

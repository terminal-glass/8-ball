from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "AGENTS"
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
GENERATED_PAGES_DIR = GENERATED_DIR / "pages"
GENERATED_PAGES_FAMILIES_DIR = GENERATED_PAGES_DIR / "families"
GENERATED_PAGES_DEPLOYMENT_TYPES_DIR = GENERATED_PAGES_DIR / "deployment-types"
GENERATED_PAGES_MODELS_DIR = GENERATED_PAGES_DIR / "models"
GENERATED_INSTALL_MANIFEST_PATH = GENERATED_PAGES_DIR / "install-manifest.json"
REPORTS_DIR = REPO_ROOT / "reports"
INDEXES_DIR = REPO_ROOT / "indexes"
DATA_SCIENCE_DIR = REPO_ROOT / "AGENTS" / "data-science"
PROFILE_MAPPING_DIR = DATA_SCIENCE_DIR / "profile-mapping"
OLLAMA_MAPPING_DIR = DATA_SCIENCE_DIR / "ollama-mapping"
P4_PUBLIC_CATALOG_DIR = OLLAMA_MAPPING_DIR / "P4-Public-Catalog"
PROFILES_DIR = REPO_ROOT / "profiles"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

SAMPLE_FAMILIES = (
    "tinyllama",
    "llama3",
    "codestral",
    "llava",
    "nomic-embed-text",
    "gemini-3-flash-preview",
)

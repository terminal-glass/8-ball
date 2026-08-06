from __future__ import annotations

import re
from pathlib import Path

import pytest

from eight_ball.config import deployment_type_ids, deployment_types_config
from eight_ball.paths import (
    GENERATED_INSTALL_MANIFEST_PATH,
    GENERATED_PAGES_DEPLOYMENT_TYPES_DIR,
    GENERATED_PAGES_DIR,
    GENERATED_PAGES_FAMILIES_DIR,
    GENERATED_PAGES_MODELS_DIR,
    REPO_ROOT,
)

EXPECTED_DEPLOYMENT_TYPE_IDS = ("3", "4", "5", "6", "7")

# Agent-facing docs that must describe the C5 page tree correctly.
AGENT_DOC_PATHS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "install-manifest-contract.md",
    REPO_ROOT / "AGENTS" / "history" / "cursorFileC5-profile-folder-structure.md",
    REPO_ROOT / "profiles" / "README.md",
)

# Paths excluded from "no 02-models under generated pages" scans.
GENERATED_PAGES_BAD_REFERENCE_EXCLUDES = (
    "tests/test_c2_profiles.py",
    "src/eight_ball/generate/profiles.py",
    "AGENTS/history/",
)


def test_deployment_types_yaml_exists() -> None:
    path = REPO_ROOT / "config" / "deployment_types.yaml"
    assert path.is_file(), "config/deployment_types.yaml must exist"


def test_deployment_type_ids_are_exactly_three_through_seven() -> None:
    ids = deployment_type_ids()
    assert ids == list(EXPECTED_DEPLOYMENT_TYPE_IDS)


def test_deployment_types_have_required_fields() -> None:
    required = {
        "deployment_type_id",
        "display_name",
        "description",
        "hardware_profile_ids",
        "runtime_policy_ids",
        "cpu_suitability",
        "gpu_suitability",
    }
    for row in deployment_types_config().get("deployment_types", []):
        missing = required - set(row)
        assert not missing, f"deployment type {row.get('deployment_type_id')} missing {missing}"


def test_generated_pages_path_constants() -> None:
    assert GENERATED_PAGES_DIR == REPO_ROOT / "data" / "generated" / "pages"
    assert GENERATED_PAGES_FAMILIES_DIR.name == "families"
    assert GENERATED_PAGES_DEPLOYMENT_TYPES_DIR.name == "deployment-types"
    assert GENERATED_PAGES_MODELS_DIR.name == "models"
    assert GENERATED_INSTALL_MANIFEST_PATH.name == "install-manifest.json"


def test_install_manifest_contract_documented() -> None:
    contract = REPO_ROOT / "docs" / "install-manifest-contract.md"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    assert "data/generated/pages/install-manifest.json" in text
    assert "manifest.models[model_id].deployments[deployment_type_id]" in text
    for field in (
        "model_id",
        "model_slug",
        "family_id",
        "family_slug",
        "deployment_type_id",
        "ollama_identifier",
        "hardware_profile_id",
        "assessment",
    ):
        assert field in text


@pytest.mark.parametrize("doc_path", AGENT_DOC_PATHS)
def test_agent_docs_reference_generated_pages_models(doc_path: Path) -> None:
    text = doc_path.read_text(encoding="utf-8")
    assert "data/generated/pages/models/" in text


@pytest.mark.parametrize("doc_path", AGENT_DOC_PATHS)
def test_agent_docs_describe_numbered_deployment_folders(doc_path: Path) -> None:
    text = doc_path.read_text(encoding="utf-8")
    assert (
        re.search(r"<3-7>", text)
        or re.search(r"<deployment-type-number>", text)
        or re.search(r"models/.+/[34567]/", text)
    )


def test_no_agent_docs_instruct_generating_02_models_under_generated_pages() -> None:
    bad_patterns = (
        re.compile(r"data/generated/pages/02-models"),
        re.compile(r"data/generated/pages/2-models"),
        re.compile(r"generated/pages/02-models"),
    )
    scan_roots = (REPO_ROOT / "AGENTS", REPO_ROOT / "docs", REPO_ROOT / "AGENTS.md")
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".md", ".py", ".yaml", ".yml"}:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if any(rel.startswith(prefix) or rel == prefix for prefix in GENERATED_PAGES_BAD_REFERENCE_EXCLUDES):
                continue
            if "/history/" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in bad_patterns:
                if pattern.search(text):
                    offenders.append(f"{rel}: {pattern.pattern}")
    assert not offenders, "Bad generated-pages references:\n" + "\n".join(offenders)


def test_c5_doc_forbids_02_models_page_tree() -> None:
    c5 = (
        REPO_ROOT / "AGENTS" / "history" / "cursorFileC5-profile-folder-structure.md"
    ).read_text(encoding="utf-8")
    assert "Do not create or use 02-models" in c5
    assert "data/generated/pages/models/" in c5

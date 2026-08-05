from __future__ import annotations

import csv
from pathlib import Path

import pytest

from eight_ball.config import load_json, write_json
from eight_ball.generate.deployments import generate_deployments
from eight_ball.generate.pages import generate_pages
from eight_ball.generate.root_profiles import (
    PRESERVED_PROFILE_FILES,
    RootProfilesError,
    generate_root_profiles,
)
from eight_ball.paths import GENERATED_PAGES_DIR, PROFILES_DIR


def _write_minimal_catalog(root: Path) -> None:
    root.mkdir(parents=True)
    write_json(
        root / "families.json",
        [
            {
                "id": "llama3",
                "publisher_id": "meta",
                "name": "Llama 3",
                "description": "Meta Llama 3 family",
                "source_url": "https://ollama.com/library/llama3",
                "retrieved_at": "2026-08-01T12:00:00Z",
            }
        ],
    )
    write_json(
        root / "models.json",
        [
            {
                "id": "llama3-8b",
                "family_id": "llama3",
                "display_name": "Llama 3 8B",
                "availability": "local",
                "default_tag": "llama3:8b",
                "capabilities": {"text_generation": "true"},
            }
        ],
    )
    write_json(
        root / "tags.json",
        [
            {
                "id": "llama3__8b",
                "ollama_identifier": "llama3:8b",
                "model_id": "llama3-8b",
                "tag": "8b",
                "download_size_bytes": 4700000000,
                "installed_storage_bytes_estimated": 5000000000,
                "availability": "local",
                "pull_command": "ollama pull llama3:8b",
                "run_command": "ollama run llama3:8b",
                "source_url": "https://ollama.com/library/llama3/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
            }
        ],
    )
    write_json(root / "publishers.json", [])
    write_json(root / "capabilities.json", [])


def test_generate_root_profiles_from_pages(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    pages_root = tmp_path / "pages"
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "README.md").write_text("# preserved\n", encoding="utf-8")

    _write_minimal_catalog(normalized)
    tags = load_json(normalized / "tags.json")
    generate_pages(
        families=load_json(normalized / "families.json"),
        models=load_json(normalized / "models.json"),
        tags=tags,
        deployments=generate_deployments(tags),
        output_root=pages_root,
    )

    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_FAMILIES_DIR",
        pages_root / "families",
    )
    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_DEPLOYMENT_TYPES_DIR",
        pages_root / "deployment-types",
    )
    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_MODELS_DIR",
        pages_root / "models",
    )

    summary = generate_root_profiles(
        pages_root=pages_root,
        profiles_dir=profiles_dir,
        include_provider_assumptions=False,
    )

    assert summary.family_count == 1
    assert summary.model_count == 1
    assert summary.deployment_class_count == 5
    assert summary.model_deployment_count == 5
    assert summary.provider_assumption_count == 0
    assert (profiles_dir / "manifest.json").is_file()
    assert (profiles_dir / "index.csv").is_file()
    assert (profiles_dir / "families" / "llama3" / "profile.json").is_file()
    assert (profiles_dir / "deployment-classes" / "5" / "profile.json").is_file()
    assert (profiles_dir / "models" / "llama3-8b" / "model.json").is_file()
    assert (profiles_dir / "models" / "llama3-8b" / "5" / "profile.json").is_file()
    assert (profiles_dir / "README.md").is_file()

    manifest = load_json(profiles_dir / "manifest.json")
    assert manifest["schema_version"] == "profiles.manifest.v1"
    assert manifest["counts"]["families"] == 1
    assert manifest["primary_source"]["install_manifest_schema"] == "c5.install-manifest.v1"

    family_profile = load_json(profiles_dir / "families" / "llama3" / "profile.json")
    assert family_profile["schema_version"] == "profiles.family.v1"
    assert family_profile["provenance_status"] == "derived_from_c5_pages"
    assert family_profile["profile"]["family_id"] == "llama3"

    with (profiles_dir / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row_types = {row["row_type"] for row in rows}
    assert row_types == {"family", "model", "model_deployment", "deployment_class"}


def test_generate_root_profiles_reports_missing_install_manifest(tmp_path: Path) -> None:
    pages_root = tmp_path / "pages"
    pages_root.mkdir()
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    with pytest.raises(RootProfilesError) as exc_info:
        generate_root_profiles(pages_root=pages_root, profiles_dir=profiles_dir)

    assert any(path.endswith("install-manifest.json") for path in exc_info.value.missing_files)


def test_generate_root_profiles_includes_labeled_provider_assumptions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    normalized = tmp_path / "normalized"
    pages_root = tmp_path / "pages"
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    _write_minimal_catalog(normalized)
    tags = load_json(normalized / "tags.json")
    generate_pages(
        families=load_json(normalized / "families.json"),
        models=load_json(normalized / "models.json"),
        tags=tags,
        deployments=generate_deployments(tags),
        output_root=pages_root,
    )

    assumptions = [
        {
            "id": "assumed_profile:test",
            "profile_id": "test_assumption",
            "display_name": "Test Assumption",
            "provenance_status": "internal_assumption_class",
            "source_reference": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
        }
    ]
    normalized.mkdir(parents=True, exist_ok=True)
    write_json(normalized / "hardware-assumed-profiles.json", assumptions)

    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_FAMILIES_DIR",
        pages_root / "families",
    )
    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_DEPLOYMENT_TYPES_DIR",
        pages_root / "deployment-types",
    )
    monkeypatch.setattr(
        "eight_ball.generate.root_profiles.GENERATED_PAGES_MODELS_DIR",
        pages_root / "models",
    )
    monkeypatch.setattr("eight_ball.generate.root_profiles.NORMALIZED_DIR", normalized)

    summary = generate_root_profiles(
        pages_root=pages_root,
        profiles_dir=profiles_dir,
        include_provider_assumptions=True,
    )
    assert summary.provider_assumption_count == 1

    assumption_manifest = load_json(profiles_dir / "provider-assumptions" / "manifest.json")
    assert assumption_manifest["provenance_status"] == "assumption"
    assumption_profile = load_json(profiles_dir / "provider-assumptions" / "test_assumption.json")
    assert assumption_profile["provenance_status"] == "assumption"


def test_committed_root_profiles_match_generated_pages() -> None:
    manifest_path = PROFILES_DIR / "manifest.json"
    assert manifest_path.is_file(), "profiles/manifest.json missing; run profile generator"

    manifest = load_json(manifest_path)
    if manifest.get("generator") == "scripts/generate-profiles-from-agents.py":
        pytest.skip("C10 AGENTS profile manifest replaces C5 root-profiles export schema")

    install_manifest = load_json(GENERATED_PAGES_DIR / "install-manifest.json")
    assert manifest["primary_source"]["install_manifest_path"] == "data/generated/pages/install-manifest.json"
    assert manifest["primary_source"]["install_manifest_schema"] == install_manifest["schema_version"]
    assert manifest["counts"]["families"] == len(list((PROFILES_DIR / "families").iterdir()))
    assert manifest["counts"]["models"] == len(install_manifest["models"])
    assert manifest["counts"]["deployment_classes"] == 5

    for preserved in PRESERVED_PROFILE_FILES:
        assert (PROFILES_DIR / preserved).is_file()

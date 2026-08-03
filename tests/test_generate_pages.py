from __future__ import annotations

from pathlib import Path

from eight_ball.config import load_json, write_json
from eight_ball.generate.deployments import generate_deployments
from eight_ball.generate.outputs import generate_outputs
from eight_ball.generate.pages import generate_pages, validate_generated_pages
from eight_ball.paths import GENERATED_PAGES_DIR, NORMALIZED_DIR


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
            },
            {
                "id": "llama3__70b",
                "ollama_identifier": "llama3:70b",
                "model_id": "llama3-8b",
                "tag": "70b",
                "download_size_bytes": 40000000000,
                "installed_storage_bytes_estimated": 43000000000,
                "availability": "local",
                "pull_command": "ollama pull llama3:70b",
                "run_command": "ollama run llama3:70b",
                "source_url": "https://ollama.com/library/llama3/tags",
                "retrieved_at": "2026-08-01T12:00:00Z",
            },
        ],
    )
    write_json(root / "publishers.json", [])
    write_json(root / "capabilities.json", [])


def test_generate_pages_from_fixture_catalog(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    generated = tmp_path / "generated"
    _write_minimal_catalog(normalized)
    tags = load_json(normalized / "tags.json")
    deployments = generate_deployments(tags)
    summary = generate_pages(
        families=load_json(normalized / "families.json"),
        models=load_json(normalized / "models.json"),
        tags=tags,
        deployments=deployments,
        output_root=generated / "pages",
    )

    assert summary["family_pages"] == 1
    assert summary["deployment_type_pages"] == 5
    assert summary["model_pages"] == 1
    assert summary["model_deployment_pages"] == 5
    assert summary["install_manifest_models"] == 1
    assert summary["install_manifest_deployments"] == 5

    pages = generated / "pages"
    assert (pages / "families" / "llama3" / "info.json").is_file()
    assert (pages / "deployment-types" / "3" / "info.json").is_file()
    assert (pages / "models" / "llama3-8b" / "model.json").is_file()
    assert (pages / "models" / "llama3-8b" / "5" / "info.json").is_file()
    assert not (pages / "02-models").exists()

    family_info = load_json(pages / "families" / "llama3" / "info.json")
    assert family_info["model_count"] == 1
    assert family_info["tag_count"] == 2

    deployment_info = load_json(pages / "models" / "llama3-8b" / "5" / "info.json")
    for field in (
        "model_id",
        "model_slug",
        "family_id",
        "family_slug",
        "deployment_type_id",
        "ollama_identifier",
        "hardware_profile_id",
        "assessment",
        "installed_storage_bytes_estimated",
        "min_system_ram_gb_estimated",
        "recommended_system_ram_gb_estimated",
        "cpu_suitability",
        "gpu_suitability",
        "min_vram_gb_estimated",
        "recommended_vram_gb_estimated",
    ):
        assert field in deployment_info

    manifest = load_json(pages / "install-manifest.json")
    entry = manifest["models"]["llama3-8b"]["deployments"]["5"]
    assert entry["model_id"] == "llama3-8b"
    assert entry["deployment_type_id"] == "5"
    assert entry["ollama_identifier"] == "llama3:8b"
    assert entry["helper_path"].endswith("models/llama3-8b/5/info.json")

    report = validate_generated_pages(pages)
    assert report["valid"] is True
    assert report["forbidden_02_models_exists"] is False


def test_validate_generated_pages_rejects_missing_tree(tmp_path: Path) -> None:
    report = validate_generated_pages(tmp_path / "missing")
    assert report["valid"] is False
    assert report["errors"]


def test_generate_outputs_builds_full_page_tree(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    generated = tmp_path / "generated"
    indexes = tmp_path / "indexes"
    normalized.mkdir()
    for name in ("families.json", "models.json", "tags.json", "publishers.json", "capabilities.json"):
        source = NORMALIZED_DIR / name
        if source.exists():
            (normalized / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("eight_ball.generate.outputs.INDEXES_DIR", indexes)
    summary = generate_outputs(normalized_dir=normalized, generated_dir=generated, indexes_dir=indexes)
    pages = summary["pages"]
    families = load_json(normalized / "families.json")
    models = load_json(normalized / "models.json")

    assert pages["family_pages"] == len(families)
    assert pages["model_pages"] == len(models)
    assert pages["deployment_type_pages"] == 5
    assert pages["model_deployment_pages"] == pages["install_manifest_deployments"]
    assert pages["install_manifest_models"] == len(models)

    report = validate_generated_pages(generated / "pages")
    assert report["valid"] is True
    assert not (generated / "pages" / "02-models").exists()


def test_full_catalog_page_tree_is_committed() -> None:
    pages = GENERATED_PAGES_DIR
    assert (pages / "install-manifest.json").is_file(), "Committed page tree missing; run eight-ball generate"
    families = load_json(NORMALIZED_DIR / "families.json")
    models = load_json(NORMALIZED_DIR / "models.json")
    report = validate_generated_pages(pages)
    assert report["valid"] is True
    assert report["family_pages"] == len(families)
    assert report["model_pages"] == len(models)
    assert report["deployment_type_pages"] == 5
    assert report["model_deployment_pages"] > 0
    assert not (pages / "02-models").exists()

    manifest = load_json(pages / "install-manifest.json")
    assert manifest["schema_version"] == "c5.install-manifest.v1"
    assert set(manifest["deployment_types"]) == {"3", "4", "5", "6", "7"}
    sample_model_id = models[0]["id"]
    assert sample_model_id in manifest["models"]
    assert manifest["models"][sample_model_id]["deployments"]

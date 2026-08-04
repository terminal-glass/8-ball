from __future__ import annotations

from pathlib import Path

import pytest

from eight_ball.agents_csv.enrichment import enrich_deployment_hardware, load_canonical_hardware
from eight_ball.agents_csv.import_collection import (
    HardwareImportError,
    discover_agents_csv_files,
    import_hardware_collection,
)
from eight_ball.agents_csv.registry import source_specs
from eight_ball.config import load_json
from eight_ball.generate.outputs import generate_outputs
from eight_ball.generate.pages import validate_generated_pages
from eight_ball.paths import GENERATED_INSTALL_MANIFEST_PATH, GENERATED_PAGES_DIR, NORMALIZED_DIR


def test_every_agents_csv_is_classified():
    discovered = {path.name for path in discover_agents_csv_files()}
    registered = {
        Path(spec.path).name
        for spec in source_specs()
        if spec.path.startswith("AGENTS/") and spec.path.endswith(".csv")
    }
    assert discovered == registered


def test_import_hardware_collection_writes_canonical_files():
    report = import_hardware_collection(write_outputs=True)
    assert report.ok, report.errors
    for filename in (
        "hardware-provider-instances.json",
        "hardware-assumed-profiles.json",
        "hardware-measured-hosts.json",
        "hardware-accelerator-classes.json",
        "hardware-deployment-types.json",
        "hardware-import-meta.json",
    ):
        assert (NORMALIZED_DIR / filename).is_file()


def test_control_files_are_not_imported_as_hardware():
    report = import_hardware_collection(write_outputs=False)
    control_paths = {
        spec.path
        for spec in source_specs()
        if spec.namespace == "control_and_provenance"
    }
    for entry in report.files:
        if entry.path in control_paths:
            assert entry.imported is False
            assert entry.imported_count == 0


def test_amd_profiles_are_not_labeled_cuda():
    report = import_hardware_collection(write_outputs=False)
    assert report.ok, report.errors
    hardware = load_canonical_hardware()
    for item in hardware["provider_instances"]:
        if (item.get("gpu_vendor") or "").lower() == "amd":
            assert item.get("cuda_available") is not True
            assert item.get("accelerator_class_id") == "amd_rocm"


def test_apple_profiles_are_not_labeled_cuda():
    hardware = load_canonical_hardware()
    for item in hardware["assumed_profiles"]:
        if item.get("accelerator_class_id") == "apple_metal":
            assert item.get("cuda_available") is not True


def test_lightsail_research_gpu_preserves_unknown_fields():
    hardware = load_canonical_hardware()
    research_rows = [
        item
        for item in hardware["provider_instances"]
        if "lightsail for research" in (item.get("product_line") or "").lower()
    ]
    assert len(research_rows) == 3
    for item in research_rows:
        assert item.get("gpu_model") is None
        assert item.get("vram_gb_per_gpu") is None
        assert item.get("accelerator_class_id") == "unknown_gpu"


def test_measured_host_is_not_provider_template():
    hardware = load_canonical_hardware()
    assert len(hardware["measured_hosts"]) == 1
    host = hardware["measured_hosts"][0]
    assert host["record_type"] == "measured_hardware_host"
    assert host["host_profile_id"] == "local-brain1-rtx3060-12gb"
    assert host["ollama_inference_verified"] is False


def test_enrichment_references_existing_profile_ids():
    hardware = load_canonical_hardware()
    enrichment = enrich_deployment_hardware(
        deployment_type_id="6",
        hardware_profile_id="gpu-midrange",
        hardware=hardware,
    )
    provider_ids = {item["id"] for item in hardware["provider_instances"]}
    assumed_ids = {item["id"] for item in hardware["assumed_profiles"]}
    for profile_id in enrichment["compatible_provider_instance_ids"]:
        assert profile_id in provider_ids
    for profile_id in enrichment["compatible_assumed_profile_ids"]:
        assert profile_id in assumed_ids


def test_duplicate_provider_key_fails_validation(tmp_path: Path):
    csv_path = tmp_path / "dup-provider.csv"
    csv_path.write_text(
        "provider,product_line,internal_plan_id,provenance_status\n"
        "DigitalOcean,GPU Droplets,dup-plan,provider_published_current_pricing_page\n"
        "DigitalOcean,GPU Droplets,dup-plan,assumed_client_class\n",
        encoding="utf-8",
    )
    from eight_ball.agents_csv.registry import SourceSpec
    from eight_ball.agents_csv.validate import validate_agents_csv_collection

    source = SourceSpec(
        id="dup-provider",
        path=str(csv_path),
        namespace="provider_instance_data",
        format="csv",
        importable=True,
        options={
            "provider_field": "provider",
            "product_line_field": "product_line",
            "plan_id_field": "internal_plan_id",
        },
    )
    report = validate_agents_csv_collection(sources=[source], repo_root=tmp_path)
    assert not report.ok
    assert any("lower-confidence record would overwrite" in error for error in report.errors)


def test_generate_outputs_fails_when_hardware_import_fails(monkeypatch):
    from eight_ball.generate import outputs

    def _fail_import(**kwargs):
        raise HardwareImportError(["forced import failure for test"])

    monkeypatch.setattr(outputs, "import_hardware_collection", _fail_import)
    with pytest.raises(HardwareImportError):
        generate_outputs()


def test_manifest_includes_hardware_enrichment_after_generate():
    import_hardware_collection(write_outputs=True)
    generate_outputs()
    manifest = load_json(GENERATED_INSTALL_MANIFEST_PATH)
    assert manifest.get("hardware_catalog")
    assert manifest.get("hardware_data_version")
    sample_model = next(iter(manifest["models"].values()))
    sample_deployment = next(iter(sample_model["deployments"].values()))
    enrichment = sample_deployment.get("hardware_enrichment")
    assert enrichment is not None
    assert "compatible_provider_instance_ids" in enrichment
    assert "compatible_assumed_profile_ids" in enrichment
    assert "accelerator_class_ids" in enrichment


def test_generated_pages_do_not_use_02_models():
    import_hardware_collection(write_outputs=True)
    generate_outputs()
    report = validate_generated_pages(GENERATED_PAGES_DIR)
    assert not report.get("errors"), report.get("errors")
    assert not (GENERATED_PAGES_DIR / "02-models").exists()


def test_deployment_types_remain_three_through_seven():
    hardware = load_canonical_hardware()
    deployment_ids = {
        str(item.get("deployment_type_id"))
        for item in hardware["deployment_types"]
        if item.get("deployment_type_id")
    }
    assert deployment_ids == {"3", "4", "5", "6", "7"}


def test_recovered_count_contracts_are_checked_not_hardcoded():
    report = import_hardware_collection(write_outputs=False)
    metrics = {entry["metric"] for entry in report.count_contract_checks}
    assert "DigitalOcean NVIDIA GPU rows" in metrics
    assert "Measured local GPU host rows" in metrics

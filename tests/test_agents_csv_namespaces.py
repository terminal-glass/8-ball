from __future__ import annotations

import csv
from pathlib import Path

from eight_ball.agents_csv.keys import (
    host_profile_key,
    profile_key,
    provider_composite_key,
    record_dedup_key,
)
from eight_ball.agents_csv.registry import SourceSpec, precedence_rank, source_specs
from eight_ball.agents_csv.validate import validate_agents_csv_collection


def test_registry_maps_each_agents_csv_to_one_namespace():
    specs = source_specs()
    paths = [spec.path for spec in specs]
    assert len(paths) == len(set(paths))
    namespaces = {spec.namespace for spec in specs}
    assert namespaces == {
        "provider_instance_data",
        "assumed_hardware_profiles",
        "measured_hardware_inventory",
        "classification_data",
        "control_and_provenance",
    }


def test_provider_composite_key_uses_provider_product_line_and_plan_id():
    key = provider_composite_key(
        {
            "provider": "DigitalOcean",
            "product_line": "GPU Droplets",
            "internal_plan_id": "do-gpu-rtx-4000-ada-1x",
        },
        plan_id_field="internal_plan_id",
    )
    assert key == "provider_instance:DigitalOcean|GPU Droplets|do-gpu-rtx-4000-ada-1x"


def test_profile_and_host_keys_are_namespace_prefixed():
    assert profile_key({"profile_id": "cuda_entry_8gb"}) == "assumed_profile:cuda_entry_8gb"
    assert host_profile_key({"host_profile_id": "local-brain1-rtx3060-12gb"}) == (
        "measured_host:local-brain1-rtx3060-12gb"
    )


def test_precedence_ordering():
    assert precedence_rank("measured_host_inventory") > precedence_rank("provider_published")
    assert precedence_rank("provider_published_hardware_plan") > precedence_rank(
        "assumed_client_class"
    )
    assert precedence_rank("internal_assumption_class") > precedence_rank("unknown")


def test_validate_agents_csv_collection_passes_on_committed_files():
    report = validate_agents_csv_collection()
    assert report.ok, report.errors
    assert report.namespace_counts["provider_instance_data"] > 0
    assert report.namespace_counts["assumed_hardware_profiles"] > 0
    assert report.namespace_counts["measured_hardware_inventory"] == 1
    assert report.namespace_counts["classification_data"] > 0
    assert not report.duplicate_keys
    assert len(report.intentional_overlaps) > 0


def test_duplicate_profile_id_fails(tmp_path: Path):
    csv_path = tmp_path / "dup-profiles.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["profile_id", "provenance_status"])
        writer.writeheader()
        writer.writerow({"profile_id": "dup_profile", "provenance_status": "assumed_client_class"})
        writer.writerow({"profile_id": "dup_profile", "provenance_status": "assumed_client_class"})

    source = SourceSpec(
        id="dup-test",
        path=str(csv_path),
        namespace="assumed_hardware_profiles",
        format="csv",
        importable=True,
        options={"profile_id_field": "profile_id"},
    )
    report = validate_agents_csv_collection(sources=[source], repo_root=tmp_path)
    assert not report.ok
    assert any("duplicate assumed_hardware_profiles" in error for error in report.errors)


def test_lower_confidence_duplicate_triggers_precedence_error(tmp_path: Path):
    csv_path = tmp_path / "precedence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["host_profile_id", "provenance_status"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "host_profile_id": "host-dup",
                "provenance_status": "measured_host_inventory",
            }
        )
        writer.writerow(
            {
                "host_profile_id": "host-dup",
                "provenance_status": "assumed_client_class",
            }
        )

    source = SourceSpec(
        id="precedence-test",
        path=str(csv_path),
        namespace="measured_hardware_inventory",
        format="csv",
        importable=True,
        options={"host_profile_id_field": "host_profile_id"},
    )
    report = validate_agents_csv_collection(sources=[source], repo_root=tmp_path)
    assert not report.ok
    assert any("lower-confidence record would overwrite" in error for error in report.errors)


def test_control_file_with_data_identifiers_fails(tmp_path: Path):
    csv_path = tmp_path / "bad-control.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["step", "profile_id"])
        writer.writeheader()
        writer.writerow({"step": "1", "profile_id": "mac_air_apple_silicon_8gb"})

    source = SourceSpec(
        id="bad-control",
        path=str(csv_path),
        namespace="control_and_provenance",
        format="csv",
        importable=False,
        options={"control_kind": "cursor_checklist"},
    )
    report = validate_agents_csv_collection(sources=[source], repo_root=tmp_path)
    assert not report.ok
    assert any("control/provenance file contains importable data-row identifiers" in error for error in report.errors)


def test_record_dedup_key_for_p2_json_provider_row():
    source = next(spec for spec in source_specs() if spec.id == "digitalocean-basic")
    key = record_dedup_key(
        {
            "provider": "digitalocean",
            "family": "Basic",
            "plan_slug": "s-1vcpu-1gb",
        },
        source,
    )
    assert key == "provider_instance:digitalocean|Basic|s-1vcpu-1gb"

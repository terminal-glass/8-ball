from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import load_json
from eight_ball.paths import NORMALIZED_DIR


def _hardware_paths(normalized_dir: Path) -> dict[str, Path]:
    return {
        "provider_instances": normalized_dir / "hardware-provider-instances.json",
        "assumed_profiles": normalized_dir / "hardware-assumed-profiles.json",
        "measured_hosts": normalized_dir / "hardware-measured-hosts.json",
        "accelerator_classes": normalized_dir / "hardware-accelerator-classes.json",
        "deployment_types": normalized_dir / "hardware-deployment-types.json",
    }


def load_canonical_hardware(*, normalized_dir: Path = NORMALIZED_DIR) -> dict[str, list[dict[str, Any]]]:
    paths = _hardware_paths(normalized_dir)
    loaded: dict[str, list[dict[str, Any]]] = {}
    for key, path in paths.items():
        if path.is_file():
            loaded[key] = load_json(path)
        else:
            loaded[key] = []
    return loaded


def build_hardware_index(hardware: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    provider_by_id = {item["id"]: item for item in hardware.get("provider_instances", [])}
    assumed_by_id = {item["id"]: item for item in hardware.get("assumed_profiles", [])}
    measured_by_id = {item["id"]: item for item in hardware.get("measured_hosts", [])}
    accelerator_by_id = {item["id"]: item for item in hardware.get("accelerator_classes", [])}
    return {
        "provider_instances": provider_by_id,
        "assumed_profiles": assumed_by_id,
        "measured_hosts": measured_by_id,
        "accelerator_classes": accelerator_by_id,
    }


def _matches_deployment_type(record: dict[str, Any], deployment_type_id: str) -> bool:
    record_type = record.get("deployment_type_id")
    if record_type in (None, "unassigned"):
        return deployment_type_id == "3"
    return str(record_type) == str(deployment_type_id)


def enrich_deployment_hardware(
    *,
    deployment_type_id: str,
    hardware_profile_id: str,
    hardware: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    provider_instances = [
        item["id"]
        for item in hardware.get("provider_instances", [])
        if _matches_deployment_type(item, deployment_type_id)
    ]
    assumed_profiles = [
        item["id"]
        for item in hardware.get("assumed_profiles", [])
        if _matches_deployment_type(item, deployment_type_id)
    ]
    compatible_measured_host_ids = [
        item["id"]
        for item in hardware.get("measured_hosts", [])
        if _matches_deployment_type(item, deployment_type_id) or item.get("deployment_type_id") in (
            None,
            "unassigned",
        )
    ]
    accelerator_ids = sorted(
        {
            item.get("accelerator_class_id")
            for item in hardware.get("provider_instances", []) + hardware.get("assumed_profiles", [])
            if item.get("accelerator_class_id")
            and _matches_deployment_type(item, deployment_type_id)
        }
    )
    cuda_suitable = any(
        item.get("cuda_available")
        for item in hardware.get("provider_instances", []) + hardware.get("assumed_profiles", [])
        if _matches_deployment_type(item, deployment_type_id)
    )
    rocm_suitable = any(
        item.get("rocm_available")
        for item in hardware.get("provider_instances", []) + hardware.get("assumed_profiles", [])
        if _matches_deployment_type(item, deployment_type_id)
    )
    apple_metal_suitable = any(
        item.get("apple_metal_available")
        for item in hardware.get("assumed_profiles", [])
        if _matches_deployment_type(item, deployment_type_id)
    )
    cpu_only_suitable = hardware_profile_id in {
        "cpu-small",
        "desktop-standard",
        "server-high-mem",
    } or any(
        item.get("accelerator_class_id") == "none_cpu_only"
        for item in hardware.get("provider_instances", []) + hardware.get("assumed_profiles", [])
        if _matches_deployment_type(item, deployment_type_id)
    )
    measured_evidence = [
        {
            "host_profile_id": item.get("host_profile_id"),
            "provenance_status": item.get("provenance_status"),
            "ollama_inference_verified": item.get("ollama_inference_verified"),
        }
        for item in hardware.get("measured_hosts", [])
    ]
    return {
        "compatible_provider_instance_ids": provider_instances,
        "compatible_assumed_profile_ids": assumed_profiles,
        "compatible_measured_host_ids": compatible_measured_host_ids,
        "accelerator_class_ids": [item for item in accelerator_ids if item],
        "cpu_only_suitable": cpu_only_suitable,
        "cuda_suitable": cuda_suitable,
        "rocm_suitable": rocm_suitable,
        "apple_metal_suitable": apple_metal_suitable,
        "measured_host_evidence": measured_evidence,
        "provenance_status": "derived_from_c6_import",
    }


def compact_hardware_catalog(hardware: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "provider_instances": {
            item["id"]: {
                "provider": item.get("provider"),
                "product_line": item.get("product_line"),
                "provider_plan_id": item.get("provider_plan_id"),
                "display_name": item.get("display_name"),
                "deployment_type_id": item.get("deployment_type_id"),
                "accelerator_class_id": item.get("accelerator_class_id"),
                "provenance_status": item.get("provenance_status"),
            }
            for item in hardware.get("provider_instances", [])
        },
        "assumed_profiles": {
            item["id"]: {
                "profile_id": item.get("profile_id"),
                "display_name": item.get("display_name"),
                "deployment_type_id": item.get("deployment_type_id"),
                "accelerator_class_id": item.get("accelerator_class_id"),
                "provenance_status": item.get("provenance_status"),
            }
            for item in hardware.get("assumed_profiles", [])
        },
        "measured_hosts": {
            item["id"]: {
                "host_profile_id": item.get("host_profile_id"),
                "host_name": item.get("host_name"),
                "gpu_model": item.get("gpu_model"),
                "provenance_status": item.get("provenance_status"),
                "ollama_inference_verified": item.get("ollama_inference_verified"),
            }
            for item in hardware.get("measured_hosts", [])
        },
        "accelerator_classes": {
            item["id"]: {
                "accelerator_class_id": item.get("accelerator_class_id"),
                "display_name": item.get("display_name"),
                "vendor": item.get("vendor"),
                "backend": item.get("backend"),
                "provenance_status": item.get("provenance_status"),
            }
            for item in hardware.get("accelerator_classes", [])
        },
    }

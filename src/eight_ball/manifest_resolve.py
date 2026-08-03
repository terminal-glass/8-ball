from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eight_ball.config import deployment_type_ids, load_json
from eight_ball.paths import GENERATED_INSTALL_MANIFEST_PATH

VALID_DEPLOYMENT_TYPE_IDS = tuple(deployment_type_ids())

UNSUITABLE_ASSESSMENTS = frozenset({"insufficient_memory"})

SIZING_LOG_FIELDS = (
    "installed_storage_bytes_estimated",
    "min_system_ram_gb_estimated",
    "recommended_system_ram_gb_estimated",
    "min_vram_gb_estimated",
    "recommended_vram_gb_estimated",
    "disk_estimate_gb",
    "cpu_suitability",
    "gpu_suitability",
)


@dataclass(frozen=True)
class ManifestSelection:
    model_id: str
    model_slug: str
    family_id: str
    family_slug: str
    deployment_type_id: str
    ollama_identifier: str
    deployment: dict[str, Any]
    requested_model_ref: str
    requested_deployment_type_id: str
    fallback_used: bool
    fallback_reason: str | None


def load_install_manifest(path: Path = GENERATED_INSTALL_MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_json(path)
    if manifest.get("schema_version") != "c5.install-manifest.v1":
        raise ValueError(f"unsupported install manifest schema: {manifest.get('schema_version')}")
    return manifest


def resolve_model_id(manifest: dict[str, Any], model_ref: str) -> str | None:
    models = manifest.get("models", {})
    if model_ref in models:
        return model_ref

    normalized_ref = model_ref.strip()
    for model_id, entry in models.items():
        if entry.get("model_id") == normalized_ref:
            return model_id
        if entry.get("model_slug") == normalized_ref:
            return model_id

    for model_id, entry in models.items():
        deployments = entry.get("deployments", {})
        for deployment in deployments.values():
            if deployment.get("ollama_identifier") == normalized_ref:
                return model_id
    return None


def deployment_is_suitable(deployment: dict[str, Any]) -> bool:
    return deployment.get("assessment") not in UNSUITABLE_ASSESSMENTS


def get_manifest_deployment(
    manifest: dict[str, Any],
    model_ref: str,
    deployment_type_id: str,
) -> dict[str, Any] | None:
    model_id = resolve_model_id(manifest, model_ref)
    if model_id is None:
        return None
    return manifest["models"][model_id].get("deployments", {}).get(str(deployment_type_id))


def _deployment_type_fallback_order(requested_deployment_type_id: str) -> list[str]:
    if requested_deployment_type_id not in VALID_DEPLOYMENT_TYPE_IDS:
        return list(VALID_DEPLOYMENT_TYPE_IDS)
    requested = int(requested_deployment_type_id)
    return [str(value) for value in range(requested, 2, -1) if str(value) in VALID_DEPLOYMENT_TYPE_IDS]


def _model_fallback_candidates(
    manifest: dict[str, Any],
    *,
    deployment_type_id: str,
    family_slug: str | None,
) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any], int, int, str]] = []
    for model_id, entry in manifest.get("models", {}).items():
        deployment = entry.get("deployments", {}).get(deployment_type_id)
        if deployment is None or not deployment_is_suitable(deployment):
            continue
        storage = deployment.get("installed_storage_bytes_estimated")
        storage_sort = storage if isinstance(storage, int) else 10**18
        same_family = 0 if entry.get("family_slug") == family_slug else 1
        candidates.append((model_id, deployment, same_family, storage_sort, entry.get("model_slug", model_id)))
    candidates.sort(key=lambda item: (item[2], item[3], item[4], item[0]))
    return [(model_id, deployment) for model_id, deployment, _, _, _ in candidates]


def iter_manifest_fallback_deployments(
    manifest: dict[str, Any],
    model_ref: str,
    deployment_type_id: str,
) -> Iterator[tuple[str, dict[str, Any], str]]:
    model_id = resolve_model_id(manifest, model_ref)
    if model_id is None:
        return

    entry = manifest["models"][model_id]
    deployments = entry.get("deployments", {})
    seen: set[tuple[str, str]] = set()

    for candidate_type_id in _deployment_type_fallback_order(deployment_type_id):
        deployment = deployments.get(candidate_type_id)
        if deployment is None or not deployment_is_suitable(deployment):
            continue
        key = (model_id, candidate_type_id)
        if key in seen:
            continue
        seen.add(key)
        reason = (
            "exact_match"
            if candidate_type_id == str(deployment_type_id)
            else f"deployment_type_fallback:{deployment_type_id}->{candidate_type_id}"
        )
        yield model_id, deployment, reason

    family_slug = entry.get("family_slug")
    for candidate_model_id, deployment in _model_fallback_candidates(
        manifest,
        deployment_type_id=str(deployment_type_id),
        family_slug=family_slug,
    ):
        if candidate_model_id == model_id:
            continue
        key = (candidate_model_id, str(deployment_type_id))
        if key in seen:
            continue
        seen.add(key)
        yield candidate_model_id, deployment, f"model_fallback:{model_id}->{candidate_model_id}"


def resolve_manifest_selection(
    manifest: dict[str, Any],
    *,
    model_ref: str,
    deployment_type_id: str,
) -> ManifestSelection | None:
    deployment_type_id = str(deployment_type_id)
    if deployment_type_id not in VALID_DEPLOYMENT_TYPE_IDS:
        raise ValueError(
            f"deployment_type_id must be one of {VALID_DEPLOYMENT_TYPE_IDS}, got {deployment_type_id!r}"
        )

    for model_id, deployment, reason in iter_manifest_fallback_deployments(
        manifest, model_ref, deployment_type_id
    ):
        return ManifestSelection(
            model_id=deployment["model_id"],
            model_slug=deployment["model_slug"],
            family_id=deployment["family_id"],
            family_slug=deployment["family_slug"],
            deployment_type_id=deployment["deployment_type_id"],
            ollama_identifier=deployment["ollama_identifier"],
            deployment=deployment,
            requested_model_ref=model_ref,
            requested_deployment_type_id=deployment_type_id,
            fallback_used=reason != "exact_match",
            fallback_reason=None if reason == "exact_match" else reason,
        )
    return None


def sizing_log_record(selection: ManifestSelection) -> dict[str, Any]:
    deployment = selection.deployment
    return {
        "model_id": selection.model_id,
        "model_slug": selection.model_slug,
        "family_id": selection.family_id,
        "family_slug": selection.family_slug,
        "deployment_type_id": selection.deployment_type_id,
        "requested_model_ref": selection.requested_model_ref,
        "requested_deployment_type_id": selection.requested_deployment_type_id,
        "ollama_identifier": selection.ollama_identifier,
        "hardware_profile_id": deployment.get("hardware_profile_id"),
        "runtime_policy_id": deployment.get("runtime_policy_id"),
        "assessment": deployment.get("assessment"),
        "reason_codes": deployment.get("reason_codes", []),
        "explanation": deployment.get("explanation"),
        "installed_storage_bytes_estimated": deployment.get("installed_storage_bytes_estimated"),
        "min_system_ram_gb_estimated": deployment.get("min_system_ram_gb_estimated"),
        "recommended_system_ram_gb_estimated": deployment.get(
            "recommended_system_ram_gb_estimated"
        ),
        "min_vram_gb_estimated": deployment.get("min_vram_gb_estimated"),
        "recommended_vram_gb_estimated": deployment.get("recommended_vram_gb_estimated"),
        "disk_estimate_gb": deployment.get("disk_estimate_gb"),
        "cpu_suitability": deployment.get("cpu_suitability"),
        "gpu_suitability": deployment.get("gpu_suitability"),
        "pull_command": deployment.get("pull_command"),
        "run_command": deployment.get("run_command"),
        "helper_path": deployment.get("helper_path"),
        "fallback_used": selection.fallback_used,
        "fallback_reason": selection.fallback_reason,
    }


def format_sizing_log_lines(selection: ManifestSelection) -> list[str]:
    record = sizing_log_record(selection)
    lines = [
        f"Model ID: {record['model_id']}",
        f"Model slug: {record['model_slug']}",
        f"Family: {record['family_slug']}",
        f"Deployment type: {record['deployment_type_id']}",
        f"Ollama identifier: {record['ollama_identifier']}",
        f"Assessment: {record['assessment']}",
        f"Hardware profile: {record['hardware_profile_id']}",
        f"Runtime policy: {record['runtime_policy_id']}",
        f"Installed storage (bytes est.): {record['installed_storage_bytes_estimated']}",
        f"Min system RAM (GB est.): {record['min_system_ram_gb_estimated']}",
        f"Recommended system RAM (GB est.): {record['recommended_system_ram_gb_estimated']}",
        f"Min VRAM (GB est.): {record['min_vram_gb_estimated']}",
        f"Recommended VRAM (GB est.): {record['recommended_vram_gb_estimated']}",
        f"Disk estimate (GB): {record['disk_estimate_gb']}",
        f"CPU suitability: {record['cpu_suitability']}",
        f"GPU suitability: {record['gpu_suitability']}",
        f"Pull command: {record['pull_command']}",
        f"Run command: {record['run_command']}",
    ]
    if record["fallback_used"]:
        lines.append(f"Fallback reason: {record['fallback_reason']}")
    return lines

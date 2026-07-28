from __future__ import annotations

import hashlib
from typing import Any

from eight_ball.config import deployment_tiers_config
from eight_ball.estimate.hardware import estimate_memory_gb, load_hardware_profiles


def stable_deployment_id(tag_id: str, profile_id: str, policy_id: str) -> str:
    raw = f"{tag_id}|{profile_id}|{policy_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def assess_deployment(
    tag: dict[str, Any],
    profile: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    availability = tag.get("availability", "unknown")
    if availability in {"cloud", "cloud_only"}:
        if profile["id"] == "cloud-only":
            return _result(
                tag,
                profile,
                policy,
                "recommended",
                ["cloud_model", "cloud_profile"],
                "Cloud-hosted model accessed from a cloud-capable client profile.",
            )
        return _result(
            tag,
            profile,
            policy,
            "cloud_only",
            ["cloud_model", "local_profile_unsuitable"],
            "Model is cloud-hosted; local hardware profile is not applicable for weights.",
        )

    memory = estimate_memory_gb(
        tag,
        context_tokens=policy.get("context_tokens", 4096),
        safety_margin=policy.get("safety_margin", 1.15),
    )
    required_ram = memory["recommended_system_ram_gb"] or 0.0
    required_vram = memory["recommended_vram_gb"] or 0.0
    profile_ram = profile["system_ram_gb"]
    profile_vram = profile["vram_gb"]

    if profile["id"] == "cloud-only":
        return _result(
            tag,
            profile,
            policy,
            "insufficient_memory",
            ["local_model", "cloud_only_profile"],
            "Local model cannot run on a cloud-only access profile.",
            memory,
        )

    if required_ram == 0:
        return _result(
            tag,
            profile,
            policy,
            "unknown",
            ["missing_size_or_parameters"],
            "Insufficient metadata to estimate memory requirements.",
            memory,
        )

    if profile["cpu_only"]:
        if required_ram <= profile_ram:
            return _result(
                tag,
                profile,
                policy,
                "cpu_only_practical",
                ["fits_system_ram", "cpu_profile"],
                "Estimated memory fits CPU-only system RAM with constraints.",
                memory,
            )
        return _result(
            tag,
            profile,
            policy,
            "insufficient_memory",
            ["exceeds_system_ram", "cpu_profile"],
            "Estimated memory exceeds CPU-only system RAM.",
            memory,
        )

    if required_vram <= profile_vram and required_ram <= profile_ram:
        return _result(
            tag,
            profile,
            policy,
            "full_gpu_fit",
            ["fits_vram", "fits_system_ram"],
            "Estimated model and runtime memory fit available VRAM and system RAM.",
            memory,
        )
    if required_vram * 0.6 <= profile_vram:
        return _result(
            tag,
            profile,
            policy,
            "partial_gpu_offload",
            ["partial_vram_fit"],
            "Model may run with partial GPU offload and CPU assistance.",
            memory,
        )
    if required_ram <= profile_ram:
        return _result(
            tag,
            profile,
            policy,
            "runs_with_constraints",
            ["fits_system_ram", "limited_vram"],
            "May run with constraints using CPU RAM and limited VRAM.",
            memory,
        )
    return _result(
        tag,
        profile,
        policy,
        "insufficient_memory",
        ["exceeds_system_ram"],
        "Estimated memory exceeds available system resources.",
        memory,
    )


def _result(
    tag: dict[str, Any],
    profile: dict[str, Any],
    policy: dict[str, Any],
    assessment: str,
    reason_codes: list[str],
    explanation: str,
    memory: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    memory = memory or estimate_memory_gb(tag, context_tokens=policy.get("context_tokens", 4096))
    return {
        "id": stable_deployment_id(tag["id"], profile["id"], policy["id"]),
        "tag_id": tag["id"],
        "hardware_profile_id": profile["id"],
        "runtime_policy_id": policy["id"],
        "assessment": assessment,
        "reason_codes": reason_codes,
        "explanation": explanation,
        "min_system_ram_gb_estimated": memory.get("min_system_ram_gb"),
        "recommended_system_ram_gb_estimated": memory.get("recommended_system_ram_gb"),
        "min_vram_gb_estimated": memory.get("min_vram_gb"),
        "recommended_vram_gb_estimated": memory.get("recommended_vram_gb"),
    }


def generate_deployments(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles = load_hardware_profiles()
    policies = deployment_tiers_config().get("runtime_policies", [])
    rows: list[dict[str, Any]] = []
    for tag in tags:
        for profile in profiles:
            for policy in policies:
                rows.append(assess_deployment(tag, profile, policy))
    rows.sort(key=lambda row: row["id"])
    return rows

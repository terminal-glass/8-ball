from __future__ import annotations

from typing import Any

from eight_ball.config import hardware_profiles_config

# Heuristic bytes-per-parameter by quantization family (estimated, not vendor guarantees).
QUANT_BYTES_PER_PARAM: dict[str, float] = {
    "fp16": 2.0,
    "q8_0": 1.0,
    "q6_K": 0.85,
    "q5_K_M": 0.7,
    "q5_0": 0.7,
    "q4_K_M": 0.55,
    "q4_0": 0.55,
    "q3_K_M": 0.45,
    "q2_K": 0.35,
}


def _quantization_key(quantization: str | None) -> str:
    if not quantization:
        return "q4_0"
    return quantization


def estimate_installed_storage_bytes(tag: dict[str, Any]) -> int | None:
    observed = tag.get("download_size_bytes")
    if observed is not None:
        return int(observed * 1.08)
    params = tag.get("parameter_count")
    if params is None:
        return None
    quant = _quantization_key(tag.get("quantization"))
    bpp = QUANT_BYTES_PER_PARAM.get(quant, 0.55)
    return int(params * bpp * 1.08)


def estimate_memory_gb(
    tag: dict[str, Any],
    *,
    context_tokens: int = 4096,
    safety_margin: float = 1.15,
) -> dict[str, float | None]:
    storage_bytes = tag.get("download_size_bytes") or estimate_installed_storage_bytes(tag)
    if storage_bytes is None:
        return {
            "min_system_ram_gb": None,
            "recommended_system_ram_gb": None,
            "min_vram_gb": None,
            "recommended_vram_gb": None,
        }

    model_gb = storage_bytes / 1_000_000_000
    params = tag.get("parameter_count") or 0
    kv_gb = (params / 1_000_000_000) * (context_tokens / 4096) * 0.25
    runtime_gb = 1.5
    total = (model_gb + kv_gb + runtime_gb) * safety_margin

    if tag.get("availability") in {"cloud", "cloud_only"} and tag.get("download_size_bytes") is None:
        return {
            "min_system_ram_gb": 0.0,
            "recommended_system_ram_gb": 0.0,
            "min_vram_gb": 0.0,
            "recommended_vram_gb": 0.0,
        }

    return {
        "min_system_ram_gb": round(total, 2),
        "recommended_system_ram_gb": round(total * 1.2, 2),
        "min_vram_gb": round(model_gb * safety_margin, 2),
        "recommended_vram_gb": round(total, 2),
    }


def load_hardware_profiles() -> list[dict[str, Any]]:
    return hardware_profiles_config().get("profiles", [])

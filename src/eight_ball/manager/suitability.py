from __future__ import annotations

from typing import Any

# Estimated bytes per parameter. Used only with a known parameter count and
# quantization. Download size is never an input to this table.
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

CLASSIFICATIONS = (
    "recommended",
    "estimated_fit",
    "insufficient_resources",
    "unknown",
    "not_local",
)
LOCAL_DOWNLOAD = {"local", "both"}
HOSTED_ONLY = {"cloud", "cloud_only"}


def format_si_bytes(value: int | None) -> str | None:
    """Decimal SI labels. 1 KB = 1000 bytes."""
    if value is None:
        return None
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1000 or unit == "TB":
            if unit == "B":
                return f"{int(number)} B"
            return f"{number:.1f} {unit}"
        number /= 1000
    return None


def estimate_runtime_memory_bytes(tag: dict[str, Any]) -> int | None:
    """Estimate runtime memory from parameter count and quantization only."""
    params = tag.get("parameter_count")
    quant = tag.get("quantization")
    if params is None or quant is None:
        return None
    per_param = QUANT_BYTES_PER_PARAM.get(quant)
    if per_param is None:
        return None
    return int(params * per_param * 1.15)


def assess_suitability(
    tag: dict[str, Any],
    hardware: dict[str, Any] | None = None,
    *,
    measured_memory_bytes: int | None = None,
) -> dict[str, Any]:
    hardware = hardware or {}
    availability = tag.get("availability", "unknown")
    download_bytes = tag.get("download_size_bytes")
    base = {
        "exact_tag": tag.get("ollama_identifier"),
        "availability": availability,
        "download_size_bytes": download_bytes,
        "download_size_text": format_si_bytes(download_bytes) or tag.get("download_size_text"),
        "estimated_runtime_memory_bytes": None,
        "download_size_used_as_memory": False,
        "evidence_level": "unknown",
        "classification": "unknown",
        "reason": "Suitability is unknown.",
        "local_download": availability in LOCAL_DOWNLOAD,
    }
    if availability in HOSTED_ONLY:
        base["classification"] = "not_local"
        base["local_download"] = False
        base["reason"] = (
            "This model is hosted. It is not offered as a local download. "
            "Download size is not a RAM or VRAM requirement."
        )
        return base

    if measured_memory_bytes is not None:
        memory = measured_memory_bytes
        evidence = "observed"
        memory_source = "a measured test"
    else:
        memory = estimate_runtime_memory_bytes(tag)
        evidence = "estimated" if memory is not None else "unknown"
        memory_source = "parameter count and quantization"
    base["estimated_runtime_memory_bytes"] = memory
    base["evidence_level"] = evidence
    if memory is None:
        base["classification"] = "unknown"
        base["reason"] = (
            "Parameter count or quantization is unresolved, so runtime memory stays unknown. "
            "Download size is not used as RAM or VRAM."
        )
        return base

    ram = hardware.get("ram_bytes")
    vram = hardware.get("vram_bytes")
    if ram is None:
        base["classification"] = "unknown"
        base["reason"] = (
            f"Runtime memory is {evidence} at {memory} bytes from {memory_source}. "
            "RAM was not detected, so fit stays unknown."
        )
        return base
    if memory > ram:
        base["classification"] = "insufficient_resources"
        base["reason"] = (
            f"Estimated runtime memory is {memory} bytes and detected RAM is {ram} bytes. "
            "Download size was not used for this comparison."
        )
        return base
    if vram is None:
        base["classification"] = "estimated_fit"
        base["reason"] = (
            f"Estimated runtime memory is {memory} bytes and detected RAM is {ram} bytes. "
            "VRAM was not detected, so the fit stays estimated."
        )
        return base
    if memory <= vram and memory * 1.2 <= ram:
        base["classification"] = "recommended"
        base["reason"] = (
            f"Estimated runtime memory is {memory} bytes. Detected RAM is {ram} bytes "
            f"and detected VRAM is {vram} bytes."
        )
        return base
    if memory * 0.6 <= vram:
        base["classification"] = "estimated_fit"
        base["reason"] = (
            "VRAM covers only part of the estimated runtime memory. "
            f"Estimated runtime memory is {memory} bytes and detected VRAM is {vram} bytes."
        )
        return base
    base["classification"] = "insufficient_resources"
    base["reason"] = (
        f"Estimated runtime memory is {memory} bytes and detected VRAM is {vram} bytes."
    )
    return base

from __future__ import annotations

import re
from typing import Any

_UNKNOWN_TOKENS = frozenset(
    {
        "",
        "unknown",
        "unassigned",
        "null",
        "none",
        "n/a",
        "na",
        "not listed in cited hardware-plan table",
        "runtime_detection_required",
        "runtime verification required",
        "unverified until gpu model, driver, and vram are detected",
    }
)


def _is_unknown(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in _UNKNOWN_TOKENS


def as_optional_string(value: Any) -> str | None:
    if _is_unknown(value):
        return None
    text = str(value).strip()
    return text or None


def as_optional_bool(value: Any) -> bool | None:
    if _is_unknown(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    return None


def as_optional_int(value: Any) -> int | None:
    if _is_unknown(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if "|" in text:
        return None
    match = re.match(r"^-?\d+$", text)
    if match:
        return int(text)
    match = re.match(r"^-?\d+\.?\d*$", text)
    if match:
        return int(float(text))
    return None


def as_optional_float(value: Any) -> float | None:
    if _is_unknown(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if "|" in text:
        return None
    match = re.match(r"^-?\d+(\.\d+)?$", text)
    if match:
        return float(text)
    return None


def accelerator_flags(accelerator_class_id: str | None) -> dict[str, bool | None]:
    if not accelerator_class_id:
        return {
            "cuda_available": None,
            "rocm_available": None,
            "apple_metal_available": None,
        }
    normalized = accelerator_class_id.strip().lower()
    return {
        "cuda_available": normalized.startswith("nvidia_cuda"),
        "rocm_available": normalized == "amd_rocm",
        "apple_metal_available": normalized == "apple_metal",
    }

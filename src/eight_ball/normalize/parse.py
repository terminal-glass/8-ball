from __future__ import annotations

import re

_SIZE_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$",
    re.IGNORECASE,
)
_CONTEXT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMG])", re.IGNORECASE)
_PARAM_RE = re.compile(r"^(\d+(?:\.\d+)?)([kmbt])$", re.IGNORECASE)


def parse_size_text_to_bytes(text: str | None, *, decimal: bool = True) -> int | None:
    if not text:
        return None
    cleaned = text.strip().replace(" ", "")
    match = _SIZE_RE.match(cleaned)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).upper()
    base = 1000 if decimal else 1024
    multipliers = {
        "B": 1,
        "KB": base,
        "MB": base**2,
        "GB": base**3,
        "TB": base**4,
    }
    return int(amount * multipliers[unit])


def parse_context_length(text: str | None) -> int | None:
    if not text:
        return None
    match = _CONTEXT_RE.match(text.strip())
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"K": 1_000, "M": 1_000_000, "G": 1_000_000_000}
    return int(amount * multipliers[unit])


def parse_parameter_label(label: str | None) -> tuple[int | None, str | None]:
    if not label:
        return None, None
    match = _PARAM_RE.match(label.strip().lower())
    if not match:
        return None, label
    amount = float(match.group(1))
    unit = match.group(2)
    scale = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
    return int(amount * scale[unit]), label


def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "-")

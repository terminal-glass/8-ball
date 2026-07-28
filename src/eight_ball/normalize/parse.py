from __future__ import annotations

import re
from decimal import Decimal

_SIZE_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$",
    re.IGNORECASE,
)
_CONTEXT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMG])", re.IGNORECASE)
_PARAM_RE = re.compile(r"^(\d+(?:\.\d+)?)([kmbt])$", re.IGNORECASE)

_DECIMAL_MULTIPLIERS = {
    "B": Decimal(1),
    "KB": Decimal(1_000),
    "MB": Decimal(1_000_000),
    "GB": Decimal(1_000_000_000),
    "TB": Decimal(1_000_000_000_000),
}
_BINARY_MULTIPLIERS = {
    "B": Decimal(1),
    "KB": Decimal(1024),
    "MB": Decimal(1024) ** 2,
    "GB": Decimal(1024) ** 3,
    "TB": Decimal(1024) ** 4,
}
_CONTEXT_MULTIPLIERS = {"K": Decimal(1_000), "M": Decimal(1_000_000), "G": Decimal(1_000_000_000)}
_PARAM_SCALE = {
    "k": Decimal(1_000),
    "m": Decimal(1_000_000),
    "b": Decimal(1_000_000_000),
    "t": Decimal(1_000_000_000_000),
}


def parse_size_text_to_bytes(text: str | None, *, decimal: bool = True) -> int | None:
    if not text:
        return None
    cleaned = text.strip().replace(" ", "")
    match = _SIZE_RE.match(cleaned)
    if not match:
        return None
    amount = Decimal(match.group(1))
    unit = match.group(2).upper()
    multipliers = _DECIMAL_MULTIPLIERS if decimal else _BINARY_MULTIPLIERS
    return int(amount * multipliers[unit])


def parse_context_length(text: str | None) -> int | None:
    if not text:
        return None
    match = _CONTEXT_RE.match(text.strip())
    if not match:
        return None
    amount = Decimal(match.group(1))
    unit = match.group(2).upper()
    return int(amount * _CONTEXT_MULTIPLIERS[unit])


def parse_parameter_label(label: str | None) -> tuple[int | None, str | None]:
    if not label:
        return None, None
    match = _PARAM_RE.match(label.strip().lower())
    if not match:
        return None, label
    amount = Decimal(match.group(1))
    unit = match.group(2)
    return int(amount * _PARAM_SCALE[unit]), label


def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "-")

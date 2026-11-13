"""The 0-9 machine scale. Older profile names are aliases of these levels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from eight_ball.config import load_json, load_yaml
from eight_ball.paths import CONFIG_DIR, SCHEMAS_DIR

SCALE_PATH = CONFIG_DIR / "hardware_scale.yaml"


def load_scale(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or SCALE_PATH)


def scale_errors(document: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMAS_DIR / "hardware-scale.schema.json")
    validator = Draft202012Validator(schema)
    errors = [
        error.message
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    ]
    levels = [row.get("level") for row in document.get("levels") or []]
    if levels != list(range(10)):
        errors.append("hardware scale levels must be 0 through 9 in order")
    seen: set[str] = set()
    for row in document.get("levels") or []:
        for legacy_id in row.get("legacy_ids") or []:
            if legacy_id in seen:
                errors.append(f"legacy id {legacy_id} is on more than one level")
            seen.add(legacy_id)
            if legacy_id == "cloud-only":
                errors.append("cloud-only is hosted access, not a machine level")
    return errors


def level_row(document: dict[str, Any], level: int) -> dict[str, Any]:
    for row in document["levels"]:
        if row["level"] == level:
            return row
    raise KeyError(level)


def place_by_ram(document: dict[str, Any], ram_bytes: int | None) -> dict[str, Any]:
    """Place a machine from measured RAM. Missing RAM stays unknown."""
    if ram_bytes is None:
        return {
            "level": None,
            "display_name": None,
            "evidence": "unknown",
            "reason": "RAM was not measured, so the machine is not placed on the 0-9 scale.",
        }
    for row in document["levels"]:
        upper = row["max_ram_bytes"]
        if ram_bytes >= row["min_ram_bytes"] and (upper is None or ram_bytes < upper):
            return {
                "level": row["level"],
                "display_name": row["display_name"],
                "evidence": "measured",
                "reason": (
                    f"Measured RAM is {ram_bytes} bytes, which is level {row['level']} "
                    f"({row['display_name']})."
                ),
            }
    return {
        "level": None,
        "display_name": None,
        "evidence": "unknown",
        "reason": "Measured RAM did not match a scale band.",
    }


def legacy_level(document: dict[str, Any], legacy_id: str) -> int | None:
    for row in document["levels"]:
        if legacy_id in row.get("legacy_ids") or []:
            return row["level"]
    return None


def render_scale(document: dict[str, Any]) -> str:
    lines = [
        "<!-- Generated from config/hardware_scale.yaml by eight_ball.scale. Do not edit by hand. -->",
        "",
        "# Hardware scale 0-9",
        "",
        "This is the machine scale installers consult. Decimal SI bytes.",
        "Level 0 is Raspberry Pi class. Level 9 is top of the line.",
        "Installer stage numbers are not these levels.",
        "cloud-only is hosted access, not a row in this table.",
        "",
        "| Level | Name | RAM from | RAM below | Legacy names |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in document["levels"]:
        upper = "none" if row["max_ram_bytes"] is None else str(row["max_ram_bytes"])
        legacy = ", ".join(row["legacy_ids"]) if row["legacy_ids"] else "none"
        lines.append(
            f"| {row['level']} | {row['display_name']} | {row['min_ram_bytes']} | {upper} | {legacy} |"
        )
    lines.extend(
        [
            "",
            "Canary tag: `" + document["canary"]["tag"] + "`.",
            "",
            document["jets_note"].strip(),
            "",
        ]
    )
    return "\n".join(lines)

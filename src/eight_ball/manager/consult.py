"""Consultation: measure a canary, then offer Llama and Grok for the machine level."""

from __future__ import annotations

from typing import Any

from eight_ball.scale import level_row, load_scale, place_by_ram


def tokens_per_second(payload: dict[str, Any] | None) -> float | None:
    """Return a measured rate. Missing counts stay unknown."""
    if not payload or payload.get("eval_count") is None:
        return None
    count = payload["eval_count"]
    if not isinstance(count, int | float) or count < 0:
        return None
    if payload.get("eval_duration"):
        seconds = float(payload["eval_duration"]) / 1_000_000_000
    elif payload.get("elapsed_seconds"):
        seconds = float(payload["elapsed_seconds"])
    else:
        return None
    if seconds <= 0:
        return None
    return float(count) / seconds


def consult(
    catalog: dict[str, Any],
    *,
    ram_bytes: int | None,
    disk_free_bytes: int | None,
    vram_bytes: int | None = None,
    scale: dict[str, Any] | None = None,
    installed: set[str] | None = None,
    measurement: dict[str, Any] | None = None,
    measurement_error: str | None = None,
) -> dict[str, Any]:
    """Build the customer offer. This does not install a model."""
    document = scale or load_scale()
    placed = place_by_ram(document, ram_bytes)
    canary = document["canary"]
    canary_tag = canary["tag"]
    canary_record = _tag(catalog, canary_tag)
    fits = _canary_fits(
        canary_record,
        ram_bytes=ram_bytes,
        disk_free_bytes=disk_free_bytes,
        min_ram_bytes=canary["min_ram_bytes"],
        min_disk_bytes=canary["min_disk_bytes"],
    )
    speed = None
    canary_result = {
        "tag": canary_tag,
        "ran": False,
        "fits": fits,
        "tokens_per_second": None,
        "evidence": "unknown",
        "reason": "The canary was not run.",
    }
    level = placed["level"]
    if not fits:
        canary_result["reason"] = (
            "The canary does not fit the measured memory or disk, so it was not run."
        )
        canary_result["evidence"] = "measured"
        if level is not None and level > 0 and ram_bytes is not None and ram_bytes < canary["min_ram_bytes"]:
            level = 0
            placed = {
                "level": 0,
                "display_name": level_row(document, 0)["display_name"],
                "evidence": "measured",
                "reason": "Measured RAM is below the canary, so the machine is level 0.",
            }
    elif installed is not None and canary_tag not in installed:
        canary_result["reason"] = (
            "The canary fits and is not installed. It was not downloaded automatically."
        )
    elif measurement_error:
        canary_result["reason"] = measurement_error
    else:
        speed = tokens_per_second(measurement)
        if speed is None:
            canary_result["reason"] = (
                "The canary finished without an eval count, so speed stays unmeasured."
            )
        else:
            canary_result["ran"] = True
            canary_result["tokens_per_second"] = speed
            canary_result["evidence"] = "measured"
            threshold = None if level is None else level_row(document, level)["min_tokens_per_second"]
            if threshold is not None and speed < threshold and level is not None and level > 0:
                level -= 1
                row = level_row(document, level)
                placed = {
                    "level": level,
                    "display_name": row["display_name"],
                    "evidence": "measured",
                    "reason": (
                        f"The canary measured {speed:.2f} tokens per second, "
                        f"below {threshold}. The machine is level {level}."
                    ),
                }
                canary_result["reason"] = placed["reason"]
            else:
                canary_result["reason"] = (
                    f"The canary measured {speed:.2f} tokens per second."
                )
    options = _cloud_options(document, catalog)
    too_small = not fits
    slow_floor = canary["slow_tokens_per_second"]
    too_slow = speed is not None and speed < slow_floor and placed["level"] in {0, 1}
    low_level = placed["level"] in set(document["openclaw_consultation"]["when_levels"])
    if low_level and (too_small or too_slow):
        consultation = {
            "runner": "openclaw",
            "status": document["openclaw_consultation"]["status"],
            "uses": "ollama-cloud",
            "invoked": False,
            "implemented": False,
            "reason": (
                "Level 0 or 1 and the canary is too small or too slow. "
                "OpenClaw may run this consultation with an Ollama cloud model. "
                "Jonathan has not confirmed this path, and OpenClaw is not called."
            ),
        }
    else:
        consultation = {
            "runner": "local",
            "status": "local",
            "uses": "local-canary",
            "invoked": False,
            "implemented": True,
            "reason": "The consultation stays on this machine.",
        }
    return {
        "level": placed["level"],
        "display_name": placed["display_name"],
        "placement_reason": placed["reason"],
        "placement_evidence": placed["evidence"],
        "vram_bytes": vram_bytes,
        "canary": canary_result,
        "options": options,
        "consultation": consultation,
        "jets_note": document["jets_note"].strip(),
        "install_performed": False,
        "auto_install": False,
    }


def _canary_fits(
    tag: dict[str, Any] | None,
    *,
    ram_bytes: int | None,
    disk_free_bytes: int | None,
    min_ram_bytes: int,
    min_disk_bytes: int,
) -> bool:
    if ram_bytes is None or disk_free_bytes is None:
        return False
    if ram_bytes < min_ram_bytes or disk_free_bytes < min_disk_bytes:
        return False
    if tag is None:
        return False
    size = tag.get("download_size_bytes")
    return size is not None and disk_free_bytes >= int(size * 1.1)


def _cloud_options(document: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Offer official Ollama cloud tags for the jets line. Missing families stay gaps."""
    options: list[dict[str, Any]] = []
    for spec in document["jets"]["options"]:
        matches = _official_cloud_tags(catalog, spec["family_prefix"])
        if not matches:
            options.append(
                {
                    "id": spec["id"],
                    "family": spec["family_prefix"],
                    "runtime": "ollama-cloud",
                    "tag": None,
                    "offered": False,
                    "local_download": False,
                    "reason": document["jets"]["gap"].strip(),
                }
            )
            continue
        chosen = matches[0]
        options.append(
            {
                "id": spec["id"],
                "family": spec["family_prefix"],
                "runtime": "ollama-cloud",
                "tag": chosen["ollama_identifier"],
                "offered": True,
                "local_download": False,
                "availability": chosen.get("availability"),
                "reason": "Official Ollama cloud tag from the validated catalog. Not a local download.",
            }
        )
    return options


def _official_cloud_tags(catalog: dict[str, Any], family_prefix: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    prefix = family_prefix.casefold()
    for record in catalog.get("tags", []):
        identifier = str(record.get("ollama_identifier") or "")
        if "/" in identifier:
            continue
        family, separator, name = identifier.partition(":")
        if not separator or not family.casefold().startswith(prefix):
            continue
        cloud_name = name.casefold().endswith("cloud") or name.casefold().endswith("-cloud")
        availability = record.get("availability")
        if availability not in {"cloud", "cloud_only", "both"} and not cloud_name:
            continue
        if availability == "local" and not cloud_name:
            continue
        if cloud_name or availability in {"cloud", "cloud_only"}:
            found.append(record)
    found.sort(key=lambda row: row["ollama_identifier"])
    return found


def _tag(catalog: dict[str, Any], tag: str) -> dict[str, Any] | None:
    for record in catalog.get("tags", []):
        if record.get("ollama_identifier") == tag:
            return record
    return None

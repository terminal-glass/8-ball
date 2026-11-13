"""Consultation from the 0-9 scale.

Levels 0 and 1 use the canary when it fits. If it is too large and OpenClaw
is capable, OpenClaw gives the consultation. Larger levels drop the canary
and recommend a local Llama tag. The jets slot is a hosted Llama on Meta's
service. A code or agentic focus adds a tentative Qwen recommendation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.manager.secrets import write_private_file
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
    focus: str | None = None,
    openclaw_capable: bool | None = None,
    home: Path | None = None,
    meta_api_key: bytes | None = None,
) -> dict[str, Any]:
    """Build the customer offer. This does not install a model or call OpenClaw."""
    document = scale or load_scale()
    placed = place_by_ram(document, ram_bytes)
    level = placed["level"]
    row = None if level is None else level_row(document, level)
    use_canary = row is not None and row["local_model"] == "canary"
    canary_result, speed = _canary_result(
        document,
        catalog,
        use_canary=use_canary,
        ram_bytes=ram_bytes,
        disk_free_bytes=disk_free_bytes,
        installed=installed,
        measurement=measurement,
        measurement_error=measurement_error,
    )
    if (
        use_canary
        and speed is not None
        and level is not None
        and row is not None
        and row["min_tokens_per_second"] is not None
        and speed < row["min_tokens_per_second"]
        and level > 0
    ):
        level -= 1
        dropped = level_row(document, level)
        placed = {
            "level": level,
            "display_name": dropped["display_name"],
            "evidence": "measured",
            "reason": (
                f"The canary measured {speed:.2f} tokens per second, "
                f"below {row['min_tokens_per_second']}. The machine is level {level}."
            ),
        }
        canary_result["reason"] = placed["reason"]
        row = dropped
        use_canary = row["local_model"] == "canary"
    options = _recommendations(
        document,
        catalog,
        row=row,
        use_canary=use_canary,
        canary_fits=bool(canary_result["fits"]),
        focus=focus,
    )
    consultation = _consultation_runner(
        document,
        level=placed["level"],
        use_canary=use_canary,
        canary_fits=bool(canary_result["fits"]),
        openclaw_capable=openclaw_capable,
    )
    credential_stored = False
    if meta_api_key is not None:
        if home is None:
            raise ValueError("A home directory is required before storing a Meta API key.")
        store_meta_api_key(home, meta_api_key)
        credential_stored = True
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
        "credential_stored": credential_stored,
        "credential_present": _credential_present(document, home),
        "install_performed": False,
        "auto_install": False,
    }


def jets_prompt(document: dict[str, Any] | None = None) -> str:
    """Customer prompt. It never includes an API key."""
    source = document or load_scale()
    return source["jets"]["prompt"].strip()


def store_meta_api_key(home: Path, secret: bytes) -> Path:
    """Store the Meta API key in the installing user's home. Never under /root."""
    if not secret or secret.strip() == b"":
        raise ValueError("Refusing to store an empty Meta API key.")
    relative = load_scale()["jets"]["credential_relative_path"]
    return write_private_file(home / relative, secret, home=home)


def _canary_result(
    document: dict[str, Any],
    catalog: dict[str, Any],
    *,
    use_canary: bool,
    ram_bytes: int | None,
    disk_free_bytes: int | None,
    installed: set[str] | None,
    measurement: dict[str, Any] | None,
    measurement_error: str | None,
) -> tuple[dict[str, Any], float | None]:
    canary = document["canary"]
    canary_tag = canary["tag"]
    if not use_canary:
        return (
            {
                "tag": canary_tag,
                "ran": False,
                "fits": None,
                "dropped": True,
                "tokens_per_second": None,
                "evidence": "not-used",
                "reason": "This level drops the canary and recommends a Llama model.",
            },
            None,
        )
    record = _tag(catalog, canary_tag)
    fits = _canary_fits(
        record,
        ram_bytes=ram_bytes,
        disk_free_bytes=disk_free_bytes,
        min_ram_bytes=canary["min_ram_bytes"],
        min_disk_bytes=canary["min_disk_bytes"],
    )
    result = {
        "tag": canary_tag,
        "ran": False,
        "fits": fits,
        "dropped": False,
        "tokens_per_second": None,
        "evidence": "unknown",
        "reason": "The canary was not run.",
    }
    if not fits:
        result["reason"] = "The canary is too large for the measured memory or disk, so it was not run."
        result["evidence"] = "measured"
        return result, None
    if installed is not None and canary_tag not in installed:
        result["reason"] = "The canary fits and is not installed. It was not downloaded automatically."
        return result, None
    if measurement_error:
        result["reason"] = measurement_error
        return result, None
    speed = tokens_per_second(measurement)
    if speed is None:
        result["reason"] = "The canary finished without an eval count, so speed stays unmeasured."
        return result, None
    result["ran"] = True
    result["tokens_per_second"] = speed
    result["evidence"] = "measured"
    result["reason"] = f"The canary measured {speed:.2f} tokens per second."
    return result, speed


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


def _recommendations(
    document: dict[str, Any],
    catalog: dict[str, Any],
    *,
    row: dict[str, Any] | None,
    use_canary: bool,
    canary_fits: bool,
    focus: str | None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if row is None:
        return options
    if use_canary and canary_fits:
        options.append(
            {
                "id": "canary",
                "runtime": "ollama",
                "tag": document["canary"]["tag"],
                "offered": True,
                "local_download": True,
                "tentative": False,
                "reason": "The canary fits this low level and is the local model for the consultation.",
            }
        )
    elif not use_canary:
        llama_tag = row.get("llama_tag")
        record = _tag(catalog, llama_tag) if llama_tag else None
        if record is None:
            options.append(
                {
                    "id": "llama",
                    "runtime": "ollama",
                    "tag": llama_tag,
                    "offered": False,
                    "local_download": False,
                    "tentative": False,
                    "reason": "The Llama tag for this level is not in the validated catalog.",
                }
            )
        else:
            options.append(
                {
                    "id": "llama",
                    "runtime": "ollama",
                    "tag": llama_tag,
                    "offered": True,
                    "local_download": record.get("availability") in {"local", "both"},
                    "tentative": False,
                    "reason": "This level drops the canary and recommends this local Llama tag.",
                }
            )
    jets = document["jets"]
    options.append(
        {
            "id": "jets",
            "provider": jets["provider"],
            "runtime": jets["runtime"],
            "tag": None,
            "model_id": jets["model_id"],
            "endpoint": jets["endpoint"],
            "signup_url": jets["signup_url"],
            "offered": True,
            "ready_to_call": False,
            "local_download": False,
            "tentative": False,
            "aim": jets["aim"],
            "todos": list(jets["todos"]),
            "prompt": jets["prompt"].strip(),
            "reason": (
                "Jets is a hosted Llama on Meta's service. "
                "Sign in or create a Meta account and enter the API key. "
                "The endpoint, model id, and sign-up URL are TODO for Jonathan."
            ),
        }
    )
    if focus == "code":
        options.append(_qwen_option(document, catalog, row["level"]))
    return options


def _qwen_option(document: dict[str, Any], catalog: dict[str, Any], level: int) -> dict[str, Any]:
    code_focus = document["code_focus"]
    tag = None
    for band in code_focus["bands"]:
        if band["from_level"] <= level <= band["to_level"]:
            tag = band["tag"]
            break
    record = _tag(catalog, tag) if tag else None
    if record is None:
        reason = code_focus["note"].strip() + " The tentative tag is not in the validated catalog."
        offered = False
    else:
        reason = code_focus["note"].strip()
        offered = True
    return {
        "id": "qwen",
        "family": "qwen",
        "runtime": "ollama",
        "tag": None if record is None else tag,
        "offered": offered,
        "local_download": bool(record and record.get("availability") in {"local", "both"}),
        "tentative": True,
        "status": "tentative",
        "reason": reason,
    }


def _consultation_runner(
    document: dict[str, Any],
    *,
    level: int | None,
    use_canary: bool,
    canary_fits: bool,
    openclaw_capable: bool | None,
) -> dict[str, Any]:
    policy = document["openclaw_consultation"]
    canary_too_large = use_canary and not canary_fits and level in set(policy["levels"])
    if not canary_too_large:
        return {
            "runner": "local",
            "status": "local",
            "invoked": False,
            "implemented": True,
            "openclaw_capable": openclaw_capable,
            "reason": "The consultation stays on this machine.",
        }
    if openclaw_capable is True:
        return {
            "runner": "openclaw",
            "status": "openclaw-capable",
            "invoked": False,
            "implemented": False,
            "adapter_status": "planned",
            "openclaw_capable": True,
            "reason": (
                "The canary is too large for this low level and OpenClaw is capable, "
                "so OpenClaw gives the consultation. The adapter is planned and was not called."
            ),
        }
    if openclaw_capable is False:
        return {
            "runner": "none",
            "status": "openclaw-not-capable",
            "invoked": False,
            "implemented": False,
            "openclaw_capable": False,
            "reason": "The canary is too large and OpenClaw is not capable on this machine.",
        }
    return {
        "runner": "openclaw",
        "status": "openclaw-capability-unknown",
        "invoked": False,
        "implemented": False,
        "adapter_status": "planned",
        "openclaw_capable": None,
        "reason": (
            "The canary is too large for this low level. OpenClaw gives the consultation "
            "when it is capable. Capability was not measured, and the adapter was not called."
        ),
    }


def _credential_present(document: dict[str, Any], home: Path | None) -> bool:
    if home is None:
        return False
    path = home / document["jets"]["credential_relative_path"]
    return path.is_file()


def _tag(catalog: dict[str, Any], tag: str) -> dict[str, Any] | None:
    for record in catalog.get("tags", []):
        if record.get("ollama_identifier") == tag:
            return record
    return None

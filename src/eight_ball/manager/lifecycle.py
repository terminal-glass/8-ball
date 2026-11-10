from __future__ import annotations

from collections.abc import Callable
from typing import Any

from eight_ball.manager.argv import lookup_tag
from eight_ball.manager.ollama_http import OllamaClient, OllamaError, PullCancelled
from eight_ball.manager.suitability import assess_suitability, estimate_runtime_memory_bytes

HOSTED_ONLY = {"cloud", "cloud_only"}
DISK_MARGIN = 1.10


def disk_check(tag: dict[str, Any], free_bytes: int | None) -> dict[str, Any]:
    """Compare published download size with free disk. This is not a RAM check."""
    size = tag.get("download_size_bytes")
    if free_bytes is None:
        return {
            "ok": None,
            "reason": "Free disk was not detected.",
            "evidence_level": "unknown",
            "bytes_required": None,
        }
    if size is None:
        return {
            "ok": None,
            "reason": "Published download size is unknown, so the disk check is unknown.",
            "evidence_level": "unknown",
            "bytes_required": None,
        }
    required = int(size * DISK_MARGIN)
    if free_bytes < required:
        return {
            "ok": False,
            "reason": f"The download needs {required} bytes of disk and {free_bytes} bytes are free.",
            "evidence_level": "observed",
            "bytes_required": required,
        }
    return {
        "ok": True,
        "reason": f"The download needs {required} bytes of disk and {free_bytes} bytes are free.",
        "evidence_level": "observed",
        "bytes_required": required,
    }


def suggest_fallbacks(
    catalog: dict[str, Any],
    requested: dict[str, Any],
    hardware: dict[str, Any],
    *,
    free_bytes: int | None,
) -> list[str]:
    fits: list[tuple[int, str]] = []
    ram = hardware.get("ram_bytes")
    for tag in catalog.get("tags", []):
        if tag.get("ollama_identifier") == requested.get("ollama_identifier"):
            continue
        if tag.get("availability") not in {"local", "both"}:
            continue
        if tag.get("model_id") != requested.get("model_id"):
            continue
        memory = estimate_runtime_memory_bytes(tag)
        if memory is None or ram is None or memory > ram:
            continue
        disk = disk_check(tag, free_bytes)
        if disk["ok"] is False:
            continue
        fits.append((memory, tag["ollama_identifier"]))
    fits.sort()
    return [tag for _memory, tag in fits]


def pull_model(
    catalog: dict[str, Any],
    client: OllamaClient,
    tag: str,
    *,
    free_bytes: int | None,
    hardware: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    on_progress: Callable[[dict[str, Any]], bool | None] | None = None,
) -> dict[str, Any]:
    policy = policy or {}
    hardware = hardware or {}
    record = lookup_tag(catalog, tag)
    if record.get("availability") in HOSTED_ONLY:
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            pulled=False,
            reason="Cloud-only models are not offered as local downloads.",
            recovery="Choose a local or both-availability tag.",
        )
    disk = disk_check(record, free_bytes)
    if disk["ok"] is False or (disk["ok"] is None and not policy.get("allow_unknown_size")):
        fallbacks = suggest_fallbacks(catalog, record, hardware, free_bytes=free_bytes)
        if policy.get("allow_unattended_fallback") and fallbacks:
            substituted = pull_model(
                catalog,
                client,
                fallbacks[0],
                free_bytes=free_bytes,
                hardware=hardware,
                policy={"allow_unknown_size": policy.get("allow_unknown_size", False)},
                on_progress=on_progress,
            )
            substituted["substituted"] = True
            substituted["requested_tag"] = tag
            substituted["fallback_tag"] = fallbacks[0]
            return substituted
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            pulled=False,
            reason=disk["reason"],
            recovery="Free disk space or choose a smaller local model. No model was substituted.",
            fallbacks=fallbacks,
            substituted=False,
        )
    if client.has_model(tag):
        return _result(
            ok=True,
            status="skipped",
            exact_tag=tag,
            pulled=False,
            reason="The exact tag is already installed.",
        )
    try:
        events = client.pull(tag, on_progress=on_progress)
    except PullCancelled:
        return _result(
            ok=False,
            status="cancelled",
            exact_tag=tag,
            pulled=False,
            reason="The pull was cancelled.",
            recovery="Rerun the pull for the same exact tag.",
        )
    except OllamaError as exc:
        return _result(
            ok=False,
            status="failure",
            exact_tag=tag,
            pulled=False,
            reason=str(exc),
            recovery="Check the local Ollama API and rerun the pull. Completed stages stay recorded.",
        )
    return _result(
        ok=True,
        status="success",
        exact_tag=tag,
        pulled=True,
        reason="Pull finished.",
        progress=events,
        substituted=False,
    )


def use_model(catalog: dict[str, Any], client: OllamaClient, tag: str, prompt: str) -> dict[str, Any]:
    record = lookup_tag(catalog, tag)
    if record.get("availability") in HOSTED_ONLY:
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            reason="A hosted model is not started as a local runtime.",
            recovery="Use a locally installed tag.",
            enrolled_network=False,
            tools_granted=False,
        )
    if not client.has_model(tag):
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            reason="The exact tag is not installed.",
            recovery="Pull the exact tag, then use it.",
            enrolled_network=False,
            tools_granted=False,
        )
    try:
        reply = client.chat(tag, prompt)
    except OllamaError as exc:
        return _result(
            ok=False,
            status="failure",
            exact_tag=tag,
            reason=str(exc),
            recovery="Check the local Ollama API and retry the same tag.",
            enrolled_network=False,
            tools_granted=False,
        )
    return _result(
        ok=True,
        status="success",
        exact_tag=tag,
        reason="Local chat completed.",
        reply=reply,
        enrolled_network=False,
        tools_granted=False,
    )


def list_state(client: OllamaClient) -> dict[str, Any]:
    installed = sorted(_name(model) for model in client.list_models() if _name(model))
    running = sorted(_name(model) for model in client.running() if _name(model))
    return {"installed": installed, "running": running}


def remove_model(
    catalog: dict[str, Any],
    client: OllamaClient,
    tag: str,
    assignments: list[dict[str, str]],
    *,
    decision: str | None = None,
    reassign_to: str | None = None,
) -> dict[str, Any]:
    lookup_tag(catalog, tag)
    running = client.is_running(tag)
    assigned = [row for row in assignments if row.get("tag") == tag]
    if (running or assigned) and decision is None:
        dependency = "running" if running else "assigned"
        if running and assigned:
            dependency = "running and assigned"
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            removed=False,
            reason=f"The exact tag is {dependency}. Removal needs an explicit decision.",
            recovery="Choose stop, reassign, or remove for this exact tag. Other models stay installed.",
            running=running,
            assignments=assigned,
        )
    if decision == "stop":
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            removed=False,
            reason="Stop was requested. The tag stays installed until it is absent from the running list.",
            recovery="Stop the model, then retry remove once it is not running.",
            running=running,
        )
    if decision == "reassign":
        if not reassign_to or reassign_to == tag:
            return _result(
                ok=False,
                status="refused",
                exact_tag=tag,
                removed=False,
                reason="Reassign needs a different exact tag.",
                recovery="Pass reassign_to as another catalog tag.",
            )
        lookup_tag(catalog, reassign_to)
        for row in assignments:
            if row.get("tag") == tag:
                row["tag"] = reassign_to
        return _result(
            ok=True,
            status="reassigned",
            exact_tag=tag,
            removed=False,
            reason=f"Assignments now use {reassign_to}. The original tag was not removed.",
            reassign_to=reassign_to,
        )
    if decision not in (None, "remove"):
        return _result(
            ok=False,
            status="refused",
            exact_tag=tag,
            removed=False,
            reason="The removal decision is not one of stop, reassign, or remove.",
            recovery="Repeat the request with an explicit decision.",
        )
    try:
        client.delete(tag)
    except OllamaError as exc:
        return _result(
            ok=False,
            status="failure",
            exact_tag=tag,
            removed=False,
            reason=str(exc),
            recovery="Resolve the Ollama error and retry removal of the same exact tag.",
        )
    kept = [row for row in assignments if row.get("tag") != tag]
    assignments[:] = kept
    return _result(
        ok=True,
        status="success",
        exact_tag=tag,
        removed=True,
        reason="Removed the exact tag.",
    )


def suitability_for(catalog: dict[str, Any], tag: str, hardware: dict[str, Any] | None) -> dict[str, Any]:
    return assess_suitability(lookup_tag(catalog, tag), hardware)


def _name(model: dict[str, Any]) -> str:
    value = model.get("name") or model.get("model") or ""
    return str(value)


def _result(**fields: Any) -> dict[str, Any]:
    fields.setdefault("substituted", False)
    fields.setdefault("install_performed", bool(fields.get("pulled")))
    return fields

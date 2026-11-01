"""Deterministic fit policy (fit-policy.v1). All results are estimates from catalog metadata.

States, each always shown with a text label:
  fits         Green  host meets the recommended RAM (or VRAM) and disk estimates
  constrained  Amber  host meets the minimum but not the recommended estimate, or disk headroom is low
  rejected     Red    host is below the minimum RAM/VRAM estimate or the minimum free disk
  unknown      Grey   an estimate or a host fact needed for the decision is missing
  cloud        Blue   the tag runs on Ollama's cloud; no local weights are pulled
"""
from __future__ import annotations

from typing import Any

POLICY_ID = "fit-policy.v1"
LABELS = {
    "fits": ("green", "Fits"),
    "constrained": ("amber", "Constrained"),
    "rejected": ("red", "Rejected"),
    "unknown": ("grey", "Unknown"),
    "cloud": ("blue", "Cloud"),
}


def is_cloud_ref(ref: str) -> bool:
    tag = ref.split(":", 1)[1] if ":" in ref else ""
    return tag == "cloud" or tag.endswith("-cloud")


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def requirements(size_doc: dict[str, Any]) -> dict[str, float | None]:
    est = size_doc.get("estimated") or {}
    norm = size_doc.get("normalized") or {}
    return {
        "min_ram_gb": _num(norm.get("minimum_ram_gb", est.get("min_system_ram_gb"))),
        "rec_ram_gb": _num(norm.get("recommended_ram_gb", est.get("recommended_system_ram_gb"))),
        "min_vram_gb": _num(norm.get("minimum_vram_gb", est.get("min_vram_gb"))),
        "rec_vram_gb": _num(norm.get("recommended_vram_gb", est.get("recommended_vram_gb"))),
        "min_disk_free_gb": _num(norm.get("minimum_disk_free_gb")),
        "headroom_disk_gb": _num(est.get("min_disk_gb")),
    }


def host_capacity(profile: dict[str, Any] | None) -> dict[str, float | None]:
    """Host values used for fit. Unknown stays None; it is never treated as zero or as enough."""
    if not profile:
        return {"ram_gb": None, "vram_gb": None, "disk_free_gb": None}
    cap = profile.get("capacity") or {}
    return {
        "ram_gb": _num(cap.get("system_ram_gb")),
        "vram_gb": _num(cap.get("gpu_vram_gb")),
        "disk_free_gb": _num(cap.get("model_disk_free_gb")),
    }


def evaluate(ref: str, size_doc: dict[str, Any] | None, host: dict[str, float | None],
             disk_free_gb: float | None = None) -> dict[str, Any]:
    """Return {state, color, label, reasons[], estimated: True, policy}."""
    reasons: list[str] = []

    def out(state: str) -> dict[str, Any]:
        color, label = LABELS[state]
        return {"state": state, "color": color, "label": label, "reasons": reasons,
                "estimated": True, "policy": POLICY_ID}

    if is_cloud_ref(ref):
        reasons.append("runs on Ollama cloud; no local download; needs an online Ollama account")
        return out("cloud")
    if not size_doc:
        reasons.append("tag has no size/requirement record in the catalog")
        return out("unknown")
    req = requirements(size_doc)
    ram, vram = host.get("ram_gb"), host.get("vram_gb")
    disk = disk_free_gb if disk_free_gb is not None else host.get("disk_free_gb")

    if req["min_ram_gb"] is None and req["min_vram_gb"] is None:
        reasons.append("catalog has no RAM/VRAM estimate for this tag")
        return out("unknown")
    if disk is None:
        reasons.append("free disk on the model store is unknown")
        return out("unknown")
    if req["min_disk_free_gb"] is None:
        reasons.append("catalog has no disk estimate for this tag")
        return out("unknown")
    if disk < req["min_disk_free_gb"]:
        reasons.append(f"free disk {disk:.1f} GB < minimum {req['min_disk_free_gb']:.1f} GB")
        return out("rejected")

    gpu_fits = vram is not None and req["rec_vram_gb"] is not None and vram >= req["rec_vram_gb"]
    gpu_min = vram is not None and req["min_vram_gb"] is not None and vram >= req["min_vram_gb"]
    if ram is None and vram is None:
        reasons.append("system RAM and GPU VRAM are unknown")
        return out("unknown")
    ram_fits = ram is not None and req["rec_ram_gb"] is not None and ram >= req["rec_ram_gb"]
    ram_min = ram is not None and req["min_ram_gb"] is not None and ram >= req["min_ram_gb"]

    if vram is None:
        reasons.append("GPU VRAM unknown; decided on system RAM (CPU inference)")
    low_headroom = req["headroom_disk_gb"] is not None and disk < req["headroom_disk_gb"]
    if gpu_fits or ram_fits:
        reasons.append("meets the recommended " + ("VRAM" if gpu_fits else "RAM") + " estimate")
        if low_headroom:
            reasons.append(f"free disk {disk:.1f} GB < suggested headroom {req['headroom_disk_gb']:.1f} GB")
            return out("constrained")
        return out("fits")
    if gpu_min or ram_min:
        reasons.append("meets the minimum but not the recommended estimate")
        return out("constrained")
    if ram is None:
        reasons.append("below the VRAM minimum and system RAM is unknown")
        return out("unknown")
    reasons.append(f"system RAM {ram:.1f} GB < minimum {req['min_ram_gb'] or 0:.1f} GB")
    return out("rejected")

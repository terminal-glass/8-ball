from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any


def detect_hardware(
    *,
    disk_path: Path | None = None,
    meminfo_text: str | None = None,
    gpu_probe: Callable[[], dict[str, Any]] | None = None,
    runtime_probe: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Detect what the machine reports. Missing probes stay unknown."""
    incomplete: list[str] = []
    ram_bytes = _ram_bytes(meminfo_text)
    if ram_bytes is None:
        incomplete.append("RAM was not detected.")
    gpu = gpu_probe() if gpu_probe is not None else _gpu_not_probed()
    if not gpu.get("available"):
        incomplete.append(str(gpu.get("reason") or "GPU was not detected."))
    runtime = runtime_probe() if runtime_probe is not None else {
        "available": False,
        "reason": "Ollama runtime was not probed.",
    }
    if not runtime.get("available"):
        incomplete.append(str(runtime.get("reason") or "Runtime was not detected."))
    try:
        disk = shutil.disk_usage(disk_path or Path.cwd())
        disk_free = int(disk.free)
    except OSError:
        disk_free = None
        incomplete.append("Free disk was not detected.")
    return {
        "os": platform.system().lower() or "unknown",
        "architecture": platform.machine() or "unknown",
        "cpu_count": os.cpu_count(),
        "ram_bytes": ram_bytes,
        "vram_bytes": gpu.get("vram_bytes"),
        "gpu": gpu,
        "disk_free_bytes": disk_free,
        "runtime": runtime,
        "incomplete": incomplete,
        "detection_complete": not incomplete,
    }


def _ram_bytes(meminfo_text: str | None) -> int | None:
    text = meminfo_text
    if text is None:
        meminfo = Path("/proc/meminfo")
        if not meminfo.is_file():
            return None
        text = meminfo.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                # /proc/meminfo reports KiB. This is detected RAM, not a catalog size.
                return int(parts[1]) * 1024
    return None


def _gpu_not_probed() -> dict[str, Any]:
    return {
        "available": False,
        "vram_bytes": None,
        "reason": "GPU was not probed. VRAM stays unknown.",
    }

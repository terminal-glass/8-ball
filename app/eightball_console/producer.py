"""Host profile producer.

  scan   (the "hardware scan" step)    -> 8ball.host-scan.v1     real host facts, unknowns explicit
  build  (the "validated profile" step) -> 8ball.host-profile.v1  scan + catalog lane/type + suitability

Neither step installs, pulls or changes anything. Values that cannot be measured are recorded as
null and listed in "unknowns" with the reason; they are never guessed or defaulted to zero.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
import uuid
from pathlib import Path
from typing import Any

from . import __version__, fit
from .catalog import Catalog

SCAN_SCHEMA = "8ball.host-scan.v1"
PROFILE_SCHEMA = "8ball.host-profile.v1"
SUPPORTED_PLATFORMS = ("linux-x86_64", "linux-aarch64")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], timeout: float = 10) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "not found"
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _os_release() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (_read("/etc/os-release") or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v.strip().strip('"')
    return out


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in (_read("/proc/meminfo") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            try:
                out[parts[0][:-1]] = int(parts[1])
            except ValueError:
                pass
    return out


def _cpu_model() -> str | None:
    for line in (_read("/proc/cpuinfo") or "").splitlines():
        if line.lower().startswith(("model name", "hardware", "cpu model")):
            return line.split(":", 1)[1].strip() or None
    return platform.processor() or None


def _disk(path: Path, role: str) -> dict[str, Any] | None:
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        u = shutil.disk_usage(p)
    except OSError:
        return None
    return {"role": role, "path": str(path), "measured_at_path": str(p),
            "total_mb": u.total // (1024 * 1024), "free_mb": u.free // (1024 * 1024)}


def _pci_display() -> list[dict[str, Any]]:
    out = []
    root = Path("/sys/bus/pci/devices")
    for dev in sorted(root.glob("*")) if root.is_dir() else []:
        cls = (_read(str(dev / "class")) or "").strip()
        if cls.startswith(("0x0300", "0x0302")):
            out.append({"vendor_id": (_read(str(dev / "vendor")) or "").strip() or None,
                        "device_id": (_read(str(dev / "device")) or "").strip() or None})
    return out


def _gpu(unknowns: list[dict[str, str]]) -> dict[str, Any]:
    gpu: dict[str, Any] = {"detected": None, "devices": [], "probes": []}
    smi = shutil.which("nvidia-smi")
    if smi:
        rc, out, err = _run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        if rc == 0 and out.strip():
            for line in out.strip().splitlines():
                parts = [x.strip() for x in line.split(",")]
                try:
                    vram = int(float(parts[1]))
                except (IndexError, ValueError):
                    vram = None
                gpu["devices"].append({"vendor": "nvidia", "name": parts[0] or None, "vram_mb": vram,
                                       "driver": parts[2] if len(parts) > 2 else None, "source": "nvidia-smi"})
            gpu["probes"].append({"tool": "nvidia-smi", "status": "ok"})
        else:
            msg = (err or out).strip().splitlines()
            gpu["probes"].append({"tool": "nvidia-smi", "status": "failed", "message": (msg[0] if msg else f"exit {rc}")[:200]})
    else:
        gpu["probes"].append({"tool": "nvidia-smi", "status": "absent"})
    # AMD (amdgpu exposes VRAM in sysfs)
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")) if Path("/sys/class/drm").is_dir() else []:
        vendor = (_read(str(card / "device" / "vendor")) or "").strip()
        if vendor == "0x1002":
            total = (_read(str(card / "device" / "mem_info_vram_total")) or "").strip()
            gpu["devices"].append({"vendor": "amd", "name": None,
                                   "vram_mb": int(total) // (1024 * 1024) if total.isdigit() else None,
                                   "driver": "amdgpu", "source": "sysfs"})
    # PCI display controllers (presence only; never used as proof of a working driver or VRAM)
    pci = _pci_display()
    gpu["pci_display_controllers"] = pci
    # virtual / BMC display adapters (QEMU, virtio, VMware, Cirrus, Hyper-V, Matrox, ASPEED) are not compute GPUs
    pci = [d for d in pci if d["vendor_id"] not in ("0x1234", "0x1af4", "0x15ad", "0x1013", "0x1414", "0x102b", "0x1a03")]
    have_vram = any(d.get("vram_mb") for d in gpu["devices"])
    nvidia_pci = any(d["vendor_id"] == "0x10de" for d in pci)
    if gpu["devices"]:
        gpu["detected"] = True
    elif nvidia_pci:
        gpu["detected"] = True
        gpu["devices"].append({"vendor": "nvidia", "name": None, "vram_mb": None, "driver": None, "source": "pci"})
    elif pci or smi:
        gpu["detected"] = None
    else:
        gpu["detected"] = False
    if gpu["detected"] and not have_vram:
        reason = "GPU present but VRAM could not be read"
        failed = [p for p in gpu["probes"] if p["status"] == "failed"]
        if failed:
            reason += f" ({failed[0]['tool']}: {failed[0].get('message', '')})"
        unknowns.append({"field": "gpu.vram_mb", "reason": reason})
    elif gpu["detected"] is None:
        unknowns.append({"field": "gpu.detected", "reason": "display controller present but no GPU tool answered"})
    return gpu


def _cloud(os_rel: dict[str, str]) -> str | None:
    if Path("/etc/digitalocean").is_file() or "digitalocean" in os_rel.get("ID", "").lower():
        return "digitalocean"
    uu = (_read("/sys/hypervisor/uuid") or "").lower()
    if uu.startswith("ec2"):
        return "aws"
    vendor = (_read("/sys/class/dmi/id/sys_vendor") or "").lower()
    if "amazon" in vendor:
        return "aws"
    if "digitalocean" in vendor:
        return "digitalocean"
    return None


def _ollama_fact(base_url: str) -> dict[str, Any]:
    import urllib.request
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/version", timeout=3) as r:  # noqa: S310 (fixed URL)
            return {"reachable": True, "version": json.loads(r.read().decode()).get("version")}
    except Exception:  # noqa: BLE001
        return {"reachable": False, "version": None}


def scan(models_dir: str = "/usr/share/ollama/.ollama/models", ollama_url: str | None = "http://127.0.0.1:11434") -> dict[str, Any]:
    unknowns: list[dict[str, str]] = []
    os_rel = _os_release()
    mem = _meminfo()
    arch = platform.machine() or None
    if not os_rel:
        unknowns.append({"field": "os.id", "reason": "/etc/os-release not readable"})
    total_mb = mem.get("MemTotal", 0) // 1024 or None
    if total_mb is None:
        unknowns.append({"field": "memory.total_mb", "reason": "/proc/meminfo has no MemTotal"})
    threads = os.cpu_count()
    if not threads:
        unknowns.append({"field": "cpu.threads", "reason": "cpu count unavailable"})
    virt = None
    if shutil.which("systemd-detect-virt"):
        rc, out, _ = _run(["systemd-detect-virt"])
        virt = out.strip() or None
    else:
        unknowns.append({"field": "virtualization", "reason": "systemd-detect-virt not available"})
    disks = [d for d in (_disk(Path("/"), "root"), _disk(Path(models_dir), "models")) if d]
    if not any(d["role"] == "models" for d in disks):
        unknowns.append({"field": "disk.models", "reason": f"cannot stat {models_dir}"})
    doc = {
        "schema_version": SCAN_SCHEMA,
        "scan_id": str(uuid.uuid4()),
        "captured_at": now_utc(),
        "producer": {"name": "eightball-console scan", "version": __version__},
        "host": {"hostname": socket.gethostname()},
        "os": {"family": platform.system().lower() or None, "id": os_rel.get("ID"),
               "version_id": os_rel.get("VERSION_ID"), "pretty_name": os_rel.get("PRETTY_NAME"),
               "kernel": platform.release() or None, "arch": arch},
        "cpu": {"model": _cpu_model(), "threads": threads},
        "memory": {"total_mb": total_mb, "available_mb": (mem.get("MemAvailable", 0) // 1024) or None,
                   "swap_mb": mem.get("SwapTotal", 0) // 1024 if "SwapTotal" in mem else None},
        "disk": disks,
        "gpu": _gpu(unknowns),
        "virtualization": virt,
        "cloud_provider": _cloud(os_rel),
        "ollama": _ollama_fact(ollama_url) if ollama_url else None,
        "unknowns": unknowns,
    }
    return doc


# ---------------------------------------------------------------- build (validated profile)

def _load_c10(catalog_root: Path):
    p = catalog_root / "install" / "shared" / "c10-hardware-resolve.py"
    if not p.is_file():
        return None
    spec = importlib.util.spec_from_file_location("eightball_c10_resolve", p)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_scan(doc: Any) -> list[str]:
    errs = []
    if not isinstance(doc, dict):
        return ["scan is not a JSON object"]
    if doc.get("schema_version") != SCAN_SCHEMA:
        errs.append(f"schema_version must be {SCAN_SCHEMA}")
    for key in ("scan_id", "captured_at", "os", "cpu", "memory", "disk", "gpu", "unknowns"):
        if key not in doc:
            errs.append(f"missing {key}")
    return errs


def build(scan_doc: dict[str, Any], catalog: Catalog, menu: dict[str, Any] | None = None) -> dict[str, Any]:
    errs = validate_scan(scan_doc)
    if errs:
        raise ValueError("; ".join(errs))
    unknowns = list(scan_doc.get("unknowns") or [])
    os_ = scan_doc["os"]
    plat = f"{os_.get('family') or 'unknown'}-{os_.get('arch') or 'unknown'}"
    total_mb = scan_doc["memory"].get("total_mb")
    ram_gb = round(total_mb / 1024, 2) if total_mb else None
    vrams = [d["vram_mb"] for d in scan_doc["gpu"].get("devices", []) if d.get("vram_mb")]
    vram_gb = round(max(vrams) / 1024, 2) if vrams else None
    disk = {d["role"]: d for d in scan_doc["disk"]}
    mdisk = disk.get("models") or disk.get("root")
    disk_gb = round(mdisk["free_mb"] / 1024, 2) if mdisk else None
    cuda = bool(vrams) and any(d.get("vendor") == "nvidia" and d.get("vram_mb") for d in scan_doc["gpu"]["devices"])

    c10 = _load_c10(catalog.root)
    hw = {"ram_mb": total_mb or 0, "cloud_provider": scan_doc.get("cloud_provider"),
          "gpu": {"vram_mb": max(vrams) if vrams else 0, "cuda_available": cuda}}
    if c10 is not None:
        lane = c10.resolve_lane(hw)
        dtype = c10.deployment_type_for_hardware(hw)
        lane_src = "install/shared/c10-hardware-resolve.py"
    else:
        lane = {"lane_path": "ubuntu/cuda" if cuda else "ubuntu/cpu", "resolution_source": "fallback"}
        dtype = None
        lane_src = "fallback (catalog resolver not found)"
    notes = []
    if scan_doc["gpu"].get("detected") and vram_gb is None:
        notes.append("GPU present but VRAM unknown: lane and type are resolved for CPU/RAM only (conservative)")

    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA,
        "state": "complete",
        "profile_id": str(uuid.uuid4()),
        "created_at": now_utc(),
        "captured_at": scan_doc["captured_at"],
        "scan_id": scan_doc["scan_id"],
        "scan_sha256": hashlib.sha256(json.dumps(scan_doc, sort_keys=True).encode()).hexdigest(),
        "producer": {"name": "eightball-console build", "version": __version__},
        "catalog": {"commit": catalog.commit, "lane_resolver": lane_src},
        "fit_policy": fit.POLICY_ID,
        "platform": {"id": plat, "authorized": plat in SUPPORTED_PLATFORMS,
                     "supported": list(SUPPORTED_PLATFORMS)},
        "host": {"hostname": scan_doc.get("host", {}).get("hostname"), "os": os_.get("pretty_name"),
                 "cpu_model": scan_doc["cpu"].get("model"), "cloud_provider": scan_doc.get("cloud_provider"),
                 "virtualization": scan_doc.get("virtualization"),
                 "gpu_devices": scan_doc["gpu"].get("devices", [])},
        "capacity": {"system_ram_gb": ram_gb, "usable_model_ram_gb": round(ram_gb * 0.6, 2) if ram_gb else None,
                     "gpu_vram_gb": vram_gb, "model_disk_free_gb": disk_gb,
                     "cpu_threads": scan_doc["cpu"].get("threads")},
        "lane": lane,
        "classification": {
            "catalog_deployment_type_id": dtype,
            "catalog_deployment_type_source": "config/deployment_types.yaml (via the catalog resolver)",
            "p_identity": {"value": None, "status": "unknown",
                           "reason": "P# identities are not defined in the catalog"},
            "m_tier": {"value": None, "status": "unclassified",
                       "reason": "M1-M6 tiers are not defined in the catalog"},
            "notes": notes,
        },
        "unknowns": unknowns,
    }
    if menu:
        host = fit.host_capacity(profile)
        fams: dict[str, list[dict[str, Any]]] = {}
        counts = {k: 0 for k in fit.LABELS}
        for entry in menu.get("featured", []):
            slug = entry["family_slug"]
            rows = []
            for s in catalog.sizes(slug):
                f = fit.evaluate(s["ollama_ref"], s, host)
                counts[f["state"]] += 1
                rows.append({"ref": s["ollama_ref"], "fit": f["state"]})
            fams[slug] = rows
        profile["suitability"] = {"menu": menu.get("schema_version"), "counts": counts, "families": fams}
    return profile


def write_atomic(path: Path, doc: dict[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)

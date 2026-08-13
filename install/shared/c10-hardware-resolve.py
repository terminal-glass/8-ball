#!/usr/bin/env python3
"""Hardware detection, lane resolution, and model candidate building for 8.2.sh."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def find_repo_root(start: Path | None = None) -> Path:
    hint = os.environ.get("EIGHTBALL_REPO_ROOT", "").strip()
    if hint:
        root = Path(hint)
        if (root / "profiles").is_dir():
            return root
    current = (start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / "profiles").is_dir() and (current / "install").is_dir():
            return current
        current = current.parent
    raise SystemExit("Could not locate repository root (profiles/ + install/).")


def read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip().strip('"')
    return data


def detect_cloud_provider() -> str | None:
    if Path("/etc/digitalocean").is_file():
        return "digitalocean"
    os_release = read_os_release()
    if "digitalocean" in os_release.get("ID", "").lower():
        return "digitalocean"
    uuid_path = Path("/sys/hypervisor/uuid")
    if uuid_path.is_file():
        try:
            if "ec2" in uuid_path.read_text(encoding="utf-8").lower():
                return "aws"
        except OSError:
            pass
    vendor = Path("/sys/class/dmi/id/sys_vendor")
    if vendor.is_file():
        text = vendor.read_text(encoding="utf-8", errors="ignore").lower()
        if "amazon" in text:
            return "aws"
        if "digitalocean" in text:
            return "digitalocean"
    return None


def detect_gpu() -> dict[str, Any]:
    gpu: dict[str, Any] = {
        "present": False,
        "vendor": "none",
        "name": "none",
        "vram_mb": 0,
        "cuda_available": False,
    }
    if not Path("/usr/bin/nvidia-smi").is_file() and not shutil_which("nvidia-smi"):
        return gpu
    name = run_first_line(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    vram = run_first_line(
        ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
    )
    gpu["present"] = True
    gpu["vendor"] = "nvidia"
    gpu["name"] = name or "nvidia-gpu"
    try:
        gpu["vram_mb"] = int(float(vram or "0"))
    except ValueError:
        gpu["vram_mb"] = 0
    cuda_version = run_first_line(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    gpu["cuda_available"] = bool(cuda_version)
    return gpu


def shutil_which(cmd: str) -> str | None:
    for path in os.environ.get("PATH", "").split(":"):
        candidate = Path(path) / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def run_first_line(cmd: list[str]) -> str:
    import subprocess

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip().splitlines()[0] if proc.stdout.strip() else ""


def detect_hardware() -> dict[str, Any]:
    os_release = read_os_release()
    distro = os_release.get("ID", "unknown")
    version = os_release.get("VERSION_ID", "")
    arch = run_first_line(["uname", "-m"]) or "unknown"
    ram_mb = 0
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                ram_mb = int(line.split()[1]) // 1024
                break
    cpu_threads = 1
    try:
        cpu_threads = int(run_first_line(["nproc"]) or "1")
    except ValueError:
        cpu_threads = 1
    free_disk_mb = 0
    try:
        proc = subprocess.run(["df", "-Pm", "/"], capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    free_disk_mb = int(parts[3])
                    break
    except OSError:
        pass
    gpu = detect_gpu()
    cloud = detect_cloud_provider()
    return {
        "os": "linux",
        "distro": distro,
        "distro_version": version,
        "architecture": arch,
        "ram_mb": ram_mb,
        "cpu_threads": cpu_threads,
        "free_disk_mb": free_disk_mb,
        "gpu": gpu,
        "cloud_provider": cloud,
    }


def resolve_lane(hardware: dict[str, Any], install_lane: str | None = None) -> dict[str, str]:
    if install_lane:
        lane = install_lane.strip("/")
        return {
            "lane_path": lane,
            "provider_assumption": provider_assumption_for_lane(lane),
            "resolution_source": "env:EIGHTBALL_INSTALL_LANE",
        }
    cloud = hardware.get("cloud_provider")
    gpu = hardware.get("gpu", {})
    cuda = bool(gpu.get("cuda_available"))
    if cloud == "digitalocean":
        lane = "cloud/digitalocean/gpu-droplet" if cuda else "cloud/digitalocean/cpu-droplet"
        return {
            "lane_path": lane,
            "provider_assumption": provider_assumption_for_lane(lane),
            "resolution_source": "detected:cloud-digitalocean",
        }
    if cloud == "aws":
        lane = "cloud/aws-lightsail/gpu" if cuda else "cloud/aws-lightsail/cpu"
        return {
            "lane_path": lane,
            "provider_assumption": provider_assumption_for_lane(lane),
            "resolution_source": "detected:cloud-aws",
        }
    if cuda and int(gpu.get("vram_mb") or 0) >= 6000:
        return {
            "lane_path": "ubuntu/cuda",
            "provider_assumption": "profiles/provider-assumptions/ubuntu-cuda.json",
            "resolution_source": "detected:ubuntu-cuda",
        }
    return {
        "lane_path": "ubuntu/cpu",
        "provider_assumption": "profiles/provider-assumptions/ubuntu-cpu.json",
        "resolution_source": "detected:ubuntu-cpu",
    }


def provider_assumption_for_lane(lane: str) -> str:
    mapping = {
        "ubuntu/cpu": "profiles/provider-assumptions/ubuntu-cpu.json",
        "ubuntu/cuda": "profiles/provider-assumptions/ubuntu-cuda.json",
        "cloud/digitalocean/cpu-droplet": "profiles/provider-assumptions/cloud-digitalocean-cpu-droplet.json",
        "cloud/digitalocean/gpu-droplet": "profiles/provider-assumptions/cloud-digitalocean-gpu-droplet.json",
        "cloud/aws-lightsail/cpu": "profiles/provider-assumptions/cloud-aws-lightsail-cpu.json",
        "cloud/aws-lightsail/gpu": "profiles/provider-assumptions/cloud-aws-lightsail-gpu.json",
    }
    return mapping.get(lane, f"profiles/provider-assumptions/{lane.replace('/', '-')}.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pilot_menu_candidates(repo_root: Path, ram_mb: int) -> list[str]:
    menu_path = repo_root / "AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json"
    if not menu_path.is_file():
        return ["qwen3:0.6b", "qwen3:1.7b", "qwen3:4b", "qwen3:8b", "qwen3:14b"]
    menu = load_json(menu_path)
    band = None
    if ram_mb < 4096:
        band = "fallback-under-4gb"
    elif ram_mb < 8192:
        band = "pilot-4gb"
    elif ram_mb < 12288:
        band = "pilot-8gb"
    elif ram_mb < 24576:
        band = "pilot-12gb"
    else:
        band = "pilot-24gb-plus"
    for entry in menu.get("bands", []):
        if entry.get("pilot_menu_band") == band:
            return list(entry.get("ordered_pilot_candidates", []))
    return list(menu.get("pilot_candidates", []))


def lane_fit_candidates(repo_root: Path, model_slug: str, lane_path: str) -> list[str]:
    lane_json = repo_root / "profiles" / model_slug / lane_path / "lane.json"
    model_json = repo_root / "profiles" / f"{model_slug}.json"
    if not lane_json.is_file() or not model_json.is_file():
        return []
    lane_data = load_json(lane_json)
    model_data = load_json(model_json)
    fit_refs = [
        row["ollama_ref"]
        for row in lane_data.get("size_fit", [])
        if row.get("fit_status") == "fit" and row.get("fits")
    ]
    if not fit_refs:
        return []
    size_order = [row["ollama_ref"] for row in model_data.get("sizes", [])]
    rank = {ref: idx for idx, ref in enumerate(size_order)}
    fit_refs.sort(key=lambda ref: rank.get(ref, 10_000))
    # Largest-first for trial selection; fallback tries smaller later.
    return list(reversed(fit_refs))


def merge_candidates(primary: list[str], fallback: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for ref in primary + fallback:
        if ref and ref not in seen:
            seen.add(ref)
            merged.append(ref)
    return merged


def minimum_disk_mib(repo_root: Path, model_ref: str, ram_mb: int) -> int:
    menu_path = repo_root / "AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json"
    if menu_path.is_file():
        menu = load_json(menu_path)
        for band in menu.get("bands", []):
            thresholds = band.get("disk_thresholds_mib", {})
            if model_ref in thresholds:
                return int(thresholds[model_ref])
    # Conservative default: 3 GiB + model size hint from slug.
    base = 3072
    if re.search(r":14b", model_ref):
        return 14336
    if re.search(r":8b", model_ref):
        return 9216
    if re.search(r":4b", model_ref):
        return 6144
    if re.search(r":1\.7b", model_ref):
        return 4096
    return base


def build_plan(
    *,
    repo_root: Path,
    model_slug: str,
    install_lane: str | None,
    requested_model: str,
) -> dict[str, Any]:
    hardware = detect_hardware()
    lane_info = resolve_lane(hardware, install_lane)
    lane_path = lane_info["lane_path"]
    profile_candidates = lane_fit_candidates(repo_root, model_slug, lane_path)
    pilot_candidates = pilot_menu_candidates(repo_root, int(hardware.get("ram_mb") or 0))
    if profile_candidates:
        candidates = merge_candidates(profile_candidates, pilot_candidates)
        selection_source = "profile-lane-fit+pilot-fallback"
    else:
        candidates = pilot_candidates
        selection_source = "pilot-menu-fallback"
    if requested_model:
        candidates = [requested_model]
        selection_source = "manual-override"
    tier = "LOCAL LITE"
    if lane_path.endswith("/cuda") or "gpu" in lane_path:
        tier = "LOCAL GPU"
    return {
        "hardware": hardware,
        "lane_path": lane_path,
        "provider_assumption": lane_info["provider_assumption"],
        "resolution_source": lane_info["resolution_source"],
        "model_slug": model_slug,
        "selection_source": selection_source,
        "tier": tier,
        "candidates": candidates,
        "minimum_disk_mib": {
            ref: minimum_disk_mib(repo_root, ref, int(hardware.get("ram_mb") or 0))
            for ref in candidates
        },
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: c10-hardware-resolve.py plan [--model REF] [--lane PATH] [--slug SLUG]", file=sys.stderr)
        return 2
    command = sys.argv[1]
    if command != "plan":
        print(f"Unknown command: {command}", file=sys.stderr)
        return 2
    requested = ""
    install_lane = os.environ.get("EIGHTBALL_INSTALL_LANE", "").strip() or None
    model_slug = os.environ.get("EIGHTBALL_MODEL_SLUG", "qwen3").strip() or "qwen3"
    args = sys.argv[2:]
    idx = 0
    while idx < len(args):
        if args[idx] == "--model":
            requested = args[idx + 1]
            idx += 2
        elif args[idx] == "--lane":
            install_lane = args[idx + 1]
            idx += 2
        elif args[idx] == "--slug":
            model_slug = args[idx + 1]
            idx += 2
        else:
            print(f"Unknown argument: {args[idx]}", file=sys.stderr)
            return 2
    repo_root = find_repo_root()
    plan = build_plan(
        repo_root=repo_root,
        model_slug=model_slug,
        install_lane=install_lane,
        requested_model=requested,
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

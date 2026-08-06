#!/usr/bin/env python3
"""C10 profile and install-lane generator.

Reads normalized catalog data and AGENTS hardware CSVs, then emits:
- profiles/<model-slug>.json model data pages
- profiles/<model-slug>/<lane>/ stage JSON files
- profiles/provider-assumptions/<lane-id>.json
- install/<lane>/ executable installer payloads
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = REPO_ROOT / "profiles"
INSTALL_DIR = REPO_ROOT / "install"
REPORT_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"
MAPPING_DIR = REPORT_DIR / "C10.1-1-executable-install-matrix"

STAGE_FILES = (
    "lane.json",
    "3-cpu.json",
    "4-ram.json",
    "5-hard_disk.json",
    "6-CPU_only.json",
    "7-video_card.json",
)

INSTALL_LANES: list[dict[str, Any]] = [
    {
        "lane_path": "ubuntu/cpu",
        "provider_id": "ubuntu-cpu",
        "platform": "ubuntu",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "ubuntu",
        "shell": True,
        "detection_signals": ["os=linux", "distro=ubuntu|debian", "cuda=false"],
        "assumed_profile_id": "cuda_entry_8gb",
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "CPU-only Ubuntu lane; GPU stage not required for lane selection.",
        "source_csv": "AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv",
    },
    {
        "lane_path": "ubuntu/cuda",
        "provider_id": "ubuntu-cuda",
        "platform": "ubuntu",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "ubuntu",
        "shell": True,
        "detection_signals": ["os=linux", "cuda=true", "nvidia-smi"],
        "assumed_profile_id": "cuda_mid_12_16gb",
        "fallback_profile_id": "cuda_entry_8gb",
        "stage7_applicable": True,
        "stage7_reason": "CUDA server lane; NVIDIA GPU and driver detection required.",
        "source_csv": "AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv",
    },
    {
        "lane_path": "mac/apple-silicon",
        "provider_id": "mac-apple-silicon",
        "platform": "mac",
        "provider": None,
        "architecture": "arm64",
        "gpu_lane": True,
        "source_dir": "mac",
        "shell": True,
        "detection_signals": ["os=darwin", "arch=arm64", "apple-metal"],
        "assumed_profile_id": "mac_air_apple_silicon_16gb",
        "fallback_profile_id": "mac_air_apple_silicon_8gb",
        "stage7_applicable": True,
        "stage7_reason": "Apple Silicon unified memory; Metal GPU path.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    {
        "lane_path": "mac/intel",
        "provider_id": "mac-intel",
        "platform": "mac",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "mac",
        "shell": True,
        "detection_signals": ["os=darwin", "arch=x86_64"],
        "assumed_profile_id": "mac_air_apple_silicon_8gb",
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "Intel Mac lane uses CPU-only fallback; discrete GPU not assumed.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    {
        "lane_path": "windows/cpu",
        "provider_id": "windows-cpu",
        "platform": "windows",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "windows",
        "shell": True,
        "detection_signals": ["os=windows", "cuda=false"],
        "assumed_profile_id": "windows_cpu_16gb",
        "fallback_profile_id": "windows_cpu_8gb",
        "stage7_applicable": False,
        "stage7_reason": "Windows CPU-only lane; no NVIDIA CUDA assumed.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    {
        "lane_path": "windows/cuda",
        "provider_id": "windows-cuda",
        "platform": "windows",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "windows",
        "shell": True,
        "detection_signals": ["os=windows", "cuda=true", "nvidia-smi"],
        "assumed_profile_id": "windows_nvidia_32_64gb_vram_12_16gb",
        "fallback_profile_id": "windows_nvidia_16gb_vram_6_8gb",
        "stage7_applicable": True,
        "stage7_reason": "Windows NVIDIA CUDA lane.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    {
        "lane_path": "cloud/digitalocean/cpu-droplet",
        "provider_id": "cloud-digitalocean-cpu-droplet",
        "platform": "cloud",
        "provider": "digitalocean",
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "cloud/digitalocean-droplet",
        "shell": True,
        "detection_signals": ["provider=digitalocean", "droplet=true", "gpu=false"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "DigitalOcean CPU droplet lane; no GPU assumed.",
        "source_csv": "AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/general-purpose.json",
        "provider_plan_hint": "s-2vcpu-4gb",
    },
    {
        "lane_path": "cloud/digitalocean/gpu-droplet",
        "provider_id": "cloud-digitalocean-gpu-droplet",
        "platform": "cloud",
        "provider": "digitalocean",
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "cloud/digitalocean-droplet",
        "shell": True,
        "detection_signals": ["provider=digitalocean", "gpu-droplet=true", "nvidia"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": True,
        "stage7_reason": "DigitalOcean GPU droplet lane.",
        "source_csv": "AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv",
        "provider_plan_hint": "gpu-h100x1-80gb",
    },
    {
        "lane_path": "cloud/aws-lightsail/cpu",
        "provider_id": "cloud-aws-lightsail-cpu",
        "platform": "cloud",
        "provider": "aws-lightsail",
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "cloud/aws-lightsail",
        "shell": True,
        "detection_signals": ["provider=aws", "lightsail=true", "gpu=false"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "AWS Lightsail CPU instance lane.",
        "source_csv": "AGENTS/data-science/P2-Provider-Datasets/providers/lightsail/linux-unix-public-ipv4-bundles.json",
        "provider_plan_hint": "medium_3_0",
    },
    {
        "lane_path": "cloud/aws-lightsail/gpu",
        "provider_id": "cloud-aws-lightsail-gpu",
        "platform": "cloud",
        "provider": "aws-lightsail",
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "cloud/aws-lightsail",
        "shell": True,
        "detection_signals": ["provider=aws", "lightsail=true", "gpu=true"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": True,
        "stage7_reason": "AWS Lightsail GPU instance lane when GPU bundles are available.",
        "source_csv": "AGENTS/TG-8Ball-GPU-Source-Inventory.csv",
        "provider_plan_hint": None,
    },
]

PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([bmk])", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_size_slug(tag: str) -> str:
    slug = tag.strip().lower()
    slug = slug.replace("_", "-")
    slug = re.sub(r"-(?=\d)", "", slug)
    return slug


def param_sort_key(tag: dict[str, Any]) -> tuple[float, str]:
    params = tag.get("parameter_count")
    if isinstance(params, (int, float)) and params > 0:
        return (-float(params), tag.get("tag", ""))
    label = tag.get("tag", "") or tag.get("size_slug", "")
    match = PARAM_RE.search(label)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        multiplier = {"b": 1e9, "m": 1e6, "k": 1e3}.get(unit, 1.0)
        return (-value * multiplier, label)
    return (0.0, label)


def size_sort_key(size: dict[str, Any]) -> tuple[float, str]:
    return param_sort_key(
        {"parameter_count": size.get("parameter_count"), "tag": size.get("size_slug")}
    )


def ollama_model_name(ollama_identifier: str) -> str:
    if ":" in ollama_identifier:
        return ollama_identifier.split(":", 1)[0]
    return ollama_identifier


def estimate_memory_gb(tag: dict[str, Any]) -> dict[str, float | None]:
    storage_bytes = tag.get("download_size_bytes")
    if storage_bytes is None:
        return {
            "min_system_ram_gb": None,
            "recommended_system_ram_gb": None,
            "min_vram_gb": None,
            "recommended_vram_gb": None,
            "min_disk_gb": None,
        }
    model_gb = storage_bytes / 1_000_000_000
    params = tag.get("parameter_count") or 0
    kv_gb = (params / 1_000_000_000) * 0.25
    runtime_gb = 1.5
    total = (model_gb + kv_gb + runtime_gb) * 1.15
    disk_gb = round(model_gb * 1.2 + 5, 2)
    return {
        "min_system_ram_gb": round(total, 2),
        "recommended_system_ram_gb": round(total * 1.2, 2),
        "min_vram_gb": round(model_gb * 1.15, 2),
        "recommended_vram_gb": round(total, 2),
        "min_disk_gb": disk_gb,
    }


def load_hardware_profiles() -> dict[str, dict[str, Any]]:
    path = REPO_ROOT / "data/normalized/hardware-assumed-profiles.json"
    profiles: dict[str, dict[str, Any]] = {}
    for row in load_json(path):
        profile_id = row.get("profile_id")
        if profile_id:
            profiles[profile_id] = row
    return profiles


def load_cloud_plan_defaults() -> dict[str, dict[str, Any]]:
    defaults: dict[str, dict[str, Any]] = {}
    do_gp = REPO_ROOT / "AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/general-purpose.json"
    if do_gp.exists():
        plans = load_json(do_gp)
        if plans:
            plan = plans[0]
            defaults["cloud-digitalocean-cpu-droplet"] = {
                "vcpu": plan.get("vcpus"),
                "ram_gb": plan.get("memory_gb"),
                "disk_gb": plan.get("disk_gb"),
                "source_path": str(do_gp.relative_to(REPO_ROOT)),
            }
    ls = REPO_ROOT / "AGENTS/data-science/P2-Provider-Datasets/providers/lightsail/linux-unix-public-ipv4-bundles.json"
    if ls.exists():
        plans = load_json(ls)
        medium = next((p for p in plans if p.get("bundle_id") == "medium_3_0"), plans[0] if plans else None)
        if medium:
            defaults["cloud-aws-lightsail-cpu"] = {
                "vcpu": medium.get("vcpu_count"),
                "ram_gb": medium.get("ram_gb"),
                "disk_gb": medium.get("ssd_gb"),
                "source_path": str(ls.relative_to(REPO_ROOT)),
            }
    do_gpu_csv = REPO_ROOT / "AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv"
    if do_gpu_csv.exists():
        with do_gpu_csv.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            row = rows[0]
            defaults["cloud-digitalocean-gpu-droplet"] = {
                "vcpu": int(row.get("vcpus") or 0) or None,
                "ram_gb": float(row.get("ram_gb") or 0) or None,
                "disk_gb": float(row.get("disk_gb") or 0) or None,
                "vram_gb": float(row.get("vram_gb") or 0) or None,
                "source_path": str(do_gpu_csv.relative_to(REPO_ROOT)),
            }
    return defaults


def build_model_pages(tags: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        oid = tag.get("ollama_identifier")
        if not oid or ":" not in oid:
            continue
        model_slug = ollama_model_name(oid)
        grouped[model_slug].append(tag)

    pages: dict[str, dict[str, Any]] = {}
    for model_slug, model_tags in grouped.items():
        seen: set[str] = set()
        sizes: list[dict[str, Any]] = []
        for tag in sorted(model_tags, key=param_sort_key):
            size_slug = normalize_size_slug(tag.get("tag", ""))
            ollama_ref = tag["ollama_identifier"]
            if ollama_ref in seen:
                continue
            seen.add(ollama_ref)
            mem = estimate_memory_gb(tag)
            sizes.append(
                {
                    "size_slug": size_slug,
                    "ollama_ref": ollama_ref,
                    "parameter_count": tag.get("parameter_count"),
                    "quantization": tag.get("quantization"),
                    "download_size_bytes": tag.get("download_size_bytes"),
                    "promoted": tag.get("id") == model_tags[0].get("id"),
                    "provenance": {
                        "source_path": "data/normalized/tags.json",
                        "source_url": tag.get("source_url"),
                        "retrieved_at": tag.get("retrieved_at"),
                    },
                    "estimated": mem,
                }
            )
        if not sizes:
            continue
        sizes.sort(key=size_sort_key)
        pages[model_slug] = {
            "schema_version": "c10.model-page.v1",
            "model_slug": model_slug,
            "generated_at": utc_now(),
            "sizes": sizes,
            "promoted_size_slug": sizes[0]["size_slug"],
            "source_paths": ["data/normalized/tags.json", "data/normalized/models.json"],
        }
    return pages


def lane_hardware(lane: dict[str, Any], hardware_profiles: dict[str, dict[str, Any]], cloud_defaults: dict[str, dict[str, Any]]) -> dict[str, Any]:
    profile_id = lane.get("assumed_profile_id")
    if profile_id and profile_id in hardware_profiles:
        p = hardware_profiles[profile_id]
        return {
            "cpu_cores": p.get("cpu_count"),
            "system_ram_gb": p.get("system_ram_gb"),
            "usable_model_ram_gb": p.get("usable_model_ram_gb"),
            "minimum_free_disk_gb": p.get("minimum_free_disk_gb"),
            "total_vram_gb": p.get("total_vram_gb"),
            "cuda_available": p.get("cuda_available"),
            "apple_metal_available": p.get("apple_metal_available"),
            "source_path": p.get("source_reference"),
            "provenance_status": p.get("provenance_status"),
        }
    cloud = cloud_defaults.get(lane["provider_id"])
    if cloud:
        return {
            "cpu_cores": cloud.get("vcpu"),
            "system_ram_gb": cloud.get("ram_gb"),
            "usable_model_ram_gb": round((cloud.get("ram_gb") or 0) * 0.6, 2) if cloud.get("ram_gb") else None,
            "minimum_free_disk_gb": cloud.get("disk_gb"),
            "total_vram_gb": cloud.get("vram_gb"),
            "cuda_available": lane.get("gpu_lane"),
            "apple_metal_available": False,
            "source_path": cloud.get("source_path"),
            "provenance_status": "provider_published",
        }
    return {
        "cpu_cores": None,
        "system_ram_gb": None,
        "usable_model_ram_gb": None,
        "minimum_free_disk_gb": None,
        "total_vram_gb": None,
        "cuda_available": lane.get("gpu_lane"),
        "apple_metal_available": lane.get("provider_id") == "mac-apple-silicon",
        "source_path": lane.get("source_csv"),
        "provenance_status": "data_gap",
    }


def size_fits_lane(size: dict[str, Any], lane: dict[str, Any], hardware: dict[str, Any]) -> tuple[bool, str]:
    est = size.get("estimated") or {}
    ram_need = est.get("min_system_ram_gb")
    vram_need = est.get("min_vram_gb")
    disk_need = est.get("min_disk_gb")
    usable_ram = hardware.get("usable_model_ram_gb") or hardware.get("system_ram_gb")
    if usable_ram is not None and ram_need is not None and ram_need > usable_ram:
        return False, f"requires {ram_need} GB RAM; lane provides {usable_ram} GB usable"
    if lane.get("gpu_lane"):
        vram_avail = hardware.get("total_vram_gb")
        if vram_avail is not None and vram_need is not None and vram_need > vram_avail:
            return False, f"requires {vram_need} GB VRAM; lane provides {vram_avail} GB"
    elif vram_need is not None and usable_ram is not None and vram_need > usable_ram and not lane.get("gpu_lane"):
        return False, f"CPU lane cannot satisfy VRAM-heavy size ({vram_need} GB estimated)"
    disk_avail = hardware.get("minimum_free_disk_gb")
    if disk_avail is not None and disk_need is not None and disk_need > disk_avail:
        return False, f"requires {disk_need} GB disk; lane minimum free disk is {disk_avail} GB"
    if ram_need is None and disk_need is None:
        return False, "insufficient source measurements to confirm fit"
    return True, "fits lane hardware assumptions"


def build_stage_file(stage: str, lane: dict[str, Any], hardware: dict[str, Any], model_slug: str, sizes: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "schema_version": "c10.stage.v1",
        "model_slug": model_slug,
        "lane_path": lane["lane_path"],
        "provider_assumption_id": lane["provider_id"],
        "generated_at": utc_now(),
        "provenance": {
            "source_path": hardware.get("source_path"),
            "provenance_status": hardware.get("provenance_status"),
        },
    }
    if stage == "lane":
        fitting = []
        for size in sizes:
            fits, reason = size_fits_lane(size, lane, hardware)
            fitting.append(
                {
                    "size_slug": size["size_slug"],
                    "ollama_ref": size["ollama_ref"],
                    "fits": fits,
                    "reason": reason,
                }
            )
        return {
            **base,
            "lane_id": lane["lane_path"],
            "provider_assumption": f"profiles/provider-assumptions/{lane['provider_id']}.json",
            "detection_signals": lane["detection_signals"],
            "size_fit": fitting,
        }
    if stage == "3-cpu":
        return {
            **base,
            "applicable": True,
            "minimum_cpu_cores": hardware.get("cpu_cores"),
            "recommended_cpu_cores": hardware.get("cpu_cores"),
            "reason": "CPU stage applies to all lanes.",
        }
    if stage == "4-ram":
        return {
            **base,
            "applicable": True,
            "system_ram_gb": hardware.get("system_ram_gb"),
            "usable_model_ram_gb": hardware.get("usable_model_ram_gb"),
            "reason": "RAM limits sourced from provider or client hardware assumptions.",
        }
    if stage == "5-hard_disk":
        return {
            **base,
            "applicable": True,
            "minimum_free_disk_gb": hardware.get("minimum_free_disk_gb"),
            "reason": "Disk headroom sourced from hardware or provider plan assumptions.",
        }
    if stage == "6-CPU_only":
        cpu_only = not lane.get("gpu_lane")
        return {
            **base,
            "applicable": cpu_only or lane["provider_id"] in {"ubuntu-cuda", "windows-cuda", "cloud-digitalocean-gpu-droplet"},
            "fallback_lane": f"{lane['lane_path'].rsplit('/', 1)[0]}/cpu" if lane.get("gpu_lane") else None,
            "reason": "CPU-only fallback when GPU path is unavailable or lane is CPU-first.",
        }
    if stage == "7-video_card":
        return {
            **base,
            "applicable": lane.get("stage7_applicable", False),
            "cuda_available": hardware.get("cuda_available"),
            "apple_metal_available": hardware.get("apple_metal_available"),
            "total_vram_gb": hardware.get("total_vram_gb"),
            "reason": lane.get("stage7_reason"),
        }
    raise ValueError(stage)


def build_provider_assumption(lane: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "c10.provider-assumption.v1",
        "provider_assumption_id": lane["provider_id"],
        "lane_path": lane["lane_path"],
        "platform": lane["platform"],
        "provider": lane.get("provider"),
        "architecture": lane["architecture"],
        "gpu_lane": lane.get("gpu_lane", False),
        "detection_signals": lane["detection_signals"],
        "hardware": hardware,
        "fallback_profile_id": lane.get("fallback_profile_id"),
        "assumed_profile_id": lane.get("assumed_profile_id"),
        "source_paths": [lane.get("source_csv")],
        "generated_at": utc_now(),
        "installer_reference": f"install/{lane['lane_path']}/trial-install.sh",
        "profiles_reference": f"profiles/provider-assumptions/{lane['provider_id']}.json",
    }


def copy_install_lane(lane: dict[str, Any]) -> None:
    source = INSTALL_DIR / lane["source_dir"]
    target = INSTALL_DIR / lane["lane_path"]
    target.mkdir(parents=True, exist_ok=True)
    for name in ("trial-install.sh", "8.1.sh", "8.2.sh", "8.3.sh"):
        src = source / name
        if src.exists():
            text = src.read_text(encoding="utf-8")
            text = text.replace(
                f'EIGHTBALL_INSTALL_PROFILE="{lane["source_dir"].split("/")[-1]}"',
                f'EIGHTBALL_INSTALL_PROFILE="{lane["lane_path"]}"',
            )
            text = text.replace(
                f"install/{lane['source_dir'].split('/')[-1]}",
                f"install/{lane['lane_path']}",
            )
            if "EIGHTBALL_INSTALL_LANE" not in text:
                text = text.replace(
                    "set -euo pipefail\n",
                    f"set -euo pipefail\n\nEIGHTBALL_INSTALL_LANE=\"{lane['lane_path']}\"\nEIGHTBALL_PROVIDER_ASSUMPTION=\"profiles/provider-assumptions/{lane['provider_id']}.json\"\n",
                    1,
                )
            (target / name).write_text(text, encoding="utf-8")
            (target / name).chmod(0o755)
    assets_src = source / "assets"
    assets_dst = target / "assets"
    if assets_src.exists():
        assets_dst.mkdir(parents=True, exist_ok=True)
        for item in assets_src.iterdir():
            dst = assets_dst / item.name
            if item.is_file():
                shutil.copy2(item, dst)
    readme = target / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# Install lane: {lane['lane_path']}",
                "",
                f"Provider assumption: `profiles/provider-assumptions/{lane['provider_id']}.json`",
                "",
                "Generated by `scripts/generate-c10-profiles.py`.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_inventory(model_pages: dict[str, dict[str, Any]], gaps: list[str]) -> None:
    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    inventory = {
        "generated_at": utc_now(),
        "source_paths": [
            "data/normalized/tags.json",
            "data/normalized/models.json",
            "data/normalized/hardware-assumed-profiles.json",
            "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
            "AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv",
            "AGENTS/data-science/P2-Provider-Datasets/",
        ],
        "model_count": len(model_pages),
        "size_count": sum(len(p["sizes"]) for p in model_pages.values()),
        "install_lane_count": len(INSTALL_LANES),
        "data_gaps": gaps,
    }
    write_json(MAPPING_DIR / "input-inventory.json", inventory)


def generate() -> dict[str, Any]:
    tags = load_json(REPO_ROOT / "data/normalized/tags.json")
    hardware_profiles = load_hardware_profiles()
    cloud_defaults = load_cloud_plan_defaults()
    model_pages = build_model_pages(tags)
    gaps: list[str] = []

    if not (REPO_ROOT / "AGENTS/data-science/ollama-mapping").exists():
        gaps.append("AGENTS/data-science/ollama-mapping/ not present; used data/normalized/ and AGENTS/data-science/P1-P4 instead.")

    provider_dir = PROFILES_DIR / "provider-assumptions"
    provider_dir.mkdir(parents=True, exist_ok=True)
    lane_hardware_map: dict[str, dict[str, Any]] = {}
    for lane in INSTALL_LANES:
        hw = lane_hardware(lane, hardware_profiles, cloud_defaults)
        lane_hardware_map[lane["lane_path"]] = hw
        if hw.get("provenance_status") == "data_gap":
            gaps.append(f"Hardware defaults incomplete for lane {lane['lane_path']}")
        write_json(provider_dir / f"{lane['provider_id']}.json", build_provider_assumption(lane, hw))
        copy_install_lane(lane)

    profile_leaf_count = 0
    for model_slug, page in sorted(model_pages.items()):
        write_json(PROFILES_DIR / f"{model_slug}.json", page)
        for lane in INSTALL_LANES:
            hw = lane_hardware_map[lane["lane_path"]]
            leaf = PROFILES_DIR / model_slug / lane["lane_path"]
            leaf.mkdir(parents=True, exist_ok=True)
            mapping = {
                "lane.json": "lane",
                "3-cpu.json": "3-cpu",
                "4-ram.json": "4-ram",
                "5-hard_disk.json": "5-hard_disk",
                "6-CPU_only.json": "6-CPU_only",
                "7-video_card.json": "7-video_card",
            }
            for filename, stage_key in mapping.items():
                stage = "lane" if stage_key == "lane" else stage_key
                write_json(leaf / filename, build_stage_file(stage, lane, hw, model_slug, page["sizes"]))
                profile_leaf_count += 1

    write_inventory(model_pages, gaps)

    index_rows = []
    for model_slug, page in sorted(model_pages.items()):
        for lane in INSTALL_LANES:
            index_rows.append(
                {
                    "model_slug": model_slug,
                    "lane_path": lane["lane_path"],
                    "provider_assumption_id": lane["provider_id"],
                    "model_page": f"profiles/{model_slug}.json",
                    "lane_dir": f"profiles/{model_slug}/{lane['lane_path']}",
                }
            )
    write_json(PROFILES_DIR / "c10-index.json", {"generated_at": utc_now(), "rows": index_rows})

    return {
        "model_count": len(model_pages),
        "size_count": sum(len(p["sizes"]) for p in model_pages.values()),
        "install_lane_count": len(INSTALL_LANES),
        "profile_leaf_count": profile_leaf_count,
        "provider_assumption_count": len(INSTALL_LANES),
        "data_gaps": gaps,
    }


def main() -> int:
    stats = generate()
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

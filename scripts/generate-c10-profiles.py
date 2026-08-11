#!/usr/bin/env python3
"""C10 profile and install-lane generator.

Reads normalized catalog data and AGENTS hardware CSVs, then emits:
- profiles/lanes.json canonical lane manifest
- profiles/<model-slug>.json model data pages
- profiles/<model-slug>/sizes/<size-slug>.json size records
- profiles/<model-slug>/<lane>/ stage JSON files and profile-sizes.csv
- profiles/index.csv model-size-lane index
- profiles/_lane-matrix-audit.{json,csv}
- install/<lane>/ executable installer payloads (shell or PowerShell)
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

import importlib.util
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_COMMON_PATH = REPO_ROOT / "scripts" / "c10_common.py"
_SPEC = importlib.util.spec_from_file_location("c10_common", _C10_COMMON_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load {_C10_COMMON_PATH}")
c10_common = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_common
_SPEC.loader.exec_module(c10_common)
_C10_LANES_PATH = REPO_ROOT / "scripts" / "c10_lanes.py"
_LANES_SPEC = importlib.util.spec_from_file_location("c10_lanes", _C10_LANES_PATH)
if _LANES_SPEC is None or _LANES_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {_C10_LANES_PATH}")
c10_lanes = importlib.util.module_from_spec(_LANES_SPEC)
sys.modules[_LANES_SPEC.name] = c10_lanes
_LANES_SPEC.loader.exec_module(c10_lanes)
PROFILES_DIR = REPO_ROOT / "profiles"
INSTALL_DIR = REPO_ROOT / "install"
REPORT_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"
MAPPING_DIR = REPORT_DIR / "C10.1-1-executable-install-matrix"
INSTALL_LANES: list[dict[str, Any]] = c10_lanes.build_install_lanes()

STAGE_FILES = (
    "lane.json",
    "3-cpu.json",
    "4-ram.json",
    "5-hard_disk.json",
    "6-CPU_only.json",
    "7-video_card.json",
)

PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([bmk])", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    if isinstance(payload, dict):
        c10_common.write_json_preserve_timestamp(path, payload, build_timestamp=c10_common.build_timestamp())
        return
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
            defaults["digitalocean-cpu-droplet"] = {
                "vcpu": plan.get("vcpus"),
                "ram_gb": plan.get("memory_gb"),
                "disk_gb": plan.get("disk_gb"),
                "source_path": str(do_gp.relative_to(REPO_ROOT)),
                "plans": plans,
            }
    ls = REPO_ROOT / "AGENTS/data-science/P2-Provider-Datasets/providers/lightsail/linux-unix-public-ipv4-bundles.json"
    if ls.exists():
        plans = load_json(ls)
        medium = next((p for p in plans if p.get("bundle_id") == "medium_3_0"), plans[0] if plans else None)
        if medium:
            defaults["aws-lightsail-cpu"] = {
                "vcpu": medium.get("vcpu_count"),
                "ram_gb": medium.get("ram_gb"),
                "disk_gb": medium.get("ssd_gb"),
                "source_path": str(ls.relative_to(REPO_ROOT)),
                "plans": plans,
            }
    do_gpu_plans = c10_common.load_digitalocean_gpu_plans(REPO_ROOT)
    if do_gpu_plans:
        baseline = c10_common.smallest_digitalocean_gpu_plan(do_gpu_plans)
        if baseline:
            defaults["digitalocean-gpu-droplet"] = {
                **baseline,
                "baseline_plan_id": baseline.get("plan_id"),
                "plans": do_gpu_plans,
                "selection_policy": "smallest_published_plan_conservative_baseline",
            }
    aws_gpu_plans = c10_common.load_aws_lightsail_gpu_plans(REPO_ROOT)
    if aws_gpu_plans:
        baseline = c10_common.smallest_aws_lightsail_gpu_plan(aws_gpu_plans)
        if baseline:
            defaults["aws-lightsail-gpu"] = {
                **baseline,
                "baseline_plan_name": baseline.get("plan_name"),
                "plans": aws_gpu_plans,
                "selection_policy": "smallest_published_plan_conservative_baseline",
                "cuda_available": None,
                "vram_status": "unknown",
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


def lane_hardware(lane: dict[str, Any], hardware_profiles: dict[str, dict[str, Any]], cloud_defaults: dict[str, Any]) -> dict[str, Any]:
    profile_id = lane.get("assumed_profile_id")
    if profile_id and profile_id in hardware_profiles:
        p = hardware_profiles[profile_id]
        hw = {
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
        return c10_common.normalize_lane_hardware(hw, lane)
    cloud = cloud_defaults.get(lane["lane_id"])
    if cloud:
        ram_gb = cloud.get("ram_gb")
        hw = {
            "cpu_cores": cloud.get("vcpu"),
            "system_ram_gb": ram_gb,
            "usable_model_ram_gb": round(ram_gb * 0.6, 2) if ram_gb is not None else None,
            "minimum_free_disk_gb": cloud.get("disk_gb"),
            "total_vram_gb": cloud.get("total_vram_gb"),
            "vram_gb_per_gpu": cloud.get("vram_gb_per_gpu"),
            "gpu_count": cloud.get("gpu_count"),
            "cuda_available": cloud.get("cuda_available"),
            "apple_metal_available": False,
            "source_path": cloud.get("source_path"),
            "provenance_status": cloud.get("evidence_status") or "provider_published",
            "baseline_plan_id": cloud.get("baseline_plan_id") or cloud.get("baseline_plan_name"),
            "selection_policy": cloud.get("selection_policy"),
            "plans": cloud.get("plans"),
            "vram_status": cloud.get("vram_status"),
        }
        if lane.get("gpu_lane") and hw["total_vram_gb"] is not None:
            hw["cuda_available"] = True
        return c10_common.normalize_lane_hardware(hw, lane)
    hw = {
        "cpu_cores": None,
        "system_ram_gb": None,
        "usable_model_ram_gb": None,
        "minimum_free_disk_gb": None,
        "total_vram_gb": None,
        "cuda_available": None if lane.get("gpu_lane") else False,
        "apple_metal_available": lane.get("lane_id") == "mac-apple-silicon",
        "source_path": lane.get("source_csv"),
        "provenance_status": "data_gap",
    }
    return c10_common.normalize_lane_hardware(hw, lane)


def size_fits_lane(size: dict[str, Any], lane: dict[str, Any], hardware: dict[str, Any]) -> c10_common.FitResult:
    return c10_common.evaluate_lane_fit(size, lane, hardware)


def build_stage_file(stage: str, lane: dict[str, Any], hardware: dict[str, Any], model_slug: str, sizes: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "schema_version": "c10.stage.v1",
        "model_slug": model_slug,
        "lane_path": lane["lane_path"],
        "provider_assumption_id": lane["lane_id"],
        "generated_at": utc_now(),
        "provenance": {
            "source_path": hardware.get("source_path"),
            "provenance_status": hardware.get("provenance_status"),
        },
    }
    if stage == "lane":
        fitting = []
        for size in sizes:
            fit = size_fits_lane(size, lane, hardware)
            fitting.append(
                {
                    "size_slug": size["size_slug"],
                    "ollama_ref": size["ollama_ref"],
                    "fit_status": fit.fit_status,
                    "fits": fit.fits,
                    "reason": fit.reason,
                    "missing_evidence": list(fit.missing_evidence),
                }
            )
        return {
            **base,
            "lane_id": lane["lane_id"],
            "install_path": lane["install_path"],
            "profile_path": lane["profile_path"],
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
        size_ram_fit = []
        for size in sizes:
            fit = c10_common.evaluate_ram_fit(size, hardware)
            est = size.get("estimated") or {}
            size_ram_fit.append(
                {
                    "size_slug": size["size_slug"],
                    "ollama_ref": size["ollama_ref"],
                    "min_system_ram_gb": est.get("min_system_ram_gb"),
                    "recommended_system_ram_gb": est.get("recommended_system_ram_gb"),
                    "ram_fit_status": fit.fit_status,
                    "fits": fit.fits,
                    "reason": fit.reason,
                    "missing_evidence": list(fit.missing_evidence),
                }
            )
        return {
            **base,
            "applicable": True,
            "system_ram_gb": hardware.get("system_ram_gb"),
            "usable_model_ram_gb": hardware.get("usable_model_ram_gb"),
            "size_ram_fit": size_ram_fit,
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
            "applicable": cpu_only or lane["lane_id"] in {"ubuntu-cuda", "windows-cuda", "digitalocean-gpu-droplet"},
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


def build_size_record(model_slug: str, size: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "c10.size.v1",
        "model_slug": model_slug,
        "size_slug": size["size_slug"],
        "ollama_ref": size["ollama_ref"],
        "parameter_count": size.get("parameter_count"),
        "quantization": size.get("quantization"),
        "download_size_bytes": size.get("download_size_bytes"),
        "promoted": size.get("promoted"),
        "provenance": size.get("provenance"),
        "estimated": size.get("estimated"),
        "generated_at": utc_now(),
    }


def write_profile_sizes_csv(path: Path, model_slug: str, sizes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["size_slug", "size_json_path", "ollama_ref"])
        for size in sizes:
            rel = f"profiles/{model_slug}/sizes/{size['size_slug']}.json"
            writer.writerow([size["size_slug"], rel, size["ollama_ref"]])


def copy_install_lane(lane: dict[str, Any]) -> None:
    source = INSTALL_DIR / lane["source_dir"]
    target = INSTALL_DIR / lane["lane_path"]
    target.mkdir(parents=True, exist_ok=True)
    runtime = lane.get("runtime_type", "shell")
    is_powershell = runtime.lower() == "powershell"

    if is_powershell:
        for old in target.glob("*.sh"):
            old.unlink()
        for _role, rel in c10_lanes.POWERSHELL_PAYLOAD_ROLES:
            if rel.startswith("assets/"):
                continue
            script_name = Path(rel).name
            (target / script_name).write_text(
                c10_lanes.windows_ps1_stub(lane["lane_id"], lane["lane_path"], script_name),
                encoding="utf-8",
            )
    else:
        for old in target.glob("*.ps1"):
            old.unlink()
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
                for line in list(text.splitlines()):
                    if "EIGHTBALL_PROVIDER_ASSUMPTION" in line:
                        text = "\n".join(
                            ln for ln in text.splitlines() if "EIGHTBALL_PROVIDER_ASSUMPTION" not in ln
                        )
                        break
                if "EIGHTBALL_INSTALL_LANE" not in text:
                    text = text.replace(
                        "set -euo pipefail\n",
                        f"set -euo pipefail\n\nEIGHTBALL_INSTALL_LANE=\"{lane['lane_path']}\"\nEIGHTBALL_LANE_ID=\"{lane['lane_id']}\"\n",
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
    if not (assets_dst / "first-MOTD.txt").is_file():
        assets_dst.mkdir(parents=True, exist_ok=True)
        (assets_dst / "first-MOTD.txt").write_text(
            "Welcome to 8-BALL trial install.\n", encoding="utf-8"
        )

    readme = target / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# Install lane: {lane['lane_path']}",
                "",
                f"Lane ID: `{lane['lane_id']}`",
                f"Install path: `{lane['install_path']}`",
                f"Profile path: `profiles/<model>/{lane['profile_path']}`",
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
            "AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv",
            "AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv",
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
    unknown_limit_count = 0
    conflict_count = 0

    c10_lanes.write_lanes_manifest(generated_at=utc_now())

    lane_hardware_map: dict[str, dict[str, Any]] = {}
    for lane in INSTALL_LANES:
        hw = lane_hardware(lane, hardware_profiles, cloud_defaults)
        lane_hardware_map[lane["lane_path"]] = hw
        if hw.get("provenance_status") == "data_gap":
            gaps.append(f"Hardware defaults incomplete for lane {lane['lane_path']}")
            unknown_limit_count += 1
        if lane["lane_id"] == "digitalocean-gpu-droplet" and hw.get("total_vram_gb") is None:
            gaps.append("DigitalOcean GPU baseline missing VRAM after CSV parse")
        copy_install_lane(lane)

    profile_leaf_count = 0
    profile_stage_payload_file_count = 0
    model_size_count = 0
    index_csv_rows: list[list[str]] = []

    for model_slug, page in sorted(model_pages.items()):
        write_json(PROFILES_DIR / f"{model_slug}.json", page)
        sizes_dir = PROFILES_DIR / model_slug / "sizes"
        sizes_dir.mkdir(parents=True, exist_ok=True)
        for size in page["sizes"]:
            write_json(sizes_dir / f"{size['size_slug']}.json", build_size_record(model_slug, size))
            model_size_count += 1

        for lane in INSTALL_LANES:
            hw = lane_hardware_map[lane["lane_path"]]
            leaf = PROFILES_DIR / model_slug / lane["lane_path"]
            leaf.mkdir(parents=True, exist_ok=True)
            write_profile_sizes_csv(leaf / "profile-sizes.csv", model_slug, page["sizes"])
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
                if filename != "lane.json":
                    profile_stage_payload_file_count += 1
            for size in page["sizes"]:
                index_csv_rows.append(
                    [
                        model_slug,
                        size["size_slug"],
                        lane["lane_id"],
                        lane["lane_path"],
                        f"profiles/{model_slug}/sizes/{size['size_slug']}.json",
                        f"profiles/{model_slug}/{lane['lane_path']}/lane.json",
                        lane["install_path"],
                    ]
                )

    write_inventory(model_pages, gaps)

    index_path = PROFILES_DIR / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "model_slug",
                "size_slug",
                "lane_id",
                "lane_path",
                "size_json_path",
                "lane_json_path",
                "install_path",
            ]
        )
        writer.writerows(index_csv_rows)

    c10_index_rows = []
    for model_slug, page in sorted(model_pages.items()):
        for lane in INSTALL_LANES:
            c10_index_rows.append(
                {
                    "model_slug": model_slug,
                    "lane_path": lane["lane_path"],
                    "lane_id": lane["lane_id"],
                    "model_page": f"profiles/{model_slug}.json",
                    "lane_dir": f"profiles/{model_slug}/{lane['lane_path']}",
                    "install_path": lane["install_path"],
                }
            )
    write_json(PROFILES_DIR / "c10-index.json", {"generated_at": utc_now(), "rows": c10_index_rows})

    model_slug_count = len(model_pages)
    profile_matrix_row_count = len(index_csv_rows)
    twelve_k = {
        "observed": False,
        "claimed_category": "model-size-lane index rows",
        "formula": "model_size_count × 10",
        "observed_count": profile_matrix_row_count,
        "target": 12000,
        "discrepancy": profile_matrix_row_count - 12000,
    }
    stage_twelve_k = {
        "observed": False,
        "claimed_category": "model-lane stage payload files (stages 3–7)",
        "formula": "model_slug_count × 10 × 5",
        "observed_count": profile_stage_payload_file_count,
        "target": 12000,
        "discrepancy": profile_stage_payload_file_count - 12000,
    }

    actual_profile_lane_count = model_slug_count * len(INSTALL_LANES)
    audit = c10_lanes.build_lane_matrix_audit(
        model_slug_count=model_slug_count,
        model_size_count=model_size_count,
        actual_profile_lane_count=actual_profile_lane_count,
        profile_matrix_row_count=profile_matrix_row_count,
        profile_stage_payload_file_count=profile_stage_payload_file_count,
        unknown_limit_count=unknown_limit_count,
        conflict_count=conflict_count,
        data_gaps=gaps,
        twelve_k_claim={
            "model_size_lane_index": twelve_k,
            "model_lane_stage_payloads": stage_twelve_k,
            "note": "12,000 was not observed for either category with current catalog inputs.",
        },
    )
    c10_lanes.write_lane_matrix_audit(audit)

    write_json(
        PROFILES_DIR / "manifest.json",
        {
            "schema_version": "c10.profiles-manifest.v1",
            "generated_at": utc_now(),
            "generator": {
                "command": "python3 scripts/generate-c10-profiles.py",
            },
            "counts": {
                "model_pages": model_slug_count,
                "model_directories": model_slug_count,
                "model_sizes": model_size_count,
                "install_lanes": len(INSTALL_LANES),
                "profile_lane_leaves": actual_profile_lane_count,
                "profile_matrix_rows": profile_matrix_row_count,
                "profile_stage_payload_files": profile_stage_payload_file_count,
                "c10_index_rows": len(c10_index_rows),
            },
            "install_lanes": [lane["lane_path"] for lane in INSTALL_LANES],
            "lane_ids": [lane["lane_id"] for lane in INSTALL_LANES],
            "stage_files": list(STAGE_FILES),
            "paths": {
                "lanes_manifest": "profiles/lanes.json",
                "lane_matrix_audit_json": "profiles/_lane-matrix-audit.json",
                "lane_matrix_audit_csv": "profiles/_lane-matrix-audit.csv",
                "profiles_index": "profiles/index.csv",
                "c10_index": "profiles/c10-index.json",
                "model_page_pattern": "profiles/<model-slug>.json",
                "model_size_pattern": "profiles/<model-slug>/sizes/<size-slug>.json",
                "model_lane_pattern": "profiles/<model-slug>/<profile-path>/",
                "canonical_families": "data/generated/pages/families/",
                "canonical_models": "data/generated/pages/models/",
                "canonical_deployment_types": "data/generated/pages/deployment-types/",
                "canonical_install_manifest": "data/generated/pages/install-manifest.json",
            },
            "source_paths": [
                "data/normalized/tags.json",
                "data/normalized/models.json",
                "data/normalized/hardware-assumed-profiles.json",
                "profiles/lanes.json",
            ],
        },
    )

    return {
        "model_count": model_slug_count,
        "size_count": model_size_count,
        "install_lane_count": len(INSTALL_LANES),
        "profile_leaf_count": actual_profile_lane_count,
        "profile_matrix_row_count": profile_matrix_row_count,
        "profile_stage_payload_file_count": profile_stage_payload_file_count,
        "data_gaps": gaps,
        "audit": audit["counts"],
    }


def main() -> int:
    stats = generate()
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

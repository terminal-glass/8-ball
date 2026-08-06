#!/usr/bin/env python3
"""Validate C10 profiles and install lane matrix."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from eight_ball.agents_csv.import_collection import discover_agents_csv_files
from eight_ball.agents_csv.registry import source_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = REPO_ROOT / "profiles"
INSTALL_DIR = REPO_ROOT / "install"

INSTALL_LANES = [
    "ubuntu/cpu",
    "ubuntu/cuda",
    "mac/apple-silicon",
    "mac/intel",
    "windows/cpu",
    "windows/cuda",
    "cloud/digitalocean/cpu-droplet",
    "cloud/digitalocean/gpu-droplet",
    "cloud/aws-lightsail/cpu",
    "cloud/aws-lightsail/gpu",
]

CPU_LANES = {
    "ubuntu/cpu",
    "mac/intel",
    "windows/cpu",
    "cloud/digitalocean/cpu-droplet",
    "cloud/aws-lightsail/cpu",
}

STAGE_FILES = (
    "lane.json",
    "3-cpu.json",
    "4-ram.json",
    "5-hard_disk.json",
    "6-CPU_only.json",
    "7-video_card.json",
)

PROVIDER_FILES = (
    "ubuntu-cpu.json",
    "ubuntu-cuda.json",
    "mac-apple-silicon.json",
    "mac-intel.json",
    "windows-cpu.json",
    "windows-cuda.json",
    "cloud-digitalocean-cpu-droplet.json",
    "cloud-digitalocean-gpu-droplet.json",
    "cloud-aws-lightsail-cpu.json",
    "cloud-aws-lightsail-gpu.json",
)

LANE_ROOTS = {"ubuntu", "mac", "windows", "cloud"}
OLLAMA_REF_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*:[^\s]+$", re.I)
C10_NAME_RE = re.compile(r"c10|10-b", re.I)


def is_size_directory(path: Path, model_slug: str) -> bool:
    if not path.is_dir():
        return False
    if path.name in LANE_ROOTS:
        return False
    return path.parent == PROFILES_DIR / model_slug


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registered_agents_csvs(errors: list[str]) -> None:
    registered = {Path(spec.path).name for spec in source_specs()}
    for path in discover_agents_csv_files(repo_root=REPO_ROOT):
        if path.name not in registered:
            fail(errors, f"Unregistered AGENTS CSV: {path.relative_to(REPO_ROOT)}")


def validate_lane_fit_semantics(lane_payload: dict, path: Path, errors: list[str]) -> None:
    for row in lane_payload.get("size_fit", []):
        fit_status = row.get("fit_status")
        fits = row.get("fits")
        if fit_status is None:
            fail(errors, f"Missing fit_status in {path} for {row.get('ollama_ref')}")
            continue
        if fit_status == "fit" and not fits:
            fail(errors, f"fit_status=fit but fits=false in {path} for {row.get('ollama_ref')}")
        if fit_status in {"unknown", "no_fit"} and fits:
            fail(errors, f"fits=true with fit_status={fit_status} in {path} for {row.get('ollama_ref')}")
        if fits and fit_status != "fit":
            fail(errors, f"fits=true without fit_status=fit in {path} for {row.get('ollama_ref')}")


def validate_provider_assumption(payload: dict, path: Path, errors: list[str]) -> None:
    if not payload.get("detection_signals"):
        fail(errors, f"Provider assumption missing detection_signals: {path}")
    hardware = payload.get("hardware") or {}
    lane_path = payload.get("lane_path", "")
    if lane_path in CPU_LANES:
        if hardware.get("cuda_available") is True:
            fail(errors, f"CPU lane claims cuda_available=true: {path}")
        vram = hardware.get("total_vram_gb")
        if isinstance(vram, (int, float)) and vram > 0:
            fail(errors, f"CPU lane claims positive VRAM: {path}")
    if payload.get("provider_assumption_id") == "cloud-digitalocean-gpu-droplet":
        if hardware.get("system_ram_gb") is None or hardware.get("total_vram_gb") is None:
            fail(errors, f"DigitalOcean GPU assumption missing parsed capacity: {path}")
    if payload.get("provider_assumption_id") == "cloud-aws-lightsail-gpu":
        if hardware.get("total_vram_gb") is not None:
            fail(errors, f"AWS Lightsail GPU assumption must not claim VRAM before runtime probe: {path}")
        if hardware.get("cuda_available") is True:
            fail(errors, f"AWS Lightsail GPU assumption must not claim CUDA before runtime probe: {path}")


def validate(errors: list[str]) -> dict:
    stats = {
        "model_pages": 0,
        "sizes": 0,
        "install_lanes": 0,
        "profile_leaves": 0,
        "provider_assumptions": 0,
        "shell_checked": 0,
        "index_rows": 0,
    }

    validate_registered_agents_csvs(errors)

    model_pages = sorted(p for p in PROFILES_DIR.glob("*.json") if p.name not in {"c10-index.json", "manifest.json"})
    stats["model_pages"] = len(model_pages)
    if not model_pages:
        fail(errors, "No profiles/<model-slug>.json model pages found")

    index_path = PROFILES_DIR / "c10-index.json"
    index_rows = []
    if index_path.exists():
        index_rows = load_json(index_path).get("rows", [])
        stats["index_rows"] = len(index_rows)

    for page_path in model_pages:
        slug = page_path.stem
        if C10_NAME_RE.search(slug):
            fail(errors, f"Model slug contains C10 label: {slug}")
        page = load_json(page_path)
        sizes = page.get("sizes", [])
        if not sizes:
            fail(errors, f"Model page has no sizes: {page_path}")
        stats["sizes"] += len(sizes)
        params = []
        for size in sizes:
            value = size.get("parameter_count")
            if isinstance(value, (int, float)) and value > 0:
                params.append(float(value))
            else:
                match = re.search(r"(\d+(?:\.\d+)?)\s*([bmk])", size.get("size_slug", ""), re.I)
                if match:
                    unit = match.group(2).lower()
                    multiplier = {"b": 1e9, "m": 1e6, "k": 1e3}.get(unit, 1.0)
                    params.append(float(match.group(1)) * multiplier)
                else:
                    params.append(0.0)
        if params != sorted(params, reverse=True):
            fail(errors, f"Sizes not descending by parameter count: {slug}")
        for size in sizes:
            ref = size.get("ollama_ref", "")
            if not OLLAMA_REF_RE.match(ref):
                fail(errors, f"Invalid ollama_ref {ref!r} in {slug}")
            size_dir = PROFILES_DIR / slug / size.get("size_slug", "MISSING")
            if is_size_directory(size_dir, slug):
                fail(errors, f"Size directory must not exist: {size_dir}")
        for lane in INSTALL_LANES:
            leaf = PROFILES_DIR / slug / lane
            if not leaf.is_dir():
                fail(errors, f"Missing profile leaf: {leaf}")
                continue
            stats["profile_leaves"] += 1
            for stage_file in STAGE_FILES:
                path = leaf / stage_file
                if not path.is_file():
                    fail(errors, f"Missing stage file: {path}")
                    continue
                payload = load_json(path)
                if stage_file == "lane.json":
                    validate_lane_fit_semantics(payload, path, errors)
                if "applicable" in payload and payload["applicable"] is False and not payload.get("reason"):
                    fail(errors, f"Non-applicable stage missing reason: {path}")

    for lane in INSTALL_LANES:
        lane_dir = INSTALL_DIR / lane
        if not lane_dir.is_dir():
            fail(errors, f"Missing install lane: {lane_dir}")
            continue
        required = ["trial-install.sh", "8.1.sh", "8.2.sh", "8.3.sh", "README.md"]
        for name in required:
            if not (lane_dir / name).is_file():
                fail(errors, f"Install lane missing {name}: {lane_dir}")
        if not (lane_dir / "assets").is_dir():
            fail(errors, f"Install lane missing assets/: {lane_dir}")
        stats["install_lanes"] += 1
        for script in lane_dir.glob("*.sh"):
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            stats["shell_checked"] += 1
            if result.returncode != 0:
                fail(errors, f"bash -n failed for {script}: {result.stderr.strip()}")

    pa_dir = PROFILES_DIR / "provider-assumptions"
    for name in PROVIDER_FILES:
        path = pa_dir / name
        if not path.is_file():
            fail(errors, f"Missing provider assumption: {path}")
        else:
            stats["provider_assumptions"] += 1
            validate_provider_assumption(load_json(path), path, errors)

    for row in index_rows:
        for key in ("model_page", "lane_dir"):
            rel = row.get(key)
            if rel and not (REPO_ROOT / rel).exists():
                fail(errors, f"Index points to missing file: {rel}")

    root_trial = REPO_ROOT / "trial-install.sh"
    if not root_trial.is_file():
        fail(errors, "Missing root trial-install.sh")
    else:
        result = subprocess.run(["bash", "-n", str(root_trial)], capture_output=True, text=True)
        stats["shell_checked"] += 1
        if result.returncode != 0:
            fail(errors, f"bash -n failed for root trial-install.sh: {result.stderr.strip()}")

    return stats


def main() -> int:
    errors: list[str] = []
    stats = validate(errors)
    report = {
        "valid": not errors,
        "stats": stats,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

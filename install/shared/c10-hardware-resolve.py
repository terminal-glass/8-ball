#!/usr/bin/env python3
"""Hardware detection, lane resolution, and runtime profile candidate building for 8.2.sh."""
from __future__ import annotations

import importlib.util
import json
import os
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


def load_c10_common(repo_root: Path) -> Any:
    path = repo_root / "scripts" / "c10_common.py"
    spec = importlib.util.spec_from_file_location("c10_common", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Missing c10_common module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def shutil_which(cmd: str) -> str | None:
    for path in os.environ.get("PATH", "").split(":"):
        candidate = Path(path) / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def run_first_line(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip().splitlines()[0] if proc.stdout.strip() else ""


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


def measured_hardware_from_env() -> dict[str, Any]:
    def _float(name: str) -> float | None:
        raw = os.environ.get(name, "").strip()
        if not raw:
            return None
        return float(raw)

    def _int(name: str) -> int | None:
        raw = os.environ.get(name, "").strip()
        if not raw:
            return None
        return int(raw)

    system_ram_gb = _float("EIGHTBALL_SYSTEM_RAM_GB")
    usable_model_ram_gb = _float("EIGHTBALL_USABLE_MODEL_RAM_GB")
    if usable_model_ram_gb is None and system_ram_gb is not None:
        usable_model_ram_gb = round(system_ram_gb * 0.6, 2)

    cuda_raw = os.environ.get("EIGHTBALL_CUDA_AVAILABLE", "").strip().lower()
    cuda_available: bool | None
    if cuda_raw in {"1", "true", "yes"}:
        cuda_available = True
    elif cuda_raw in {"0", "false", "no"}:
        cuda_available = False
    else:
        cuda_available = None

    ram_mb = int(system_ram_gb * 1024) if system_ram_gb is not None else 0
    free_disk_mb = int((_float("EIGHTBALL_FREE_DISK_GB") or 0) * 1024)
    vram_gb = _float("EIGHTBALL_GPU_VRAM_GB")
    gpu_name = os.environ.get("EIGHTBALL_GPU_NAME", "none").strip() or "none"

    return {
        "os": "linux",
        "distro": os.environ.get("EIGHTBALL_DISTRO", "ubuntu"),
        "distro_version": os.environ.get("EIGHTBALL_DISTRO_VERSION", ""),
        "architecture": os.environ.get("EIGHTBALL_ARCHITECTURE", "x86_64"),
        "ram_mb": ram_mb,
        "cpu_threads": _int("EIGHTBALL_CPU_THREADS") or 1,
        "free_disk_mb": free_disk_mb,
        "gpu": {
            "present": bool(vram_gb and vram_gb > 0),
            "vendor": "nvidia" if cuda_available else "none",
            "name": gpu_name,
            "vram_mb": int((vram_gb or 0) * 1024),
            "cuda_available": bool(cuda_available),
        },
        "cloud_provider": os.environ.get("EIGHTBALL_CLOUD_PROVIDER") or None,
    }


def detect_hardware() -> dict[str, Any]:
    if os.environ.get("EIGHTBALL_USE_MEASURED_HARDWARE_ENV", "").strip() == "1":
        return measured_hardware_from_env()

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


def hardware_for_c10(raw: dict[str, Any]) -> dict[str, Any]:
    ram_mb = int(raw.get("ram_mb") or 0)
    system_ram_gb = round(ram_mb / 1024.0, 2) if ram_mb else None
    usable_model_ram_gb = round(system_ram_gb * 0.6, 2) if system_ram_gb else None
    free_disk_mb = int(raw.get("free_disk_mb") or 0)
    minimum_free_disk_gb = round(free_disk_mb / 1024.0, 2) if free_disk_mb else None
    gpu = raw.get("gpu") or {}
    vram_mb = int(gpu.get("vram_mb") or 0)
    total_vram_gb = round(vram_mb / 1024.0, 2) if vram_mb else None
    return {
        "cpu_cores": int(raw.get("cpu_threads") or 1),
        "system_ram_gb": system_ram_gb,
        "usable_model_ram_gb": usable_model_ram_gb,
        "minimum_free_disk_gb": minimum_free_disk_gb,
        "total_vram_gb": total_vram_gb,
        "cuda_available": bool(gpu.get("cuda_available")),
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


def deployment_type_for_hardware(hardware: dict[str, Any]) -> str:
    gpu = hardware.get("gpu") or {}
    vram_mb = int(gpu.get("vram_mb") or 0)
    ram_mb = int(hardware.get("ram_mb") or 0)
    if vram_mb >= 12000:
        return "7"
    if vram_mb >= 6000:
        return "6"
    if ram_mb >= 16000:
        return "5"
    if ram_mb >= 8000:
        return "4"
    return "3"


def profile_root(repo_root: Path) -> Path:
    override = os.environ.get("EIGHTBALL_PROFILES_BASE", "").strip()
    if override and not override.startswith("http"):
        return Path(override)
    return repo_root / "profiles"


def lane_gpu_lane(lane: dict[str, Any], lane_path: str) -> bool:
    if "gpu_lane" in lane:
        return bool(lane.get("gpu_lane"))
    return "cuda" in lane_path or "gpu" in lane_path


def load_lane_document(repo_root: Path, model_slug: str, lane_path: str) -> dict[str, Any]:
    path = profile_root(repo_root) / model_slug / lane_path / "lane.json"
    if not path.is_file():
        raise SystemExit(f"Missing profile lane artifact: {path}")
    return load_json(path)


def load_model_sizes(repo_root: Path, model_slug: str) -> list[dict[str, Any]]:
    sizes_dir = profile_root(repo_root) / model_slug / "sizes"
    if sizes_dir.is_dir():
        sizes = [load_json(path) for path in sorted(sizes_dir.glob("*.json"))]
        if sizes:
            return sizes
    legacy = profile_root(repo_root) / f"{model_slug}.json"
    if legacy.is_file():
        return load_json(legacy).get("sizes", [])
    raise SystemExit(f"Missing profile sizes for model slug: {model_slug}")


def reference_validation_slug(repo_root: Path) -> str:
    menu_path = repo_root / "AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json"
    if menu_path.is_file():
        menu = load_json(menu_path)
        pilot = menu.get("pilot_candidates") or []
        if pilot:
            return str(pilot[0]).split(":", 1)[0]
    return ""


def resolve_model_slug(
    repo_root: Path,
    explicit_slug: str,
    requested_model: str,
    manifest_path: str | None,
) -> tuple[str, str]:
    if explicit_slug:
        return explicit_slug, "arg:--slug"
    env_slug = os.environ.get("EIGHTBALL_MODEL_SLUG", "").strip()
    if env_slug:
        return env_slug, "env:EIGHTBALL_MODEL_SLUG"
    if requested_model and ":" in requested_model:
        return requested_model.split(":", 1)[0], "derived:--model"
    ref_slug = reference_validation_slug(repo_root)
    if ref_slug and (profile_root(repo_root) / ref_slug / "model.json").is_file():
        return ref_slug, "data:base-pilot-menu.reference"
    if manifest_path:
        manifest_slug = manifest_model_slug_for_reference(manifest_path, repo_root)
        if manifest_slug:
            return manifest_slug, "data:install-manifest.reference"
    raise SystemExit(
        "Missing model slug for profile-driven selection. "
        "Provide --model-slug, set EIGHTBALL_MODEL_SLUG, or supply install-manifest.json."
    )


def manifest_model_slug_for_reference(manifest_path: str, repo_root: Path) -> str:
    path = Path(manifest_path)
    if not path.is_file():
        return ""
    manifest = load_json(path)
    models = manifest.get("models", {})
    menu_path = repo_root / "AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json"
    preferred: list[str] = []
    if menu_path.is_file():
        menu = load_json(menu_path)
        for ref in menu.get("pilot_candidates", []):
            slug = str(ref).split(":", 1)[0]
            if slug not in preferred:
                preferred.append(slug)
    for slug in preferred:
        for entry in models.values():
            if entry.get("model_slug") == slug:
                return slug
    for entry in models.values():
        slug = entry.get("model_slug")
        if slug:
            return str(slug)
    return ""


def manifest_candidates(
    manifest_path: str,
    deployment_type: str,
    model_slug: str,
) -> list[str]:
    path = Path(manifest_path)
    if not path.is_file():
        return []
    manifest = load_json(path)
    candidates: list[str] = []
    for entry in manifest.get("models", {}).values():
        if entry.get("model_slug") != model_slug:
            continue
        deployment = (entry.get("deployments") or {}).get(str(deployment_type))
        if not deployment:
            continue
        ollama_id = deployment.get("ollama_identifier")
        if ollama_id:
            candidates.append(str(ollama_id))
    return candidates


def evaluate_profile_candidates(
    repo_root: Path,
    c10_common: Any,
    model_slug: str,
    lane_path: str,
    hardware_c10: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    lane = load_lane_document(repo_root, model_slug, lane_path)
    sizes = load_model_sizes(repo_root, model_slug)
    lane_meta = {"gpu_lane": lane_gpu_lane(lane, lane_path)}
    hardware = c10_common.normalize_lane_hardware(dict(hardware_c10), lane_meta)
    evaluated: list[dict[str, Any]] = []
    for size in sizes:
        ref = size.get("ollama_ref")
        if not ref:
            continue
        fit = c10_common.evaluate_lane_fit(size, lane_meta, hardware)
        evaluated.append(
            {
                "ollama_ref": ref,
                "size_slug": size.get("size_slug"),
                "parameter_count": size.get("parameter_count") or 0,
                "fit_status": fit.fit_status,
                "fits": fit.fits,
                "reason": fit.reason,
                "missing_evidence": list(fit.missing_evidence),
                "min_disk_gb": (size.get("estimated") or {}).get("min_disk_gb"),
            }
        )
    fits = [row for row in evaluated if row["fit_status"] == "fit" and row["fits"]]
    fits.sort(key=lambda row: int(row.get("parameter_count") or 0), reverse=True)
    candidates = [row["ollama_ref"] for row in fits]
    return candidates, evaluated, lane


def minimum_disk_map(evaluated: list[dict[str, Any]], candidates: list[str]) -> dict[str, int]:
    lookup = {row["ollama_ref"]: row for row in evaluated}
    result: dict[str, int] = {}
    for ref in candidates:
        row = lookup.get(ref, {})
        disk_gb = row.get("min_disk_gb")
        if disk_gb is None:
            continue
        result[ref] = int(float(disk_gb) * 1024)
    return result


def build_plan(
    *,
    repo_root: Path,
    model_slug: str,
    install_lane: str | None,
    requested_model: str,
    manifest_path: str | None,
) -> dict[str, Any]:
    raw_hardware = detect_hardware()
    hardware_c10 = hardware_for_c10(raw_hardware)
    lane_info = resolve_lane(raw_hardware, install_lane)
    lane_path = lane_info["lane_path"]
    deployment_type = deployment_type_for_hardware(raw_hardware)

    slug_source = ""
    if requested_model and not model_slug:
        model_slug = requested_model.split(":", 1)[0]
        slug_source = "derived:--model"
    else:
        model_slug, slug_source = resolve_model_slug(repo_root, model_slug, requested_model, manifest_path)

    c10_common = load_c10_common(repo_root)

    profile_id = f"{model_slug}/{lane_path}"
    selection_source = "profile-runtime-fit"
    manual_selection_status = None
    manual_rejection_reason = None
    candidates: list[str] = []
    fallback_chain: list[dict[str, Any]] = []
    lane_doc: dict[str, Any] = {}

    if requested_model:
        candidates = [requested_model]
        selection_source = "manual-override"
        try:
            lane_doc = load_lane_document(repo_root, model_slug, lane_path)
            sizes = load_model_sizes(repo_root, model_slug)
            lane_meta = {"gpu_lane": lane_gpu_lane(lane_doc, lane_path)}
            hardware = c10_common.normalize_lane_hardware(dict(hardware_c10), lane_meta)
            size = next((s for s in sizes if s.get("ollama_ref") == requested_model), None)
            if size is None:
                manual_selection_status = "unknown-metadata"
                manual_rejection_reason = "requested model not present in profile sizes"
                fallback_chain.append(
                    {
                        "ollama_ref": requested_model,
                        "fit_status": "unknown",
                        "fits": False,
                        "reason": manual_rejection_reason,
                        "missing_evidence": ["profile_size_record"],
                    }
                )
            else:
                fit = c10_common.evaluate_lane_fit(size, lane_meta, hardware)
                fallback_chain.append(
                    {
                        "ollama_ref": requested_model,
                        "fit_status": fit.fit_status,
                        "fits": fit.fits,
                        "reason": fit.reason,
                        "missing_evidence": list(fit.missing_evidence),
                        "min_disk_gb": (size.get("estimated") or {}).get("min_disk_gb"),
                    }
                )
                if fit.fit_status == "fit" and fit.fits:
                    manual_selection_status = "approved"
                elif fit.fit_status == "unknown":
                    manual_selection_status = "unknown-metadata"
                    manual_rejection_reason = fit.reason
                else:
                    manual_selection_status = "rejected-by-gates"
                    manual_rejection_reason = fit.reason
                    selection_source = "manual-override-rejected-by-gates"
        except SystemExit as exc:
            manual_selection_status = "unknown-metadata"
            manual_rejection_reason = str(exc)
            fallback_chain.append(
                {
                    "ollama_ref": requested_model,
                    "fit_status": "unknown",
                    "fits": False,
                    "reason": str(exc),
                    "missing_evidence": ["profile_lane_artifact"],
                }
            )
    else:
        candidates, fallback_chain, lane_doc = evaluate_profile_candidates(
            repo_root, c10_common, model_slug, lane_path, hardware_c10
        )
        if not candidates and manifest_path:
            manifest_refs = manifest_candidates(manifest_path, deployment_type, model_slug)
            if manifest_refs:
                candidates = manifest_refs
                selection_source = "install-manifest-fallback"
        if not candidates:
            raise SystemExit(
                f"No approved profile candidates fit measured hardware for {profile_id}. "
                "Provide --model, --model-slug, or resolve missing profile evidence."
            )

    tier = "LOCAL LITE"
    if lane_path.endswith("/cuda") or "gpu" in lane_path:
        tier = "LOCAL GPU"

    minimum_disk = minimum_disk_map(fallback_chain, candidates)

    return {
        "hardware": raw_hardware,
        "hardware_c10": hardware_c10,
        "lane_path": lane_path,
        "profile_id": profile_id,
        "provider_assumption": lane_info["provider_assumption"],
        "resolution_source": lane_info["resolution_source"],
        "model_slug": model_slug,
        "model_slug_source": slug_source,
        "selection_source": selection_source,
        "manual_selection_status": manual_selection_status,
        "manual_rejection_reason": manual_rejection_reason,
        "tier": tier,
        "deployment_type": deployment_type,
        "candidates": candidates,
        "fallback_chain": fallback_chain,
        "minimum_disk_mib": minimum_disk,
        "manifest_path": manifest_path,
        "requested_model": requested_model or None,
    }


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "plan":
        print(
            "Usage: c10-hardware-resolve.py plan [--model REF] [--lane PATH] "
            "[--slug SLUG] [--manifest PATH]",
            file=sys.stderr,
        )
        return 2
    requested = ""
    install_lane = os.environ.get("EIGHTBALL_INSTALL_LANE", "").strip() or None
    model_slug = ""
    manifest_path = os.environ.get("EIGHTBALL_MANIFEST", "").strip() or None
    args = sys.argv[2:]
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--model":
            requested = args[idx + 1]
            idx += 2
        elif token == "--lane":
            install_lane = args[idx + 1]
            idx += 2
        elif token == "--slug":
            model_slug = args[idx + 1]
            idx += 2
        elif token == "--manifest":
            manifest_path = args[idx + 1]
            idx += 2
        else:
            print(f"Unknown argument: {token}", file=sys.stderr)
            return 2
    repo_root = find_repo_root()
    if manifest_path and not Path(manifest_path).is_file():
        default_manifest = repo_root / "data/generated/pages/install-manifest.json"
        if default_manifest.is_file():
            manifest_path = str(default_manifest)
    plan = build_plan(
        repo_root=repo_root,
        model_slug=model_slug,
        install_lane=install_lane,
        requested_model=requested,
        manifest_path=manifest_path,
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

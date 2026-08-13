#!/usr/bin/env python3
"""Profile-driven Ubuntu installer runtime selection (measured hardware)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
_C10_COMMON_PATH = REPO_ROOT / "scripts" / "c10_common.py"
_SPEC = importlib.util.spec_from_file_location("c10_common", _C10_COMMON_PATH)
assert _SPEC and _SPEC.loader
c10_common = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(c10_common)


def find_repo_root(start: Path | None = None) -> Path:
    hint = os.environ.get("EIGHTBALL_REPO_ROOT", "").strip()
    if hint:
        root = Path(hint)
        if (root / "profiles" / "manifest.json").is_file():
            return root
    current = (start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / "profiles" / "manifest.json").is_file():
            return current
        current = current.parent
    raise SystemExit(
        "Missing profiles/manifest.json. Clone the full 8-ball repository or set EIGHTBALL_REPO_ROOT."
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_profiles_base(repo_root: Path) -> Path:
    override = os.environ.get("EIGHTBALL_PROFILES_BASE", "").strip()
    if override and not override.startswith("http"):
        return Path(override)
    return repo_root / "profiles"


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

    return {
        "cpu_cores": _int("EIGHTBALL_CPU_THREADS"),
        "system_ram_gb": system_ram_gb,
        "usable_model_ram_gb": usable_model_ram_gb,
        "minimum_free_disk_gb": _float("EIGHTBALL_FREE_DISK_GB"),
        "total_vram_gb": _float("EIGHTBALL_GPU_VRAM_GB"),
        "cuda_available": cuda_available,
    }


def lane_document(repo_root: Path, model_slug: str, lane_path: str) -> dict[str, Any]:
    path = repo_root / "profiles" / model_slug / lane_path / "lane.json"
    if not path.is_file():
        raise SystemExit(f"Missing profile lane artifact: {path}")
    return load_json(path)


def lane_gpu_lane(lane: dict[str, Any], lane_path: str) -> bool:
    if "gpu_lane" in lane:
        return bool(lane.get("gpu_lane"))
    return "cuda" in lane_path or "gpu" in lane_path


def load_model_sizes(repo_root: Path, model_slug: str) -> list[dict[str, Any]]:
    sizes_dir = repo_root / "profiles" / model_slug / "sizes"
    if not sizes_dir.is_dir():
        legacy = repo_root / "profiles" / f"{model_slug}.json"
        if legacy.is_file():
            return load_json(legacy).get("sizes", [])
        raise SystemExit(f"Missing profile sizes for model: {model_slug}")
    sizes: list[dict[str, Any]] = []
    for path in sorted(sizes_dir.glob("*.json")):
        sizes.append(load_json(path))
    if not sizes:
        raise SystemExit(f"No size records found under {sizes_dir}")
    return sizes


def model_page(repo_root: Path, model_slug: str) -> dict[str, Any]:
    path = repo_root / "profiles" / model_slug / "model.json"
    if not path.is_file():
        legacy = repo_root / "profiles" / f"{model_slug}.json"
        if legacy.is_file():
            return load_json(legacy)
        raise SystemExit(f"Missing profile model page: {path}")
    page = load_json(path)
    page["sizes"] = load_model_sizes(repo_root, model_slug)
    return page


def find_size(sizes: list[dict[str, Any]], ollama_ref: str) -> dict[str, Any] | None:
    for size in sizes:
        if size.get("ollama_ref") == ollama_ref:
            return size
    return None


def select_for_slug(
    repo_root: Path,
    model_slug: str,
    lane_path: str,
    hardware: dict[str, Any],
) -> dict[str, Any]:
    lane = lane_document(repo_root, model_slug, lane_path)
    page = model_page(repo_root, model_slug)
    sizes = page.get("sizes", [])
    lane_meta = {"gpu_lane": lane_gpu_lane(lane, lane_path)}
    hardware = c10_common.normalize_lane_hardware(hardware, lane_meta)

    selected = None
    fallback_chain: list[dict[str, Any]] = []
    for size in sizes:
        ref = size.get("ollama_ref")
        if not ref:
            continue
        fit = c10_common.evaluate_lane_fit(size, lane_meta, hardware)
        row = {
            "ollama_ref": ref,
            "fit_status": fit.fit_status,
            "fits": fit.fits,
            "reason": fit.reason,
            "missing_evidence": list(fit.missing_evidence),
        }
        if fit.fit_status == "fit" and fit.fits:
            selected = ref
            fallback_chain.append(row)
            break
        fallback_chain.append(row)

    if not selected:
        return {
            "selection_status": "unverified",
            "selected_ollama_ref": None,
            "model_slug": model_slug,
            "lane_path": lane_path,
            "fallback_chain": fallback_chain,
            "message": (
                "No model size fits measured hardware using committed profile lane data. "
                "Provide a smaller model slug or resolve missing profile evidence."
            ),
        }

    return {
        "selection_status": "selected",
        "selected_ollama_ref": selected,
        "model_slug": model_slug,
        "lane_path": lane_path,
        "fallback_chain": fallback_chain,
        "hardware_used": hardware,
        "cpu_participates": hardware.get("cpu_cores") is not None,
        "gpu_participates": lane_meta["gpu_lane"] and hardware.get("total_vram_gb") is not None,
    }


def validate_requested_model(
    repo_root: Path,
    model_slug: str,
    lane_path: str,
    ollama_ref: str,
    hardware: dict[str, Any],
) -> dict[str, Any]:
    page = model_page(repo_root, model_slug)
    sizes = page.get("sizes", [])
    lane = lane_document(repo_root, model_slug, lane_path)
    lane_meta = {"gpu_lane": lane_gpu_lane(lane, lane_path)}
    hardware = c10_common.normalize_lane_hardware(hardware, lane_meta)
    size = find_size(sizes, ollama_ref)
    if size is None:
        for candidate in sizes:
            ref = candidate.get("ollama_ref") or ""
            if ref == ollama_ref or ref.endswith(f":{ollama_ref.split(':')[-1]}"):
                size = candidate
                ollama_ref = ref
                break
    if size is None:
        return {
            "selection_status": "rejected",
            "selected_ollama_ref": None,
            "model_slug": model_slug,
            "lane_path": lane_path,
            "message": f"Requested model {ollama_ref!r} is not present in profiles/{model_slug}/sizes/",
        }

    fit = c10_common.evaluate_lane_fit(size, lane_meta, hardware)
    if fit.fit_status != "fit" or not fit.fits:
        return {
            "selection_status": "rejected",
            "selected_ollama_ref": None,
            "model_slug": model_slug,
            "lane_path": lane_path,
            "requested_ollama_ref": ollama_ref,
            "fit_status": fit.fit_status,
            "reason": fit.reason,
            "missing_evidence": list(fit.missing_evidence),
            "message": f"Requested model {ollama_ref} does not fit measured hardware: {fit.reason}",
        }

    return {
        "selection_status": "selected",
        "selected_ollama_ref": ollama_ref,
        "model_slug": model_slug,
        "lane_path": lane_path,
        "fit_status": fit.fit_status,
        "reason": fit.reason,
        "hardware_used": hardware,
        "cpu_participates": hardware.get("cpu_cores") is not None,
        "gpu_participates": lane_meta["gpu_lane"] and hardware.get("total_vram_gb") is not None,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: ubuntu-profile-runtime.py select --model-slug SLUG --lane PATH\n"
            "       ubuntu-profile-runtime.py validate --model-slug SLUG --lane PATH --model REF",
            file=sys.stderr,
        )
        return 2

    command = sys.argv[1]
    args = sys.argv[2:]
    model_slug = ""
    lane_path = ""
    requested = ""
    while args:
        token = args.pop(0)
        if token == "--model-slug":
            model_slug = args.pop(0)
        elif token == "--lane":
            lane_path = args.pop(0)
        elif token == "--model":
            requested = args.pop(0)
        else:
            print(f"Unknown argument: {token}", file=sys.stderr)
            return 2

    if not model_slug or not lane_path:
        print("--model-slug and --lane are required", file=sys.stderr)
        return 2

    repo_root = find_repo_root()
    hardware = measured_hardware_from_env()
    if command == "select":
        output = select_for_slug(repo_root, model_slug, lane_path, hardware)
    elif command == "validate":
        if not requested:
            print("--model is required for validate", file=sys.stderr)
            return 2
        output = validate_requested_model(repo_root, model_slug, lane_path, requested, hardware)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 2

    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output.get("selection_status") == "selected" else 1


if __name__ == "__main__":
    raise SystemExit(main())

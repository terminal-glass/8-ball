#!/usr/bin/env python3
"""Validate C10 profiles and install lane matrix."""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from eight_ball.agents_csv.import_collection import discover_agents_csv_files
from eight_ball.agents_csv.registry import source_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_LANES_PATH = REPO_ROOT / "scripts" / "c10_lanes.py"
_LANES_SPEC = importlib.util.spec_from_file_location("c10_lanes", _C10_LANES_PATH)
if _LANES_SPEC is None or _LANES_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {_C10_LANES_PATH}")
c10_lanes = importlib.util.module_from_spec(_LANES_SPEC)
sys.modules[_LANES_SPEC.name] = c10_lanes
_LANES_SPEC.loader.exec_module(c10_lanes)

PROFILES_DIR = REPO_ROOT / "profiles"
INSTALL_DIR = REPO_ROOT / "install"
PROVIDER_ASSUMPTIONS_DIR = REPO_ROOT / "data" / "generated" / "provider-assumptions"

FORBIDDEN_PROFILE_DIRS = frozenset(
    {
        "families",
        "models",
        "deployment-classes",
        "provider-assumptions",
    }
)
ALLOWED_PROFILE_ROOT_FILES = frozenset(
    {
        "README.md",
        "c10-index.json",
        "manifest.json",
        "lanes.json",
        "index.csv",
        "_lane-matrix-audit.json",
        "_lane-matrix-audit.csv",
    }
)
FORBIDDEN_PROFILE_ROOT_FILES = frozenset({"environment.profile.example.env"})

LANE_ROOTS = {"ubuntu", "mac", "windows", "cloud"}
OLLAMA_REF_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*:[^\s]+$", re.I)
C10_NAME_RE = re.compile(r"c10|10-b", re.I)
STAGE_FILES = c10_lanes.STAGE_PAYLOAD_FILES


def is_size_directory(path: Path, model_slug: str) -> bool:
    if not path.is_dir():
        return False
    if path.name in LANE_ROOTS or path.name == "sizes":
        return False
    return path.parent == PROFILES_DIR / model_slug


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_canonical_lanes(errors: list[str]) -> list[dict[str, str]]:
    manifest_path = PROFILES_DIR / "lanes.json"
    if not manifest_path.is_file():
        fail(errors, "Missing profiles/lanes.json")
        return []
    manifest = load_json(manifest_path)
    rows = c10_lanes.canonical_lane_rows_from_manifest(manifest)
    if not c10_lanes.lane_rows_match_canonical(rows):
        fail(errors, "profiles/lanes.json does not match the canonical ten-lane contract")
    return rows


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


def validate_ram_fit_semantics(ram_payload: dict, path: Path, errors: list[str]) -> None:
    size_ram_fit = ram_payload.get("size_ram_fit")
    if not isinstance(size_ram_fit, list) or not size_ram_fit:
        fail(errors, f"Missing size_ram_fit in {path}")
        return
    for row in size_ram_fit:
        fit_status = row.get("ram_fit_status")
        fits = row.get("fits")
        if fit_status is None:
            fail(errors, f"Missing ram_fit_status in {path} for {row.get('ollama_ref')}")
            continue
        if fit_status == "fit" and not fits:
            fail(errors, f"ram_fit_status=fit but fits=false in {path} for {row.get('ollama_ref')}")
        if fit_status in {"unknown", "no_fit"} and fits:
            fail(errors, f"fits=true with ram_fit_status={fit_status} in {path} for {row.get('ollama_ref')}")
        if fits and fit_status != "fit":
            fail(errors, f"fits=true without ram_fit_status=fit in {path} for {row.get('ollama_ref')}")
        if row.get("min_system_ram_gb") is None and fit_status == "fit":
            fail(errors, f"ram_fit_status=fit with null min_system_ram_gb in {path} for {row.get('ollama_ref')}")


def validate_profiles_namespace(errors: list[str]) -> set[str]:
    for name in FORBIDDEN_PROFILE_DIRS:
        path = PROFILES_DIR / name
        if path.exists():
            fail(errors, f"Forbidden profiles/ directory exists: {path}")

    for name in FORBIDDEN_PROFILE_ROOT_FILES:
        path = PROFILES_DIR / name
        if path.is_file():
            fail(errors, f"Forbidden profiles/ root file exists: {path}")

    if (PROFILES_DIR / "provider-assumptions").exists():
        fail(errors, "profiles/provider-assumptions/ must not exist")

    if PROVIDER_ASSUMPTIONS_DIR.exists():
        fail(errors, "data/generated/provider-assumptions/ must not exist for C10.2 contract")

    model_pages = {
        path.stem
        for path in PROFILES_DIR.glob("*.json")
        if path.name
        not in {"c10-index.json", "manifest.json", "lanes.json", "_lane-matrix-audit.json"}
    }

    model_dirs = {
        path.name
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in FORBIDDEN_PROFILE_DIRS
    }

    for child in PROFILES_DIR.iterdir():
        if child.is_dir():
            assert child.name not in FORBIDDEN_PROFILE_DIRS
            continue
        if child.suffix == ".json" and child.name not in ALLOWED_PROFILE_ROOT_FILES:
            continue
        if child.suffix == ".csv" and child.name in {"index.csv", "_lane-matrix-audit.csv"}:
            continue
        if child.name not in ALLOWED_PROFILE_ROOT_FILES:
            fail(errors, f"Unexpected profiles root file: {child}")

    missing_dirs = sorted(model_pages - model_dirs)
    missing_pages = sorted(model_dirs - model_pages)
    if missing_dirs:
        fail(errors, f"Model pages without directories: {missing_dirs[:10]}")
    if missing_pages:
        fail(errors, f"Model directories without pages: {missing_pages[:10]}")

    return model_pages


def validate_c10_manifest(errors: list[str]) -> None:
    manifest_path = PROFILES_DIR / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != "c10.profiles-manifest.v1":
        fail(errors, f"profiles/manifest.json must use c10.profiles-manifest.v1: {manifest_path}")
    paths = manifest.get("paths") or {}
    stale_keys = ("families", "models", "deployment_classes", "provider_assumptions")
    for key in stale_keys:
        if key in paths:
            fail(errors, f"Stale legacy path in profiles/manifest.json: {key}")


def validate_install_lane_contract(lanes: list[dict[str, str]], errors: list[str]) -> dict[str, int]:
    stats = {
        "install_lanes": 0,
        "install_payload_files": 0,
        "install_readmes": 0,
        "shell_checked": 0,
    }
    if len(lanes) != c10_lanes.REQUIRED_INSTALL_LANE_COUNT:
        fail(errors, f"Canonical lane count is {len(lanes)}, expected 10")
        return stats

    for lane in lanes:
        lane_dir = c10_lanes.install_lane_dir(lane)
        if not lane_dir.is_dir():
            fail(errors, f"Missing install lane directory: {lane_dir}")
            continue
        stats["install_lanes"] += 1
        readme = lane_dir / "README.md"
        if not readme.is_file() or readme.stat().st_size == 0:
            fail(errors, f"Install lane missing non-empty README.md: {lane_dir}")
        else:
            stats["install_readmes"] += 1

        roles = c10_lanes.payload_roles_for_runtime(lane["runtime_type"])
        for _role, rel in roles:
            path = lane_dir / rel
            if not path.is_file() or path.stat().st_size == 0:
                fail(errors, f"Install lane missing payload {rel}: {lane_dir}")
            else:
                stats["install_payload_files"] += 1
            if rel.endswith(".sh"):
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                stats["shell_checked"] += 1
                if result.returncode != 0:
                    fail(errors, f"bash -n failed for {path}: {result.stderr.strip()}")
            if lane["runtime_type"].lower() == "powershell" and rel.endswith(".ps1"):
                text = path.read_text(encoding="utf-8")
                if not text.strip():
                    fail(errors, f"Empty PowerShell payload: {path}")

    if stats["install_payload_files"] != c10_lanes.REQUIRED_INSTALL_PAYLOAD_FILE_COUNT:
        fail(
            errors,
            f"Install payload file count is {stats['install_payload_files']}, expected 50",
        )
    if stats["install_readmes"] != c10_lanes.REQUIRED_INSTALL_README_COUNT:
        fail(errors, f"Install README count is {stats['install_readmes']}, expected 10")
    return stats


def validate_index_csv(lanes: list[dict[str, str]], errors: list[str]) -> int:
    index_path = PROFILES_DIR / "index.csv"
    if not index_path.is_file():
        fail(errors, "Missing profiles/index.csv")
        return 0
    lane_ids = {lane["lane_id"] for lane in lanes}
    seen: set[tuple[str, str, str]] = set()
    row_count = 0
    with index_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            key = (row.get("model_slug", ""), row.get("size_slug", ""), row.get("lane_id", ""))
            if key in seen:
                fail(errors, f"Duplicate index.csv row: {key}")
            seen.add(key)
            if row.get("lane_id") not in lane_ids:
                fail(errors, f"index.csv references unknown lane_id: {row.get('lane_id')}")
            size_path = REPO_ROOT / row.get("size_json_path", "")
            if not size_path.is_file():
                fail(errors, f"index.csv points to missing size file: {row.get('size_json_path')}")
            lane_json = REPO_ROOT / row.get("lane_json_path", "")
            if not lane_json.is_file():
                fail(errors, f"index.csv points to missing lane.json: {row.get('lane_json_path')}")
    return row_count


def validate(errors: list[str]) -> dict:
    stats = {
        "model_pages": 0,
        "sizes": 0,
        "install_lanes": 0,
        "profile_leaves": 0,
        "shell_checked": 0,
        "index_rows": 0,
        "profile_matrix_rows": 0,
    }

    lanes = load_canonical_lanes(errors)
    validate_registered_agents_csvs(errors)
    validate_profiles_namespace(errors)
    validate_c10_manifest(errors)
    install_stats = validate_install_lane_contract(lanes, errors)
    stats.update(install_stats)

    audit_path = PROFILES_DIR / "_lane-matrix-audit.json"
    if not audit_path.is_file():
        fail(errors, "Missing profiles/_lane-matrix-audit.json")

    model_pages_paths = sorted(
        p for p in PROFILES_DIR.glob("*.json") if p.stem not in {"c10-index", "manifest", "lanes", "_lane-matrix-audit"}
    )
    stats["model_pages"] = len(model_pages_paths)
    if not model_pages_paths:
        fail(errors, "No profiles/<model-slug>.json model pages found")

    stats["profile_matrix_rows"] = validate_index_csv(lanes, errors)
    stats["index_rows"] = stats["profile_matrix_rows"]

    lane_paths = [lane["profile_path"].rstrip("/") for lane in lanes]

    for page_path in model_pages_paths:
        slug = page_path.stem
        if C10_NAME_RE.search(slug):
            fail(errors, f"Model slug contains C10 label: {slug}")
        page = load_json(page_path)
        sizes = page.get("sizes", [])
        if not sizes:
            fail(errors, f"Model page has no sizes: {page_path}")
        stats["sizes"] += len(sizes)

        sizes_dir = PROFILES_DIR / slug / "sizes"
        for size in sizes:
            size_json = sizes_dir / f"{size['size_slug']}.json"
            if not size_json.is_file():
                fail(errors, f"Missing size JSON: {size_json}")
            size_dir = PROFILES_DIR / slug / size.get("size_slug", "MISSING")
            if is_size_directory(size_dir, slug):
                fail(errors, f"Size directory must not exist: {size_dir}")

        for lane_path in lane_paths:
            leaf = PROFILES_DIR / slug / lane_path
            if not leaf.is_dir():
                fail(errors, f"Missing profile leaf: {leaf}")
                continue
            stats["profile_leaves"] += 1
            if not (leaf / "profile-sizes.csv").is_file():
                fail(errors, f"Missing profile-sizes.csv: {leaf}")
            for stage_file in ("lane.json", *STAGE_FILES):
                path = leaf / stage_file
                if not path.is_file():
                    fail(errors, f"Missing stage file: {path}")
                    continue
                payload = load_json(path)
                if stage_file == "lane.json":
                    validate_lane_fit_semantics(payload, path, errors)
                    install_path = payload.get("install_path", "")
                    expected = next(
                        (lane["install_path"] for lane in lanes if lane["profile_path"].rstrip("/") == lane_path),
                        "",
                    )
                    if install_path and expected and install_path != expected:
                        fail(errors, f"lane.json install_path mismatch at {path}")
                if stage_file == "4-ram.json":
                    validate_ram_fit_semantics(payload, path, errors)
                if "applicable" in payload and payload["applicable"] is False and not payload.get("reason"):
                    fail(errors, f"Non-applicable stage missing reason: {path}")

    index_path = PROFILES_DIR / "c10-index.json"
    if index_path.exists():
        for row in load_json(index_path).get("rows", []):
            rel = row.get("lane_dir")
            if rel and not (REPO_ROOT / rel).exists():
                fail(errors, f"c10-index points to missing lane_dir: {rel}")

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

#!/usr/bin/env python3
"""Validate C10 AGENTS-generated /profiles/ output."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "AGENTS"
PROFILES_DIR = REPO_ROOT / "profiles"

INVENTORY_JSON = PROFILES_DIR / "_agent-input-inventory.json"
NORMALIZED_JSONL = PROFILES_DIR / "_agent-normalized-records.jsonl"
MANIFEST_JSON = PROFILES_DIR / "manifest.json"
INDEX_CSV = PROFILES_DIR / "index.csv"
LANES_JSON = PROFILES_DIR / "lanes.json"
REPORT_JSON = PROFILES_DIR / "_agent-generation-report.json"

PLATFORM_LANES = (
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
)

STEP_FILES_SHELL = ("3.sh", "4.sh", "5.sh", "6.sh", "7.sh")
STEP_FILES_WINDOWS = ("3.ps1", "4.ps1", "5.ps1", "6.ps1", "7.ps1")

NON_MODEL_DIRS = frozenset(
    {
        "families",
        "models",
        "deployment-classes",
        "provider-assumptions",
    }
)


class ValidationError(Exception):
    pass


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate(errors: list[str]) -> None:
    if not AGENTS_DIR.is_dir():
        fail(errors, f"Missing AGENTS directory: {AGENTS_DIR}")
    if not PROFILES_DIR.is_dir():
        fail(errors, f"Missing profiles directory: {PROFILES_DIR}")
    for required in (INVENTORY_JSON, NORMALIZED_JSONL, MANIFEST_JSON, INDEX_CSV, LANES_JSON, REPORT_JSON):
        if not required.is_file():
            fail(errors, f"Missing required profiles artifact: {required.relative_to(REPO_ROOT)}")

    if INVENTORY_JSON.is_file():
        inventory = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
        if not inventory.get("files"):
            fail(errors, "AGENTS inventory is empty")

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.is_file() else {}
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8")) if REPORT_JSON.is_file() else {}
    expected_models = manifest.get("counts", {}).get("models")
    expected_matrix = manifest.get("counts", {}).get("matrix_rows")

    model_dirs = sorted(
        path
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in NON_MODEL_DIRS and not path.name.startswith("_")
    )
    if expected_models is not None and len(model_dirs) != expected_models:
        fail(
            errors,
            f"Model folder count mismatch: expected {expected_models}, found {len(model_dirs)}",
        )

    index_rows = list(csv.DictReader(INDEX_CSV.open(encoding="utf-8")))
    if expected_matrix is not None and len(index_rows) != expected_matrix:
        fail(
            errors,
            f"Matrix row count mismatch: expected {expected_matrix}, found {len(index_rows)}",
        )

    for model_dir in model_dirs:
        sizes_dir = model_dir / "sizes"
        if not (model_dir / "model.json").is_file():
            fail(errors, f"Missing model.json: {model_dir.relative_to(REPO_ROOT)}")
        if not (model_dir / "sizes.csv").is_file():
            fail(errors, f"Missing sizes.csv: {model_dir.relative_to(REPO_ROOT)}")
        if not sizes_dir.is_dir():
            fail(errors, f"Missing sizes directory: {sizes_dir.relative_to(REPO_ROOT)}")

        for child in sizes_dir.iterdir():
            if child.is_dir():
                fail(errors, f"Size slug created as directory: {child.relative_to(REPO_ROOT)}")

        size_files = {p.stem for p in sizes_dir.glob("*.json")}
        for lane in PLATFORM_LANES:
            lane_dir = model_dir / lane
            if not lane_dir.is_dir():
                fail(errors, f"Missing profile lane: {lane_dir.relative_to(REPO_ROOT)}")
                continue
            step_files = STEP_FILES_WINDOWS if lane.startswith("windows/") else STEP_FILES_SHELL
            for step in step_files:
                if not (lane_dir / step).is_file():
                    fail(errors, f"Missing lane step payload: {lane_dir.relative_to(REPO_ROOT)}/{step}")
            if not (lane_dir / "lane.json").is_file():
                fail(errors, f"Missing lane.json: {lane_dir.relative_to(REPO_ROOT)}")
            profile_sizes = lane_dir / "profile-sizes.csv"
            if not profile_sizes.is_file():
                fail(errors, f"Missing profile-sizes.csv: {profile_sizes.relative_to(REPO_ROOT)}")
            with profile_sizes.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    size_slug = row.get("size_slug", "")
                    size_file = row.get("size_file", "")
                    if size_slug and size_slug not in size_files:
                        fail(
                            errors,
                            f"profile-sizes.csv references missing size JSON: "
                            f"{model_dir.relative_to(REPO_ROOT)}/sizes/{size_slug}.json",
                        )
                    if not row.get("fit_status"):
                        fail(errors, f"Missing fit_status in {profile_sizes.relative_to(REPO_ROOT)}")
                    if size_file and not (model_dir / size_file.replace("../", "")).is_file():
                        fail(
                            errors,
                            f"profile-sizes.csv size_file missing: {lane_dir.relative_to(REPO_ROOT)}/{size_file}",
                        )

    for row in index_rows:
        for field in ("source_kind", "source_path", "source_locator", "fit_status"):
            if not row.get(field):
                fail(errors, f"Index row missing {field}: {row.get('model_slug')} {row.get('size_slug')} {row.get('target_lane')}")
        size_file = row.get("size_file", "")
        if size_file and not (REPO_ROOT / size_file).is_file():
            fail(errors, f"index.csv references missing file: {size_file}")

    if report and report.get("matrix row count") != len(index_rows):
        fail(
            errors,
            "Report matrix row count does not match index.csv",
        )

    if (PROFILES_DIR / "linux").exists():
        fail(errors, "Forbidden profiles/linux/ directory exists")


def main() -> int:
    errors: list[str] = []
    try:
        validate(errors)
    except ValidationError as exc:
        errors.append(str(exc))
    if errors:
        print("Profile validation failed:", file=sys.stderr)
        for error in errors[:50]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1
    print("Profile validation passed.")
    print(f"  models: {json.loads(MANIFEST_JSON.read_text())['counts']['models']}")
    print(f"  matrix rows: {len(list(csv.DictReader(INDEX_CSV.open(encoding='utf-8'))))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

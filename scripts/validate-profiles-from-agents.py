#!/usr/bin/env python3
"""Validate canonical C10.3 AGENTS-generated /profiles/ output."""

from __future__ import annotations

import csv
import json
import re
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
REPORT_JSON = PROFILES_DIR / "generated" / "profile-generation-report.json"

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

CANONICAL_STEP_FILES = (
    "3-cpu.json",
    "4-ram.json",
    "5-hard-disk.json",
    "6-cpu-only.json",
    "7-gpu-vram.json",
)

FORBIDDEN_LEGACY_ROOT_FILES = (
    "c10-index.json",
)

FORBIDDEN_LEGACY_ROOT_DIRS = (
    "models",
    "families",
    "deployment-classes",
)

NON_MODEL_DIRS = frozenset(
    {
        *FORBIDDEN_LEGACY_ROOT_DIRS,
        "legacy",
        "generated",
        "provider-assumptions",
        "provider-compatibility",
    }
)

CURSOR_PROMPT_MARKERS = ("cursorfile", "cursorc", "roadmap", "prompt")

FIT_WITH_EVIDENCE = frozenset({"fit"})


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def validate_inventory(errors: list[str]) -> dict:
    if not INVENTORY_JSON.is_file():
        fail(errors, f"Missing AGENTS inventory: {display_path(INVENTORY_JSON)}")
        return {}
    try:
        inventory = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"Malformed AGENTS inventory JSON: {exc}")
        return {}
    if not inventory.get("files"):
        fail(errors, "AGENTS inventory is empty")
    for row in inventory.get("files", []):
        source_path = row.get("source_path", "")
        if any(marker in Path(source_path).name.lower() for marker in CURSOR_PROMPT_MARKERS):
            if row.get("parse_status") not in {"skipped_cursor_prompt", "skipped", "skipped_markdown"}:
                fail(errors, f"Cursor prompt file parsed as model data: {source_path}")
    return inventory


def validate_legacy_labeling(errors: list[str]) -> None:
    for dirname in FORBIDDEN_LEGACY_ROOT_DIRS:
        path = PROFILES_DIR / dirname
        if path.exists():
            fail(errors, f"Unlabeled legacy directory at profiles root: profiles/{dirname}")
    for filename in FORBIDDEN_LEGACY_ROOT_FILES:
        path = PROFILES_DIR / filename
        if path.is_file():
            fail(errors, f"Unlabeled legacy file at profiles root: profiles/{filename}")
    for child in PROFILES_DIR.iterdir():
        if child.is_file() and child.suffix == ".json" and child.name not in {
            "manifest.json",
            "lanes.json",
            "_agent-input-inventory.json",
        }:
            if not child.name.startswith("_"):
                fail(errors, f"Unlabeled legacy flat model page at profiles root: profiles/{child.name}")


def validate_manifest_counts(errors: list[str], manifest: dict, model_dirs: list[Path], index_rows: list[dict]) -> None:
    counts = manifest.get("counts", {})
    expected_models = counts.get("models")
    expected_matrix = counts.get("matrix_rows")
    if expected_models is not None and len(model_dirs) != expected_models:
        fail(errors, f"Model folder count mismatch: expected {expected_models}, found {len(model_dirs)}")
    if expected_matrix is not None and len(index_rows) != expected_matrix:
        fail(errors, f"Matrix row count mismatch: expected {expected_matrix}, found {len(index_rows)}")
    if REPORT_JSON.is_file():
        report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        if report.get("matrix_row_count") != len(index_rows):
            fail(errors, "Generation report matrix_row_count does not match index.csv")


def validate_fit_semantics(errors: list[str], row: dict) -> None:
    fit_status = row.get("fit_status", "")
    if fit_status in FIT_WITH_EVIDENCE:
        if not row.get("source_kind") or not row.get("source_path") or not row.get("source_locator"):
            fail(
                errors,
                f"fit asserted without provenance: {row.get('model_slug')} {row.get('size_slug')} {row.get('target_lane')}",
            )


def validate_numeric_fields(errors: list[str], row: dict) -> None:
    for field in (
        "minimum_ram_gb",
        "recommended_ram_gb",
        "minimum_vram_gb",
        "recommended_vram_gb",
        "minimum_disk_free_gb",
    ):
        value = row.get(field, "")
        if value == "":
            continue
        if not re.fullmatch(r"-?\d+(\.\d+)?", str(value)):
            fail(errors, f"Non-numeric {field} in index row: {row.get('model_slug')} {value}")


def validate(errors: list[str]) -> None:
    if not AGENTS_DIR.is_dir():
        fail(errors, f"Missing AGENTS directory: {AGENTS_DIR}")
    if not PROFILES_DIR.is_dir():
        fail(errors, f"Missing profiles directory: {PROFILES_DIR}")

    for required in (INVENTORY_JSON, NORMALIZED_JSONL, MANIFEST_JSON, INDEX_CSV, LANES_JSON, REPORT_JSON):
        if not required.is_file():
            fail(errors, f"Missing required profiles artifact: {display_path(required)}")

    validate_inventory(errors)
    validate_legacy_labeling(errors)

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.is_file() else {}
    lanes_payload = json.loads(LANES_JSON.read_text(encoding="utf-8")) if LANES_JSON.is_file() else {}
    lane_paths = lanes_payload.get("profile_lanes") or [lane.get("lane_path") for lane in lanes_payload.get("lanes", [])]
    if list(lane_paths) != list(PLATFORM_LANES):
        fail(errors, "lanes.json does not define exactly the ten canonical lanes")

    model_dirs = sorted(
        path
        for path in PROFILES_DIR.iterdir()
        if path.is_dir() and path.name not in NON_MODEL_DIRS and not path.name.startswith("_")
    )
    index_rows = list(csv.DictReader(INDEX_CSV.open(encoding="utf-8")))
    validate_manifest_counts(errors, manifest, model_dirs, index_rows)

    for model_dir in model_dirs:
        if not (model_dir / "model.json").is_file():
            fail(errors, f"Missing model.json: {display_path(model_dir)}")
        if not (model_dir / "sizes.csv").is_file():
            fail(errors, f"Missing sizes.csv: {display_path(model_dir)}")
        sizes_dir = model_dir / "sizes"
        if not sizes_dir.is_dir():
            fail(errors, f"Missing sizes directory: {display_path(sizes_dir)}")
            continue

        for child in sizes_dir.iterdir():
            if child.is_dir():
                fail(errors, f"Size slug created as directory: {display_path(child)}")

        size_files = {p.stem for p in sizes_dir.glob("*.json")}
        for size_slug in size_files:
            size_as_dir = model_dir / size_slug
            if size_as_dir.is_dir() and (
                (size_as_dir / "model.json").is_file() or (size_as_dir / "sizes").is_dir()
            ):
                fail(errors, f"Model-size embedded in model folder slug: {model_dir.name}/{size_slug}/")

        for lane in PLATFORM_LANES:
            lane_dir = model_dir / lane
            if not lane_dir.is_dir():
                fail(errors, f"Missing profile lane: {display_path(lane_dir)}")
                continue
            for step in CANONICAL_STEP_FILES:
                if not (lane_dir / step).is_file():
                    fail(errors, f"Missing lane step payload: {display_path(lane_dir)}/{step}")
            if not (lane_dir / "lane.json").is_file():
                fail(errors, f"Missing lane.json: {display_path(lane_dir)}")
            profile_sizes = lane_dir / "profile-sizes.csv"
            if not profile_sizes.is_file():
                fail(errors, f"Missing profile-sizes.csv: {display_path(profile_sizes)}")
            with profile_sizes.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    size_slug = row.get("size_slug", "")
                    size_file = row.get("size_file", "")
                    if size_slug and size_slug not in size_files:
                        fail(
                            errors,
                            f"profile-sizes.csv references missing size JSON: "
                            f"{display_path(model_dir)}/sizes/{size_slug}.json",
                        )
                    if not row.get("fit_status"):
                        fail(errors, f"Missing fit_status in {display_path(profile_sizes)}")
                    if size_file:
                        resolved = model_dir / size_file.replace("../", "")
                        if not resolved.is_file():
                            fail(
                                errors,
                                f"profile-sizes.csv size_file missing: {display_path(lane_dir)}/{size_file}",
                            )

    for row in index_rows:
        for field in ("source_kind", "source_path", "source_locator", "fit_status"):
            if not row.get(field):
                fail(
                    errors,
                    f"Index row missing {field}: {row.get('model_slug')} {row.get('size_slug')} {row.get('target_lane')}",
                )
        size_file = row.get("size_file", "")
        if size_file and not (REPO_ROOT / size_file).is_file():
            fail(errors, f"index.csv references missing file: {size_file}")
        validate_fit_semantics(errors, row)
        validate_numeric_fields(errors, row)

    if (PROFILES_DIR / "linux").exists():
        fail(errors, "Forbidden profiles/linux/ directory exists")


def main() -> int:
    errors: list[str] = []
    validate(errors)
    if errors:
        print("Profile validation failed:", file=sys.stderr)
        for error in errors[:50]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    index_count = len(list(csv.DictReader(INDEX_CSV.open(encoding="utf-8"))))
    print("Profile validation passed.")
    print(f"  models: {manifest['counts']['models']}")
    print(f"  matrix rows: {index_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline validator for P4 workload profiles using only the Python standard library."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCHEMA_PATH = ROOT / "schemas" / "workload-profile.schema.json"
INDEX_PATH = DATA_DIR / "workloads.json"
ALLOWED_CAPABILITIES = {"text", "coding", "embedding", "vision", "tools", "thinking", "audio"}
ALLOWED_STATUS = {"internal-guidance", "specialist-guidance"}
ALLOWED_COMPUTE = {"cpu", "cpu-or-gpu", "gpu-preferred", "gpu-required"}
DEFERRED_TO = "P5-Compatibility-Estimator"
REQUIRED_TOP_LEVEL = {
    "schema_version", "profile_version", "workload_id", "display_name", "description",
    "planning_status", "expected_users", "expected_concurrency", "required_capabilities",
    "optional_capabilities", "compute", "resources", "model_guidance",
    "service_requirements", "latency_expectation", "priority", "limitations", "notes",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_profile(path: Path, profile: dict, errors: list[str]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(profile)
    extra = set(profile) - REQUIRED_TOP_LEVEL
    if missing:
        fail(errors, f"{path.name}: missing fields {sorted(missing)}")
    if extra:
        fail(errors, f"{path.name}: unexpected fields {sorted(extra)}")
    if profile.get("schema_version") != "1.0":
        fail(errors, f"{path.name}: schema_version must be 1.0")
    if not re.match(r"^P4\.\d+\.\d+$", str(profile.get("profile_version", ""))):
        fail(errors, f"{path.name}: invalid profile_version")
    workload_id = profile.get("workload_id")
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", str(workload_id)):
        fail(errors, f"{path.name}: invalid workload_id")
    if path.stem != workload_id:
        fail(errors, f"{path.name}: filename must match workload_id")
    if profile.get("planning_status") not in ALLOWED_STATUS:
        fail(errors, f"{path.name}: invalid planning_status")

    required_caps = profile.get("required_capabilities", [])
    optional_caps = profile.get("optional_capabilities", [])
    for field, caps in (("required_capabilities", required_caps), ("optional_capabilities", optional_caps)):
        if not isinstance(caps, list) or not all(isinstance(cap, str) for cap in caps):
            fail(errors, f"{path.name}: {field} must be a string array")
            continue
        if len(caps) != len(set(caps)):
            fail(errors, f"{path.name}: {field} contains duplicates")
        unknown = set(caps) - ALLOWED_CAPABILITIES
        if unknown:
            fail(errors, f"{path.name}: {field} has unknown capabilities {sorted(unknown)}")
    overlap = set(required_caps) & set(optional_caps)
    if overlap:
        fail(errors, f"{path.name}: required and optional capabilities overlap {sorted(overlap)}")

    users = profile.get("expected_users", {})
    if not (users.get("minimum", -1) <= users.get("typical", -1) <= users.get("maximum", -1)):
        fail(errors, f"{path.name}: expected_users must be minimum <= typical <= maximum")
    concurrency = profile.get("expected_concurrency", {})
    if not (concurrency.get("typical", -1) <= concurrency.get("peak", -1)):
        fail(errors, f"{path.name}: expected_concurrency must be typical <= peak")

    compute = profile.get("compute", {})
    if compute.get("preferred_compute") not in ALLOWED_COMPUTE:
        fail(errors, f"{path.name}: invalid preferred_compute")
    for key in ("cpu_supported", "gpu_optional", "gpu_recommended"):
        if not isinstance(compute.get(key), bool):
            fail(errors, f"{path.name}: compute.{key} must be boolean")

    resources = profile.get("resources", {})
    for key in ("minimum_ram_gb", "recommended_ram_gb", "minimum_vcpu", "recommended_vcpu", "base_disk_gb", "customer_data_reserve_gb"):
        value = resources.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            fail(errors, f"{path.name}: resources.{key} must be a nonnegative number")
    if resources.get("minimum_ram_gb", 0) > resources.get("recommended_ram_gb", 0):
        fail(errors, f"{path.name}: minimum RAM exceeds recommended RAM")
    if resources.get("minimum_vcpu", 0) > resources.get("recommended_vcpu", 0):
        fail(errors, f"{path.name}: minimum vCPU exceeds recommended vCPU")

    guidance = profile.get("model_guidance", {})
    if guidance.get("exact_model_selection_deferred_to") != DEFERRED_TO:
        fail(errors, f"{path.name}: exact model selection must be deferred to {DEFERRED_TO}")
    if any(":" in str(value) for value in guidance.get("recommended_model_classes", [])):
        fail(errors, f"{path.name}: model classes must not contain exact Ollama tags")

    forbidden_fragments = ("price", "pricing", "provider_plan", "plan_id", "installer", "passport", "checkout", "ordering", "fulfillment")
    serialized = json.dumps(profile, sort_keys=True).lower()
    for fragment in forbidden_fragments:
        if fragment in serialized:
            fail(errors, f"{path.name}: forbidden fragment present: {fragment}")


def main() -> int:
    errors: list[str] = []
    if not SCHEMA_PATH.exists():
        fail(errors, "schema file is missing")
    else:
        load_json(SCHEMA_PATH)

    profile_paths = sorted(path for path in DATA_DIR.glob("*.json") if path.name != "workloads.json")
    profiles = []
    ids = []
    for path in profile_paths:
        profile = load_json(path)
        validate_profile(path, profile, errors)
        profiles.append((path, profile))
        ids.append(profile.get("workload_id"))

    if len(ids) != len(set(ids)):
        fail(errors, "workload IDs must be unique")

    index = load_json(INDEX_PATH)
    indexed = index.get("workloads", [])
    index_ids = [entry.get("workload_id") for entry in indexed]
    if len(index_ids) != len(set(index_ids)):
        fail(errors, "workloads.json contains duplicate workload IDs")
    profile_ids = {profile.get("workload_id") for _, profile in profiles}
    if set(index_ids) != profile_ids:
        fail(errors, "workloads.json must include every individual workload exactly once")
    for entry in indexed:
        rel = entry.get("path")
        if not rel or not (DATA_DIR / rel).exists():
            fail(errors, f"workloads.json references missing file: {rel}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(profiles)} P4 workload profiles and {len(indexed)} index entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

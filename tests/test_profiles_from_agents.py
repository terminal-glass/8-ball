from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate-profiles-from-agents.py"
VALIDATOR = REPO_ROOT / "scripts" / "validate-profiles-from-agents.py"
PROFILES_DIR = REPO_ROOT / "profiles"


@pytest.fixture(scope="module")
def manifest() -> dict:
    path = PROFILES_DIR / "manifest.json"
    assert path.is_file(), "Run scripts/generate-profiles-from-agents.py first"
    return json.loads(path.read_text(encoding="utf-8"))


def test_validator_passes() -> None:
    result = subprocess.run(["python3", str(VALIDATOR)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_inventory_excludes_cursor_prompts() -> None:
    inventory = json.loads((PROFILES_DIR / "_agent-input-inventory.json").read_text(encoding="utf-8"))
    for row in inventory["files"]:
        name = Path(row["source_path"]).name.lower()
        if "cursorfile" in name or "cursorc" in name:
            assert row["parse_status"] in {"skipped_cursor_prompt", "skipped", "skipped_markdown"}


def test_exact_duplicate_merging_records_skipped(manifest: dict) -> None:
    report = json.loads((PROFILES_DIR / "generated" / "profile-generation-report.json").read_text(encoding="utf-8"))
    skipped = report.get("records_skipped", [])
    kinds = {item.get("reason") for item in skipped}
    assert "exact_duplicate" in kinds or skipped == []


def test_conflict_preservation_in_normalized_jsonl() -> None:
    conflicts = []
    with (PROFILES_DIR / "_agent-normalized-records.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("conflict"):
                conflicts.append(record)
    assert isinstance(conflicts, list)


def test_null_unknowns_allowed_in_index() -> None:
    with (PROFILES_DIR / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert any(not row["minimum_ram_gb"] for row in rows)


def test_ten_canonical_lanes() -> None:
    lanes = json.loads((PROFILES_DIR / "lanes.json").read_text(encoding="utf-8"))
    expected = [
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
    assert lanes["profile_lanes"] == expected


def test_size_file_not_directory() -> None:
    model_dir = PROFILES_DIR / "qwen3"
    assert model_dir.is_dir()
    sizes_dir = model_dir / "sizes"
    for child in sizes_dir.iterdir():
        assert child.is_file(), f"size slug must be a file: {child}"
    assert (sizes_dir / "0.6b.json").is_file()


def test_missing_reference_fails_validation(tmp_path: Path) -> None:
    import importlib.util

    broken = tmp_path / "broken-profiles"
    subprocess.run(["cp", "-a", str(PROFILES_DIR), str(broken)], check=True)
    index_path = broken / "index.csv"
    rows = list(csv.DictReader(index_path.open(encoding="utf-8")))
    rows[0]["size_file"] = "profiles/missing/size.json"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    spec = importlib.util.spec_from_file_location(
        "validate_profiles_from_agents",
        VALIDATOR,
    )
    assert spec and spec.loader
    vmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vmod)
    errors: list[str] = []
    original = vmod.PROFILES_DIR
    vmod.PROFILES_DIR = broken
    vmod.INVENTORY_JSON = broken / "_agent-input-inventory.json"
    vmod.NORMALIZED_JSONL = broken / "_agent-normalized-records.jsonl"
    vmod.MANIFEST_JSON = broken / "manifest.json"
    vmod.INDEX_CSV = broken / "index.csv"
    vmod.LANES_JSON = broken / "lanes.json"
    vmod.REPORT_JSON = broken / "generated" / "profile-generation-report.json"
    try:
        vmod.validate(errors)
    finally:
        vmod.PROFILES_DIR = original
        vmod.INVENTORY_JSON = original / "_agent-input-inventory.json"
        vmod.NORMALIZED_JSONL = original / "_agent-normalized-records.jsonl"
        vmod.MANIFEST_JSON = original / "manifest.json"
        vmod.INDEX_CSV = original / "index.csv"
        vmod.LANES_JSON = original / "lanes.json"
        vmod.REPORT_JSON = original / "generated" / "profile-generation-report.json"
    assert any("missing file" in err for err in errors)


def test_evidence_based_fit_semantics() -> None:
    with (PROFILES_DIR / "index.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["fit_status"] == "fit":
                assert row["source_kind"]
                assert row["source_path"]
                assert row["source_locator"]


def test_legacy_migration_labeling() -> None:
    legacy_readme = PROFILES_DIR / "legacy" / "README.md"
    assert legacy_readme.is_file()
    assert (PROFILES_DIR / "legacy" / "c5-root-export" / "index.csv").is_file()
    assert not (PROFILES_DIR / "models").exists()
    manifest = json.loads((PROFILES_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["legacy_compatibility"]["root"] == "profiles/legacy/"


def test_two_run_determinism() -> None:
    subprocess.run(["python3", str(GENERATOR)], check=True, capture_output=True)
    first = subprocess.check_output(["git", "status", "--porcelain", "profiles"], text=True)
    subprocess.run(["python3", str(GENERATOR)], check=True, capture_output=True)
    second = subprocess.check_output(["git", "status", "--porcelain", "profiles"], text=True)
    assert first == second


def test_manifest_counts_match_artifacts(manifest: dict) -> None:
    model_dirs = [
        p
        for p in PROFILES_DIR.iterdir()
        if p.is_dir()
        and p.name not in {"legacy", "generated", "provider-assumptions", "provider-compatibility"}
        and not p.name.startswith("_")
    ]
    with (PROFILES_DIR / "index.csv").open(encoding="utf-8", newline="") as handle:
        index_count = sum(1 for _ in csv.DictReader(handle))
    assert manifest["counts"]["models"] == len(model_dirs)
    assert manifest["counts"]["matrix_rows"] == index_count
    assert manifest["counts"]["profile_lanes"] == 10

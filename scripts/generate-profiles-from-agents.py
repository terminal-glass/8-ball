#!/usr/bin/env python3
"""C10: Generate root /profiles/ from AGENTS/ data (glass ball)."""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "AGENTS"
PROFILES_DIR = REPO_ROOT / "profiles"
REPORT_PATH = PROFILES_DIR / "_agent-generation-report.json"

P4_MODELS_PATH = AGENTS_DIR / "data-science" / "P4-Public-Catalog" / "index" / "models.json"
P3_SELECTION_PATH = AGENTS_DIR / "data-science" / "P3-Ollama-Metadata-Catalog" / "indexes" / "model-selection.json"
MANIFEST_PATH = REPO_ROOT / "data/generated/pages/install-manifest.json"

PLATFORM_LANES: tuple[str, ...] = (
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

INSTALL_PATH_BY_LANE: dict[str, str] = {
    "ubuntu/cpu": "install/ubuntu",
    "ubuntu/cuda": "install/ubuntu",
    "mac/apple-silicon": "install/mac",
    "mac/intel": "install/mac",
    "windows/cpu": "install/windows",
    "windows/cuda": "install/windows",
    "cloud/digitalocean/cpu-droplet": "install/cloud/digitalocean-droplet",
    "cloud/digitalocean/gpu-droplet": "install/cloud/digitalocean-droplet",
    "cloud/aws-lightsail/cpu": "install/cloud/aws-lightsail",
    "cloud/aws-lightsail/gpu": "install/cloud/aws-lightsail",
}

LANE_HARDWARE_PROFILES: dict[str, list[str]] = {
    "ubuntu/cpu": ["cpu-small", "desktop-standard"],
    "ubuntu/cuda": ["gpu-entry", "gpu-midrange", "gpu-high-mem", "multi-gpu"],
    "mac/apple-silicon": ["desktop-standard", "cpu-small"],
    "mac/intel": ["cpu-small", "desktop-standard"],
    "windows/cpu": ["cpu-small", "desktop-standard"],
    "windows/cuda": ["gpu-entry", "gpu-midrange"],
    "cloud/digitalocean/cpu-droplet": ["cpu-small", "server-high-mem", "desktop-standard"],
    "cloud/digitalocean/gpu-droplet": ["gpu-entry", "gpu-midrange", "gpu-high-mem"],
    "cloud/aws-lightsail/cpu": ["cpu-small", "server-high-mem"],
    "cloud/aws-lightsail/gpu": ["gpu-entry", "gpu-midrange"],
}

STEP_FILES_SHELL = ("3.sh", "4.sh", "5.sh", "6.sh", "7.sh")
STEP_FILES_WINDOWS = ("3.ps1", "4.ps1", "5.ps1", "6.ps1", "7.ps1")

DEPLOYMENT_STEP_NAMES = {
    "3": "Deployment Lane",
    "4": "Hard Disk Gate",
    "5": "RAM Gate",
    "6": "CPU Gate",
    "7": "GPU Gate",
}

CURSOR_PROMPT_MARKERS = ("cursorfile", "cursorc", "roadmap", "prompt")

PRESERVED_PROFILE_FILES = frozenset({"environment.profile.example.env"})

NORMALIZED_FIELDS = (
    "model_id",
    "model_slug",
    "size_slug",
    "ollama_ref",
    "parameter_size",
    "quantization",
    "minimum_ram_gb",
    "recommended_ram_gb",
    "minimum_vram_gb",
    "recommended_vram_gb",
    "minimum_disk_free_gb",
    "target_lane",
    "fit_status",
    "source_kind",
    "source_path",
    "source_locator",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def filesystem_slug(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[/:]+", "-", slug)
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-") or "unknown"


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


@dataclass
class InventoryRow:
    source_path: str
    source_type: str
    parse_status: str
    row_count: int
    recognized_model_rows: int
    recognized_size_rows: int
    recognized_platform_rows: int
    recognized_hardware_fields: int
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "parse_status": self.parse_status,
            "row_count": self.row_count,
            "recognized_model_rows": self.recognized_model_rows,
            "recognized_size_rows": self.recognized_size_rows,
            "recognized_platform_rows": self.recognized_platform_rows,
            "recognized_hardware_fields": self.recognized_hardware_fields,
            "notes": self.notes,
        }


@dataclass
class NormalizedRecord:
    model_id: str | None = None
    model_slug: str | None = None
    size_slug: str | None = None
    ollama_ref: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    minimum_ram_gb: float | None = None
    recommended_ram_gb: float | None = None
    minimum_vram_gb: float | None = None
    recommended_vram_gb: float | None = None
    minimum_disk_free_gb: float | None = None
    target_lane: str | None = None
    fit_status: str | None = None
    source_kind: str | None = None
    source_path: str | None = None
    source_locator: str | None = None
    conflict: bool = False
    conflict_notes: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in NORMALIZED_FIELDS}
        payload["conflict"] = self.conflict
        if self.conflict_notes:
            payload["conflict_notes"] = self.conflict_notes
        if self.provenance:
            payload["provenance"] = self.provenance
        return payload

    def key(self) -> tuple[str, ...]:
        return (
            self.model_id or "",
            self.size_slug or "",
            self.target_lane or "",
            self.source_kind or "",
            self.source_path or "",
            self.source_locator or "",
        )


@dataclass
class GenerationReport:
    agents_files_inspected: int = 0
    agents_files_parsed: int = 0
    model_count: int = 0
    distinct_model_size_count: int = 0
    install_lane_count: int = 0
    profile_lane_count: int = 0
    matrix_row_count: int = 0
    records_with_unknown_limits: int = 0
    records_with_conflicts: int = 0
    records_skipped: list[dict[str, str]] = field(default_factory=list)


def is_cursor_prompt(path: Path) -> bool:
    name = path.name.lower()
    return any(marker in name for marker in CURSOR_PROMPT_MARKERS)


def inventory_file(path: Path) -> InventoryRow:
    source_path = rel(path)
    suffix = path.suffix.lower()
    notes: list[str] = []
    row_count = 0
    model_rows = 0
    size_rows = 0
    platform_rows = 0
    hardware_fields = 0
    parse_status = "skipped"
    source_type = suffix.lstrip(".") or "unknown"

    if suffix in {".csv", ".json", ".jsonl", ".yaml", ".yml"}:
        try:
            if suffix == ".csv":
                with path.open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                row_count = len(rows)
                headers = {h.lower() for h in (rows[0].keys() if rows else [])}
                if {"model_id", "ollama_name"} & headers or "family_id" in headers:
                    model_rows = row_count
                if "ollama_identifier" in headers or "tag" in headers:
                    size_rows = row_count
                if {"platform_family", "profile_id", "deployment_type_id"} & headers:
                    platform_rows = row_count
                if {"ram_gb", "vram_gb", "minimum_free_disk_gb", "vram_gb_minimum"} & headers:
                    hardware_fields = row_count
                parse_status = "parsed"
            elif suffix == ".jsonl":
                with path.open(encoding="utf-8") as handle:
                    rows = [json.loads(line) for line in handle if line.strip()]
                row_count = len(rows)
                parse_status = "parsed"
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    row_count = len(payload)
                    if payload and isinstance(payload[0], dict):
                        if "deployment_variants" in payload[0]:
                            model_rows = len(payload)
                            size_rows = sum(len(item.get("deployment_variants", [])) for item in payload)
                        elif "id" in payload[0] and "family_id" in payload[0]:
                            model_rows = row_count
                elif isinstance(payload, dict):
                    row_count = 1
                    if "models" in payload:
                        models_val = payload["models"]
                        model_rows = len(models_val) if isinstance(models_val, (list, dict)) else 0
                    profiles_val = payload.get("profiles")
                    if isinstance(profiles_val, dict):
                        platform_rows = len(profiles_val)
                        for profile in profiles_val.values():
                            if isinstance(profile, dict):
                                size_rows += len(profile.get("candidates", []))
                    deployment_types = payload.get("deployment_types")
                    if isinstance(deployment_types, (list, dict)):
                        platform_rows = max(platform_rows, len(deployment_types))
                parse_status = "parsed"
        except (OSError, json.JSONDecodeError, csv.Error, UnicodeDecodeError) as exc:
            parse_status = "error"
            notes.append(str(exc))
    elif suffix == ".md":
        if is_cursor_prompt(path):
            parse_status = "skipped_cursor_prompt"
            notes.append("cursor prompt or roadmap; not parsed as model data")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "|" in text and re.search(r"\bmodel\b|\bollama\b|\bram\b|\bvram\b", text, re.IGNORECASE):
                parse_status = "inspected_markdown"
                notes.append("markdown contains table-like model/hardware content; not row-parsed")
            else:
                parse_status = "skipped_markdown"
                notes.append("markdown without parseable model table rows")
    else:
        parse_status = "skipped"
        notes.append("unsupported extension")

    return InventoryRow(
        source_path=source_path,
        source_type=source_type,
        parse_status=parse_status,
        row_count=row_count,
        recognized_model_rows=model_rows,
        recognized_size_rows=size_rows,
        recognized_platform_rows=platform_rows,
        recognized_hardware_fields=hardware_fields,
        notes="; ".join(notes),
    )


def inventory_agents() -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    for path in sorted(AGENTS_DIR.rglob("*")):
        if not path.is_file():
            continue
        rows.append(inventory_file(path))
    return rows


def load_model_slug_map() -> dict[str, str]:
    if MANIFEST_PATH.is_file():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return {
            model_id: entry.get("model_slug") or filesystem_slug(model_id)
            for model_id, entry in manifest.get("models", {}).items()
        }
    return {}


def load_p3_candidate_index() -> dict[str, dict[str, dict[str, Any]]]:
    """Map ollama_identifier -> hardware_profile_id -> candidate row."""
    if not P3_SELECTION_PATH.is_file():
        return {}
    payload = json.loads(P3_SELECTION_PATH.read_text(encoding="utf-8"))
    index: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for profile_id, profile in payload.get("profiles", {}).items():
        for candidate in profile.get("candidates", []):
            ollama_ref = candidate.get("ollama_identifier")
            if ollama_ref:
                index[ollama_ref][profile_id] = candidate
    return index


def normalize_from_p4(models: list[dict[str, Any]], slug_map: dict[str, str]) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    p3_index = load_p3_candidate_index()

    for model in models:
        model_id = model["id"]
        model_slug = slug_map.get(model_id) or filesystem_slug(model_id)
        for variant_index, variant in enumerate(model.get("deployment_variants", []), start=1):
            tag = variant.get("tag") or variant.get("ollama_identifier", "").split(":", 1)[-1]
            size_slug = filesystem_slug(tag)
            ollama_ref = variant.get("ollama_identifier")
            parameter_size = variant.get("parameter_unit") or (
                str(variant["parameter_count"]) if variant.get("parameter_count") else None
            )
            quantization = variant.get("quantization")
            download_bytes = variant.get("download_size_bytes")
            minimum_disk = None
            disk_provenance = None
            if download_bytes is not None:
                minimum_disk = round(download_bytes / (1024**3), 3)
                disk_provenance = variant.get("provenance", {}).get("download_size_bytes")

            base = NormalizedRecord(
                model_id=model_id,
                model_slug=model_slug,
                size_slug=size_slug,
                ollama_ref=ollama_ref,
                parameter_size=parameter_size,
                quantization=quantization,
                minimum_disk_free_gb=minimum_disk,
                fit_status="agents_catalog_variant",
                source_kind="p4_deployment_variant",
                source_path=rel(P4_MODELS_PATH),
                source_locator=f"model={model_id};variant_index={variant_index};tag={tag}",
                provenance={
                    "download_size_bytes": download_bytes,
                    "download_size_provenance": disk_provenance,
                    "variant_provenance": variant.get("provenance"),
                },
            )

            if ollama_ref and ollama_ref in p3_index:
                candidates = p3_index[ollama_ref]
                ram_values = {
                    c.get("estimated_min_system_ram_gb")
                    for c in candidates.values()
                    if c.get("estimated_min_system_ram_gb") is not None
                }
                rec_ram_values = {
                    c.get("estimated_recommended_system_ram_gb")
                    for c in candidates.values()
                    if c.get("estimated_recommended_system_ram_gb") is not None
                }
                vram_values = {
                    c.get("estimated_min_vram_gb")
                    for c in candidates.values()
                    if c.get("estimated_min_vram_gb") is not None
                }
                if len(ram_values) > 1 or len(rec_ram_values) > 1 or len(vram_values) > 1:
                    base.conflict = True
                    base.conflict_notes.append("conflicting P3 hardware-profile RAM/VRAM estimates")
                if ram_values:
                    base.minimum_ram_gb = min(ram_values)
                if rec_ram_values:
                    base.recommended_ram_gb = min(rec_ram_values)
                if vram_values:
                    base.minimum_vram_gb = min(vram_values)
                    base.recommended_vram_gb = min(vram_values)
                base.provenance["p3_selection_profiles"] = list(candidates.keys())
                base.source_locator += ";p3_profiles=" + ",".join(sorted(candidates))

            records.append(base)

    return records


def build_lane_matrix_records(base_records: list[NormalizedRecord]) -> list[NormalizedRecord]:
    matrix: list[NormalizedRecord] = []
    p3_index = load_p3_candidate_index()
    size_records = [
        r for r in base_records if r.model_slug and r.size_slug and r.source_kind == "p4_deployment_variant"
    ]
    for base in size_records:
        for lane, profile_ids in LANE_HARDWARE_PROFILES.items():
            lane_record = NormalizedRecord(
                model_id=base.model_id,
                model_slug=base.model_slug,
                size_slug=base.size_slug,
                ollama_ref=base.ollama_ref,
                parameter_size=base.parameter_size,
                quantization=base.quantization,
                minimum_ram_gb=base.minimum_ram_gb,
                recommended_ram_gb=base.recommended_ram_gb,
                minimum_vram_gb=base.minimum_vram_gb,
                recommended_vram_gb=base.recommended_vram_gb,
                minimum_disk_free_gb=base.minimum_disk_free_gb,
                target_lane=lane,
                source_kind="p4_deployment_variant_lane_matrix",
                source_path=base.source_path,
                source_locator=f"{base.source_locator};lane={lane}",
                conflict=base.conflict,
                conflict_notes=list(base.conflict_notes),
                provenance=dict(base.provenance),
            )
            ollama_ref = base.ollama_ref
            if ollama_ref and ollama_ref in p3_index:
                matched = [pid for pid in profile_ids if pid in p3_index[ollama_ref]]
                if matched:
                    lane_record.fit_status = "listed_in_agents_selection"
                    lane_record.provenance["matched_hardware_profiles"] = matched
                else:
                    lane_record.fit_status = "not_listed_in_agents_selection"
            else:
                lane_record.fit_status = "not_listed_in_agents_selection"
            matrix.append(lane_record)
    return matrix


def normalize_hardware_csv(path: Path) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.DictReader(handle), start=2):
            profile_id = row.get("profile_id") or row.get("host_profile_id")
            records.append(
                NormalizedRecord(
                    model_id=None,
                    model_slug=None,
                    size_slug=None,
                    ollama_ref=None,
                    parameter_size=None,
                    quantization=None,
                    minimum_ram_gb=_float_or_none(row.get("ram_gb") or row.get("system_ram_gb_minimum")),
                    recommended_ram_gb=_float_or_none(
                        row.get("system_ram_gb_recommended") or row.get("ram_gb")
                    ),
                    minimum_vram_gb=_float_or_none(row.get("vram_gb_minimum") or row.get("vram_gb_per_gpu")),
                    recommended_vram_gb=_float_or_none(row.get("vram_gb_recommended")),
                    minimum_disk_free_gb=_float_or_none(
                        row.get("minimum_free_disk_gb") or row.get("disk_gb_minimum")
                    ),
                    target_lane=row.get("platform_family") or row.get("provider"),
                    fit_status=row.get("provenance_status") or "agents_hardware_row",
                    source_kind="agents_csv_hardware",
                    source_path=rel(path),
                    source_locator=f"row={row_index};profile_id={profile_id}",
                    provenance={"raw_row": row},
                )
            )
    return records


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def dedupe_records(records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], list[dict[str, str]]]:
    seen: dict[tuple[str, ...], NormalizedRecord] = {}
    skipped: list[dict[str, str]] = []
    for record in records:
        key = record.key()
        if key in seen:
            skipped.append({"reason": "exact_duplicate", "key": "|".join(key)})
            continue
        seen[key] = record
    return list(seen.values()), skipped


def write_inventory_outputs(rows: list[InventoryRow]) -> None:
    payload = {
        "schema_version": "profiles.agent-input-inventory.v1",
        "generated_at": utc_now_iso(),
        "agents_root": rel(AGENTS_DIR),
        "file_count": len(rows),
        "files": [row.as_dict() for row in rows],
    }
    write_json(PROFILES_DIR / "_agent-input-inventory.json", payload)
    with (PROFILES_DIR / "_agent-input-inventory.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_path",
                "source_type",
                "parse_status",
                "row_count",
                "recognized_model_rows",
                "recognized_size_rows",
                "recognized_platform_rows",
                "recognized_hardware_fields",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def write_normalized_jsonl(records: list[NormalizedRecord]) -> None:
    path = PROFILES_DIR / "_agent-normalized-records.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")


def clean_profiles_dir(model_slugs: set[str]) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    for child in PROFILES_DIR.iterdir():
        if child.name in PRESERVED_PROFILE_FILES:
            continue
        if child.is_dir() and child.name not in model_slugs and not child.name.startswith("_"):
            shutil.rmtree(child)
        elif child.is_file() and child.name not in {
            "README.md",
            *PRESERVED_PROFILE_FILES,
        } and not child.name.startswith("_"):
            child.unlink(missing_ok=True)


def shell_step_script(step: str, lane: str, model_slug: str) -> str:
    gate = DEPLOYMENT_STEP_NAMES[step]
    return f"""#!/usr/bin/env bash
# C10 profile step {step} — {gate}
# Model: {model_slug}  Lane: {lane}
set -euo pipefail
PROFILE_STEP="{step}"
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
LANE_JSON="${{SCRIPT_DIR}}/lane.json"
PROFILE_SIZES="${{SCRIPT_DIR}}/profile-sizes.csv"
MODEL_SLUG="{model_slug}"
TARGET_LANE="{lane}"
if [[ ! -f "${{LANE_JSON}}" ]]; then
  echo "Missing lane metadata: ${{LANE_JSON}}" >&2
  exit 1
fi
echo "[profile-step-${{PROFILE_STEP}}] ${{MODEL_SLUG}} / ${{TARGET_LANE}} — {gate}"
python3 - "${{LANE_JSON}}" "${{PROFILE_SIZES}}" "${{PROFILE_STEP}}" <<'PY'
import csv, json, sys
lane = json.loads(open(sys.argv[1], encoding="utf-8").read())
step = sys.argv[3]
print(json.dumps({{"step": step, "lane": lane.get("target_lane"), "install_path": lane.get("install_path")}}, indent=2))
with open(sys.argv[2], encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
print(f"profile_sizes={{len(rows)}}")
PY
"""


def ps1_step_script(step: str, lane: str, model_slug: str) -> str:
    gate = DEPLOYMENT_STEP_NAMES[step]
    return f"""# C10 profile step {step} — {gate}
# Model: {model_slug}  Lane: {lane}
$ErrorActionPreference = 'Stop'
$ProfileStep = '{step}'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) {{ throw "Missing lane metadata: $LaneJson" }}
Write-Host "[profile-step-$ProfileStep] {model_slug} / {lane} — {gate}"
"""


def generate_profiles(
    models: list[dict[str, Any]],
    slug_map: dict[str, str],
    matrix_records: list[NormalizedRecord],
    base_records: list[NormalizedRecord],
    report: GenerationReport,
) -> list[dict[str, str]]:
    model_slugs = {slug_map.get(m["id"], filesystem_slug(m["id"])) for m in models}
    clean_profiles_dir(model_slugs)

    index_rows: list[dict[str, str]] = []
    size_records_by_model: dict[str, list[NormalizedRecord]] = defaultdict(list)

    for record in matrix_records:
        if record.target_lane and record.model_slug and record.size_slug:
            size_records_by_model[record.model_slug].append(record)
        elif record.model_slug and record.size_slug and not record.target_lane:
            pass

    base_by_model_size: dict[tuple[str, str], NormalizedRecord] = {}
    for model in models:
        model_id = model["id"]
        model_slug = slug_map.get(model_id) or filesystem_slug(model_id)
        model_dir = PROFILES_DIR / model_slug
        model_dir.mkdir(parents=True, exist_ok=True)

        size_rows_csv: list[dict[str, str]] = []
        sizes_dir = model_dir / "sizes"
        sizes_dir.mkdir(parents=True, exist_ok=True)

        for variant_index, variant in enumerate(model.get("deployment_variants", []), start=1):
            tag = variant.get("tag") or variant.get("ollama_identifier", "").split(":", 1)[-1]
            size_slug = filesystem_slug(tag)
            ollama_ref = variant.get("ollama_identifier")
            base_key = (model_slug, size_slug)
            if base_key not in base_by_model_size:
                rec = next(
                    (
                        r
                        for r in base_records
                        if r.model_slug == model_slug
                        and r.size_slug == size_slug
                        and r.source_kind == "p4_deployment_variant"
                    ),
                    None,
                )
                if rec is None:
                    continue
                base_by_model_size[base_key] = rec
                write_json(sizes_dir / f"{size_slug}.json", rec.as_dict())
                size_rows_csv.append(
                    {
                        "size_slug": size_slug,
                        "ollama_ref": ollama_ref or "",
                        "size_file": f"sizes/{size_slug}.json",
                    }
                )

        write_json(
            model_dir / "model.json",
            {
                "schema_version": "profiles.model.v1",
                "model_id": model_id,
                "model_slug": model_slug,
                "family_id": model.get("family_id"),
                "display_name": model.get("display_name"),
                "default_tag": model.get("default_tag"),
                "size_count": len(size_rows_csv),
                "source_path": rel(P4_MODELS_PATH),
                "generated_at": utc_now_iso(),
            },
        )
        with (model_dir / "sizes.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["size_slug", "ollama_ref", "size_file"])
            writer.writeheader()
            writer.writerows(size_rows_csv)

        for lane in PLATFORM_LANES:
            lane_dir = model_dir / lane
            lane_dir.mkdir(parents=True, exist_ok=True)
            lane_sizes: list[dict[str, str]] = []
            for size_row in size_rows_csv:
                size_slug = size_row["size_slug"]
                matrix_rec = next(
                    (
                        r
                        for r in matrix_records
                        if r.model_slug == model_slug
                        and r.size_slug == size_slug
                        and r.target_lane == lane
                    ),
                    None,
                )
                fit_status = matrix_rec.fit_status if matrix_rec else "not_listed_in_agents_selection"
                lane_sizes.append(
                    {
                        "size_slug": size_slug,
                        "ollama_ref": size_row["ollama_ref"],
                        "size_file": f"../sizes/{size_slug}.json",
                        "fit_status": fit_status or "unknown",
                    }
                )
                index_rows.append(
                    {
                        "model_id": model_id,
                        "model_slug": model_slug,
                        "size_slug": size_slug,
                        "ollama_ref": size_row["ollama_ref"],
                        "size_file": f"profiles/{model_slug}/sizes/{size_slug}.json",
                        "target_lane": lane,
                        "profile_lane_path": f"profiles/{model_slug}/{lane}",
                        "install_path": INSTALL_PATH_BY_LANE[lane],
                        "fit_status": fit_status or "unknown",
                        "minimum_ram_gb": _csv_num(matrix_rec.minimum_ram_gb if matrix_rec else None),
                        "recommended_ram_gb": _csv_num(matrix_rec.recommended_ram_gb if matrix_rec else None),
                        "minimum_vram_gb": _csv_num(matrix_rec.minimum_vram_gb if matrix_rec else None),
                        "recommended_vram_gb": _csv_num(matrix_rec.recommended_vram_gb if matrix_rec else None),
                        "minimum_disk_free_gb": _csv_num(
                            matrix_rec.minimum_disk_free_gb if matrix_rec else None
                        ),
                        "source_kind": matrix_rec.source_kind if matrix_rec else "",
                        "source_path": matrix_rec.source_path if matrix_rec else "",
                        "source_locator": matrix_rec.source_locator if matrix_rec else "",
                    }
                )

            write_json(
                lane_dir / "lane.json",
                {
                    "schema_version": "profiles.lane.v1",
                    "model_slug": model_slug,
                    "target_lane": lane,
                    "install_path": INSTALL_PATH_BY_LANE[lane],
                    "hardware_profile_ids": LANE_HARDWARE_PROFILES[lane],
                    "source_path": rel(P4_MODELS_PATH),
                    "generated_at": utc_now_iso(),
                },
            )
            with (lane_dir / "profile-sizes.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["size_slug", "ollama_ref", "size_file", "fit_status"]
                )
                writer.writeheader()
                writer.writerows(lane_sizes)

            step_files = STEP_FILES_WINDOWS if lane.startswith("windows/") else STEP_FILES_SHELL
            for step_file in step_files:
                step = step_file.split(".", 1)[0]
                content = (
                    ps1_step_script(step, lane, model_slug)
                    if step_file.endswith(".ps1")
                    else shell_step_script(step, lane, model_slug)
                )
                target = lane_dir / step_file
                target.write_text(content, encoding="utf-8")
                if step_file.endswith(".sh"):
                    target.chmod(0o755)

    report.model_count = len(models)
    report.distinct_model_size_count = sum(len(m.get("deployment_variants", [])) for m in models)
    report.install_lane_count = len({INSTALL_PATH_BY_LANE[lane] for lane in PLATFORM_LANES})
    report.profile_lane_count = len(PLATFORM_LANES)
    report.matrix_row_count = len(index_rows)

    write_json(
        PROFILES_DIR / "lanes.json",
        {
            "schema_version": "profiles.lanes.v1",
            "generated_at": utc_now_iso(),
            "profile_lanes": list(PLATFORM_LANES),
            "install_path_by_lane": INSTALL_PATH_BY_LANE,
            "hardware_profile_ids_by_lane": LANE_HARDWARE_PROFILES,
            "source_paths": [rel(P4_MODELS_PATH), rel(P3_SELECTION_PATH)],
        },
    )

    write_json(
        PROFILES_DIR / "manifest.json",
        {
            "schema_version": "profiles.manifest.v1",
            "generated_at": utc_now_iso(),
            "generator": "scripts/generate-profiles-from-agents.py",
            "primary_sources": [rel(P4_MODELS_PATH), rel(P3_SELECTION_PATH), rel(AGENTS_DIR)],
            "counts": {
                "models": report.model_count,
                "distinct_model_sizes": report.distinct_model_size_count,
                "profile_lanes": report.profile_lane_count,
                "install_lanes": report.install_lane_count,
                "matrix_rows": report.matrix_row_count,
            },
        },
    )

    index_fields = [
        "model_id",
        "model_slug",
        "size_slug",
        "ollama_ref",
        "size_file",
        "target_lane",
        "profile_lane_path",
        "install_path",
        "fit_status",
        "minimum_ram_gb",
        "recommended_ram_gb",
        "minimum_vram_gb",
        "recommended_vram_gb",
        "minimum_disk_free_gb",
        "source_kind",
        "source_path",
        "source_locator",
    ]
    with (PROFILES_DIR / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=index_fields)
        writer.writeheader()
        writer.writerows(index_rows)

    readme = (PROFILES_DIR / "README.md").read_text(encoding="utf-8") if (PROFILES_DIR / "README.md").is_file() else ""
    if "generate-profiles-from-agents.py" not in readme:
        appendix = """

## C10 AGENTS-generated profiles (glass ball)

Regenerate the model/size/profile matrix from AGENTS/ data:

```bash
python3 scripts/generate-profiles-from-agents.py
python3 scripts/validate-profiles-from-agents.py
```

Authoritative inputs: `AGENTS/data-science/P4-Public-Catalog/index/models.json`,
`AGENTS/data-science/P3-Ollama-Metadata-Catalog/indexes/model-selection.json`, and
classified `AGENTS/TG-8Ball-*.csv` hardware research files.
"""
        (PROFILES_DIR / "README.md").write_text(readme.rstrip() + appendix + "\n", encoding="utf-8")

    return index_rows


def _csv_num(value: float | None) -> str:
    return "" if value is None else str(value)


def main() -> int:
    if not AGENTS_DIR.is_dir():
        raise SystemExit(f"Missing AGENTS directory: {AGENTS_DIR}")
    if not P4_MODELS_PATH.is_file():
        raise SystemExit(f"Missing canonical AGENTS model catalog: {P4_MODELS_PATH}")

    report = GenerationReport()
    inventory = inventory_agents()
    report.agents_files_inspected = len(inventory)
    report.agents_files_parsed = sum(1 for row in inventory if row.parse_status == "parsed")
    write_inventory_outputs(inventory)

    models = json.loads(P4_MODELS_PATH.read_text(encoding="utf-8"))
    slug_map = load_model_slug_map()
    records: list[NormalizedRecord] = []
    records.extend(normalize_from_p4(models, slug_map))

    for csv_path in sorted(AGENTS_DIR.glob("TG-8Ball-*.csv")):
        if "Checklist" in csv_path.name or "Inventory" in csv_path.name or "Counts" in csv_path.name:
            continue
        records.extend(normalize_hardware_csv(csv_path))

    records, skipped = dedupe_records(records)
    report.records_skipped = skipped
    report.records_with_conflicts = sum(1 for r in records if r.conflict)
    report.records_with_unknown_limits = sum(
        1
        for r in records
        if r.minimum_ram_gb is None
        and r.minimum_vram_gb is None
        and r.minimum_disk_free_gb is None
    )

    write_normalized_jsonl(records)
    lane_matrix_records = build_lane_matrix_records(records)
    generate_profiles(models, slug_map, lane_matrix_records, records, report)

    report_payload = {
        "generated_at": utc_now_iso(),
        "AGENTS files inspected": report.agents_files_inspected,
        "AGENTS files parsed": report.agents_files_parsed,
        "model count": report.model_count,
        "distinct model-size count": report.distinct_model_size_count,
        "install lane count": report.install_lane_count,
        "profile lane count": report.profile_lane_count,
        "matrix row count": report.matrix_row_count,
        "records with unknown limits": report.records_with_unknown_limits,
        "records with conflicts": report.records_with_conflicts,
        "records skipped and why": report.records_skipped,
    }
    write_json(REPORT_PATH, report_payload)

    print(json.dumps(report_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

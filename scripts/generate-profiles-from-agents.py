#!/usr/bin/env python3
"""C10.3: Generate canonical data-only /profiles/ from AGENTS and catalog inputs."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "AGENTS"
PROFILES_DIR = REPO_ROOT / "profiles"
LEGACY_DIR = PROFILES_DIR / "legacy"
GENERATED_REPORT_DIR = PROFILES_DIR / "generated"
REPORT_PATH = GENERATED_REPORT_DIR / "profile-generation-report.json"

P4_MODELS_PATH = AGENTS_DIR / "data-science" / "ollama-mapping" / "P4-Public-Catalog" / "index" / "models.json"
P3_SELECTION_PATH = (
    AGENTS_DIR / "data-science" / "ollama-mapping" / "P3-Ollama-Metadata-Catalog" / "indexes" / "model-selection.json"
)
TAGS_PATH = REPO_ROOT / "data" / "normalized" / "tags.json"
MANIFEST_PATH = REPO_ROOT / "data" / "generated" / "pages" / "install-manifest.json"

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

CANONICAL_STEP_FILES: tuple[tuple[str, str], ...] = (
    ("3-cpu.json", "3-cpu"),
    ("4-ram.json", "4-ram"),
    ("5-hard-disk.json", "5-hard_disk"),
    ("6-cpu-only.json", "6-CPU_only"),
    ("7-gpu-vram.json", "7-video_card"),
)

CURSOR_PROMPT_MARKERS = ("cursorfile", "cursorc", "roadmap", "prompt")

PRESERVED_PROFILE_FILES = frozenset({"environment.profile.example.env"})

PRESERVED_ROOT_NAMES = frozenset(
    {
        "README.md",
        "manifest.json",
        "lanes.json",
        "index.csv",
        "legacy",
        "generated",
        "provider-assumptions",
        "provider-compatibility",
        "_agent-input-inventory.json",
        "_agent-input-inventory.csv",
        "_agent-normalized-records.jsonl",
        *PRESERVED_PROFILE_FILES,
    }
)

LEGACY_ARCHIVE_DIRS = (
    "models",
    "families",
    "deployment-classes",
)

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

GENERATOR_COMMAND = "python3 scripts/generate-profiles-from-agents.py"
GENERATED_AT = ""


def _load_c10_generator():
    path = REPO_ROOT / "scripts" / "generate-c10-profiles.py"
    spec = importlib.util.spec_from_file_location("generate_c10_profiles", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_iso() -> str:
    return GENERATED_AT or utc_now_iso()


def deterministic_generated_at(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.is_file():
            digest.update(path.as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    # Fixed epoch anchor keeps output stable while still encoding input identity.
    seed = int(digest.hexdigest()[:8], 16)
    anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return anchor.replace(second=seed % 60, minute=(seed // 60) % 60, hour=(seed // 3600) % 24).isoformat().replace(
        "+00:00", "Z"
    )


GENERATION_TIMESTAMP_PATHS = (
    TAGS_PATH,
    P3_SELECTION_PATH,
    P4_MODELS_PATH,
)


def filesystem_slug(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[/:]+", "-", slug)
    slug = re.sub(r"[^a-z0-9_.-]+", "-", slug)
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
    profile_lane_count: int = 0
    matrix_row_count: int = 0
    records_with_unknown_limits: int = 0
    records_with_conflicts: int = 0
    records_skipped: list[dict[str, str]] = field(default_factory=list)
    legacy_archived_paths: list[str] = field(default_factory=list)


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
                    models_val = payload.get("models")
                    if isinstance(models_val, (list, dict)):
                        model_rows = len(models_val)
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


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_num(value: float | None) -> str:
    return "" if value is None else str(value)


def load_p3_candidate_index() -> dict[str, dict[str, dict[str, Any]]]:
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


def normalize_from_tags(tags: list[dict[str, Any]], model_pages: dict[str, dict[str, Any]]) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    p3_index = load_p3_candidate_index()
    tag_by_ref = {t.get("ollama_identifier"): t for t in tags if t.get("ollama_identifier")}

    for model_slug, page in model_pages.items():
        for size_index, size in enumerate(page.get("sizes", []), start=1):
            ollama_ref = size.get("ollama_ref")
            tag = tag_by_ref.get(ollama_ref, {})
            est = size.get("estimated") or {}
            download_bytes = size.get("download_size_bytes")
            minimum_disk = None
            if download_bytes is not None:
                minimum_disk = round(download_bytes / (1024**3), 3)

            record = NormalizedRecord(
                model_id=tag.get("model_id"),
                model_slug=model_slug,
                size_slug=size.get("size_slug"),
                ollama_ref=ollama_ref,
                parameter_size=str(size.get("parameter_count")) if size.get("parameter_count") else None,
                quantization=size.get("quantization"),
                minimum_ram_gb=_float_or_none(est.get("min_system_ram_gb")),
                recommended_ram_gb=_float_or_none(est.get("recommended_system_ram_gb")),
                minimum_vram_gb=_float_or_none(est.get("min_vram_gb")),
                recommended_vram_gb=_float_or_none(est.get("recommended_vram_gb")),
                minimum_disk_free_gb=minimum_disk,
                fit_status="unknown",
                source_kind="normalized_catalog_tag",
                source_path=rel(TAGS_PATH),
                source_locator=f"model_slug={model_slug};size_index={size_index};ollama_ref={ollama_ref}",
                provenance={
                    "download_size_bytes": download_bytes,
                    "estimated": est,
                    "tag_provenance": size.get("provenance"),
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
                    record.conflict = True
                    record.conflict_notes.append("conflicting P3 hardware-profile RAM/VRAM estimates")
                if ram_values and record.minimum_ram_gb is None:
                    record.minimum_ram_gb = min(ram_values)
                if rec_ram_values and record.recommended_ram_gb is None:
                    record.recommended_ram_gb = min(rec_ram_values)
                if vram_values and record.minimum_vram_gb is None:
                    record.minimum_vram_gb = min(vram_values)
                    record.recommended_vram_gb = min(vram_values)
                record.provenance["p3_selection_profiles"] = list(candidates.keys())

            records.append(record)
    return records


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
        "generated_at": timestamp_iso(),
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


def archive_legacy_artifacts(report: GenerationReport) -> None:
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    c5_dir = LEGACY_DIR / "c5-root-export"
    c10_pages_dir = LEGACY_DIR / "c10-model-pages"

    for dirname in LEGACY_ARCHIVE_DIRS:
        src = PROFILES_DIR / dirname
        if not src.exists():
            continue
        dst = c5_dir / dirname
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))
        report.legacy_archived_paths.append(rel(dst))

    for name in ("manifest.json", "index.csv", "c10-index.json"):
        src = PROFILES_DIR / name
        if not src.is_file():
            continue
        if name == "manifest.json":
            try:
                payload = json.loads(src.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if payload.get("schema_version") == "profiles.manifest.v1" and payload.get("generator", "").endswith(
                "generate-profiles-from-agents.py"
            ):
                continue
            dst = c5_dir / name
        elif name == "index.csv":
            with src.open(encoding="utf-8", newline="") as handle:
                headers = next(csv.reader(handle), [])
            if "target_lane" in headers:
                continue
            dst = c5_dir / name
        else:
            dst = LEGACY_DIR / "c10-index.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        report.legacy_archived_paths.append(rel(dst))

    c10_pages_dir.mkdir(parents=True, exist_ok=True)
    for child in list(PROFILES_DIR.iterdir()):
        if not child.is_file() or child.suffix != ".json":
            continue
        if child.name in {
            "manifest.json",
            "lanes.json",
            "_agent-input-inventory.json",
            "_agent-generation-report.json",
        }:
            continue
        if child.name.startswith("_"):
            continue
        dst = c10_pages_dir / child.name
        if dst.exists():
            dst.unlink()
        shutil.move(str(child), str(dst))
        report.legacy_archived_paths.append(rel(dst))

    for child in list(PROFILES_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name in PRESERVED_ROOT_NAMES or child.name.startswith("_"):
            continue
        if child.name in LEGACY_ARCHIVE_DIRS:
            continue
        if (child / "model.json").is_file() and (child / "sizes.csv").is_file():
            continue
        dst = LEGACY_DIR / "c10-lane-skeletons" / child.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(child), str(dst))
        report.legacy_archived_paths.append(rel(dst))

    readme = LEGACY_DIR / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Legacy profile exports (non-runtime compatibility)",
                "",
                "These artifacts are retained for migration reference only.",
                "The canonical runtime-facing profile matrix lives at the repository root under `profiles/`.",
                "",
                "| Path | Origin | Removal condition |",
                "| --- | --- | --- |",
                "| `c5-root-export/` | C5 `eight-ball generate-root-profiles` | No consumers of C5 entity index remain |",
                "| `c10-model-pages/` | C10 flat `profiles/<slug>.json` pages | 8.x resolver reads canonical model folders only |",
                "| `c10-lane-skeletons/` | Empty or pre-C10.3 lane trees | Canonical per-model lane trees validated |",
                "| `c10-index.json` | C10 model×lane index | Superseded by `profiles/index.csv` matrix |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def clean_model_dirs(model_slugs: set[str]) -> None:
    for child in PROFILES_DIR.iterdir():
        if not child.is_dir():
            continue
        if child.name in PRESERVED_ROOT_NAMES or child.name.startswith("_"):
            continue
        if child.name not in model_slugs:
            shutil.rmtree(child)


def canonical_fit_status(raw: str | None) -> str:
    if not raw:
        return "unknown"
    if raw == "fit":
        return "fit"
    if raw in {"no_fit", "unknown"}:
        return raw
    if raw.startswith("unknown"):
        return "unknown"
    return raw


def lane_semantics(lane_path: str) -> dict[str, Any]:
    is_cuda = lane_path.endswith("/cuda") or lane_path.endswith("/gpu") or lane_path.endswith("/gpu-droplet")
    is_apple_silicon = lane_path == "mac/apple-silicon"
    is_intel_mac = lane_path == "mac/intel"
    is_cloud = lane_path.startswith("cloud/")
    platform = lane_path.split("/", 1)[0]
    return {
        "lane_path": lane_path,
        "platform": platform,
        "acceleration": "cuda" if is_cuda else ("apple-metal" if is_apple_silicon else "cpu"),
        "gpu_lane": is_cuda or is_apple_silicon,
        "cloud_lane": is_cloud,
        "intel_mac_cpu_only": is_intel_mac,
    }


def build_lanes_json(c10_module: Any) -> dict[str, Any]:
    lanes: list[dict[str, Any]] = []
    for lane in c10_module.INSTALL_LANES:
        semantics = lane_semantics(lane["lane_path"])
        lanes.append(
            {
                "lane_path": lane["lane_path"],
                "provider_id": lane["provider_id"],
                "platform": lane["platform"],
                "provider": lane.get("provider"),
                "architecture": lane["architecture"],
                "gpu_lane": lane.get("gpu_lane", False),
                "detection_signals": lane["detection_signals"],
                "operating_system": semantics["platform"],
                "acceleration": semantics["acceleration"],
                "cloud_lane": semantics["cloud_lane"],
                "intel_mac_cpu_only": semantics["intel_mac_cpu_only"],
            }
        )
    return {
        "schema_version": "profiles.lanes.v1",
        "generated_at": timestamp_iso(),
        "profile_lanes": list(PLATFORM_LANES),
        "lanes": lanes,
        "source_paths": [rel(TAGS_PATH), rel(P3_SELECTION_PATH)],
    }


def generate_profiles(
    c10_module: Any,
    model_pages: dict[str, dict[str, Any]],
    lane_hardware_map: dict[str, dict[str, Any]],
    normalized_records: list[NormalizedRecord],
    report: GenerationReport,
) -> list[dict[str, str]]:
    model_slugs = set(model_pages)
    clean_model_dirs(model_slugs)

    norm_by_slug: dict[tuple[str, str], NormalizedRecord] = {}
    for record in normalized_records:
        if record.model_slug and record.size_slug and not record.target_lane:
            norm_by_slug[(record.model_slug, record.size_slug)] = record

    index_rows: list[dict[str, str]] = []

    for model_slug, page in sorted(model_pages.items()):
        model_dir = PROFILES_DIR / model_slug
        model_dir.mkdir(parents=True, exist_ok=True)
        sizes_dir = model_dir / "sizes"
        sizes_dir.mkdir(parents=True, exist_ok=True)

        size_rows_csv: list[dict[str, str]] = []
        for size in page.get("sizes", []):
            size_slug = size["size_slug"]
            ollama_ref = size.get("ollama_ref", "")
            norm = norm_by_slug.get((model_slug, size_slug))
            size_payload = {
                "schema_version": "profiles.size.v1",
                "model_slug": model_slug,
                "size_slug": size_slug,
                "ollama_ref": ollama_ref,
                "parameter_count": size.get("parameter_count"),
                "quantization": size.get("quantization"),
                "download_size_bytes": size.get("download_size_bytes"),
                "estimated": size.get("estimated"),
                "provenance": size.get("provenance"),
                "source_path": rel(TAGS_PATH),
                "generated_at": timestamp_iso(),
            }
            if norm:
                size_payload["normalized"] = {
                    field: getattr(norm, field)
                    for field in (
                        "minimum_ram_gb",
                        "recommended_ram_gb",
                        "minimum_vram_gb",
                        "recommended_vram_gb",
                        "minimum_disk_free_gb",
                        "fit_status",
                        "source_kind",
                        "source_path",
                        "source_locator",
                    )
                }
            write_json(sizes_dir / f"{size_slug}.json", size_payload)
            size_rows_csv.append(
                {
                    "size_slug": size_slug,
                    "ollama_ref": ollama_ref,
                    "size_file": f"sizes/{size_slug}.json",
                }
            )

        write_json(
            model_dir / "model.json",
            {
                "schema_version": "profiles.model.v1",
                "model_slug": model_slug,
                "display_name": model_slug,
                "size_count": len(size_rows_csv),
                "promoted_size_slug": page.get("promoted_size_slug"),
                "source_paths": page.get("source_paths", [rel(TAGS_PATH)]),
                "generated_at": timestamp_iso(),
            },
        )
        with (model_dir / "sizes.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["size_slug", "ollama_ref", "size_file"])
            writer.writeheader()
            writer.writerows(size_rows_csv)

        for lane in c10_module.INSTALL_LANES:
            lane_path = lane["lane_path"]
            hw = lane_hardware_map[lane_path]
            lane_dir = model_dir / lane_path
            lane_dir.mkdir(parents=True, exist_ok=True)

            lane_stage = c10_module.build_stage_file("lane", lane, hw, model_slug, page["sizes"])
            lane_fit_by_slug = {item["size_slug"]: item for item in lane_stage.get("size_fit", [])}

            write_json(
                lane_dir / "lane.json",
                {
                    "schema_version": "profiles.lane.v1",
                    "model_slug": model_slug,
                    "target_lane": lane_path,
                    "provider_assumption_id": lane["provider_id"],
                    "detection_signals": lane["detection_signals"],
                    "hardware": {
                        key: hw.get(key)
                        for key in (
                            "cpu_cores",
                            "system_ram_gb",
                            "usable_model_ram_gb",
                            "minimum_free_disk_gb",
                            "total_vram_gb",
                            "cuda_available",
                            "apple_metal_available",
                            "provenance_status",
                            "source_path",
                        )
                    },
                    "size_fit": lane_stage.get("size_fit", []),
                    "source_path": rel(TAGS_PATH),
                    "generated_at": timestamp_iso(),
                },
            )

            lane_sizes: list[dict[str, str]] = []
            for size_row in size_rows_csv:
                size_slug = size_row["size_slug"]
                fit_item = lane_fit_by_slug.get(size_slug, {})
                fit_status = canonical_fit_status(fit_item.get("fit_status"))
                lane_sizes.append(
                    {
                        "size_slug": size_slug,
                        "ollama_ref": size_row["ollama_ref"],
                        "size_file": f"../sizes/{size_slug}.json",
                        "fit_status": fit_status,
                    }
                )
                norm = norm_by_slug.get((model_slug, size_slug))
                index_rows.append(
                    {
                        "model_id": norm.model_id if norm else "",
                        "model_slug": model_slug,
                        "size_slug": size_slug,
                        "ollama_ref": size_row["ollama_ref"],
                        "size_file": f"profiles/{model_slug}/sizes/{size_slug}.json",
                        "target_lane": lane_path,
                        "profile_lane_path": f"profiles/{model_slug}/{lane_path}",
                        "fit_status": fit_status,
                        "minimum_ram_gb": _csv_num(norm.minimum_ram_gb if norm else None),
                        "recommended_ram_gb": _csv_num(norm.recommended_ram_gb if norm else None),
                        "minimum_vram_gb": _csv_num(norm.minimum_vram_gb if norm else None),
                        "recommended_vram_gb": _csv_num(norm.recommended_vram_gb if norm else None),
                        "minimum_disk_free_gb": _csv_num(norm.minimum_disk_free_gb if norm else None),
                        "source_kind": norm.source_kind if norm else "normalized_catalog_tag",
                        "source_path": norm.source_path if norm else rel(TAGS_PATH),
                        "source_locator": norm.source_locator if norm else f"model_slug={model_slug};size_slug={size_slug}",
                    }
                )

            with (lane_dir / "profile-sizes.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["size_slug", "ollama_ref", "size_file", "fit_status"]
                )
                writer.writeheader()
                writer.writerows(lane_sizes)

            for filename, stage_key in CANONICAL_STEP_FILES:
                stage_payload = c10_module.build_stage_file(stage_key, lane, hw, model_slug, page["sizes"])
                stage_payload["schema_version"] = "profiles.stage.v1"
                write_json(lane_dir / filename, stage_payload)

    report.model_count = len(model_pages)
    report.distinct_model_size_count = sum(len(p.get("sizes", [])) for p in model_pages.values())
    report.profile_lane_count = len(PLATFORM_LANES)
    report.matrix_row_count = len(index_rows)

    write_json(PROFILES_DIR / "lanes.json", build_lanes_json(c10_module))

    index_fields = [
        "model_id",
        "model_slug",
        "size_slug",
        "ollama_ref",
        "size_file",
        "target_lane",
        "profile_lane_path",
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

    return index_rows


def write_manifest(report: GenerationReport, inventory: list[InventoryRow]) -> None:
    write_json(
        PROFILES_DIR / "manifest.json",
        {
            "schema_version": "profiles.manifest.v1",
            "generated_at": timestamp_iso(),
            "generator": GENERATOR_COMMAND,
            "primary_sources": [
                source
                for source in (
                    rel(TAGS_PATH),
                    rel(P3_SELECTION_PATH),
                    rel(P4_MODELS_PATH) if P4_MODELS_PATH.is_file() else None,
                    rel(AGENTS_DIR),
                )
                if source
            ],
            "inventory": {
                "json": "profiles/_agent-input-inventory.json",
                "csv": "profiles/_agent-input-inventory.csv",
                "normalized_jsonl": "profiles/_agent-normalized-records.jsonl",
                "agents_files_inspected": report.agents_files_inspected,
                "agents_files_parsed": report.agents_files_parsed,
            },
            "counts": {
                "models": report.model_count,
                "distinct_model_sizes": report.distinct_model_size_count,
                "profile_lanes": report.profile_lane_count,
                "matrix_rows": report.matrix_row_count,
                "records_with_unknown_limits": report.records_with_unknown_limits,
                "records_with_conflicts": report.records_with_conflicts,
            },
            "index_csv": "profiles/index.csv",
            "lanes_json": "profiles/lanes.json",
            "generation_report": rel(REPORT_PATH),
            "legacy_compatibility": {
                "root": "profiles/legacy/",
                "archived_paths": report.legacy_archived_paths,
                "removal_condition": "No consumers of legacy C5/C10 export paths remain",
            },
        },
    )


def write_profiles_readme() -> None:
    (PROFILES_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Canonical profile data contract (C10.3)",
                "",
                "This directory is the **data-only**, runtime-facing profile matrix for later",
                "`8.1` / `8.2` / `8.3` resolver work. It does not contain installer scripts.",
                "",
                "## Canonical artifacts",
                "",
                "| Path | Role |",
                "| --- | --- |",
                "| `manifest.json` | Schema version, generator command, source inventory, counts |",
                "| `lanes.json` | Exactly ten install/profile lanes and OS/acceleration semantics |",
                "| `index.csv` | One row per model-size-lane combination |",
                "| `<model-slug>/model.json` | Model metadata |",
                "| `<model-slug>/sizes.csv` | Size index for the model |",
                "| `<model-slug>/sizes/<size-slug>.json` | Size records (file, never directory) |",
                "| `<model-slug>/<lane>/lane.json` | Lane metadata and per-size fit summary |",
                "| `<model-slug>/<lane>/profile-sizes.csv` | Lane-local size references |",
                "| `<model-slug>/<lane>/3-cpu.json` … `7-gpu-vram.json` | Data-only stage payloads |",
                "",
                "## Regenerate",
                "",
                "```bash",
                "python3 scripts/generate-profiles-from-agents.py",
                "python3 scripts/validate-profiles-from-agents.py",
                "```",
                "",
                "## Legacy compatibility",
                "",
                "Non-runtime exports from earlier C5/C10 work are retained under",
                "`profiles/legacy/` with a migration README. They must not be treated as the",
                "canonical profile source.",
                "",
                "C5 generated pages remain the catalog page source of truth under",
                "`data/generated/pages/models/<model-slug>/<3-7>/` and",
                "`data/generated/pages/install-manifest.json`.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    if not AGENTS_DIR.is_dir():
        raise SystemExit(f"Missing AGENTS directory: {AGENTS_DIR}")
    if not TAGS_PATH.is_file():
        raise SystemExit(f"Missing normalized tags catalog: {TAGS_PATH}")

    generated_at = deterministic_generated_at([p for p in GENERATION_TIMESTAMP_PATHS if p.is_file()])
    global GENERATED_AT
    GENERATED_AT = generated_at

    c10_module = _load_c10_generator()
    c10_module.utc_now = lambda: generated_at
    report = GenerationReport()

    inventory = inventory_agents()
    report.agents_files_inspected = len(inventory)
    report.agents_files_parsed = sum(1 for row in inventory if row.parse_status == "parsed")
    write_inventory_outputs(inventory)

    archive_legacy_artifacts(report)

    tags = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    hardware_profiles = c10_module.load_hardware_profiles()
    cloud_defaults = c10_module.load_cloud_plan_defaults()
    model_pages = c10_module.build_model_pages(tags)

    lane_hardware_map: dict[str, dict[str, Any]] = {}
    for lane in c10_module.INSTALL_LANES:
        lane_hardware_map[lane["lane_path"]] = c10_module.lane_hardware(lane, hardware_profiles, cloud_defaults)

    records: list[NormalizedRecord] = []
    records.extend(normalize_from_tags(tags, model_pages))
    for csv_path in sorted(AGENTS_DIR.glob("TG-8Ball-*.csv")):
        if any(skip in csv_path.name for skip in ("Checklist", "Inventory", "Counts")):
            continue
        records.extend(normalize_hardware_csv(csv_path))

    records, skipped = dedupe_records(records)
    report.records_skipped = skipped
    report.records_with_conflicts = sum(1 for r in records if r.conflict)
    report.records_with_unknown_limits = sum(
        1
        for r in records
        if r.minimum_ram_gb is None and r.minimum_vram_gb is None and r.minimum_disk_free_gb is None
    )
    write_normalized_jsonl(records)

    generate_profiles(c10_module, model_pages, lane_hardware_map, records, report)
    write_manifest(report, inventory)
    write_profiles_readme()

    GENERATED_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "schema_version": "profiles.generation-report.v1",
        "generated_at": timestamp_iso(),
        "generator": GENERATOR_COMMAND,
        "agents_files_inspected": report.agents_files_inspected,
        "agents_files_parsed": report.agents_files_parsed,
        "model_count": report.model_count,
        "distinct_model_size_count": report.distinct_model_size_count,
        "profile_lane_count": report.profile_lane_count,
        "matrix_row_count": report.matrix_row_count,
        "records_with_unknown_limits": report.records_with_unknown_limits,
        "records_with_conflicts": report.records_with_conflicts,
        "records_skipped": report.records_skipped,
        "legacy_archived_paths": report.legacy_archived_paths,
    }
    write_json(REPORT_PATH, report_payload)
    print(json.dumps(report_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

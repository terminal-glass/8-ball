"""AGENTS tree inventory and normalized record export for C10 Glass Ball."""
from __future__ import annotations

import csv
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "AGENTS"
PROFILES_DIR = REPO_ROOT / "profiles"
REPORT_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"

P4_MODELS_PATH = AGENTS_DIR / "data-science/ollama-mapping/P4-Public-Catalog/index/models.json"

INVENTORY_JSON = PROFILES_DIR / "_agent-input-inventory.json"
INVENTORY_CSV = PROFILES_DIR / "_agent-input-inventory.csv"
NORMALIZED_JSONL = PROFILES_DIR / "_agent-normalized-records.jsonl"
REPORT_MD = REPORT_DIR / "C10-glassball-generation-report.md"

DATA_EXTENSIONS = frozenset({".csv", ".json", ".jsonl", ".yaml", ".yml"})
PROMPT_MARKERS = ("cursorfile", "cursor prompt", "roadmap", "handoff")

INDEX_HEADERS = (
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
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_prompt_or_prose(path: Path, text: str) -> bool:
    if path.name.lower().startswith("cursorfile") or "history" in path.parts:
        return True
    sample = text[:4000].lower()
    return any(marker in sample for marker in PROMPT_MARKERS) and "|" not in text[:2000]


def looks_like_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    return sum(1 for line in lines[:40] if "|" in line) >= 3


def inventory_agents_file(path: Path, *, load_json: Callable[[Path], Any], load_csv_rows: Callable[[Path], list]) -> dict[str, Any]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    suffix = path.suffix.lower()
    source_type = suffix.lstrip(".") if suffix else "text"
    row: dict[str, Any] = {
        "source_path": rel,
        "source_type": source_type,
        "parse_status": "skipped",
        "row_count": 0,
        "recognized_model_rows": 0,
        "recognized_size_rows": 0,
        "recognized_platform_rows": 0,
        "recognized_hardware_fields": 0,
        "notes": "",
    }
    try:
        if suffix in DATA_EXTENSIONS:
            if suffix == ".csv":
                rows = load_csv_rows(path)
                row["row_count"] = len(rows)
                row["parse_status"] = "parsed"
                header = rows[0] if rows else {}
                if "profile_id" in header:
                    row["recognized_hardware_fields"] = len(rows)
                    row["recognized_platform_rows"] = len(rows)
                elif any(k in header for k in ("provider_plan_id", "internal_plan_id", "plan_id")):
                    row["recognized_platform_rows"] = len(rows)
                elif any(k in header for k in ("host_profile_id", "accelerator_class_id")):
                    row["recognized_hardware_fields"] = len(rows)
                row["notes"] = "csv"
                return row
            if suffix == ".jsonl":
                row["row_count"] = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
                row["parse_status"] = "parsed"
                row["notes"] = "jsonl"
                return row
            payload = load_json(path)
            if isinstance(payload, list):
                row["row_count"] = len(payload)
                row["parse_status"] = "parsed"
                if path == P4_MODELS_PATH:
                    row["recognized_model_rows"] = len(payload)
                    row["recognized_size_rows"] = sum(
                        len(m.get("deployment_variants") or []) for m in payload if isinstance(m, dict)
                    )
                elif payload and isinstance(payload[0], dict):
                    keys = set(payload[0])
                    if "deployment_variants" in keys or "ollama_name" in keys:
                        row["recognized_model_rows"] = len(payload)
                    if any(k in keys for k in ("ollama_identifier", "bundle_id", "plan_slug", "vcpus")):
                        row["recognized_platform_rows"] = len(payload)
                row["notes"] = "json_array"
                return row
            if isinstance(payload, dict):
                row["row_count"] = 1
                row["parse_status"] = "parsed"
                if "deployment_variants" in payload or "ollama_name" in payload:
                    row["recognized_model_rows"] = 1
                row["notes"] = "json_object"
                return row
        if suffix in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if is_prompt_or_prose(path, text):
                row["notes"] = "prompt_or_prose_skipped"
                return row
            if looks_like_table(text):
                row["parse_status"] = "inspected"
                row["row_count"] = text.count("\n") + 1
                row["notes"] = "markdown_table_candidate"
            else:
                row["notes"] = "text_no_structured_rows"
            return row
        row["notes"] = f"unsupported_extension:{suffix}"
    except Exception as exc:  # noqa: BLE001
        row["parse_status"] = "error"
        row["notes"] = str(exc)
    return row


def inventory_agents_tree(*, load_json: Callable[[Path], Any], load_csv_rows: Callable[[Path], list]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(AGENTS_DIR.rglob("*")):
        if path.is_file():
            rows.append(inventory_agents_file(path, load_json=load_json, load_csv_rows=load_csv_rows))
    return rows


def write_agent_inventory(rows: list[dict[str, Any]], *, write_json: Callable[[Path, Any], None]) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    write_json(INVENTORY_JSON, {"generated_at": utc_now(), "files_inspected": len(rows), "sources": rows})
    fieldnames = [
        "source_path",
        "source_type",
        "parse_status",
        "row_count",
        "recognized_model_rows",
        "recognized_size_rows",
        "recognized_platform_rows",
        "recognized_hardware_fields",
        "notes",
    ]
    with INVENTORY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_size_json(model_slug: str, size: dict[str, Any]) -> dict[str, Any]:
    est = size.get("estimated") or {}
    prov = size.get("provenance") or {}
    return {
        "schema_version": "c10.size.v1",
        "model_slug": model_slug,
        "size_slug": size["size_slug"],
        "ollama_ref": size["ollama_ref"],
        "parameter_count": size.get("parameter_count"),
        "quantization": size.get("quantization"),
        "download_size_bytes": size.get("download_size_bytes"),
        "minimum_ram_gb": est.get("min_system_ram_gb"),
        "recommended_ram_gb": est.get("recommended_system_ram_gb"),
        "minimum_vram_gb": est.get("min_vram_gb"),
        "recommended_vram_gb": est.get("recommended_vram_gb"),
        "minimum_disk_free_gb": est.get("min_disk_gb"),
        "source_kind": "normalized_catalog_tag",
        "source_path": prov.get("source_path") or "data/normalized/tags.json",
        "source_locator": size.get("ollama_ref"),
        "provenance": prov,
        "estimated": est,
        "generated_at": utc_now(),
    }


def write_size_records(
    model_pages: dict[str, dict[str, Any]],
    *,
    write_json: Callable[[Path, Any], None],
) -> int:
    count = 0
    for model_slug, page in model_pages.items():
        sizes_dir = PROFILES_DIR / model_slug / "sizes"
        sizes_dir.mkdir(parents=True, exist_ok=True)
        for size in page["sizes"]:
            write_json(sizes_dir / f"{size['size_slug']}.json", build_size_json(model_slug, size))
            count += 1
    return count


def write_matrix_index(
    model_pages: dict[str, dict[str, Any]],
    install_lanes: list[dict[str, Any]],
    lane_fit_lookup: dict[tuple[str, str, str], str],
) -> tuple[list[dict[str, Any]], list[list[str]]]:
    records: list[dict[str, Any]] = []
    csv_rows: list[list[str]] = []
    for model_slug, page in sorted(model_pages.items()):
        for size in page["sizes"]:
            est = size.get("estimated") or {}
            prov = size.get("provenance") or {}
            for lane in install_lanes:
                lane_path = lane["lane_path"]
                lane_id = lane["provider_id"]
                fit_status = lane_fit_lookup.get((model_slug, size["ollama_ref"], lane_path), "unknown")
                size_file = f"profiles/{model_slug}/sizes/{size['size_slug']}.json"
                profile_lane_path = f"profiles/{model_slug}/{lane_path}"
                install_path = f"install/{lane_path}/"
                record = {
                    "model_id": model_slug,
                    "model_slug": model_slug,
                    "size_slug": size["size_slug"],
                    "ollama_ref": size["ollama_ref"],
                    "parameter_size": size.get("size_slug"),
                    "quantization": size.get("quantization"),
                    "minimum_ram_gb": est.get("min_system_ram_gb"),
                    "recommended_ram_gb": est.get("recommended_system_ram_gb"),
                    "minimum_vram_gb": est.get("min_vram_gb"),
                    "recommended_vram_gb": est.get("recommended_vram_gb"),
                    "minimum_disk_free_gb": est.get("min_disk_gb"),
                    "target_lane": lane_id,
                    "fit_status": fit_status,
                    "source_kind": "normalized_catalog_tag",
                    "source_path": prov.get("source_path") or "data/normalized/tags.json",
                    "source_locator": size.get("ollama_ref"),
                    "size_file": size_file,
                    "profile_lane_path": profile_lane_path,
                    "install_path": install_path,
                }
                records.append(record)
                csv_rows.append(
                    [
                        model_slug,
                        model_slug,
                        size["size_slug"],
                        size["ollama_ref"],
                        size_file,
                        lane_id,
                        profile_lane_path,
                        install_path,
                        fit_status,
                        "" if est.get("min_system_ram_gb") is None else str(est["min_system_ram_gb"]),
                        "" if est.get("recommended_system_ram_gb") is None else str(est["recommended_system_ram_gb"]),
                        "" if est.get("min_vram_gb") is None else str(est["min_vram_gb"]),
                        "" if est.get("recommended_vram_gb") is None else str(est["recommended_vram_gb"]),
                        "" if est.get("min_disk_gb") is None else str(est["min_disk_gb"]),
                        record["source_kind"],
                        record["source_path"],
                        record["source_locator"],
                    ]
                )
    index_path = PROFILES_DIR / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(INDEX_HEADERS)
        writer.writerows(csv_rows)
    return records, csv_rows


def write_normalized_jsonl(records: list[dict[str, Any]]) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    with NORMALIZED_JSONL.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def p4_deployment_variant_count(*, load_json: Callable[[Path], Any]) -> int | None:
    if not P4_MODELS_PATH.is_file():
        return None
    models = load_json(P4_MODELS_PATH)
    if not isinstance(models, list):
        return None
    return sum(len(m.get("deployment_variants") or []) for m in models if isinstance(m, dict))


def write_glassball_report(
    *,
    inventory_rows: list[dict[str, Any]],
    model_count: int,
    model_size_count: int,
    profile_lane_count: int,
    matrix_row_count: int,
    stage_payload_count: int,
    conflict_count: int,
    unknown_limit_count: int,
    skipped: list[str],
    p4_variants: int | None,
) -> None:
    files_parsed = sum(1 for row in inventory_rows if row.get("parse_status") == "parsed")
    lines = [
        "# C10 Glass Ball generation report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Counts",
        "",
        f"- AGENTS files inspected: {len(inventory_rows)}",
        f"- AGENTS files parsed: {files_parsed}",
        f"- model count: {model_count}",
        f"- distinct model-size count: {model_size_count}",
        "- install lane count: 10",
        f"- profile lane count: {profile_lane_count}",
        f"- matrix row count: {matrix_row_count}",
        f"- JSON stage payload files (stages 3–7): {stage_payload_count}",
        f"- records with unknown limits: {unknown_limit_count}",
        f"- records with conflicts: {conflict_count}",
        f"- P4 deployment variants in AGENTS: {p4_variants if p4_variants is not None else 'n/a'}",
        "",
        "## Skipped / gaps",
        "",
    ]
    for item in skipped[:50]:
        lines.append(f"- {item}")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

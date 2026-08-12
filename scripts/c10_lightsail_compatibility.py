"""AWS Lightsail provider-plan compatibility projection for C10.1-5."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"
CPU_BUNDLES_CSV = MAPPING_DIR / "aws-lightsail-linux-bundles.csv"
GPU_BUNDLES_CSV = MAPPING_DIR / "aws-lightsail-research-gpu-bundles.csv"
PILOT_MENU_JSON = MAPPING_DIR / "8ball-base-pilot-menu.json"
SOURCE_SNAPSHOT_JSON = MAPPING_DIR / "aws-lightsail-source-snapshot.json"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility"
CPU_COMPAT_CSV = COMPAT_DIR / "aws-lightsail-cpu.csv"
GPU_COMPAT_CSV = COMPAT_DIR / "aws-lightsail-gpu.csv"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "aws-lightsail-capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-5-aws-lightsail-capability-report.md"

COMPAT_COLUMNS = [
    "model_id",
    "model_slug",
    "size_slug",
    "ollama_ref",
    "target_lane",
    "provider_plan_id",
    "pilot_menu_band",
    "pilot_candidate_chain",
    "system_ram_gb",
    "included_ssd_gb",
    "accelerator_present",
    "gpu_model",
    "gpu_vram_gb",
    "model_minimum_ram_gb",
    "model_minimum_disk_free_gb",
    "model_minimum_vram_gb",
    "ram_gate",
    "disk_capacity_gate",
    "gpu_vram_gate",
    "compatibility_status",
    "runtime_model_test_required",
    "source_paths",
]

PILOT_OLLAMA_REFS = frozenset(
    {
        "qwen3:0.6b",
        "qwen3:1.7b",
        "qwen3:4b",
        "qwen3:8b",
        "qwen3:14b",
    }
)

FALLBACK_BAND = "fallback-under-4gb"


def _nullish(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"null", "none", "n/a"}:
        return None
    return value


def _parse_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    return text in {"true", "1", "yes"}


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_lightsail_plans(repo_root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = repo_root / "AGENTS" / "data-science" / "profile-mapping"
    cpu_path = mapping / "aws-lightsail-linux-bundles.csv"
    gpu_path = mapping / "aws-lightsail-research-gpu-bundles.csv"
    cpu_plans = [_normalize_plan_row(row) for row in load_csv_rows(cpu_path)]
    gpu_plans = [_normalize_plan_row(row) for row in load_csv_rows(gpu_path)]
    return cpu_plans, gpu_plans


def _normalize_plan_row(row: dict[str, str]) -> dict[str, Any]:
    ram = float(row["system_ram_gb"])
    ssd = float(row["included_ssd_gb"])
    vcpu = int(row["vcpu_count"])
    return {
        "provider": row["provider"],
        "product_line": row["product_line"],
        "provider_plan_id": row["provider_plan_id"],
        "display_name": row["display_name"],
        "target_lane": row["target_lane"],
        "plan_class": row["plan_class"],
        "addressing": row["addressing"],
        "vcpu_count": vcpu,
        "system_ram_gb": ram,
        "included_ssd_gb": ssd,
        "accelerator_present": _parse_bool(row["accelerator_present"]),
        "gpu_model": _nullish(row.get("gpu_model")),
        "gpu_vram_gb": _nullish(row.get("gpu_vram_gb")),
        "source_url": row["source_url"],
        "source_retrieved_at": row["source_retrieved_at"],
        "evidence_level": row["evidence_level"],
        "notes": row.get("notes", ""),
    }


def load_pilot_menu(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    path = repo_root / "AGENTS" / "data-science" / "profile-mapping" / "8ball-base-pilot-menu.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _band_lookup(menu: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {band["pilot_menu_band"]: band for band in menu.get("bands", [])}


def _plan_band(menu: dict[str, Any], plan_id: str) -> str:
    return menu["plan_to_band"][plan_id]


def _chain_for_plan(menu: dict[str, Any], plan_id: str) -> list[str]:
    band_id = _plan_band(menu, plan_id)
    return list(_band_lookup(menu)[band_id]["ordered_pilot_candidates"])


def _disk_threshold_gb(menu: dict[str, Any], band_id: str, ollama_ref: str) -> float | None:
    band = _band_lookup(menu)[band_id]
    mib = band.get("disk_thresholds_mib", {}).get(ollama_ref)
    if mib is None:
        return None
    return round(mib / 1024, 4)


def load_model_id_by_ollama_ref(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    tags_path = repo_root / "data" / "normalized" / "tags.json"
    tags = json.loads(tags_path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for tag in tags:
        oid = tag.get("ollama_identifier")
        mid = tag.get("model_id")
        if oid and mid:
            mapping[oid] = mid
    return mapping


def load_model_pages(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    profiles = repo_root / "profiles"
    pages: dict[str, dict[str, Any]] = {}
    for path in sorted(profiles.glob("*.json")):
        if path.name in {"c10-index.json", "manifest.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == "c10.model-page.v1":
            pages[path.stem] = payload
    return pages


def _model_requirements(ollama_ref: str, menu: dict[str, Any], band_id: str) -> dict[str, float | None]:
    if ollama_ref not in PILOT_OLLAMA_REFS:
        return {
            "model_minimum_ram_gb": None,
            "model_minimum_disk_free_gb": None,
            "model_minimum_vram_gb": None,
        }
    disk_gb = _disk_threshold_gb(menu, band_id, ollama_ref)
    return {
        "model_minimum_ram_gb": None,
        "model_minimum_disk_free_gb": disk_gb,
        "model_minimum_vram_gb": None,
    }


def _evaluate_gates(
    *,
    plan: dict[str, Any],
    ollama_ref: str,
    band_id: str,
    chain: list[str],
    requirements: dict[str, float | None],
    gpu_lane: bool,
) -> dict[str, str]:
    ram_gate = "unknown"
    disk_gate = "unknown"
    if band_id != FALLBACK_BAND and ollama_ref in chain:
        ram_gate = "pass"
    disk_need = requirements["model_minimum_disk_free_gb"]
    if disk_need is not None:
        if plan["included_ssd_gb"] >= disk_need:
            disk_gate = "nominal-pass"
        else:
            disk_gate = "fail"
    gpu_gate = "unknown" if gpu_lane else "not-applicable"
    return {
        "ram_gate": ram_gate,
        "disk_capacity_gate": disk_gate,
        "gpu_vram_gate": gpu_gate,
    }


def _compatibility_status(
    *,
    band_id: str,
    ollama_ref: str,
    chain: list[str],
    gates: dict[str, str],
) -> str:
    if band_id == FALLBACK_BAND:
        return "unknown"
    if ollama_ref not in PILOT_OLLAMA_REFS:
        return "unknown"
    if ollama_ref not in chain:
        return "no-fit"
    if gates["disk_capacity_gate"] == "fail" or gates["ram_gate"] == "fail":
        return "no-fit"
    if gates["disk_capacity_gate"] == "nominal-pass" and gates["ram_gate"] == "pass":
        return "capacity-candidate"
    return "unknown"


def build_compatibility_row(
    *,
    model_id: str,
    model_slug: str,
    size: dict[str, Any],
    plan: dict[str, Any],
    menu: dict[str, Any],
) -> dict[str, Any]:
    plan_id = plan["provider_plan_id"]
    band_id = _plan_band(menu, plan_id)
    chain = _chain_for_plan(menu, plan_id)
    ollama_ref = size["ollama_ref"]
    requirements = _model_requirements(ollama_ref, menu, band_id)
    gpu_lane = plan["target_lane"].endswith("/gpu")
    gates = _evaluate_gates(
        plan=plan,
        ollama_ref=ollama_ref,
        band_id=band_id,
        chain=chain,
        requirements=requirements,
        gpu_lane=gpu_lane,
    )
    status = _compatibility_status(
        band_id=band_id,
        ollama_ref=ollama_ref,
        chain=chain,
        gates=gates,
    )
    source_paths = [
        str(CPU_BUNDLES_CSV.relative_to(REPO_ROOT))
        if plan["target_lane"].endswith("/cpu")
        else str(GPU_BUNDLES_CSV.relative_to(REPO_ROOT)),
        str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
    ]
    if ollama_ref in PILOT_OLLAMA_REFS:
        source_paths.append("install/cloud/aws-lightsail/cpu/8.2.sh")
    return {
        "model_id": model_id,
        "model_slug": model_slug,
        "size_slug": size["size_slug"],
        "ollama_ref": ollama_ref,
        "target_lane": plan["target_lane"],
        "provider_plan_id": plan_id,
        "pilot_menu_band": band_id,
        "pilot_candidate_chain": "|".join(chain),
        "system_ram_gb": plan["system_ram_gb"],
        "included_ssd_gb": plan["included_ssd_gb"],
        "accelerator_present": plan["accelerator_present"],
        "gpu_model": plan["gpu_model"],
        "gpu_vram_gb": plan["gpu_vram_gb"],
        "model_minimum_ram_gb": requirements["model_minimum_ram_gb"],
        "model_minimum_disk_free_gb": requirements["model_minimum_disk_free_gb"],
        "model_minimum_vram_gb": requirements["model_minimum_vram_gb"],
        "ram_gate": gates["ram_gate"],
        "disk_capacity_gate": gates["disk_capacity_gate"],
        "gpu_vram_gate": gates["gpu_vram_gate"],
        "compatibility_status": status,
        "runtime_model_test_required": True,
        "source_paths": "|".join(source_paths),
    }


def build_compatibility_rows(
    model_pages: dict[str, dict[str, Any]],
    plans: list[dict[str, Any]],
    menu: dict[str, Any],
    model_id_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_slug in sorted(model_pages):
        page = model_pages[model_slug]
        for size in page.get("sizes", []):
            ollama_ref = size["ollama_ref"]
            model_id = model_id_map.get(ollama_ref, model_slug)
            for plan in plans:
                rows.append(
                    build_compatibility_row(
                        model_id=model_id,
                        model_slug=model_slug,
                        size=size,
                        plan=plan,
                        menu=menu,
                    )
                )
    return rows


def write_compat_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPAT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["accelerator_present"] = str(out["accelerator_present"]).lower()
            out["runtime_model_test_required"] = str(out["runtime_model_test_required"]).lower()
            for key in (
                "model_minimum_ram_gb",
                "model_minimum_disk_free_gb",
                "model_minimum_vram_gb",
                "gpu_model",
                "gpu_vram_gb",
            ):
                if out[key] is None:
                    out[key] = ""
            writer.writerow(out)


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["compatibility_status"] for row in rows))


def build_report(
    cpu_plans: list[dict[str, Any]],
    gpu_plans: list[dict[str, Any]],
    cpu_rows: list[dict[str, Any]],
    gpu_rows: list[dict[str, Any]],
    menu: dict[str, Any],
) -> dict[str, Any]:
    band_counts = Counter(menu["plan_to_band"].values())
    return {
        "schema_version": "c10.lightsail-capability-report.v1",
        "plan_counts": {
            "cpu_base_pilot": len(cpu_plans),
            "gpu_research": len(gpu_plans),
            "total": len(cpu_plans) + len(gpu_plans),
        },
        "target_lanes": {
            "cloud/aws-lightsail/cpu": [p["provider_plan_id"] for p in cpu_plans],
            "cloud/aws-lightsail/gpu": [p["provider_plan_id"] for p in gpu_plans],
        },
        "pilot_menu_band_counts": dict(band_counts),
        "compatibility_row_counts": {
            "cloud/aws-lightsail/cpu": len(cpu_rows),
            "cloud/aws-lightsail/gpu": len(gpu_rows),
        },
        "compatibility_status_counts": {
            "cloud/aws-lightsail/cpu": _status_counts(cpu_rows),
            "cloud/aws-lightsail/gpu": _status_counts(gpu_rows),
        },
        "gpu_model_unknown": all(p["gpu_model"] is None for p in gpu_plans),
        "gpu_vram_unknown": all(p["gpu_vram_gb"] is None for p in gpu_plans),
        "model_requirements_formula_generated": False,
        "source_paths": [
            str(CPU_BUNDLES_CSV.relative_to(REPO_ROOT)),
            str(GPU_BUNDLES_CSV.relative_to(REPO_ROOT)),
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
            str(SOURCE_SNAPSHOT_JSON.relative_to(REPO_ROOT)),
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    cpu_status = report["compatibility_status_counts"]["cloud/aws-lightsail/cpu"]
    gpu_status = report["compatibility_status_counts"]["cloud/aws-lightsail/gpu"]
    lines = [
        "# C10.1-5 AWS Lightsail capability report",
        "",
        "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_lightsail_compatibility.py`.",
        "",
        "## Plan inventory",
        "",
        f"- CPU base-pilot plans: **{report['plan_counts']['cpu_base_pilot']}**",
        f"- GPU research plans: **{report['plan_counts']['gpu_research']}**",
        "",
        "## Pilot menu band counts",
        "",
    ]
    for band, count in sorted(report["pilot_menu_band_counts"].items()):
        lines.append(f"- `{band}`: {count}")
    lines.extend(
        [
            "",
            "## Compatibility projection row counts",
            "",
            f"- `cloud/aws-lightsail/cpu`: {report['compatibility_row_counts']['cloud/aws-lightsail/cpu']}",
            f"- `cloud/aws-lightsail/gpu`: {report['compatibility_row_counts']['cloud/aws-lightsail/gpu']}",
            "",
            "## Compatibility status counts",
            "",
            "### CPU lane",
            "",
        ]
    )
    for status, count in sorted(cpu_status.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "### GPU lane", ""])
    for status, count in sorted(gpu_status.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            "## Evidence posture",
            "",
            f"- GPU model unknown: **{report['gpu_model_unknown']}**",
            f"- GPU VRAM unknown: **{report['gpu_vram_unknown']}**",
            f"- Model requirements formula-generated in this pass: **{report['model_requirements_formula_generated']}**",
            "",
            "Nominal SSD comparisons use `nominal-pass` and do not replace installer free-disk checks.",
            "Capacity-candidate rows are not proof of successful model execution.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_readme() -> None:
    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    readme = COMPAT_DIR / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Provider compatibility projections",
                "",
                "Plan-level compatibility matrices live outside the model profile tree.",
                "They join each normalized model size with published provider plan capacity",
                "without multiplying `profiles/index.csv` or adding plan folders under models.",
                "",
                "## AWS Lightsail (C10.1-5)",
                "",
                "- `aws-lightsail-cpu.csv` — 11 Linux/Unix general-purpose bundles × all C10 sizes",
                "- `aws-lightsail-gpu.csv` — 3 Lightsail for Research GPU plans × all C10 sizes",
                "",
                "Source tables:",
                "- `AGENTS/data-science/profile-mapping/aws-lightsail-linux-bundles.csv`",
                "- `AGENTS/data-science/profile-mapping/aws-lightsail-research-gpu-bundles.csv`",
                "- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`",
                "",
                "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def generate_lightsail_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    cpu_plans, gpu_plans = load_lightsail_plans(repo_root)
    menu = load_pilot_menu(repo_root)
    model_pages = load_model_pages(repo_root)
    model_id_map = load_model_id_by_ollama_ref(repo_root)

    cpu_rows = build_compatibility_rows(model_pages, cpu_plans, menu, model_id_map)
    gpu_rows = build_compatibility_rows(model_pages, gpu_plans, menu, model_id_map)

    write_compat_csv(CPU_COMPAT_CSV, cpu_rows)
    write_compat_csv(GPU_COMPAT_CSV, gpu_rows)
    write_readme()

    report = build_report(cpu_plans, gpu_plans, cpu_rows, gpu_rows, menu)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report_markdown(report), encoding="utf-8")

    return {
        "cpu_plan_count": len(cpu_plans),
        "gpu_plan_count": len(gpu_plans),
        "cpu_compat_rows": len(cpu_rows),
        "gpu_compat_rows": len(gpu_rows),
        "cpu_status_counts": report["compatibility_status_counts"]["cloud/aws-lightsail/cpu"],
        "gpu_status_counts": report["compatibility_status_counts"]["cloud/aws-lightsail/gpu"],
    }


def validate_lightsail_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    cpu_plans, gpu_plans = load_lightsail_plans(repo_root)
    if len(cpu_plans) != 11:
        errors.append(f"Expected 11 CPU Lightsail plans, found {len(cpu_plans)}")
    if len(gpu_plans) != 3:
        errors.append(f"Expected 3 GPU Lightsail plans, found {len(gpu_plans)}")

    keys: set[tuple[str, str, str]] = set()
    for plan in cpu_plans + gpu_plans:
        key = (plan["provider"], plan["product_line"], plan["provider_plan_id"])
        if key in keys:
            errors.append(f"Duplicate plan key: {key}")
        keys.add(key)
        for field in (
            "source_url",
            "source_retrieved_at",
            "evidence_level",
            "target_lane",
            "system_ram_gb",
            "vcpu_count",
            "included_ssd_gb",
        ):
            if plan.get(field) in (None, ""):
                errors.append(f"Plan {plan['provider_plan_id']} missing {field}")

    menu = load_pilot_menu(repo_root)
    expected_band_map = menu.get("plan_to_band", {})
    for plan in cpu_plans + gpu_plans:
        plan_id = plan["provider_plan_id"]
        if plan_id not in expected_band_map:
            errors.append(f"Plan {plan_id} missing pilot_menu_band mapping")
        chain = _chain_for_plan(menu, plan_id)
        if not chain:
            errors.append(f"Plan {plan_id} has empty pilot_candidate_chain")

    for gpu_plan in gpu_plans:
        if gpu_plan["gpu_model"] is not None:
            errors.append(f"GPU plan {gpu_plan['provider_plan_id']} must keep gpu_model null")
        if gpu_plan["gpu_vram_gb"] is not None:
            errors.append(f"GPU plan {gpu_plan['provider_plan_id']} must keep gpu_vram_gb null")

    if not CPU_COMPAT_CSV.is_file() or not GPU_COMPAT_CSV.is_file():
        errors.append("Missing provider compatibility CSV outputs")
    else:
        for path in (CPU_COMPAT_CSV, GPU_COMPAT_CSV):
            rows = load_csv_rows(path)
            if not rows:
                errors.append(f"Empty compatibility CSV: {path}")
            for row in rows:
                if path == GPU_COMPAT_CSV and row.get("gpu_vram_gate") != "unknown":
                    errors.append(
                        f"GPU row must keep gpu_vram_gate=unknown: {row.get('provider_plan_id')}:{row.get('ollama_ref')}"
                    )
                if row.get("provider_plan_id") in {
                    "lightsail-linux-gp-nano-0.5gb-ipv4",
                    "lightsail-linux-gp-micro-1gb-ipv4",
                    "lightsail-linux-gp-small-2gb-ipv4",
                } and row.get("compatibility_status") == "capacity-candidate":
                    errors.append(
                        f"Sub-4GB plan must not be capacity-candidate: {row.get('provider_plan_id')}:{row.get('ollama_ref')}"
                    )

    index_csv = repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

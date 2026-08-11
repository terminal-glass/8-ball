"""Shared C10 fit evaluation and provider CSV parsing."""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([bmk])", re.I)
UNKNOWN_TOKENS = frozenset({"", "unknown", "null", "n/a", "na", "runtime_detection_required", "unverified"})


class FitResult(NamedTuple):
    fit_status: str  # fit | no_fit | unknown
    fits: bool
    reason: str
    missing_evidence: tuple[str, ...] = ()


def parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in UNKNOWN_TOKENS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_numeric(value)
    if number is None:
        return None
    return int(number)


def parse_gpu_count(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in UNKNOWN_TOKENS:
        return None
    if "|" in text:
        counts = [parse_int(part) for part in text.split("|")]
        valid = [count for count in counts if count is not None]
        return min(valid) if valid else None
    return parse_int(text)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_digitalocean_gpu_plans(repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    csv_path = repo_root / "AGENTS/data-science/profile-mapping/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv"
    if not csv_path.is_file():
        return []
    plans: list[dict[str, Any]] = []
    for row in load_csv_rows(csv_path):
        gpu_count = parse_gpu_count(row.get("gpu_count_options"))
        vram_per_gpu = parse_numeric(row.get("vram_gb_per_gpu"))
        total_vram = None
        if gpu_count is not None and vram_per_gpu is not None:
            total_vram = round(gpu_count * vram_per_gpu, 2)
        plans.append(
            {
                "plan_id": row.get("internal_plan_id"),
                "display_name": row.get("display_name"),
                "vcpu": parse_int(row.get("vcpus")),
                "ram_gb": parse_numeric(row.get("system_ram_gib")),
                "disk_gb": parse_numeric(row.get("boot_disk_gib")),
                "gpu_count": gpu_count,
                "vram_gb_per_gpu": vram_per_gpu,
                "total_vram_gb": total_vram,
                "source_path": str(csv_path.relative_to(repo_root)),
            }
        )
    return plans


def smallest_digitalocean_gpu_plan(plans: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not plans:
        return None
    return min(
        plans,
        key=lambda plan: (
            plan.get("total_vram_gb") if plan.get("total_vram_gb") is not None else float("inf"),
            plan.get("ram_gb") if plan.get("ram_gb") is not None else float("inf"),
            plan.get("disk_gb") if plan.get("disk_gb") is not None else float("inf"),
        ),
    )


def load_aws_lightsail_gpu_plans(repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    canonical_path = (
        repo_root / "AGENTS/data-science/profile-mapping/aws-lightsail-research-gpu-bundles.csv"
    )
    if canonical_path.is_file():
        plans: list[dict[str, Any]] = []
        for row in load_csv_rows(canonical_path):
            plan_id = row.get("provider_plan_id")
            ram = parse_numeric(row.get("system_ram_gb"))
            disk = parse_numeric(row.get("included_ssd_gb"))
            plans.append(
                {
                    "plan_id": plan_id,
                    "plan_name": row.get("display_name") or plan_id,
                    "vcpu": parse_int(row.get("vcpu_count")),
                    "ram_gb": ram,
                    "disk_gb": disk,
                    "gpu_count": 1 if str(row.get("accelerator_present", "")).lower() == "true" else None,
                    "vram_gb_per_gpu": None,
                    "total_vram_gb": None,
                    "cuda_expected": "runtime_detection_required",
                    "ollama_gpu_expected": "unknown",
                    "evidence_status": row.get("evidence_level") or "provider_published",
                    "source_path": str(canonical_path.relative_to(repo_root)),
                    "source_reference": row.get("source_url"),
                }
            )
        return plans

    research_path = repo_root / "AGENTS/data-science/profile-mapping/TG-8Ball-AWS-Lightsail-Research-GPU-Plans.csv"
    provisional_path = (
        repo_root / "AGENTS/data-science/profile-mapping/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv"
    )
    research_by_plan: dict[str, dict[str, str]] = {}
    if research_path.is_file():
        for row in load_csv_rows(research_path):
            legacy_plan_id = row.get("provider_plan_id") or row.get("plan_id")
            if legacy_plan_id:
                research_by_plan[legacy_plan_id] = row

    if provisional_path.is_file():
        source_path = str(provisional_path.relative_to(repo_root))
        rows = load_csv_rows(provisional_path)
    elif research_path.is_file():
        source_path = str(research_path.relative_to(repo_root))
        rows = load_csv_rows(research_path)
    else:
        return []

    plans = []
    for row in rows:
        plan_id = row.get("plan_id") or row.get("provider_plan_id")
        research = research_by_plan.get(plan_id or "", {})
        ram = parse_numeric(
            row.get("system_ram_gib")
            or row.get("system_ram_gb")
            or research.get("system_ram_gb")
        )
        disk = parse_numeric(
            row.get("boot_disk_gib") or row.get("storage_gb") or research.get("storage_gb")
        )
        vram_per = parse_numeric(row.get("vram_gib_per_gpu") or row.get("vram_gb"))
        gpu_count = parse_gpu_count(row.get("gpu_count"))
        total_vram = parse_numeric(row.get("total_vram_gib"))
        if total_vram is None and gpu_count is not None and vram_per is not None:
            total_vram = round(gpu_count * vram_per, 2)
        plans.append(
            {
                "plan_id": plan_id,
                "plan_name": row.get("plan_name") or research.get("display_name") or plan_id,
                "vcpu": parse_int(row.get("vcpus") or research.get("vcpus")),
                "ram_gb": ram,
                "disk_gb": disk,
                "gpu_count": gpu_count,
                "vram_gb_per_gpu": vram_per,
                "total_vram_gb": total_vram,
                "cuda_expected": row.get("cuda_expected") or row.get("cuda_status"),
                "ollama_gpu_expected": row.get("ollama_gpu_expected")
                or row.get("ollama_support_status"),
                "evidence_status": row.get("evidence_status") or row.get("provenance_status"),
                "declared_gpu_behavior": row.get("declared_gpu_behavior"),
                "most_probable_runtime_behavior": row.get("most_probable_runtime_behavior"),
                "confidence": row.get("confidence"),
                "verification_commands": row.get("verification_commands"),
                "source_path": source_path,
                "source_reference": row.get("source_reference")
                or row.get("source_url")
                or str(research_path.relative_to(repo_root)),
            }
        )
    return plans


def smallest_aws_lightsail_gpu_plan(plans: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not plans:
        return None
    return min(
        plans,
        key=lambda plan: (
            plan.get("ram_gb") if plan.get("ram_gb") is not None else float("inf"),
            plan.get("disk_gb") if plan.get("disk_gb") is not None else float("inf"),
        ),
    )


def normalize_lane_hardware(hardware: dict[str, Any], lane: dict[str, Any]) -> dict[str, Any]:
    hw = dict(hardware)
    if not lane.get("gpu_lane"):
        hw["cuda_available"] = False
        hw["total_vram_gb"] = None
        hw["vram_gb_per_gpu"] = None
        hw["apple_metal_available"] = False
    return hw


def evaluate_ram_fit(
    size: dict[str, Any],
    hardware: dict[str, Any],
) -> FitResult:
    est = size.get("estimated") or {}
    ram_need = est.get("min_system_ram_gb")
    usable_ram = hardware.get("usable_model_ram_gb")
    system_ram = hardware.get("system_ram_gb")
    ram_avail = usable_ram if usable_ram is not None else system_ram
    missing: list[str] = []

    if ram_need is None:
        missing.append("model_ram_requirement")
    if ram_avail is None:
        missing.append("lane_ram_capacity")

    if ram_need is not None and ram_avail is not None and ram_need > ram_avail:
        return FitResult(
            "no_fit",
            False,
            f"requires {ram_need} GB RAM; lane provides {ram_avail} GB usable",
            tuple(missing),
        )

    if missing:
        return FitResult(
            "unknown",
            False,
            f"missing evidence: {', '.join(sorted(set(missing)))}",
            tuple(sorted(set(missing))),
        )

    return FitResult("fit", True, "fits lane RAM assumptions", ())


def evaluate_lane_fit(
    size: dict[str, Any],
    lane: dict[str, Any],
    hardware: dict[str, Any],
) -> FitResult:
    est = size.get("estimated") or {}
    ram_need = est.get("min_system_ram_gb")
    vram_need = est.get("min_vram_gb")
    disk_need = est.get("min_disk_gb")
    usable_ram = hardware.get("usable_model_ram_gb")
    system_ram = hardware.get("system_ram_gb")
    ram_avail = usable_ram if usable_ram is not None else system_ram
    disk_avail = hardware.get("minimum_free_disk_gb")
    total_vram = hardware.get("total_vram_gb")
    gpu_lane = bool(lane.get("gpu_lane"))
    missing: list[str] = []

    if ram_need is None:
        missing.append("model_ram_requirement")
    if disk_need is None:
        missing.append("model_disk_requirement")
    if gpu_lane:
        if vram_need is None:
            missing.append("model_vram_requirement")
        if total_vram is None:
            missing.append("lane_vram_capacity")
        cuda_available = hardware.get("cuda_available")
        if cuda_available is None:
            missing.append("cuda_runtime_verification")

    if ram_need is not None and ram_avail is not None and ram_need > ram_avail:
        return FitResult(
            "no_fit",
            False,
            f"requires {ram_need} GB RAM; lane provides {ram_avail} GB usable",
            tuple(missing),
        )
    if disk_need is not None and disk_avail is not None and disk_need > disk_avail:
        return FitResult(
            "no_fit",
            False,
            f"requires {disk_need} GB disk; lane minimum free disk is {disk_avail} GB",
            tuple(missing),
        )
    if gpu_lane and vram_need is not None and total_vram is not None and vram_need > total_vram:
        return FitResult(
            "no_fit",
            False,
            f"requires {vram_need} GB VRAM; lane provides {total_vram} GB",
            tuple(missing),
        )
    if not gpu_lane and vram_need is not None and ram_avail is not None and vram_need > ram_avail:
        return FitResult(
            "no_fit",
            False,
            f"CPU lane cannot satisfy VRAM-heavy size ({vram_need} GB estimated)",
            tuple(missing),
        )

    if missing:
        return FitResult(
            "unknown",
            False,
            f"missing evidence: {', '.join(sorted(set(missing)))}",
            tuple(sorted(set(missing))),
        )

    return FitResult("fit", True, "fits lane hardware assumptions", ())


def semantic_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_body = {key: value for key, value in left.items() if key != "generated_at"}
    right_body = {key: value for key, value in right.items() if key != "generated_at"}
    return left_body == right_body


def write_json_preserve_timestamp(path: Path, payload: dict[str, Any], *, build_timestamp: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = dict(payload)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if semantic_equal(existing, output):
            output["generated_at"] = existing.get("generated_at", output.get("generated_at"))
    elif build_timestamp:
        output["generated_at"] = build_timestamp
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_timestamp() -> str:
    return os.environ.get("C10_BUILD_TIMESTAMP", "").strip() or __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

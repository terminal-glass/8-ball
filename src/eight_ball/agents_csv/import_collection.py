from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eight_ball.agents_csv.keys import record_dedup_key
from eight_ball.agents_csv.loader import LoadedRow, load_source_rows
from eight_ball.agents_csv.normalize import (
    accelerator_flags,
    as_optional_bool,
    as_optional_float,
    as_optional_int,
    as_optional_string,
)
from eight_ball.agents_csv.registry import SourceSpec, precedence_rank, source_specs
from eight_ball.agents_csv.validate import validate_agents_csv_collection
from eight_ball.config import load_json, write_json
from eight_ball.paths import (
    GENERATED_DIR,
    NORMALIZED_DIR,
    REPO_ROOT,
)


class HardwareImportError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} hardware import error(s)")


@dataclass
class FileAuditEntry:
    path: str
    classification: str
    imported: bool
    primary_key: str
    row_count: int
    imported_count: int
    rejected_rows: list[dict[str, Any]] = field(default_factory=list)
    true_duplicates: list[str] = field(default_factory=list)
    intentional_overlaps: list[str] = field(default_factory=list)
    provenance_statuses: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class ImportReport:
    ok: bool
    generated_at: str
    files: list[FileAuditEntry] = field(default_factory=list)
    counts_by_namespace: dict[str, int] = field(default_factory=dict)
    provider_cpu_count: int = 0
    provider_gpu_count: int = 0
    assumed_profile_count: int = 0
    measured_host_count: int = 0
    accelerator_class_count: int = 0
    deployment_type_count: int = 0
    true_duplicate_keys: list[dict[str, Any]] = field(default_factory=list)
    intentional_overlaps: list[dict[str, Any]] = field(default_factory=list)
    rejected_rows: list[dict[str, Any]] = field(default_factory=list)
    unknown_fields: list[dict[str, Any]] = field(default_factory=list)
    count_contract_checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    canonical_paths: dict[str, str] = field(default_factory=dict)


def discover_agents_csv_files(*, repo_root: Path = REPO_ROOT) -> list[Path]:
    return sorted(
        (repo_root / "AGENTS" / "data-science" / "profile-mapping").glob("TG-8Ball-*.csv")
    )


def _classification_label(namespace: str, *, classification_kind: str | None = None) -> str:
    if namespace == "classification_data" and classification_kind == "accelerator":
        return "accelerator_classification"
    if namespace == "classification_data" and classification_kind == "deployment":
        return "accelerator_classification"
    if namespace == "classification_data":
        return "accelerator_classification"
    return namespace


def _provider_plan_id(record: dict[str, Any], source: SourceSpec) -> str | None:
    for field_name in (
        source.options.get("plan_id_field"),
        "provider_plan_id",
        "internal_plan_id",
        "plan_slug",
        "bundle_id",
    ):
        if not field_name:
            continue
        value = as_optional_string(record.get(field_name))
        if value:
            return value
    return None


def _provider_fields(record: dict[str, Any], source: SourceSpec) -> tuple[str | None, str | None]:
    provider = as_optional_string(source.options.get("provider_value")) or as_optional_string(
        record.get(source.options.get("provider_field", "provider"))
    )
    product_line = as_optional_string(source.options.get("product_line_value")) or as_optional_string(
        record.get(source.options.get("product_line_field", "product_line"))
    )
    return provider, product_line


def _build_provider_instance(record: dict[str, Any], row: LoadedRow) -> dict[str, Any]:
    source = row.source
    provider, product_line = _provider_fields(record, source)
    plan_id = _provider_plan_id(record, source)
    dedup_key = record_dedup_key(record, source)
    accelerator_class_id = as_optional_string(record.get("accelerator_class_id")) or "none_cpu_only"
    flags = accelerator_flags(accelerator_class_id)
    gpu_count = as_optional_int(record.get("gpu_count"))
    if gpu_count is None:
        gpu_count = as_optional_int(record.get("gpu_count_options"))
    vram_per = as_optional_float(record.get("vram_gb_per_gpu")) or as_optional_float(
        record.get("vram_gb")
    )
    total_vram = None
    if vram_per is not None and gpu_count is not None:
        total_vram = vram_per * gpu_count
    system_ram = (
        as_optional_float(record.get("system_ram_gb"))
        or as_optional_float(record.get("system_ram_gib"))
        or as_optional_float(record.get("ram_gb"))
    )
    storage = (
        as_optional_float(record.get("storage_gb"))
        or as_optional_float(record.get("boot_disk_gib"))
        or as_optional_float(record.get("disk_gb"))
    )
    provenance = (
        as_optional_string(record.get("provenance_status"))
        or as_optional_string(record.get("source_status"))
        or "unknown"
    )
    return {
        "id": dedup_key,
        "record_type": "provider_instance",
        "provider": provider,
        "product_line": product_line,
        "provider_plan_id": plan_id,
        "display_name": as_optional_string(record.get("display_name")),
        "os_family": as_optional_string(record.get("os_family"))
        or as_optional_string(record.get("operating_system")),
        "architecture": as_optional_string(record.get("architecture")),
        "cpu_count": as_optional_int(record.get("cpu_count"))
        or as_optional_int(record.get("vcpus"))
        or as_optional_int(record.get("vcpu")),
        "system_ram_gb": system_ram,
        "usable_model_ram_gb": as_optional_float(record.get("usable_model_ram_gb")),
        "storage_gb": storage,
        "minimum_free_disk_gb": as_optional_float(record.get("minimum_free_disk_gb")),
        "gpu_vendor": as_optional_string(record.get("gpu_vendor")),
        "gpu_model": as_optional_string(record.get("gpu_model")),
        "gpu_count": gpu_count,
        "gpu_count_options": as_optional_string(record.get("gpu_count_options")),
        "vram_gb_per_gpu": vram_per,
        "total_vram_gb": total_vram,
        "accelerator_class_id": accelerator_class_id,
        "cuda_available": flags["cuda_available"],
        "rocm_available": flags["rocm_available"],
        "apple_metal_available": flags["apple_metal_available"],
        "deployment_type_id": as_optional_string(record.get("deployment_type_id")),
        "provenance_status": provenance,
        "source_reference": as_optional_string(record.get("source_url"))
        or as_optional_string(record.get("source_reference")),
        "validation_status": "imported",
        "notes": as_optional_string(record.get("notes")),
        "source_file": source.path,
        "source_id": source.id,
        "source_row": row.row_number,
    }


def _build_assumed_profile(record: dict[str, Any], row: LoadedRow) -> dict[str, Any]:
    source = row.source
    dedup_key = record_dedup_key(record, source)
    accelerator_class_id = as_optional_string(record.get("accelerator_class_id"))
    flags = accelerator_flags(accelerator_class_id)
    cuda_from_field = as_optional_bool(record.get("cuda_available"))
    return {
        "id": dedup_key,
        "record_type": "assumed_hardware_profile",
        "profile_id": as_optional_string(record.get("profile_id")),
        "display_name": as_optional_string(record.get("display_name")),
        "os_family": as_optional_string(record.get("os_family")),
        "architecture": as_optional_string(record.get("architecture")),
        "cpu_class": as_optional_string(record.get("cpu_class")),
        "cpu_count": as_optional_int(record.get("assumed_cpu_cores"))
        or as_optional_int(record.get("vcpu_minimum")),
        "system_ram_gb": as_optional_float(record.get("ram_gb"))
        or as_optional_float(record.get("system_ram_gb_minimum")),
        "usable_model_ram_gb": as_optional_float(record.get("usable_model_ram_gb")),
        "storage_gb": as_optional_float(record.get("storage_total_gb"))
        or as_optional_float(record.get("disk_gb_minimum")),
        "minimum_free_disk_gb": as_optional_float(record.get("minimum_free_disk_gb"))
        or as_optional_float(record.get("disk_gb_minimum")),
        "gpu_present": as_optional_bool(record.get("gpu_present")),
        "gpu_vendor": None,
        "gpu_model": as_optional_string(record.get("gpu_class")),
        "gpu_count": None,
        "vram_gb_per_gpu": as_optional_float(record.get("vram_gb_minimum")),
        "total_vram_gb": as_optional_float(record.get("vram_gb_recommended")),
        "accelerator_class_id": accelerator_class_id,
        "cuda_available": cuda_from_field if cuda_from_field is not None else flags["cuda_available"],
        "rocm_available": flags["rocm_available"],
        "apple_metal_available": flags["apple_metal_available"],
        "deployment_type_id": as_optional_string(record.get("deployment_type_id")),
        "menu_label": as_optional_string(record.get("menu_label")),
        "provenance_status": as_optional_string(record.get("provenance_status")) or "unknown",
        "source_reference": source.path,
        "validation_status": "imported",
        "notes": as_optional_string(record.get("source_notes"))
        or as_optional_string(record.get("fallback_notes")),
        "source_file": source.path,
        "source_id": source.id,
        "source_row": row.row_number,
    }


def _build_measured_host(record: dict[str, Any], row: LoadedRow) -> dict[str, Any]:
    source = row.source
    dedup_key = record_dedup_key(record, source)
    accelerator_class_id = as_optional_string(record.get("accelerator_class_id"))
    flags = accelerator_flags(accelerator_class_id)
    vram_mib = as_optional_float(record.get("vram_mib"))
    vram_gb = vram_mib / 1024 if vram_mib is not None else None
    return {
        "id": dedup_key,
        "record_type": "measured_hardware_host",
        "host_profile_id": as_optional_string(record.get("host_profile_id")),
        "host_name": as_optional_string(record.get("host_name")),
        "environment_type": as_optional_string(record.get("environment_type")),
        "os_family": as_optional_string(record.get("os")),
        "architecture": as_optional_string(record.get("architecture")),
        "cpu_count": as_optional_int(record.get("cpu_threads")),
        "system_ram_gb": as_optional_float(record.get("system_ram_gb")),
        "storage_gb": as_optional_float(record.get("root_disk_gb")),
        "gpu_vendor": as_optional_string(record.get("gpu_vendor")),
        "gpu_model": as_optional_string(record.get("gpu_model")),
        "gpu_count": as_optional_int(record.get("gpu_count")),
        "vram_gb_per_gpu": vram_gb,
        "total_vram_gb": vram_gb,
        "accelerator_class_id": accelerator_class_id,
        "cuda_available": flags["cuda_available"],
        "rocm_available": flags["rocm_available"],
        "apple_metal_available": flags["apple_metal_available"],
        "deployment_type_id": as_optional_string(record.get("deployment_type_id")),
        "provenance_status": as_optional_string(record.get("provenance_status"))
        or "measured_host_inventory",
        "ollama_inference_verified": as_optional_bool(record.get("ollama_inference_verified")),
        "source_reference": as_optional_string(record.get("source_reference")),
        "measured_at_utc": as_optional_string(record.get("measured_at_utc")),
        "validation_status": "imported",
        "notes": as_optional_string(record.get("notes")),
        "source_file": source.path,
        "source_id": source.id,
        "source_row": row.row_number,
    }


def _build_accelerator_class(record: dict[str, Any], row: LoadedRow) -> dict[str, Any]:
    source = row.source
    dedup_key = record_dedup_key(record, source)
    accelerator_class_id = as_optional_string(record.get("accelerator_class_id"))
    flags = accelerator_flags(accelerator_class_id)
    return {
        "id": dedup_key,
        "record_type": "accelerator_class",
        "accelerator_class_id": accelerator_class_id,
        "display_name": as_optional_string(record.get("display_name")),
        "vendor": as_optional_string(record.get("vendor")),
        "backend": as_optional_string(record.get("backend")),
        "platform_scope": as_optional_string(record.get("platform_scope")),
        "cuda_available": flags["cuda_available"],
        "rocm_available": flags["rocm_available"],
        "apple_metal_available": flags["apple_metal_available"],
        "deployment_type_id": None,
        "provenance_status": as_optional_string(record.get("provenance_status")) or "unknown",
        "source_reference": as_optional_string(record.get("source_url")),
        "validation_status": "imported",
        "notes": as_optional_string(record.get("notes")),
        "source_file": source.path,
        "source_id": source.id,
        "source_row": row.row_number,
    }


def _build_deployment_type(record: dict[str, Any], row: LoadedRow) -> dict[str, Any]:
    source = row.source
    dedup_key = record_dedup_key(record, source)
    return {
        "id": dedup_key,
        "record_type": "deployment_type",
        "deployment_type_id": as_optional_string(record.get("deployment_type_id")),
        "display_name": as_optional_string(record.get("display_name")),
        "description": as_optional_string(record.get("description")),
        "provenance_status": "internal_classification",
        "source_reference": source.path,
        "validation_status": "imported",
        "notes": None,
        "source_file": source.path,
        "source_id": source.id,
        "source_row": row.row_number,
    }


def _validate_record_semantics(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    record_type = record.get("record_type")
    accelerator_class_id = (record.get("accelerator_class_id") or "").lower()
    gpu_vendor = (record.get("gpu_vendor") or "").lower()

    if record_type == "provider_instance":
        if gpu_vendor == "amd" and record.get("cuda_available") is True:
            errors.append(f"{record['id']}: AMD provider row must not be labeled CUDA")
        if accelerator_class_id == "amd_rocm" and record.get("cuda_available") is True:
            errors.append(f"{record['id']}: amd_rocm accelerator must not be labeled CUDA")
        if accelerator_class_id == "apple_metal" and record.get("cuda_available") is True:
            errors.append(f"{record['id']}: apple_metal accelerator must not be labeled CUDA")
        if "lightsail for research" in (record.get("product_line") or "").lower():
            gpu_model = (record.get("gpu_model") or "").lower()
            if gpu_model and gpu_model != "unknown":
                errors.append(
                    f"{record['id']}: Lightsail Research GPU must preserve unknown GPU model"
                )
            vram = record.get("vram_gb_per_gpu")
            if vram is not None:
                errors.append(
                    f"{record['id']}: Lightsail Research GPU must preserve unknown VRAM"
                )
        if record.get("provenance_status", "").lower().startswith("measured"):
            errors.append(f"{record['id']}: provider row must not claim measured provenance")

    if record_type == "measured_hardware_host" and record.get("ollama_inference_verified") is True:
        errors.append(f"{record['id']}: measured host must not claim Ollama benchmark without evidence")

    if record_type == "assumed_hardware_profile":
        if accelerator_class_id == "amd_rocm" and record.get("cuda_available") is True:
            errors.append(f"{record['id']}: AMD assumed profile must not be labeled CUDA")
        if accelerator_class_id == "apple_metal" and record.get("cuda_available") is True:
            errors.append(f"{record['id']}: Apple Metal profile must not be labeled CUDA")

    return errors


def _collect_unknown_fields(record: dict[str, Any]) -> list[dict[str, Any]]:
    unknowns: list[dict[str, Any]] = []
    for field_name in (
        "gpu_model",
        "gpu_vendor",
        "vram_gb_per_gpu",
        "total_vram_gb",
        "system_ram_gb",
        "cpu_count",
        "deployment_type_id",
    ):
        if record.get(field_name) is None:
            unknowns.append({"record_id": record["id"], "field": field_name})
    return unknowns


def _parse_recovered_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.is_file():
        return counts
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metric = (row.get("metric") or row.get("Metric") or "").strip()
            value = (row.get("value") or row.get("Value") or "").strip()
            if not metric or not value.isdigit():
                continue
            counts[metric.lower()] = int(value)
    return counts


def _dedupe_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["id"]].append(record)

    selected: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    errors: list[str] = []

    for record_id, items in sorted(grouped.items()):
        if len(items) == 1:
            selected.append(items[0])
            continue
        duplicates.append(
            {
                "id": record_id,
                "occurrences": [
                    {
                        "source_file": item["source_file"],
                        "source_row": item["source_row"],
                        "provenance_status": item.get("provenance_status"),
                        "precedence": precedence_rank(item.get("provenance_status")),
                    }
                    for item in items
                ],
            }
        )
        ranked = sorted(
            items,
            key=lambda item: precedence_rank(item.get("provenance_status")),
            reverse=True,
        )
        top_rank = precedence_rank(ranked[0].get("provenance_status"))
        low_rank = precedence_rank(ranked[-1].get("provenance_status"))
        if top_rank > low_rank:
            errors.append(
                f"lower-confidence record would overwrite higher-confidence data for {record_id}"
            )
        selected.append(ranked[0])

    return selected, duplicates, errors


def import_hardware_collection(
    *,
    repo_root: Path = REPO_ROOT,
    normalized_dir: Path = NORMALIZED_DIR,
    write_outputs: bool = True,
) -> ImportReport:
    from eight_ball.provenance import utc_now_iso

    validation = validate_agents_csv_collection(repo_root=repo_root)
    report = ImportReport(ok=True, generated_at=utc_now_iso())
    if not validation.ok:
        report.ok = False
        report.errors.extend(validation.errors)
        return report

    discovered = discover_agents_csv_files(repo_root=repo_root)
    registered_csv_paths = {
        spec.path
        for spec in source_specs()
        if spec.path.startswith("AGENTS/") and spec.path.endswith(".csv")
    }
    discovered_paths = {str(path.relative_to(repo_root)) for path in discovered}
    unclassified = sorted(discovered_paths - registered_csv_paths)
    if unclassified:
        report.ok = False
        report.errors.extend(f"unclassified AGENTS CSV file: {path}" for path in unclassified)

    missing = sorted(registered_csv_paths - discovered_paths)
    if missing:
        report.warnings.extend(f"registered CSV file missing on disk: {path}" for path in missing)

    provider_instances: list[dict[str, Any]] = []
    assumed_profiles: list[dict[str, Any]] = []
    measured_hosts: list[dict[str, Any]] = []
    accelerator_classes: list[dict[str, Any]] = []
    deployment_types: list[dict[str, Any]] = []
    file_audits: list[FileAuditEntry] = []

    for source in source_specs():
        classification = _classification_label(
            source.namespace,
            classification_kind=source.options.get("classification_kind"),
        )
        primary_key = {
            "provider_instance_data": "provider + product_line + provider_plan_id",
            "assumed_hardware_profiles": "profile_id",
            "measured_hardware_inventory": "host_profile_id",
            "classification_data": "accelerator_class_id or deployment_type_id",
            "control_and_provenance": "control row (not imported)",
        }.get(source.namespace, source.namespace)

        audit = FileAuditEntry(
            path=source.path,
            classification=classification,
            imported=source.importable,
            primary_key=primary_key,
            row_count=0,
            imported_count=0,
        )

        try:
            rows = load_source_rows(source, repo_root=repo_root)
        except (FileNotFoundError, ValueError, TypeError) as exc:
            audit.notes.append(str(exc))
            if source.importable:
                report.ok = False
                report.errors.append(f"{source.path}: {exc}")
            file_audits.append(audit)
            continue

        audit.row_count = len(rows)
        if not source.importable:
            file_audits.append(audit)
            continue

        rejected_for_source: list[dict[str, Any]] = []
        imported_for_source = 0
        provenance_counter: Counter[str] = Counter()

        for row in rows:
            try:
                if source.namespace == "provider_instance_data":
                    canonical = _build_provider_instance(row.record, row)
                elif source.namespace == "assumed_hardware_profiles":
                    canonical = _build_assumed_profile(row.record, row)
                elif source.namespace == "measured_hardware_inventory":
                    canonical = _build_measured_host(row.record, row)
                elif source.namespace == "classification_data":
                    if source.options.get("classification_kind") == "deployment":
                        canonical = _build_deployment_type(row.record, row)
                    else:
                        canonical = _build_accelerator_class(row.record, row)
                else:
                    continue
            except ValueError as exc:
                rejected_for_source.append(
                    {"source_file": source.path, "row": row.row_number, "reason": str(exc)}
                )
                continue

            semantic_errors = _validate_record_semantics(canonical)
            if semantic_errors:
                rejected_for_source.extend(
                    {"source_file": source.path, "row": row.row_number, "reason": error}
                    for error in semantic_errors
                )
                report.errors.extend(semantic_errors)
                report.ok = False
                continue

            provenance_counter[str(canonical.get("provenance_status") or "unknown")] += 1
            report.unknown_fields.extend(_collect_unknown_fields(canonical))
            imported_for_source += 1

            if source.namespace == "provider_instance_data":
                provider_instances.append(canonical)
            elif source.namespace == "assumed_hardware_profiles":
                assumed_profiles.append(canonical)
            elif source.namespace == "measured_hardware_inventory":
                measured_hosts.append(canonical)
            elif source.namespace == "classification_data":
                if canonical["record_type"] == "deployment_type":
                    deployment_types.append(canonical)
                else:
                    accelerator_classes.append(canonical)

        audit.imported_count = imported_for_source
        audit.rejected_rows = rejected_for_source
        audit.provenance_statuses = dict(provenance_counter)
        file_audits.append(audit)
        report.rejected_rows.extend(rejected_for_source)

    provider_instances, provider_dupes, provider_errors = _dedupe_records(provider_instances)
    assumed_profiles, assumed_dupes, assumed_errors = _dedupe_records(assumed_profiles)
    measured_hosts, measured_dupes, measured_errors = _dedupe_records(measured_hosts)
    accelerator_classes, accelerator_dupes, accelerator_errors = _dedupe_records(
        accelerator_classes
    )
    deployment_types, deployment_dupes, deployment_errors = _dedupe_records(deployment_types)

    report.true_duplicate_keys = (
        provider_dupes + assumed_dupes + measured_dupes + accelerator_dupes + deployment_dupes
    )
    report.errors.extend(
        provider_errors + assumed_errors + measured_errors + accelerator_errors + deployment_errors
    )
    if report.errors:
        report.ok = False

    report.intentional_overlaps = validation.intentional_overlaps
    report.files = file_audits
    report.counts_by_namespace = {
        "provider_instance_data": len(provider_instances),
        "assumed_hardware_profiles": len(assumed_profiles),
        "measured_hardware_inventory": len(measured_hosts),
        "classification_data": len(accelerator_classes) + len(deployment_types),
    }
    report.assumed_profile_count = len(assumed_profiles)
    report.measured_host_count = len(measured_hosts)
    report.accelerator_class_count = len(accelerator_classes)
    report.deployment_type_count = len(deployment_types)

    gpu_product_lines = ("gpu droplets", "lightsail for research")
    report.provider_gpu_count = sum(
        1
        for item in provider_instances
        if any(marker in (item.get("product_line") or "").lower() for marker in gpu_product_lines)
        or (item.get("accelerator_class_id") or "").startswith(("nvidia_", "amd_", "unknown_gpu"))
    )
    report.provider_cpu_count = len(provider_instances) - report.provider_gpu_count

    gpu_counts = _parse_recovered_counts(repo_root / "AGENTS/data-science/profile-mapping/TG-8Ball-GPU-Recovered-Counts.csv")
    provider_counts = _parse_recovered_counts(
        repo_root / "AGENTS/data-science/profile-mapping/TG-8Ball-Provider-Recovery-Recovered-Counts.csv"
    )
    contract_checks = [
        (
            "AWS Lightsail for Research GPU plans",
            sum(
                1
                for item in provider_instances
                if "lightsail for research" in (item.get("product_line") or "").lower()
            ),
            gpu_counts.get("aws lightsail for research gpu plans"),
        ),
        (
            "DigitalOcean NVIDIA GPU rows",
            sum(
                1
                for item in provider_instances
                if (item.get("gpu_vendor") or "").lower() == "nvidia"
            ),
            gpu_counts.get("digitalocean nvidia gpu rows"),
        ),
        (
            "DigitalOcean AMD GPU rows",
            sum(1 for item in provider_instances if (item.get("gpu_vendor") or "").lower() == "amd"),
            gpu_counts.get("digitalocean amd gpu rows"),
        ),
        (
            "Measured local GPU host rows",
            report.measured_host_count,
            gpu_counts.get("measured local gpu host rows"),
        ),
        (
            "Accelerator classes",
            report.accelerator_class_count,
            gpu_counts.get("accelerator classes"),
        ),
        (
            "CUDA server assumption profiles",
            sum(
                1
                for item in assumed_profiles
                if (item.get("profile_id") or "").startswith("cuda_")
            ),
            gpu_counts.get("cuda server assumption profiles"),
        ),
        (
            "Lightsail records",
            sum(
                1
                for item in provider_instances
                if (item.get("provider") or "").upper().startswith("AWS")
                and "research" not in (item.get("product_line") or "").lower()
            ),
            provider_counts.get("lightsail records"),
        ),
        (
            "DigitalOcean records",
            sum(
                1
                for item in provider_instances
                if (item.get("provider") or "").lower() == "digitalocean"
                and "gpu" not in (item.get("product_line") or "").lower()
            ),
            provider_counts.get("digitalocean records"),
        ),
    ]
    for label, actual, expected in contract_checks:
        entry = {"metric": label, "actual": actual, "expected": expected, "ok": actual == expected}
        report.count_contract_checks.append(entry)
        if expected is not None and actual != expected:
            report.warnings.append(
                f"count contract mismatch for {label}: imported {actual}, counts CSV expects {expected}"
            )

    if write_outputs and report.ok:
        normalized_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "provider_instances": normalized_dir / "hardware-provider-instances.json",
            "assumed_profiles": normalized_dir / "hardware-assumed-profiles.json",
            "measured_hosts": normalized_dir / "hardware-measured-hosts.json",
            "accelerator_classes": normalized_dir / "hardware-accelerator-classes.json",
            "deployment_types": normalized_dir / "hardware-deployment-types.json",
            "import_meta": normalized_dir / "hardware-import-meta.json",
        }
        canonical_payloads = {
            "provider_instances": provider_instances,
            "assumed_profiles": assumed_profiles,
            "measured_hosts": measured_hosts,
            "accelerator_classes": accelerator_classes,
            "deployment_types": deployment_types,
        }
        for key, path in paths.items():
            if key == "import_meta":
                continue
            write_json(path, canonical_payloads[key])

        content_fingerprint = hashlib.sha256(
            json.dumps(canonical_payloads, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        existing_meta = load_json(paths["import_meta"]) if paths["import_meta"].is_file() else {}
        if existing_meta.get("content_fingerprint") == content_fingerprint:
            report.generated_at = existing_meta.get("generated_at", report.generated_at)
        write_json(
            paths["import_meta"],
            {
                "generated_at": report.generated_at,
                "content_fingerprint": content_fingerprint,
                "counts_by_namespace": report.counts_by_namespace,
                "provider_cpu_count": report.provider_cpu_count,
                "provider_gpu_count": report.provider_gpu_count,
                "intentional_overlap_count": len(report.intentional_overlaps),
                "true_duplicate_key_count": len(report.true_duplicate_keys),
            },
        )
        def _repo_relative(path: Path) -> str:
            try:
                return str(path.relative_to(repo_root))
            except ValueError:
                return str(path)

        report.canonical_paths = {key: _repo_relative(path) for key, path in paths.items()}

        generated_dir = GENERATED_DIR
        generated_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            generated_dir / "provider-import-report.json",
            {
                "generated_at": report.generated_at,
                "ok": report.ok,
                "files": [entry.__dict__ for entry in report.files],
                "counts_by_namespace": report.counts_by_namespace,
                "provider_cpu_count": report.provider_cpu_count,
                "provider_gpu_count": report.provider_gpu_count,
                "assumed_profile_count": report.assumed_profile_count,
                "measured_host_count": report.measured_host_count,
                "accelerator_class_count": report.accelerator_class_count,
                "deployment_type_count": report.deployment_type_count,
                "true_duplicate_keys": report.true_duplicate_keys,
                "intentional_overlaps": report.intentional_overlaps,
                "rejected_rows": report.rejected_rows,
                "unknown_fields": report.unknown_fields,
                "count_contract_checks": report.count_contract_checks,
                "warnings": report.warnings,
                "errors": report.errors,
                "canonical_paths": report.canonical_paths,
            },
        )

    return report

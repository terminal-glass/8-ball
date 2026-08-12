"""Windows runtime host capability taxonomy and observation contract for C10.1-11."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping" / "windows"
PILOT_MENU_JSON = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping" / "8ball-base-pilot-menu.json"
TAXONOMY_JSON = MAPPING_DIR / "runtime-capability-taxonomy.json"
TAXONOMY_CSV = MAPPING_DIR / "runtime-capability-taxonomy.csv"
CONTRACT_MD = MAPPING_DIR / "runtime-observation-contract.md"
COLLECTOR_SCHEMA_JSON = MAPPING_DIR / "collector-output-schema.json"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility" / "windows"
OUTPUT_CATEGORIES_JSON = COMPAT_DIR / "host-capability-categories.json"
OUTPUT_CATEGORIES_CSV = COMPAT_DIR / "host-capability-categories.csv"
OUTPUT_CONTRACT_JSON = COMPAT_DIR / "runtime-observation-contract.json"
OUTPUT_LANE_PROJECTION_JSON = COMPAT_DIR / "lane-runtime-contract-projection.json"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "capability-catalog" / "windows" / "capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-11-windows-capability-report.md"

WINDOWS_SOURCE_SCRIPT = "install/windows/cpu/8.2.sh"
WINDOWS_SOURCE_SCRIPT_VERSION = "public-8.2-windows-cpu"

CANONICAL_LANES = ("windows/cpu", "windows/cuda")

WINDOWS_HOST_KINDS = [
    "physical",
    "hyperv_vm",
    "vmware_vm",
    "virtualbox_vm",
    "other_vm",
    "unknown",
]

GPU_REPORTING_CATEGORIES = [
    "no_gpu_or_unknown",
    "gpu_present_unverified",
    "nvidia_smi_verified_vram_under_8_gib",
    "nvidia_smi_verified_vram_8_to_under_16_gib",
    "nvidia_smi_verified_vram_16_to_under_24_gib",
    "nvidia_smi_verified_vram_24_gib_or_more",
]

CAPACITY_FIELDS = frozenset(
    {
        "windows_architecture",
        "visible_cpu_threads",
        "system_ram_gib",
        "install_path_free_disk_gib",
        "gpu_vendor",
        "gpu_model",
        "gpu_memory_gib",
        "windows_cuda_lane_eligible",
        "windows_gpu_vram_source",
        "eightball_ram_mb",
        "eightball_cpu_threads",
        "eightball_disk_free_gb",
        "eightball_gpu_vram_mb",
    }
)

TAXONOMY_COLUMNS = [
    "id",
    "category_kind",
    "target_lane",
    "windows_host_kind",
    "windows_gpu_reporting_category",
    "runtime_detection_required",
    "runtime_evidence_commands",
    "windows_architecture",
    "visible_cpu_threads",
    "system_ram_gib",
    "install_path_free_disk_gib",
    "gpu_vendor",
    "gpu_model",
    "gpu_memory_gib",
    "windows_gpu_runtime",
    "windows_cuda_lane_eligible",
    "windows_gpu_vram_source",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
    "runtime_verification_required",
    "unknown_fields",
    "notes",
]

BAND_COLUMNS = [
    "ram_band_id",
    "lower_bound_gib",
    "upper_bound_gib_or_null",
    "runtime_trial_candidates",
    "source_script_path",
    "source_script_version",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
]

DISK_GATE_COLUMNS = [
    "candidate_ollama_ref",
    "required_free_disk_gib",
    "required_free_disk_mib",
    "source_script_path",
    "source_policy_path",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
]

OBSERVATION_CONTRACT_FACTS: list[dict[str, str]] = [
    {
        "fact": "os_and_architecture",
        "preferred_evidence": "Get-CimInstance Win32_OperatingSystem; [Environment]::Is64BitOperatingSystem; PROCESSOR_ARCHITECTURE",
        "rule": "Record native Windows only. WSL must set os_family=wsl and must not use either windows lane.",
    },
    {
        "fact": "host_topology",
        "preferred_evidence": "Win32_ComputerSystem.Model, Manufacturer, HypervisorPresent",
        "rule": "Map only clearly evidenced windows_host_kind values; otherwise unknown. Do not infer cloud provider.",
    },
    {
        "fact": "installed_ram",
        "preferred_evidence": "Win32_ComputerSystem.TotalPhysicalMemory",
        "rule": "Record physical/assigned RAM in MiB as EIGHTBALL_RAM_MB. Never use free RAM as installed RAM.",
    },
    {
        "fact": "cpu_threads",
        "preferred_evidence": "Win32_Processor.NumberOfLogicalProcessors",
        "rule": "Sum valid logical processors; record EIGHTBALL_CPU_THREADS as measured integer.",
    },
    {
        "fact": "install_destination_free_disk",
        "preferred_evidence": "Get-PSDrive / volume for configured install path",
        "rule": "Measure the actual intended install destination only.",
    },
    {
        "fact": "gpu_presence",
        "preferred_evidence": "Win32_VideoController",
        "rule": "Presence alone is not CUDA evidence. AdapterRAM cannot become verified VRAM.",
    },
    {
        "fact": "nvidia_identity_and_vram",
        "preferred_evidence": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits",
        "rule": "Only successful nvidia-smi may set measured NVIDIA VRAM and windows/cuda lane eligibility.",
    },
]

NORMALIZED_ARTIFACT_FIELDS: list[dict[str, str]] = [
    {"name": "EIGHTBALL_OS_FAMILY", "values": "windows | wsl", "notes": "wsl excludes native Windows lanes"},
    {"name": "EIGHTBALL_PROVIDER", "values": "windows | bare_metal | unknown", "notes": "Not a cloud provider lane"},
    {"name": "EIGHTBALL_INSTANCE_CLASS", "values": "<observed> | unknown", "notes": "Marketing labels are not capacity claims"},
    {"name": "EIGHTBALL_RAM_MB", "values": "<measured integer>", "notes": "From TotalPhysicalMemory"},
    {"name": "EIGHTBALL_CPU_THREADS", "values": "<measured integer>", "notes": "Sum of logical processors"},
    {"name": "EIGHTBALL_DISK_FREE_GB", "values": "<measured integer>", "notes": "Install destination only"},
    {"name": "EIGHTBALL_GPU_PRESENT", "values": "yes | no | unknown", "notes": "Win32_VideoController presence"},
    {"name": "EIGHTBALL_GPU_NAME", "values": "<observed> | unknown", "notes": "nvidia-smi name when verified"},
    {"name": "EIGHTBALL_GPU_VRAM_MB", "values": "<measured integer> | unknown", "notes": "nvidia-smi only; never AdapterRAM"},
]

WINDOWS_EXTENSION_FIELDS: list[dict[str, str]] = [
    {"name": "windows_host_kind", "values": "physical | hyperv_vm | vmware_vm | virtualbox_vm | other_vm | unknown"},
    {"name": "windows_architecture", "values": "x64 | arm64 | x86 | unknown"},
    {"name": "windows_gpu_runtime", "values": "nvidia_smi_verified | gpu_present_unverified | no_gpu_detected | unknown"},
    {"name": "windows_cuda_lane_eligible", "values": "yes | no | unknown"},
    {"name": "windows_gpu_vram_source", "values": "nvidia_smi | unknown"},
]


def _host_kind_id(host_kind: str) -> str:
    return f"windows-host-kind-{host_kind.replace('_', '-')}"


def _lane_routing_id(lane: str) -> str:
    return f"windows-lane-routing-{lane.split('/')[1]}"


def _gpu_reporting_id(category: str) -> str:
    return f"windows-gpu-reporting-{category.replace('_', '-')}"


def _base_category(
    *,
    record_id: str,
    category_kind: str,
    notes: str,
    runtime_evidence_commands: list[str],
    target_lane: str | None = None,
    windows_host_kind: str | None = None,
    windows_gpu_reporting_category: str | None = None,
    windows_gpu_runtime: str | None = None,
    windows_cuda_lane_eligible: str | None = None,
    windows_gpu_vram_source: str | None = None,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "category_kind": category_kind,
        "target_lane": target_lane,
        "windows_host_kind": windows_host_kind,
        "windows_gpu_reporting_category": windows_gpu_reporting_category,
        "runtime_detection_required": True,
        "runtime_evidence_commands": runtime_evidence_commands,
        "windows_architecture": None,
        "visible_cpu_threads": None,
        "system_ram_gib": None,
        "install_path_free_disk_gib": None,
        "gpu_vendor": None,
        "gpu_model": None,
        "gpu_memory_gib": None,
        "windows_gpu_runtime": windows_gpu_runtime,
        "windows_cuda_lane_eligible": windows_cuda_lane_eligible,
        "windows_gpu_vram_source": windows_gpu_vram_source,
        "classification": "runtime-observed-host-category",
        "model_fit_proven": False,
        "runtime_trial_required": True,
        "runtime_verification_required": True,
        "unknown_fields": sorted(CAPACITY_FIELDS),
        "notes": notes,
    }


def build_host_topology_categories() -> list[dict[str, Any]]:
    evidence = [
        "Get-CimInstance Win32_ComputerSystem",
        "Win32_ComputerSystem.Model",
        "Win32_ComputerSystem.Manufacturer",
        "Win32_ComputerSystem.HypervisorPresent",
    ]
    notes_by_kind = {
        "physical": "Physical Windows host when hypervisor evidence is absent or clearly negative.",
        "hyperv_vm": "Hyper-V guest when HypervisorPresent and model/manufacturer evidence support it.",
        "vmware_vm": "VMware guest only when model/manufacturer evidence clearly supports VMware.",
        "virtualbox_vm": "VirtualBox guest only when model/manufacturer evidence clearly supports VirtualBox.",
        "other_vm": "Other VM when hypervisor evidence is present but vendor mapping is unclear.",
        "unknown": "Topology unknown when WMI evidence is missing, conflicting, or ambiguous.",
    }
    categories: list[dict[str, Any]] = []
    for host_kind in WINDOWS_HOST_KINDS:
        categories.append(
            _base_category(
                record_id=_host_kind_id(host_kind),
                category_kind="host_topology",
                windows_host_kind=host_kind,
                runtime_evidence_commands=evidence,
                notes=(
                    f"Runtime-observed Windows host topology category ({host_kind}). "
                    f"{notes_by_kind[host_kind]} Capacity values are measured at install time."
                ),
            )
        )
    return categories


def build_lane_routing_categories() -> list[dict[str, Any]]:
    categories = [
        _base_category(
            record_id=_lane_routing_id("windows/cpu"),
            category_kind="lane_routing",
            target_lane="windows/cpu",
            runtime_evidence_commands=[
                "Get-CimInstance Win32_OperatingSystem",
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits",
                "Win32_VideoController",
            ],
            windows_gpu_runtime="gpu_present_unverified",
            windows_cuda_lane_eligible="no",
            windows_gpu_vram_source="unknown",
            notes=(
                "Safe native Windows lane when nvidia-smi is absent or fails. "
                "Display adapters may be present; CPU install must not fail solely because a GPU is visible."
            ),
        ),
        _base_category(
            record_id=_lane_routing_id("windows/cuda"),
            category_kind="lane_routing",
            target_lane="windows/cuda",
            runtime_evidence_commands=[
                "Get-CimInstance Win32_OperatingSystem",
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits",
            ],
            windows_gpu_runtime="nvidia_smi_verified",
            windows_cuda_lane_eligible="yes",
            windows_gpu_vram_source="nvidia_smi",
            notes=(
                "CUDA lane candidate only after successful nvidia-smi with non-empty NVIDIA GPU name "
                "and positive VRAM. This is not a model-fit guarantee. Retain per-device GPU evidence."
            ),
        ),
    ]
    return categories


def build_gpu_reporting_categories() -> list[dict[str, Any]]:
    notes_map = {
        "no_gpu_or_unknown": "No supported GPU detected or GPU state unknown at observation time.",
        "gpu_present_unverified": (
            "Win32_VideoController may report an adapter, but AdapterRAM is not verified VRAM "
            "and nvidia-smi did not succeed."
        ),
        "nvidia_smi_verified_vram_under_8_gib": "nvidia-smi verified VRAM strictly under 8 GiB per device.",
        "nvidia_smi_verified_vram_8_to_under_16_gib": "nvidia-smi verified VRAM from 8 GiB up to under 16 GiB.",
        "nvidia_smi_verified_vram_16_to_under_24_gib": "nvidia-smi verified VRAM from 16 GiB up to under 24 GiB.",
        "nvidia_smi_verified_vram_24_gib_or_more": "nvidia-smi verified VRAM 24 GiB or more per device.",
    }
    vram_source = {
        "no_gpu_or_unknown": "unknown",
        "gpu_present_unverified": "unknown",
        "nvidia_smi_verified_vram_under_8_gib": "nvidia_smi",
        "nvidia_smi_verified_vram_8_to_under_16_gib": "nvidia_smi",
        "nvidia_smi_verified_vram_16_to_under_24_gib": "nvidia_smi",
        "nvidia_smi_verified_vram_24_gib_or_more": "nvidia_smi",
    }
    gpu_runtime = {
        "no_gpu_or_unknown": "no_gpu_detected",
        "gpu_present_unverified": "gpu_present_unverified",
        "nvidia_smi_verified_vram_under_8_gib": "nvidia_smi_verified",
        "nvidia_smi_verified_vram_8_to_under_16_gib": "nvidia_smi_verified",
        "nvidia_smi_verified_vram_16_to_under_24_gib": "nvidia_smi_verified",
        "nvidia_smi_verified_vram_24_gib_or_more": "nvidia_smi_verified",
    }
    categories: list[dict[str, Any]] = []
    for category in GPU_REPORTING_CATEGORIES:
        commands = ["Win32_VideoController"]
        if category != "gpu_present_unverified":
            commands.append("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits")
        else:
            commands = [
                "Win32_VideoController",
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits",
            ]
        categories.append(
            _base_category(
                record_id=_gpu_reporting_id(category),
                category_kind="gpu_reporting",
                windows_gpu_reporting_category=category,
                runtime_evidence_commands=commands,
                windows_gpu_runtime=gpu_runtime[category],
                windows_cuda_lane_eligible="unknown" if category.startswith("nvidia_smi") else "no",
                windows_gpu_vram_source=vram_source[category],
                notes=(
                    f"{notes_map[category]} Reporting category only; does not claim model fit or "
                    "minimum_vram_gb for any model-size record."
                ),
            )
        )
    return categories


def _ram_band_bounds(band_id: str) -> tuple[float | None, float | None]:
    mapping: dict[str, tuple[float | None, float | None]] = {
        "windows-ram-band-under-4gib": (None, 4.0),
        "windows-ram-band-4-to-8gib": (4.0, 8.0),
        "windows-ram-band-8-to-12gib": (8.0, 12.0),
        "windows-ram-band-12-to-24gib": (12.0, 24.0),
        "windows-ram-band-24gib-plus": (24.0, None),
    }
    return mapping[band_id]


def build_runtime_menu_bands(menu: dict[str, Any]) -> list[dict[str, Any]]:
    band_id_map = {
        "fallback-under-4gb": "windows-ram-band-under-4gib",
        "pilot-4gb": "windows-ram-band-4-to-8gib",
        "pilot-8gb": "windows-ram-band-8-to-12gib",
        "pilot-12gb": "windows-ram-band-12-to-24gib",
        "pilot-24gb-plus": "windows-ram-band-24gib-plus",
    }
    bands: list[dict[str, Any]] = []
    for band in menu.get("bands", []):
        pilot_band = band["pilot_menu_band"]
        ram_band_id = band_id_map[pilot_band]
        lower, upper = _ram_band_bounds(ram_band_id)
        bands.append(
            {
                "ram_band_id": ram_band_id,
                "lower_bound_gib": lower,
                "upper_bound_gib_or_null": upper,
                "runtime_trial_candidates": list(band["ordered_pilot_candidates"]),
                "source_script_path": WINDOWS_SOURCE_SCRIPT,
                "source_script_version": WINDOWS_SOURCE_SCRIPT_VERSION,
                "classification": "runtime_menu_band_only",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "disk_guard_mib_by_candidate": band.get("disk_thresholds_mib", {}),
                "source_policy_path": str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
                "notes": (
                    "Happy Nerds runtime-menu band from install/windows/cpu/8.2.sh RAM detection "
                    "(detect_hardware) and auditable pilot policy in 8ball-base-pilot-menu.json."
                ),
            }
        )
    bands.sort(key=lambda row: (row["lower_bound_gib"] is not None, row["lower_bound_gib"] or 0.0))
    return bands


def build_disk_gates(menu: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds: dict[str, int] = {}
    for band in menu.get("bands", []):
        for candidate, mib in band.get("disk_thresholds_mib", {}).items():
            thresholds[candidate] = mib
    order = ["qwen3:14b", "qwen3:8b", "qwen3:4b", "qwen3:1.7b", "qwen3:0.6b"]
    gates: list[dict[str, Any]] = []
    for candidate in order:
        mib = thresholds[candidate]
        gates.append(
            {
                "candidate_ollama_ref": candidate,
                "required_free_disk_gib": round(mib / 1024, 4),
                "required_free_disk_mib": mib,
                "source_script_path": WINDOWS_SOURCE_SCRIPT,
                "source_policy_path": str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
                "classification": "runtime_download_guard_only",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "notes": "Base-pilot free-disk gate before trial pull; not a universal catalog disk requirement.",
            }
        )
    return gates


def build_collector_output_schema() -> dict[str, Any]:
    return {
        "schema_version": "c10.windows-collector-output.v1",
        "description": "Example normalized collector output for a future Windows PowerShell probe.",
        "normalized_artifact_fields": NORMALIZED_ARTIFACT_FIELDS,
        "windows_extension_fields": WINDOWS_EXTENSION_FIELDS,
        "wsl_policy": {
            "os_family": "wsl",
            "native_windows_lane_eligible": False,
            "notes": "WSL detections must not be filed under windows/cpu or windows/cuda.",
        },
        "per_device_gpu_records_required": True,
        "adapter_ram_verified_vram_forbidden": True,
        "example_output": {
            "EIGHTBALL_OS_FAMILY": "windows",
            "EIGHTBALL_PROVIDER": "unknown",
            "EIGHTBALL_INSTANCE_CLASS": "unknown",
            "EIGHTBALL_RAM_MB": None,
            "EIGHTBALL_CPU_THREADS": None,
            "EIGHTBALL_DISK_FREE_GB": None,
            "EIGHTBALL_GPU_PRESENT": "unknown",
            "EIGHTBALL_GPU_NAME": "unknown",
            "EIGHTBALL_GPU_VRAM_MB": "unknown",
            "windows_host_kind": "unknown",
            "windows_architecture": "unknown",
            "windows_gpu_runtime": "unknown",
            "windows_cuda_lane_eligible": "unknown",
            "windows_gpu_vram_source": "unknown",
            "gpus": [],
        },
    }


def build_observation_contract_markdown() -> str:
    lines = [
        "# Windows runtime observation contract (C10.1-11)",
        "",
        "Minimal native-Windows evidence contract for `windows/cpu` and `windows/cuda` lanes.",
        "Committed taxonomy rows define categories and evidence rules only — not fixed capacities.",
        "",
        "## Normalized artifact fields",
        "",
        "| Field | Allowed values | Notes |",
        "| --- | --- | --- |",
    ]
    for field in NORMALIZED_ARTIFACT_FIELDS:
        lines.append(f"| `{field['name']}` | {field['values']} | {field['notes']} |")
    lines.extend(["", "## Windows extension fields", "", "| Field | Allowed values |", "| --- | --- |"])
    for field in WINDOWS_EXTENSION_FIELDS:
        lines.append(f"| `{field['name']}` | {field['values']} |")
    lines.extend(["", "## Facts and evidence", "", "| Fact | Preferred evidence | Rule |", "| --- | --- | --- |"])
    for fact in OBSERVATION_CONTRACT_FACTS:
        lines.append(
            f"| {fact['fact']} | `{fact['preferred_evidence']}` | {fact['rule']} |"
        )
    lines.extend(
        [
            "",
            "## WSL boundary",
            "",
            "WSL is not native Windows. When detected, set `os_family=wsl` and route to the",
            "Ubuntu/Linux runtime flow. Do not file WSL hosts under `windows/cpu` or `windows/cuda`.",
            "",
            "## CUDA and VRAM boundary",
            "",
            "`Win32_VideoController.AdapterRAM` must never become verified VRAM. Only successful",
            "`nvidia-smi` may set measured NVIDIA VRAM and `windows/cuda` lane eligibility.",
            "Retain per-device GPU evidence; expose the largest verified single-GPU VRAM value.",
            "",
            "## ARM64 boundary",
            "",
            "Native Windows on ARM64 records `windows_architecture=arm64`. Compatibility remains",
            "`unknown` unless runtime prerequisites prove support. Do not imply x64/ARM64 parity.",
            "",
            "## Sanitization",
            "",
            "No live command output, serial numbers, hostnames, MAC addresses, IP addresses,",
            "user names, or credentials may be committed. Tests use sanitized fixtures only.",
            "",
        ]
    )
    return "\n".join(lines)


def build_observation_contract_json(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    disk_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.windows-runtime-observation-contract.v1",
        "target_lanes": list(CANONICAL_LANES),
        "facts": OBSERVATION_CONTRACT_FACTS,
        "normalized_artifact_fields": NORMALIZED_ARTIFACT_FIELDS,
        "windows_extension_fields": WINDOWS_EXTENSION_FIELDS,
        "wsl_native_windows_lane_forbidden": True,
        "adapter_ram_verified_vram_forbidden": True,
        "nvidia_smi_required_for_cuda_lane": True,
        "per_device_gpu_evidence_required": True,
        "source_paths": [
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            str(COLLECTOR_SCHEMA_JSON.relative_to(REPO_ROOT)),
            WINDOWS_SOURCE_SCRIPT,
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
        ],
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "disk_gate_count": len(disk_gates),
    }


def build_lane_projection(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    disk_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    topology_ids = [c["id"] for c in categories if c["category_kind"] == "host_topology"]
    gpu_reporting_ids = [c["id"] for c in categories if c["category_kind"] == "gpu_reporting"]
    band_ids = [b["ram_band_id"] for b in bands]

    def lane_entry(lane: str) -> dict[str, Any]:
        routing_id = _lane_routing_id(lane)
        return {
            "target_lane": lane,
            "observation_contract_path": str(OUTPUT_CONTRACT_JSON.relative_to(REPO_ROOT)),
            "lane_routing_category_id": routing_id,
            "host_topology_category_ids": topology_ids,
            "gpu_reporting_category_ids": gpu_reporting_ids,
            "runtime_menu_band_ids": band_ids,
            "disk_gate_candidate_refs": [gate["candidate_ollama_ref"] for gate in disk_gates],
            "classification": "runtime-observed-host-category",
            "model_fit_proven": False,
            "runtime_trial_required": True,
            "runtime_verification_required": True,
            "notes": (
                "Lane projection for native Windows hosts only. WSL is excluded. "
                "Does not multiply the C10 model-size index."
            ),
        }

    return {
        "schema_version": "c10.windows-lane-runtime-contract-projection.v1",
        "canonical_lane_count": len(CANONICAL_LANES),
        "lanes": {
            "windows/cpu": lane_entry("windows/cpu"),
            "windows/cuda": lane_entry("windows/cuda"),
        },
    }


def build_taxonomy_payload(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    disk_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.windows-runtime-capability-taxonomy.v1",
        "canonical_lanes": list(CANONICAL_LANES),
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "disk_gate_count": len(disk_gates),
        "categories": categories,
        "runtime_menu_bands": bands,
        "disk_gates": disk_gates,
        "wsl_policy": {
            "os_family": "wsl",
            "native_windows_lane_eligible": False,
        },
    }


def _serialize_commands(commands: list[str]) -> str:
    return "|".join(commands)


def _serialize_unknown_fields(fields: list[str]) -> str:
    return "|".join(fields)


def write_taxonomy_csv(path: Path, categories: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TAXONOMY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for record in categories:
            row = {key: record.get(key) for key in TAXONOMY_COLUMNS}
            row["runtime_evidence_commands"] = _serialize_commands(record["runtime_evidence_commands"])
            row["unknown_fields"] = _serialize_unknown_fields(record["unknown_fields"])
            for bool_field in (
                "model_fit_proven",
                "runtime_trial_required",
                "runtime_detection_required",
                "runtime_verification_required",
            ):
                row[bool_field] = str(record[bool_field]).lower()
            for key in TAXONOMY_COLUMNS:
                if row.get(key) is None:
                    row[key] = ""
            writer.writerow(row)


def write_bands_csv(path: Path, bands: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BAND_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for band in bands:
            row = {
                "ram_band_id": band["ram_band_id"],
                "lower_bound_gib": band["lower_bound_gib"] if band["lower_bound_gib"] is not None else "",
                "upper_bound_gib_or_null": band["upper_bound_gib_or_null"]
                if band["upper_bound_gib_or_null"] is not None
                else "",
                "runtime_trial_candidates": "|".join(band["runtime_trial_candidates"]),
                "source_script_path": band["source_script_path"],
                "source_script_version": band["source_script_version"],
                "classification": band["classification"],
                "model_fit_proven": str(band["model_fit_proven"]).lower(),
                "runtime_trial_required": str(band["runtime_trial_required"]).lower(),
            }
            writer.writerow(row)


def write_disk_gates_csv(path: Path, gates: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISK_GATE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for gate in gates:
            row = {key: gate.get(key) for key in DISK_GATE_COLUMNS}
            row["model_fit_proven"] = str(gate["model_fit_proven"]).lower()
            row["runtime_trial_required"] = str(gate["runtime_trial_required"]).lower()
            writer.writerow(row)


def load_pilot_menu(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / PILOT_MENU_JSON.relative_to(REPO_ROOT)).read_text(encoding="utf-8"))


def load_taxonomy(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / TAXONOMY_JSON.relative_to(REPO_ROOT)).read_text(encoding="utf-8"))


def build_report(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    disk_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.windows-capability-report.v1",
        "category_counts": {
            "host_topology": sum(1 for c in categories if c["category_kind"] == "host_topology"),
            "lane_routing": sum(1 for c in categories if c["category_kind"] == "lane_routing"),
            "gpu_reporting": sum(1 for c in categories if c["category_kind"] == "gpu_reporting"),
            "total": len(categories),
            "runtime_menu_bands": len(bands),
            "disk_gates": len(disk_gates),
        },
        "canonical_lanes": list(CANONICAL_LANES),
        "install_lane_count_total": 10,
        "windows_lane_contribution": 2,
        "intentionally_unknown_fields": sorted(CAPACITY_FIELDS),
        "wsl_native_windows_lane_forbidden": True,
        "adapter_ram_verified_vram_forbidden": True,
        "model_requirements_formula_generated": False,
        "c10_index_expansion": False,
        "source_paths": [
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(COLLECTOR_SCHEMA_JSON.relative_to(REPO_ROOT)),
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
            WINDOWS_SOURCE_SCRIPT,
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    counts = report["category_counts"]
    lines = [
        "# C10.1-11 Windows runtime host capability report",
        "",
        "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_windows_compatibility.py`.",
        "",
        "## Taxonomy inventory",
        "",
        f"- Host topology categories: **{counts['host_topology']}**",
        f"- Lane routing categories: **{counts['lane_routing']}**",
        f"- GPU reporting categories: **{counts['gpu_reporting']}**",
        f"- Runtime-menu bands: **{counts['runtime_menu_bands']}**",
        f"- Disk gates: **{counts['disk_gates']}**",
        "",
        "## Lane posture",
        "",
        f"- Canonical install lanes total: **{report['install_lane_count_total']}**",
        f"- Windows contributes: **{report['windows_lane_contribution']}** lanes",
        "",
        "## Evidence posture",
        "",
        f"- WSL excluded from native Windows lanes: **{report['wsl_native_windows_lane_forbidden']}**",
        f"- AdapterRAM verified VRAM forbidden: **{report['adapter_ram_verified_vram_forbidden']}**",
        f"- Model requirements formula-generated: **{report['model_requirements_formula_generated']}**",
        f"- C10 index expansion: **{report['c10_index_expansion']}**",
        "",
        "Host capacity fields remain null in committed taxonomy rows; runtime observation supplies values.",
        "RAM-menu bands and disk gates are trial policy only and do not claim model fit.",
    ]
    return "\n".join(lines) + "\n"


def update_provider_readme() -> None:
    readme = REPO_ROOT / "profiles" / "provider-compatibility" / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    marker = "## Windows runtime hosts (C10.1-11)"
    if marker in text:
        return
    addition = "\n".join(
        [
            "",
            "## Windows runtime hosts (C10.1-11)",
            "",
            "- `windows/host-capability-categories.json` and `.csv` — runtime host categories",
            "- `windows/runtime-observation-contract.json` — Windows evidence contract",
            "- `windows/lane-runtime-contract-projection.json` — `windows/cpu` and `windows/cuda` projections",
            "",
            "Source tables:",
            "- `AGENTS/data-science/profile-mapping/windows/runtime-capability-taxonomy.json`",
            "- `AGENTS/data-science/profile-mapping/windows/runtime-observation-contract.md`",
            "- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`",
            "",
            "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
            "",
        ]
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")


def generate_windows_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    menu = load_pilot_menu(repo_root)
    categories = (
        build_host_topology_categories()
        + build_lane_routing_categories()
        + build_gpu_reporting_categories()
    )
    bands = build_runtime_menu_bands(menu)
    disk_gates = build_disk_gates(menu)
    taxonomy = build_taxonomy_payload(categories, bands, disk_gates)
    contract_json = build_observation_contract_json(categories, bands, disk_gates)
    lane_projection = build_lane_projection(categories, bands, disk_gates)
    contract_md = build_observation_contract_markdown()
    collector_schema = build_collector_output_schema()

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_MD.write_text(contract_md, encoding="utf-8")
    COLLECTOR_SCHEMA_JSON.write_text(json.dumps(collector_schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TAXONOMY_JSON.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_taxonomy_csv(TAXONOMY_CSV, categories)

    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CATEGORIES_JSON.write_text(
        json.dumps(
            {
                "categories": categories,
                "runtime_menu_bands": bands,
                "disk_gates": disk_gates,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_taxonomy_csv(OUTPUT_CATEGORIES_CSV, categories)
    OUTPUT_CONTRACT_JSON.write_text(json.dumps(contract_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT_LANE_PROJECTION_JSON.write_text(
        json.dumps(lane_projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_bands_csv(COMPAT_DIR / "runtime-menu-bands.csv", bands)
    write_disk_gates_csv(COMPAT_DIR / "disk-gates.csv", disk_gates)

    update_provider_readme()

    report = build_report(categories, bands, disk_gates)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report_markdown(report), encoding="utf-8")

    return {
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "disk_gate_count": len(disk_gates),
        "canonical_lanes": list(CANONICAL_LANES),
    }


def _invalid_capacity_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "" or value == 0:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "0", "null", "none", "unknown"}:
        return value.strip().lower() in {"", "0"}
    return False


def validate_windows_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []

    if not TAXONOMY_JSON.is_file():
        errors.append(f"Missing taxonomy: {TAXONOMY_JSON}")
        return errors
    if not CONTRACT_MD.is_file():
        errors.append(f"Missing observation contract markdown: {CONTRACT_MD}")

    taxonomy = load_taxonomy(repo_root)
    categories = taxonomy.get("categories", [])
    bands = taxonomy.get("runtime_menu_bands", [])
    disk_gates = taxonomy.get("disk_gates", [])

    if len(categories) != 14:
        errors.append(f"Expected 14 taxonomy categories, found {len(categories)}")
    if len(bands) != 5:
        errors.append(f"Expected 5 runtime-menu bands, found {len(bands)}")
    if len(disk_gates) != 5:
        errors.append(f"Expected 5 disk gates, found {len(disk_gates)}")

    host_kinds = {c["windows_host_kind"] for c in categories if c["category_kind"] == "host_topology"}
    if host_kinds != set(WINDOWS_HOST_KINDS):
        errors.append(f"Host topology kinds mismatch: {host_kinds}")

    lane_targets = {c["target_lane"] for c in categories if c["category_kind"] == "lane_routing"}
    if lane_targets != set(CANONICAL_LANES):
        errors.append(f"Lane routing targets mismatch: {lane_targets}")

    gpu_reporting = {
        c["windows_gpu_reporting_category"]
        for c in categories
        if c["category_kind"] == "gpu_reporting"
    }
    if gpu_reporting != set(GPU_REPORTING_CATEGORIES):
        errors.append(f"GPU reporting categories mismatch: {gpu_reporting}")

    forbidden_sublanes = [
        path
        for path in (repo_root / "install" / "windows").rglob("*")
        if path.is_dir() and path.name in {"vm", "physical", "hyperv", "wsl"}
    ]
    if forbidden_sublanes:
        errors.append(f"Forbidden Windows sublanes present: {forbidden_sublanes}")

    menu = load_pilot_menu(repo_root)
    expected_candidates = {tuple(band["ordered_pilot_candidates"]) for band in menu.get("bands", [])}
    actual_candidates = {tuple(band["runtime_trial_candidates"]) for band in bands}
    if actual_candidates != expected_candidates:
        errors.append("Runtime-menu bands do not match 8ball-base-pilot-menu.json candidate ladders")

    expected_disk_mib = {
        "qwen3:14b": 14336,
        "qwen3:8b": 9216,
        "qwen3:4b": 6144,
        "qwen3:1.7b": 4096,
        "qwen3:0.6b": 3072,
    }
    actual_disk_mib = {gate["candidate_ollama_ref"]: gate["required_free_disk_mib"] for gate in disk_gates}
    if actual_disk_mib != expected_disk_mib:
        errors.append(f"Disk gates mismatch: {actual_disk_mib}")

    cuda_lane = next(c for c in categories if c.get("target_lane") == "windows/cuda")
    cuda_commands = " ".join(cuda_lane.get("runtime_evidence_commands", [])).lower()
    if "nvidia-smi" not in cuda_commands:
        errors.append("windows/cuda lane routing must require nvidia-smi")

    for record in categories:
        if record.get("model_fit_proven") is True:
            errors.append(f"Category {record['id']} must not claim model_fit_proven")
        if record.get("runtime_verification_required") is not True:
            errors.append(f"Category {record['id']} must set runtime_verification_required=true")
        for field in (
            "windows_architecture",
            "visible_cpu_threads",
            "system_ram_gib",
            "install_path_free_disk_gib",
            "gpu_vendor",
            "gpu_model",
            "gpu_memory_gib",
        ):
            if _invalid_capacity_value(record.get(field)):
                errors.append(f"Category {record['id']} has invalid placeholder for {field}")

    unverified = next(
        c for c in categories if c.get("windows_gpu_reporting_category") == "gpu_present_unverified"
    )
    if "adapterram" in unverified.get("notes", "").lower():
        pass
    else:
        errors.append("gpu_present_unverified must document AdapterRAM restriction")
    if unverified.get("windows_gpu_vram_source") != "unknown":
        errors.append("gpu_present_unverified must keep windows_gpu_vram_source unknown")

    contract_path = OUTPUT_CONTRACT_JSON
    if not contract_path.is_file():
        errors.append(f"Missing generated contract JSON: {contract_path}")
    else:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if not contract.get("wsl_native_windows_lane_forbidden"):
            errors.append("Observation contract must forbid WSL native Windows lane filing")
        if not contract.get("adapter_ram_verified_vram_forbidden"):
            errors.append("Observation contract must forbid AdapterRAM verified VRAM")

    collector = COLLECTOR_SCHEMA_JSON
    if not collector.is_file():
        errors.append(f"Missing collector schema: {collector}")
    else:
        schema = json.loads(collector.read_text(encoding="utf-8"))
        if schema.get("adapter_ram_verified_vram_forbidden") is not True:
            errors.append("Collector schema must forbid AdapterRAM verified VRAM")

    projection_path = OUTPUT_LANE_PROJECTION_JSON
    if not projection_path.is_file():
        errors.append(f"Missing lane projection: {projection_path}")
    else:
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if set(projection.get("lanes", {})) != set(CANONICAL_LANES):
            errors.append("Lane projection must reference only windows/cpu and windows/cuda")

    index_csv = repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

"""Ubuntu runtime host capability taxonomy and observation contract for C10.1-10."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"
PILOT_MENU_JSON = MAPPING_DIR / "8ball-base-pilot-menu.json"
TAXONOMY_JSON = MAPPING_DIR / "ubuntu-runtime-capability-taxonomy.json"
TAXONOMY_CSV = MAPPING_DIR / "ubuntu-runtime-capability-taxonomy.csv"
CONTRACT_MD = MAPPING_DIR / "ubuntu-runtime-observation-contract.md"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility" / "ubuntu"
OUTPUT_CATEGORIES_JSON = COMPAT_DIR / "host-capability-categories.json"
OUTPUT_CATEGORIES_CSV = COMPAT_DIR / "host-capability-categories.csv"
OUTPUT_CONTRACT_JSON = COMPAT_DIR / "runtime-observation-contract.json"
OUTPUT_LANE_PROJECTION_JSON = COMPAT_DIR / "lane-runtime-contract-projection.json"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "ubuntu-capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-10-ubuntu-capability-report.md"

UBUNTU_SOURCE_SCRIPT = "install/ubuntu/cpu/8.2.sh"
UBUNTU_SOURCE_SCRIPT_VERSION = "public-8.2-ubuntu-cpu"

TOPOLOGY_LANES: list[tuple[str, str]] = [
    ("bare-metal", "ubuntu/cpu"),
    ("bare-metal", "ubuntu/cuda"),
    ("virtual-machine", "ubuntu/cpu"),
    ("virtual-machine", "ubuntu/cuda"),
    ("unknown", "ubuntu/cpu"),
    ("unknown", "ubuntu/cuda"),
]

GPU_RUNTIME_STATES = [
    "nvidia-cuda-ready",
    "gpu-present-not-cuda-ready",
    "no-supported-gpu-detected",
    "gpu-state-unknown",
]

CAPACITY_FIELDS = frozenset(
    {
        "cpu_architecture",
        "visible_cpu_threads",
        "system_ram_gib",
        "ollama_filesystem_path",
        "free_disk_gib",
        "gpu_vendor",
        "gpu_model",
        "gpu_memory_gib",
        "cuda_runtime_ready",
        "virtualization_kind",
        "provider",
    }
)

TAXONOMY_COLUMNS = [
    "id",
    "target_lane",
    "host_topology",
    "runtime_detection_required",
    "runtime_evidence_commands",
    "cpu_architecture",
    "visible_cpu_threads",
    "system_ram_gib",
    "ollama_filesystem_path",
    "free_disk_gib",
    "gpu_runtime_state",
    "gpu_vendor",
    "gpu_model",
    "gpu_memory_gib",
    "cuda_runtime_ready",
    "virtualization_kind",
    "provider",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
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

PROVIDER_INFERENCE_PATTERNS = re.compile(
    r"\b(aws|amazon|digitalocean|google|azure|oracle|hetzner|linode|vultr|lightsail)\b",
    re.I,
)

OBSERVATION_CONTRACT_FACTS: list[dict[str, str]] = [
    {
        "fact": "host_topology",
        "preferred_evidence": "systemd-detect-virt",
        "rule": "Preserve status/output; unrecognized output is unknown. Map none to bare-metal, vm/kvm/qemu/vmware/microsoft/oracle to virtual-machine; provider stays null.",
    },
    {
        "fact": "vm_detail",
        "preferred_evidence": "systemd-detect-virt --vm and/or lscpu -J",
        "rule": "Optional detail only; never infer provider from hypervisor strings.",
    },
    {
        "fact": "os_architecture",
        "preferred_evidence": "/etc/os-release, uname -m",
        "rule": "Record observed values, not an imagined release target.",
    },
    {
        "fact": "cpu_threads",
        "preferred_evidence": "nproc, lscpu -J",
        "rule": "Record visible/assigned threads; do not derive performance class.",
    },
    {
        "fact": "system_ram",
        "preferred_evidence": "/proc/meminfo",
        "rule": "Record observed physical memory; never a model requirement.",
    },
    {
        "fact": "model_filesystem",
        "preferred_evidence": "configured Ollama/8-BALL data path then df -P",
        "rule": "Use free space on that filesystem only; never sum mounts.",
    },
    {
        "fact": "gpu_presence",
        "preferred_evidence": "nvidia-smi first, then lspci -nn when available",
        "rule": "Adapter discovery is not CUDA readiness.",
    },
    {
        "fact": "cuda_state",
        "preferred_evidence": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits",
        "rule": "Only successful nvidia-smi yields nvidia-cuda-ready; retain per-device evidence.",
    },
]


def _topology_id(host_topology: str, target_lane: str) -> str:
    lane_suffix = target_lane.split("/", 1)[1]
    return f"ubuntu-topology-{host_topology}-{lane_suffix}"


def _gpu_state_id(gpu_state: str) -> str:
    return f"ubuntu-gpu-state-{gpu_state}"


def _topology_evidence_commands(host_topology: str) -> list[str]:
    return [
        "systemd-detect-virt",
        "systemd-detect-virt --vm",
        "/etc/os-release",
        "uname -m",
        "nproc",
        "lscpu -J",
        "/proc/meminfo",
        "df -P <ollama-data-path>",
    ]


def _gpu_state_evidence_commands(gpu_state: str) -> list[str]:
    commands = ["nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"]
    if gpu_state in {"gpu-present-not-cuda-ready", "gpu-state-unknown"}:
        commands.append("lspci -nn")
    return commands


def _topology_unknown_fields() -> list[str]:
    return sorted(CAPACITY_FIELDS)


def build_topology_categories() -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    for host_topology, target_lane in TOPOLOGY_LANES:
        record_id = _topology_id(host_topology, target_lane)
        notes = (
            f"Runtime-observed host topology category for {target_lane}. "
            "Capacity values are supplied by the host at install time; "
            "this record does not prescribe RAM, CPU, disk, or GPU requirements."
        )
        if host_topology == "virtual-machine":
            notes += (
                " Virtualization kind may be kvm, qemu, vmware, or hypervisor strings;"
                " must not infer cloud provider — provider remains null."
            )
        categories.append(
            {
                "id": record_id,
                "target_lane": target_lane,
                "host_topology": host_topology,
                "runtime_detection_required": True,
                "runtime_evidence_commands": _topology_evidence_commands(host_topology),
                "cpu_architecture": None,
                "visible_cpu_threads": None,
                "system_ram_gib": None,
                "ollama_filesystem_path": None,
                "free_disk_gib": None,
                "gpu_runtime_state": None,
                "gpu_vendor": None,
                "gpu_model": None,
                "gpu_memory_gib": None,
                "cuda_runtime_ready": None,
                "virtualization_kind": None,
                "provider": None,
                "classification": "runtime-observed-host-category",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "unknown_fields": _topology_unknown_fields(),
                "notes": notes,
            }
        )
    return categories


def build_gpu_state_categories() -> list[dict[str, Any]]:
    notes_map = {
        "nvidia-cuda-ready": (
            "Successful nvidia-smi query with per-device name and memory.total evidence. "
            "lspci alone is insufficient."
        ),
        "gpu-present-not-cuda-ready": (
            "Display or compute adapter may be visible via lspci, but nvidia-smi did not succeed. "
            "Do not infer VRAM, ROCm, or CUDA readiness from PCI IDs."
        ),
        "no-supported-gpu-detected": (
            "Neither nvidia-smi nor lspci reported a supported GPU adapter at observation time."
        ),
        "gpu-state-unknown": (
            "GPU probing incomplete or ambiguous; retain unknown and use CPU-safe fallback."
        ),
    }
    categories: list[dict[str, Any]] = []
    for gpu_state in GPU_RUNTIME_STATES:
        cuda_ready = True if gpu_state == "nvidia-cuda-ready" else None
        categories.append(
            {
                "id": _gpu_state_id(gpu_state),
                "target_lane": None,
                "host_topology": None,
                "runtime_detection_required": True,
                "runtime_evidence_commands": _gpu_state_evidence_commands(gpu_state),
                "cpu_architecture": None,
                "visible_cpu_threads": None,
                "system_ram_gib": None,
                "ollama_filesystem_path": None,
                "free_disk_gib": None,
                "gpu_runtime_state": gpu_state,
                "gpu_vendor": None,
                "gpu_model": None,
                "gpu_memory_gib": None,
                "cuda_runtime_ready": cuda_ready,
                "virtualization_kind": None,
                "provider": None,
                "classification": "runtime-observed-host-category",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "unknown_fields": sorted(set(_topology_unknown_fields()) | {"host_topology", "target_lane"}),
                "notes": notes_map[gpu_state],
            }
        )
    return categories


def _ram_band_bounds(band_id: str) -> tuple[float | None, float | None]:
    mapping: dict[str, tuple[float | None, float | None]] = {
        "ubuntu-ram-band-under-4gib": (None, 4.0),
        "ubuntu-ram-band-4-to-8gib": (4.0, 8.0),
        "ubuntu-ram-band-8-to-12gib": (8.0, 12.0),
        "ubuntu-ram-band-12-to-24gib": (12.0, 24.0),
        "ubuntu-ram-band-24gib-plus": (24.0, None),
    }
    return mapping[band_id]


def build_runtime_menu_bands(menu: dict[str, Any]) -> list[dict[str, Any]]:
    band_id_map = {
        "fallback-under-4gb": "ubuntu-ram-band-under-4gib",
        "pilot-4gb": "ubuntu-ram-band-4-to-8gib",
        "pilot-8gb": "ubuntu-ram-band-8-to-12gib",
        "pilot-12gb": "ubuntu-ram-band-12-to-24gib",
        "pilot-24gb-plus": "ubuntu-ram-band-24gib-plus",
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
                "source_script_path": UBUNTU_SOURCE_SCRIPT,
                "source_script_version": UBUNTU_SOURCE_SCRIPT_VERSION,
                "classification": "runtime_menu_band_only",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "disk_guard_mib_by_candidate": band.get("disk_thresholds_mib", {}),
                "source_policy_path": str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
                "notes": (
                    "Happy Nerds runtime-menu band sourced from install/ubuntu/cpu/8.2.sh "
                    "RAM detection (detect_hardware) and auditable pilot policy in "
                    "8ball-base-pilot-menu.json. Disk guard values are runtime download guards only."
                ),
            }
        )
    bands.sort(key=lambda row: (row["lower_bound_gib"] is not None, row["lower_bound_gib"] or 0.0))
    return bands


def build_observation_contract_markdown() -> str:
    lines = [
        "# Ubuntu runtime observation contract (C10.1-10)",
        "",
        "Minimal Linux-runtime evidence contract for Ubuntu CPU and CUDA install lanes.",
        "Values are observed on the actual host at install time; committed taxonomy rows",
        "define categories and evidence rules only — not fixed machine capacities.",
        "",
        "## Facts and evidence",
        "",
        "| Fact | Preferred evidence | Rule |",
        "| --- | --- | --- |",
    ]
    for fact in OBSERVATION_CONTRACT_FACTS:
        lines.append(
            f"| {fact['fact']} | `{fact['preferred_evidence']}` | {fact['rule']} |"
        )
    lines.extend(
        [
            "",
            "## Provider boundary",
            "",
            "Hypervisor strings from `systemd-detect-virt` (kvm, qemu, vmware, oracle, microsoft)",
            "identify virtualization kind at most. They must **not** infer cloud provider.",
            "Provider remains `null` unless a separately selected provider lane supplies sourced data.",
            "",
            "## CUDA boundary",
            "",
            "A PCI display adapter from `lspci` is not CUDA-ready. Only a successful",
            "`nvidia-smi` query yields `nvidia-cuda-ready`. Retain per-device GPU evidence;",
            "do not aggregate VRAM across devices without per-device records.",
            "",
            "## Sanitization",
            "",
            "No command output, serial number, MAC address, hostname, IP address, user name,",
            "or credential may be committed. Tests use sanitized fixtures only.",
            "",
        ]
    )
    return "\n".join(lines)


def build_observation_contract_json(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.ubuntu-runtime-observation-contract.v1",
        "target_lanes": ["ubuntu/cpu", "ubuntu/cuda"],
        "facts": OBSERVATION_CONTRACT_FACTS,
        "provider_inference_forbidden": True,
        "lspci_cuda_ready_forbidden": True,
        "per_device_gpu_evidence_required": True,
        "source_paths": [
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            UBUNTU_SOURCE_SCRIPT,
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
        ],
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
    }


def build_lane_projection(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
) -> dict[str, Any]:
    topology_ids = [c["id"] for c in categories if c.get("host_topology") is not None]
    gpu_state_ids = [c["id"] for c in categories if c.get("gpu_runtime_state") is not None]
    band_ids = [b["ram_band_id"] for b in bands]

    def lane_entry(lane: str) -> dict[str, Any]:
        lane_topology = [cid for cid in topology_ids if cid.endswith(f"-{lane.split('/')[1]}")]
        return {
            "target_lane": lane,
            "observation_contract_path": str(OUTPUT_CONTRACT_JSON.relative_to(REPO_ROOT)),
            "topology_category_ids": lane_topology,
            "gpu_state_category_ids": gpu_state_ids,
            "runtime_menu_band_ids": band_ids,
            "classification": "runtime-observed-host-category",
            "model_fit_proven": False,
            "runtime_trial_required": True,
            "provider": None,
            "notes": (
                "Lane projection joins runtime topology categories, shared GPU-state categories, "
                "and RAM-menu bands without multiplying the C10 model-size index."
            ),
        }

    return {
        "schema_version": "c10.ubuntu-lane-runtime-contract-projection.v1",
        "lanes": {
            "ubuntu/cpu": lane_entry("ubuntu/cpu"),
            "ubuntu/cuda": lane_entry("ubuntu/cuda"),
        },
    }


def build_taxonomy_payload(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.ubuntu-runtime-capability-taxonomy.v1",
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "categories": categories,
        "runtime_menu_bands": bands,
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
            row["model_fit_proven"] = str(record["model_fit_proven"]).lower()
            row["runtime_trial_required"] = str(record["runtime_trial_required"]).lower()
            row["runtime_detection_required"] = str(record["runtime_detection_required"]).lower()
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


def load_pilot_menu(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / PILOT_MENU_JSON.relative_to(REPO_ROOT)).read_text(encoding="utf-8"))


def load_taxonomy(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / TAXONOMY_JSON.relative_to(REPO_ROOT)).read_text(encoding="utf-8"))


def build_report(categories: list[dict[str, Any]], bands: list[dict[str, Any]]) -> dict[str, Any]:
    topology = [c for c in categories if c.get("host_topology")]
    gpu_states = [c for c in categories if c.get("gpu_runtime_state")]
    return {
        "schema_version": "c10.ubuntu-capability-report.v1",
        "category_counts": {
            "topology_lane": len(topology),
            "gpu_runtime_state": len(gpu_states),
            "total": len(categories),
            "runtime_menu_bands": len(bands),
        },
        "topology_lane_ids": [c["id"] for c in topology],
        "gpu_state_ids": [c["id"] for c in gpu_states],
        "runtime_menu_band_ids": [b["ram_band_id"] for b in bands],
        "target_lanes": ["ubuntu/cpu", "ubuntu/cuda"],
        "provider_inference_forbidden": True,
        "model_requirements_formula_generated": False,
        "c10_index_expansion": False,
        "source_paths": [
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
            UBUNTU_SOURCE_SCRIPT,
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# C10.1-10 Ubuntu runtime host capability report",
        "",
        "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_ubuntu_compatibility.py`.",
        "",
        "## Taxonomy inventory",
        "",
        f"- Topology × lane categories: **{report['category_counts']['topology_lane']}**",
        f"- GPU runtime-state categories: **{report['category_counts']['gpu_runtime_state']}**",
        f"- Runtime-menu bands: **{report['category_counts']['runtime_menu_bands']}**",
        "",
        "## Target lanes",
        "",
    ]
    for lane in report["target_lanes"]:
        lines.append(f"- `{lane}`")
    lines.extend(
        [
            "",
            "## Evidence posture",
            "",
            f"- Provider inference from VM detection forbidden: **{report['provider_inference_forbidden']}**",
            f"- Model requirements formula-generated in this pass: **{report['model_requirements_formula_generated']}**",
            f"- C10 index expansion: **{report['c10_index_expansion']}**",
            "",
            "Host capacity fields remain null in committed taxonomy rows; runtime observation supplies values.",
            "RAM-menu bands are `runtime_menu_band_only` and do not claim model fit.",
        ]
    )
    return "\n".join(lines) + "\n"


def update_provider_readme() -> None:
    readme = REPO_ROOT / "profiles" / "provider-compatibility" / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    marker = "## Ubuntu runtime hosts (C10.1-10)"
    if marker in text:
        return
    addition = "\n".join(
        [
            "",
            "## Ubuntu runtime hosts (C10.1-10)",
            "",
            "- `ubuntu/host-capability-categories.json` and `.csv` — 10 runtime host categories",
            "- `ubuntu/runtime-observation-contract.json` — Linux evidence contract",
            "- `ubuntu/lane-runtime-contract-projection.json` — `ubuntu/cpu` and `ubuntu/cuda` projections",
            "",
            "Source tables:",
            "- `AGENTS/data-science/profile-mapping/ubuntu-runtime-capability-taxonomy.json`",
            "- `AGENTS/data-science/profile-mapping/ubuntu-runtime-observation-contract.md`",
            "- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`",
            "",
            "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
            "",
        ]
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")


def generate_ubuntu_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    menu = load_pilot_menu(repo_root)
    categories = build_topology_categories() + build_gpu_state_categories()
    bands = build_runtime_menu_bands(menu)
    taxonomy = build_taxonomy_payload(categories, bands)
    contract_json = build_observation_contract_json(categories, bands)
    lane_projection = build_lane_projection(categories, bands)
    contract_md = build_observation_contract_markdown()

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_MD.write_text(contract_md, encoding="utf-8")
    TAXONOMY_JSON.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_taxonomy_csv(TAXONOMY_CSV, categories)

    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CATEGORIES_JSON.write_text(
        json.dumps({"categories": categories, "runtime_menu_bands": bands}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_taxonomy_csv(OUTPUT_CATEGORIES_CSV, categories)
    OUTPUT_CONTRACT_JSON.write_text(json.dumps(contract_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT_LANE_PROJECTION_JSON.write_text(
        json.dumps(lane_projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    bands_csv = COMPAT_DIR / "runtime-menu-bands.csv"
    write_bands_csv(bands_csv, bands)

    update_provider_readme()

    report = build_report(categories, bands)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report_markdown(report), encoding="utf-8")

    return {
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "topology_lane_ids": [c["id"] for c in categories if c.get("host_topology")],
        "gpu_state_ids": [c["id"] for c in categories if c.get("gpu_runtime_state")],
        "runtime_menu_band_ids": [b["ram_band_id"] for b in bands],
    }


def _invalid_capacity_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "" or value == 0:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "0", "null", "none"}:
        return True
    return False


def validate_ubuntu_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []

    if not TAXONOMY_JSON.is_file():
        errors.append(f"Missing taxonomy: {TAXONOMY_JSON}")
        return errors
    if not CONTRACT_MD.is_file():
        errors.append(f"Missing observation contract markdown: {CONTRACT_MD}")

    taxonomy = load_taxonomy(repo_root)
    categories = taxonomy.get("categories", [])
    bands = taxonomy.get("runtime_menu_bands", [])

    if len(categories) != 10:
        errors.append(f"Expected 10 taxonomy categories, found {len(categories)}")

    topology_pairs = {
        (c.get("host_topology"), c.get("target_lane"))
        for c in categories
        if c.get("host_topology") is not None
    }
    expected_topology = set(TOPOLOGY_LANES)
    if topology_pairs != expected_topology:
        errors.append(f"Topology/lane combinations mismatch: {topology_pairs} != {expected_topology}")

    gpu_states = {c.get("gpu_runtime_state") for c in categories if c.get("gpu_runtime_state")}
    if gpu_states != set(GPU_RUNTIME_STATES):
        errors.append(f"GPU runtime states mismatch: {gpu_states}")

    if len(bands) != 5:
        errors.append(f"Expected 5 runtime-menu bands, found {len(bands)}")

    menu = load_pilot_menu(repo_root)
    expected_candidates = {
        tuple(band["ordered_pilot_candidates"]) for band in menu.get("bands", [])
    }
    actual_candidates = {tuple(band["runtime_trial_candidates"]) for band in bands}
    if actual_candidates != expected_candidates:
        errors.append("Runtime-menu bands do not match 8ball-base-pilot-menu.json candidate ladders")

    ids = [c["id"] for c in categories]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate taxonomy category IDs")

    for record in categories:
        for field in TAXONOMY_COLUMNS:
            if field not in record and field not in {"id"}:
                errors.append(f"Category {record.get('id')} missing field {field}")
        if record.get("classification") != "runtime-observed-host-category":
            errors.append(f"Category {record['id']} must use runtime-observed-host-category")
        if record.get("model_fit_proven") is True:
            errors.append(f"Category {record['id']} must not claim model_fit_proven")
        if record.get("runtime_trial_required") is not True:
            errors.append(f"Category {record['id']} must set runtime_trial_required=true")
        if record.get("provider") not in (None, ""):
            errors.append(f"Category {record['id']} must keep provider null")
        for field in CAPACITY_FIELDS:
            if _invalid_capacity_value(record.get(field)):
                errors.append(f"Category {record['id']} has invalid placeholder for {field}: {record.get(field)!r}")
        notes = record.get("notes", "")
        if PROVIDER_INFERENCE_PATTERNS.search(notes) and not any(
            phrase in notes.lower()
            for phrase in ("must not infer", "remains null", "stays null", "forbidden")
        ):
            errors.append(f"Category {record['id']} notes may infer provider from VM output")
        if record.get("gpu_runtime_state") == "gpu-present-not-cuda-ready":
            commands = record.get("runtime_evidence_commands", [])
            if "lspci" in " ".join(commands).lower() and "nvidia-smi" not in " ".join(commands).lower():
                errors.append(f"Category {record['id']} must require nvidia-smi before lspci")

    for band in bands:
        if band.get("classification") != "runtime_menu_band_only":
            errors.append(f"Band {band.get('ram_band_id')} must use runtime_menu_band_only")
        if band.get("model_fit_proven") is True:
            errors.append(f"Band {band.get('ram_band_id')} must not claim model_fit_proven")

    contract_path = OUTPUT_CONTRACT_JSON
    if not contract_path.is_file():
        errors.append(f"Missing generated contract JSON: {contract_path}")
    else:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if not contract.get("provider_inference_forbidden"):
            errors.append("Observation contract must forbid provider inference")
        if not contract.get("lspci_cuda_ready_forbidden"):
            errors.append("Observation contract must forbid lspci-only CUDA readiness")

    projection_path = OUTPUT_LANE_PROJECTION_JSON
    if not projection_path.is_file():
        errors.append(f"Missing lane projection: {projection_path}")
    else:
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        for lane in ("ubuntu/cpu", "ubuntu/cuda"):
            entry = projection.get("lanes", {}).get(lane)
            if not entry:
                errors.append(f"Missing lane projection for {lane}")
            elif entry.get("model_fit_proven") is True:
                errors.append(f"Lane projection {lane} must not claim model_fit_proven")

    if CONTRACT_MD.is_file():
        md_text = CONTRACT_MD.read_text(encoding="utf-8")
        if "never infer provider" not in md_text.lower() and "must **not** infer" not in md_text.lower():
            errors.append("Observation contract markdown must document provider non-inference")

    index_csv = repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

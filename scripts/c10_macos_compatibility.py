"""macOS runtime host capability taxonomy and observation contract for C10.1-12."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping" / "macos"
PILOT_MENU_JSON = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping" / "8ball-base-pilot-menu.json"
TAXONOMY_JSON = MAPPING_DIR / "runtime-capability-taxonomy.json"
TAXONOMY_CSV = MAPPING_DIR / "runtime-capability-taxonomy.csv"
CONTRACT_MD = MAPPING_DIR / "runtime-observation-contract.md"
OBSERVE_SCRIPT = REPO_ROOT / "scripts" / "macos-observe-host.sh"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility" / "macos"
OUTPUT_CATEGORIES_JSON = COMPAT_DIR / "host-capability-categories.json"
OUTPUT_CATEGORIES_CSV = COMPAT_DIR / "host-capability-categories.csv"
OUTPUT_CONTRACT_JSON = COMPAT_DIR / "runtime-observation-contract.json"
OUTPUT_LANE_PROJECTION_JSON = COMPAT_DIR / "lane-runtime-contract-projection.json"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "capability-catalog" / "macos" / "capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-12-macos-capability-report.md"

MAC_SOURCE_SCRIPT = "install/mac/apple-silicon/8.2.sh"
MAC_SOURCE_SCRIPT_VERSION = "public-8.2-mac-apple-silicon"

CANONICAL_LANES = ("mac/apple-silicon", "mac/intel")

TOPOLOGY_KINDS = ["bare_metal", "virtual_machine", "unknown"]

DISPLAY_CATEGORIES = [
    "no_gpu_or_unknown",
    "gpu_present_unverified",
    "display_data_partial",
]

CAPACITY_FIELDS = frozenset(
    {
        "physical_memory_mb",
        "free_install_disk_mb",
        "cpu_threads",
        "gpu_name",
        "gpu_memory_mb",
        "os_version",
        "cpu_brand",
    }
)

TAXONOMY_COLUMNS = [
    "id",
    "category_kind",
    "target_lane",
    "topology",
    "display_category",
    "runtime_detection_required",
    "runtime_evidence_commands",
    "architecture",
    "physical_memory_mb",
    "free_install_disk_mb",
    "cpu_threads",
    "gpu_present",
    "gpu_name",
    "gpu_memory_mb",
    "metal_status",
    "cuda_status",
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
        "fact": "os_version",
        "preferred_evidence": "sw_vers -productVersion",
        "rule": "Store raw version or null; native macOS only.",
    },
    {
        "fact": "kernel_architecture",
        "preferred_evidence": "uname -m",
        "rule": "arm64 maps to mac/apple-silicon; x86_64 maps to mac/intel; other yields unknown lane.",
    },
    {
        "fact": "cpu_brand",
        "preferred_evidence": "sysctl -n machdep.cpu.brand_string",
        "rule": "Null on failure; do not infer core count from marketing name.",
    },
    {
        "fact": "cpu_threads",
        "preferred_evidence": "sysctl -n hw.logicalcpu",
        "rule": "Positive integer or null.",
    },
    {
        "fact": "physical_memory",
        "preferred_evidence": "sysctl -n hw.memsize",
        "rule": "Convert bytes to integer MiB; observed fact only, not a model requirement.",
    },
    {
        "fact": "free_install_disk",
        "preferred_evidence": "df -Pk <install-root>",
        "rule": "Available KiB on install destination converted to MiB.",
    },
    {
        "fact": "display_adapters",
        "preferred_evidence": "system_profiler SPDisplaysDataType",
        "rule": "Retain observed chipset/vendor/Metal text only; do not parse absent fields.",
    },
    {
        "fact": "virtualization",
        "preferred_evidence": "sysctl -n hw.optional.hypervisor when present",
        "rule": "Otherwise unknown; do not guess bare metal versus VM.",
    },
]


def select_target_lane(architecture: str | None) -> str | None:
    if architecture == "arm64":
        return "mac/apple-silicon"
    if architecture == "x86_64":
        return "mac/intel"
    return None


def normalize_observation(payload: dict[str, Any]) -> dict[str, Any]:
    arch = payload.get("architecture")
    if arch in (None, "", "unknown"):
        arch_value = "unknown"
    else:
        arch_value = str(arch)

    lane = select_target_lane(arch_value if arch_value != "unknown" else None)
    normalized = {
        "os_family": "macos",
        "architecture": arch_value,
        "target_lane": lane if lane else "unknown",
        "provider": "mac",
        "topology": payload.get("topology") or "unknown",
        "os_version": payload.get("os_version"),
        "cpu_brand": payload.get("cpu_brand"),
        "physical_memory_mb": payload.get("physical_memory_mb"),
        "free_install_disk_mb": payload.get("free_install_disk_mb"),
        "cpu_threads": payload.get("cpu_threads"),
        "gpu_present": payload.get("gpu_present") or "unknown",
        "gpu_name": payload.get("gpu_name"),
        "gpu_memory_mb": payload.get("gpu_memory_mb"),
        "metal_status": payload.get("metal_status") or "unknown",
        "cuda_status": "not_applicable",
    }
    if lane == "mac/apple-silicon":
        normalized["gpu_memory_mb"] = None
    if normalized["gpu_memory_mb"] in ("", 0):
        normalized["gpu_memory_mb"] = None
    return normalized


def _base_category(
    *,
    record_id: str,
    category_kind: str,
    notes: str,
    runtime_evidence_commands: list[str],
    target_lane: str | None = None,
    topology: str | None = None,
    display_category: str | None = None,
    architecture: str | None = None,
    cuda_status: str = "not_applicable",
) -> dict[str, Any]:
    return {
        "id": record_id,
        "category_kind": category_kind,
        "target_lane": target_lane,
        "topology": topology,
        "display_category": display_category,
        "runtime_detection_required": True,
        "runtime_evidence_commands": runtime_evidence_commands,
        "architecture": architecture,
        "physical_memory_mb": None,
        "free_install_disk_mb": None,
        "cpu_threads": None,
        "gpu_present": None,
        "gpu_name": None,
        "gpu_memory_mb": None,
        "metal_status": None,
        "cuda_status": cuda_status,
        "classification": "runtime-observed-host-category",
        "model_fit_proven": False,
        "runtime_trial_required": True,
        "runtime_verification_required": True,
        "unknown_fields": sorted(CAPACITY_FIELDS),
        "notes": notes,
    }


def build_lane_routing_categories() -> list[dict[str, Any]]:
    evidence = [
        "uname -m",
        "sw_vers -productVersion",
        "sysctl -n hw.memsize",
    ]
    return [
        _base_category(
            record_id="mac-lane-routing-apple-silicon",
            category_kind="lane_routing",
            target_lane="mac/apple-silicon",
            architecture="arm64",
            runtime_evidence_commands=evidence,
            notes=(
                "Native macOS host observed as arm64. Not a CUDA lane. "
                "Unified memory is represented by physical_memory_mb; never copy into gpu_memory_mb."
            ),
        ),
        _base_category(
            record_id="mac-lane-routing-intel",
            category_kind="lane_routing",
            target_lane="mac/intel",
            architecture="x86_64",
            runtime_evidence_commands=evidence,
            notes=(
                "Native macOS host observed as x86_64. Not a CUDA lane. "
                "Display adapters are evidence only; CUDA readiness is not_applicable."
            ),
        ),
    ]


def build_topology_categories() -> list[dict[str, Any]]:
    evidence = ["sysctl -n hw.optional.hypervisor", "system_profiler SPHardwareDataType"]
    notes = {
        "bare_metal": "Hypervisor signal absent or explicitly zero when available.",
        "virtual_machine": "Hypervisor signal present when OS exposes hw.optional.hypervisor.",
        "unknown": "Topology unknown when virtualization signal is missing or ambiguous.",
    }
    return [
        _base_category(
            record_id=f"mac-topology-{kind.replace('_', '-')}",
            category_kind="host_topology",
            topology=kind,
            runtime_evidence_commands=evidence,
            notes=notes[kind],
        )
        for kind in TOPOLOGY_KINDS
    ]


def build_display_categories() -> list[dict[str, Any]]:
    notes = {
        "no_gpu_or_unknown": "No display adapter evidence or GPU state unknown.",
        "gpu_present_unverified": (
            "system_profiler reports an adapter, but Metal/GPU memory remain unverified facts."
        ),
        "display_data_partial": "system_profiler returned partial display data; retain unknown fields.",
    }
    commands = ["system_profiler SPDisplaysDataType"]
    return [
        _base_category(
            record_id=f"mac-display-{category.replace('_', '-')}",
            category_kind="display_evidence",
            display_category=category,
            runtime_evidence_commands=commands,
            notes=notes[category],
        )
        for category in DISPLAY_CATEGORIES
    ]


def _ram_band_bounds(band_id: str) -> tuple[float | None, float | None]:
    mapping: dict[str, tuple[float | None, float | None]] = {
        "mac-ram-band-under-4gib-or-unknown": (None, 4.0),
        "mac-ram-band-4-to-8gib": (4.0, 8.0),
        "mac-ram-band-8-to-12gib": (8.0, 12.0),
        "mac-ram-band-12-to-24gib": (12.0, 24.0),
        "mac-ram-band-24gib-plus": (24.0, None),
    }
    return mapping[band_id]


def build_runtime_menu_bands(menu: dict[str, Any]) -> list[dict[str, Any]]:
    band_id_map = {
        "fallback-under-4gb": "mac-ram-band-under-4gib-or-unknown",
        "pilot-4gb": "mac-ram-band-4-to-8gib",
        "pilot-8gb": "mac-ram-band-8-to-12gib",
        "pilot-12gb": "mac-ram-band-12-to-24gib",
        "pilot-24gb-plus": "mac-ram-band-24gib-plus",
    }
    bands: list[dict[str, Any]] = []
    for band in menu.get("bands", []):
        pilot_band = band["pilot_menu_band"]
        ram_band_id = band_id_map[pilot_band]
        lower, upper = _ram_band_bounds(ram_band_id)
        notes = (
            "Happy Nerds runtime-menu band from install/mac/apple-silicon/8.2.sh policy "
            "via 8ball-base-pilot-menu.json. Trial order only; not a model-fit guarantee."
        )
        if pilot_band == "fallback-under-4gb":
            notes += " Applies when physical memory is under 4 GiB or memory measurement is unknown."
        bands.append(
            {
                "ram_band_id": ram_band_id,
                "lower_bound_gib": lower,
                "upper_bound_gib_or_null": upper,
                "runtime_trial_candidates": list(band["ordered_pilot_candidates"]),
                "source_script_path": MAC_SOURCE_SCRIPT,
                "source_script_version": MAC_SOURCE_SCRIPT_VERSION,
                "classification": "runtime_menu_band_only",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "disk_guard_mib_by_candidate": band.get("disk_thresholds_mib", {}),
                "source_policy_path": str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
                "notes": notes,
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
    return [
        {
            "candidate_ollama_ref": candidate,
            "required_free_disk_gib": round(thresholds[candidate] / 1024, 4),
            "required_free_disk_mib": thresholds[candidate],
            "source_script_path": MAC_SOURCE_SCRIPT,
            "source_policy_path": str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
            "classification": "runtime_download_guard_only",
            "model_fit_proven": False,
            "runtime_trial_required": True,
            "notes": "Runtime free-disk guard before trial pull; not a catalog disk requirement.",
        }
        for candidate in order
    ]


def build_observation_contract_markdown() -> str:
    lines = [
        "# macOS runtime observation contract (C10.1-12)",
        "",
        "Native macOS evidence contract for `mac/apple-silicon` and `mac/intel` lanes.",
        "Committed taxonomy rows define categories only — not fixed Mac SKU capacities.",
        "",
        "## Normalized record fields",
        "",
        "| Field | Values | Notes |",
        "| --- | --- | --- |",
        "| `os_family` | `macos` | Native macOS only |",
        "| `architecture` | `arm64`, `x86_64`, `unknown` | From `uname -m` |",
        "| `target_lane` | `mac/apple-silicon`, `mac/intel`, `unknown` | arm64/x86_64 mapping only |",
        "| `provider` | `mac` | Not a cloud provider lane |",
        "| `topology` | `bare_metal`, `virtual_machine`, `unknown` | Hypervisor signal when present |",
        "| `physical_memory_mb` | integer or null | Unified memory on Apple Silicon |",
        "| `gpu_memory_mb` | integer or null | Normally null on Apple Silicon |",
        "| `cuda_status` | `not_applicable` | Mac lanes are never CUDA lanes |",
        "",
        "## Facts and evidence",
        "",
        "| Fact | Preferred observation | Rule |",
        "| --- | --- | --- |",
    ]
    for fact in OBSERVATION_CONTRACT_FACTS:
        lines.append(
            f"| {fact['fact']} | `{fact['preferred_evidence']}` | {fact['rule']} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Do not use `/proc/meminfo`, `nproc`, `lspci`, or `nvidia-smi` as primary Mac sources.",
            "- Display adapters are hardware evidence only; Metal and GPU memory stay unknown unless observed.",
            "- Apple Silicon unified memory must not be copied into `gpu_memory_mb`.",
            "- Observed RAM/disk facts must not change catalog model-size fit records.",
            "",
            "## Observation helper",
            "",
            f"Shell helper: `{OBSERVE_SCRIPT.relative_to(REPO_ROOT)}`",
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
        "schema_version": "c10.macos-runtime-observation-contract.v1",
        "target_lanes": list(CANONICAL_LANES),
        "facts": OBSERVATION_CONTRACT_FACTS,
        "cuda_lane_forbidden": True,
        "apple_silicon_unified_memory_vram_forbidden": True,
        "linux_commands_forbidden": [
            "/proc/meminfo",
            "nproc",
            "lspci",
            "nvidia-smi",
        ],
        "observe_script_path": str(OBSERVE_SCRIPT.relative_to(REPO_ROOT)),
        "source_paths": [
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            MAC_SOURCE_SCRIPT,
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
    display_ids = [c["id"] for c in categories if c["category_kind"] == "display_evidence"]
    band_ids = [b["ram_band_id"] for b in bands]

    def lane_entry(lane: str) -> dict[str, Any]:
        routing_id = f"mac-lane-routing-{lane.split('/')[1]}"
        return {
            "target_lane": lane,
            "observation_contract_path": str(OUTPUT_CONTRACT_JSON.relative_to(REPO_ROOT)),
            "lane_routing_category_id": routing_id,
            "host_topology_category_ids": topology_ids,
            "display_category_ids": display_ids,
            "runtime_menu_band_ids": band_ids,
            "disk_gate_candidate_refs": [gate["candidate_ollama_ref"] for gate in disk_gates],
            "classification": "runtime-observed-host-category",
            "model_fit_proven": False,
            "runtime_trial_required": True,
            "runtime_verification_required": True,
            "cuda_status": "not_applicable",
            "notes": "Mac lane projection only; does not multiply the C10 model-size index.",
        }

    return {
        "schema_version": "c10.macos-lane-runtime-contract-projection.v1",
        "canonical_lane_count": len(CANONICAL_LANES),
        "lanes": {
            "mac/apple-silicon": lane_entry("mac/apple-silicon"),
            "mac/intel": lane_entry("mac/intel"),
        },
    }


def build_taxonomy_payload(
    categories: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    disk_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "c10.macos-runtime-capability-taxonomy.v1",
        "canonical_lanes": list(CANONICAL_LANES),
        "category_count": len(categories),
        "runtime_menu_band_count": len(bands),
        "disk_gate_count": len(disk_gates),
        "categories": categories,
        "runtime_menu_bands": bands,
        "disk_gates": disk_gates,
    }


def _serialize_commands(commands: list[str]) -> str:
    return "|".join(commands)


def write_taxonomy_csv(path: Path, categories: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TAXONOMY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for record in categories:
            row = {key: record.get(key) for key in TAXONOMY_COLUMNS}
            row["runtime_evidence_commands"] = _serialize_commands(record["runtime_evidence_commands"])
            row["unknown_fields"] = "|".join(record["unknown_fields"])
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
            writer.writerow(
                {
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
            )


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
        "schema_version": "c10.macos-capability-report.v1",
        "category_counts": {
            "lane_routing": sum(1 for c in categories if c["category_kind"] == "lane_routing"),
            "host_topology": sum(1 for c in categories if c["category_kind"] == "host_topology"),
            "display_evidence": sum(1 for c in categories if c["category_kind"] == "display_evidence"),
            "total": len(categories),
            "runtime_menu_bands": len(bands),
            "disk_gates": len(disk_gates),
        },
        "canonical_lanes": list(CANONICAL_LANES),
        "install_lane_count_total": 10,
        "mac_lane_contribution": 2,
        "intentionally_unknown_fields": sorted(CAPACITY_FIELDS),
        "cuda_status": "not_applicable",
        "apple_silicon_unified_memory_vram_forbidden": True,
        "model_requirements_formula_generated": False,
        "c10_index_expansion": False,
        "source_paths": [
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(OBSERVE_SCRIPT.relative_to(REPO_ROOT)),
            str(REPORT_JSON.relative_to(REPO_ROOT)),
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
            MAC_SOURCE_SCRIPT,
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    counts = report["category_counts"]
    return "\n".join(
        [
            "# C10.1-12 macOS runtime host capability report",
            "",
            "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_macos_compatibility.py`.",
            "",
            "## Taxonomy inventory",
            "",
            f"- Lane routing categories: **{counts['lane_routing']}**",
            f"- Host topology categories: **{counts['host_topology']}**",
            f"- Display evidence categories: **{counts['display_evidence']}**",
            f"- Runtime-menu bands: **{counts['runtime_menu_bands']}**",
            f"- Disk gates: **{counts['disk_gates']}**",
            "",
            "## Lane posture",
            "",
            f"- Canonical install lanes total: **{report['install_lane_count_total']}**",
            f"- macOS contributes: **{report['mac_lane_contribution']}** lanes",
            f"- CUDA status: **{report['cuda_status']}**",
            "",
            "Apple Silicon unified memory must not be represented as dedicated VRAM.",
            "Observed RAM/disk values are runtime facts only and do not claim model fit.",
        ]
    ) + "\n"


def update_provider_readme() -> None:
    readme = REPO_ROOT / "profiles" / "provider-compatibility" / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    marker = "## macOS runtime hosts (C10.1-12)"
    if marker in text:
        return
    addition = "\n".join(
        [
            "",
            "## macOS runtime hosts (C10.1-12)",
            "",
            "- `macos/host-capability-categories.json` and `.csv` — runtime host categories",
            "- `macos/runtime-observation-contract.json` — macOS evidence contract",
            "- `macos/lane-runtime-contract-projection.json` — `mac/apple-silicon` and `mac/intel` projections",
            "",
            "Source tables:",
            "- `AGENTS/data-science/profile-mapping/macos/runtime-capability-taxonomy.json`",
            "- `AGENTS/data-science/profile-mapping/macos/runtime-observation-contract.md`",
            "- `scripts/macos-observe-host.sh`",
            "",
            "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
            "",
        ]
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")


def generate_macos_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    menu = load_pilot_menu(repo_root)
    categories = (
        build_lane_routing_categories()
        + build_topology_categories()
        + build_display_categories()
    )
    bands = build_runtime_menu_bands(menu)
    disk_gates = build_disk_gates(menu)
    taxonomy = build_taxonomy_payload(categories, bands, disk_gates)
    contract_json = build_observation_contract_json(categories, bands, disk_gates)
    lane_projection = build_lane_projection(categories, bands, disk_gates)

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_MD.write_text(build_observation_contract_markdown(), encoding="utf-8")
    TAXONOMY_JSON.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_taxonomy_csv(TAXONOMY_CSV, categories)

    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CATEGORIES_JSON.write_text(
        json.dumps(
            {"categories": categories, "runtime_menu_bands": bands, "disk_gates": disk_gates},
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
    return False


def validate_macos_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []

    if not TAXONOMY_JSON.is_file():
        errors.append(f"Missing taxonomy: {TAXONOMY_JSON}")
        return errors
    if not CONTRACT_MD.is_file():
        errors.append(f"Missing observation contract markdown: {CONTRACT_MD}")
    if not OBSERVE_SCRIPT.is_file():
        errors.append(f"Missing observation helper: {OBSERVE_SCRIPT}")

    taxonomy = load_taxonomy(repo_root)
    categories = taxonomy.get("categories", [])
    bands = taxonomy.get("runtime_menu_bands", [])
    disk_gates = taxonomy.get("disk_gates", [])

    if len(categories) != 8:
        errors.append(f"Expected 8 taxonomy categories, found {len(categories)}")
    if len(bands) != 5:
        errors.append(f"Expected 5 runtime-menu bands, found {len(bands)}")
    if len(disk_gates) != 5:
        errors.append(f"Expected 5 disk gates, found {len(disk_gates)}")

    lane_targets = {c["target_lane"] for c in categories if c["category_kind"] == "lane_routing"}
    if lane_targets != set(CANONICAL_LANES):
        errors.append(f"Lane routing targets mismatch: {lane_targets}")

    if select_target_lane("arm64") != "mac/apple-silicon":
        errors.append("arm64 must map only to mac/apple-silicon")
    if select_target_lane("x86_64") != "mac/intel":
        errors.append("x86_64 must map only to mac/intel")
    if select_target_lane("unknown") is not None:
        errors.append("unknown architecture must not select a confident Mac lane")

    forbidden = [
        repo_root / "install" / "mac" / name
        for name in ("vm", "physical", "apple-silicon-only", "intel-only")
    ]
    for path in forbidden:
        if path.exists():
            errors.append(f"Forbidden Mac sublane present: {path}")

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

    for record in categories:
        if record.get("cuda_status") != "not_applicable":
            errors.append(f"Category {record['id']} must keep cuda_status not_applicable")
        if record.get("model_fit_proven") is True:
            errors.append(f"Category {record['id']} must not claim model_fit_proven")
        for field in ("physical_memory_mb", "free_install_disk_mb", "cpu_threads", "gpu_name", "gpu_memory_mb"):
            if _invalid_capacity_value(record.get(field)):
                errors.append(f"Category {record['id']} has invalid placeholder for {field}")

    apple = normalize_observation(
        {
            "architecture": "arm64",
            "topology": "bare_metal",
            "physical_memory_mb": 16384,
            "gpu_memory_mb": 8192,
        }
    )
    if apple["gpu_memory_mb"] is not None:
        errors.append("Apple Silicon normalization must clear gpu_memory_mb")

    contract_path = OUTPUT_CONTRACT_JSON
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if not contract.get("cuda_lane_forbidden"):
            errors.append("Observation contract must forbid CUDA Mac lanes")
        if not contract.get("apple_silicon_unified_memory_vram_forbidden"):
            errors.append("Observation contract must forbid Apple Silicon VRAM fabrication")

    projection_path = OUTPUT_LANE_PROJECTION_JSON
    if not projection_path.is_file():
        errors.append(f"Missing lane projection: {projection_path}")
    else:
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if set(projection.get("lanes", {})) != set(CANONICAL_LANES):
            errors.append("Lane projection must reference only canonical Mac lanes")

    if not REPORT_JSON.is_file():
        errors.append(f"Missing macOS capability report: {REPORT_JSON}")
    elif "capability-catalog/macos/capability-report.json" not in str(REPORT_JSON):
        errors.append("macOS capability report must live under capability-catalog/macos/")

    legacy_index = repo_root / "profiles" / "legacy" / "c5-root-export" / "index.csv"
    index_csv = legacy_index if legacy_index.is_file() else repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

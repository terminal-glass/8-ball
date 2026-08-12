"""CUDA runtime observation contract and Ollama NVIDIA support mapping for C10.1-13."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping" / "cuda"
POLICY_JSON = MAPPING_DIR / "ollama-nvidia-support-policy.json"
TAXONOMY_JSON = MAPPING_DIR / "runtime-capability-taxonomy.json"
TAXONOMY_CSV = MAPPING_DIR / "runtime-capability-taxonomy.csv"
CONTRACT_MD = MAPPING_DIR / "runtime-observation-contract.md"
OBSERVE_LINUX = REPO_ROOT / "scripts" / "cuda-observe-linux.sh"
OBSERVE_WINDOWS = REPO_ROOT / "scripts" / "cuda-observe-windows.ps1"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility" / "cuda"
OUTPUT_CATEGORIES_JSON = COMPAT_DIR / "host-capability-categories.json"
OUTPUT_CATEGORIES_CSV = COMPAT_DIR / "host-capability-categories.csv"
OUTPUT_CONTRACT_JSON = COMPAT_DIR / "runtime-observation-contract.json"
OUTPUT_LANE_PROJECTION_JSON = COMPAT_DIR / "lane-runtime-contract-projection.json"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "capability-catalog" / "cuda" / "capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-13-cuda-capability-report.md"

CANONICAL_LANES = (
    "ubuntu/cuda",
    "windows/cuda",
    "cloud/digitalocean/gpu-droplet",
    "cloud/aws-lightsail/gpu",
)

MAC_LANES = ("mac/apple-silicon", "mac/intel")

NVIDIA_SMI_GPU_QUERY = (
    "nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total,compute_cap "
    "--format=csv,noheader,nounits"
)

OBSERVATION_STATES = ("cuda-observation-available", "cuda-observation-unavailable")

DEVICE_FIELDS = (
    "gpu_index",
    "gpu_uuid",
    "gpu_name",
    "gpu_vendor",
    "gpu_memory_mb",
    "compute_capability",
    "driver_version",
    "driver_reported_cuda_api_max_version",
    "cuda_toolkit_version",
    "cuda_visible",
    "ollama_nvidia_support",
    "observation_status",
    "source_command",
)

TAXONOMY_COLUMNS = [
    "id",
    "category_kind",
    "target_lane",
    "os_family",
    "provider_context",
    "observation_state",
    "runtime_detection_required",
    "runtime_evidence_commands",
    "gpu_vendor",
    "gpu_model",
    "gpu_memory_mb",
    "compute_capability",
    "driver_version",
    "driver_reported_cuda_api_max_version",
    "cuda_toolkit_version",
    "ollama_nvidia_support",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
    "unknown_fields",
    "notes",
]

CAPACITY_FIELDS = frozenset(
    {
        "gpu_vendor",
        "gpu_model",
        "gpu_memory_mb",
        "compute_capability",
        "driver_version",
        "driver_reported_cuda_api_max_version",
        "cuda_toolkit_version",
        "ollama_nvidia_support",
    }
)

HOME_PATH_PATTERN = re.compile(r"(?:/home/|/Users/|\\Users\\)[^,\s\"']+", re.I)
SECRET_PATTERN = re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[=:]\s*\S+")
CUDA_HEADER_VERSION_RE = re.compile(r"CUDA Version:\s*([0-9]+\.[0-9]+)")
NVCC_VERSION_RE = re.compile(r"release\s+([0-9]+\.[0-9]+)", re.I)
DRIVER_VERSION_RE = re.compile(r"^(\d+)")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_policy(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    path = repo_root / POLICY_JSON.relative_to(REPO_ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_driver_major(driver_version: str | None) -> int | None:
    if not driver_version:
        return None
    match = DRIVER_VERSION_RE.match(str(driver_version).strip())
    if not match:
        return None
    return int(match.group(1))


def parse_compute_capability(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "null", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def evaluate_ollama_nvidia_support(
    compute_capability: str | float | int | None,
    driver_version: str | None,
    policy: dict[str, Any] | None = None,
) -> str:
    policy = policy or load_policy()
    rules = policy["rules"]
    cc = parse_compute_capability(compute_capability)
    driver_major = parse_driver_major(driver_version)
    if cc is None or driver_major is None:
        return "unknown"
    if cc < float(rules["minimum_compute_capability"]):
        return "unsupported"
    if driver_major < int(rules["minimum_driver_version"]):
        return "unsupported"
    legacy = rules["legacy_compute_capability_range"]
    lower = float(legacy["lower_inclusive"])
    upper = float(legacy["upper_inclusive"])
    if lower <= cc <= upper and driver_major < int(legacy["minimum_driver_version"]):
        return "unsupported"
    return "supported"


def sanitize_observation_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = HOME_PATH_PATTERN.sub("<redacted-path>", text)
    text = SECRET_PATTERN.sub("<redacted-secret>", text)
    return text


def sanitize_cuda_visible_devices(value: str | None) -> str | None:
    if value is None:
        return None
    text = sanitize_observation_text(value)
    if not text:
        return None
    if len(text) > 256:
        return text[:256]
    return text


def parse_nvidia_smi_cuda_api_version(header_text: str | None) -> str | None:
    if not header_text:
        return None
    match = CUDA_HEADER_VERSION_RE.search(header_text)
    return match.group(1) if match else None


def parse_nvcc_toolkit_version(nvcc_output: str | None) -> str | None:
    if not nvcc_output:
        return None
    match = NVCC_VERSION_RE.search(nvcc_output)
    return match.group(1) if match else None


def parse_nvidia_smi_gpu_csv(csv_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in csv_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) < 5:
            continue
        record = {
            "gpu_index": parts[0],
            "gpu_uuid": parts[1],
            "gpu_name": parts[2],
            "driver_version": parts[3],
            "memory_total_mb": parts[4],
        }
        if len(parts) >= 6:
            record["compute_capability"] = parts[5]
        rows.append(record)
    return rows


def _non_negative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def resolve_cuda_visible_uuid(
    cuda_visible: str | None,
    devices: list[dict[str, Any]],
) -> str | None:
    if not cuda_visible or not devices:
        return None
    visible = cuda_visible.strip()
    if not visible:
        return None
    uuid_matches = [device["gpu_uuid"] for device in devices if device.get("gpu_uuid") == visible]
    if len(uuid_matches) == 1:
        return uuid_matches[0]
    if visible.isdigit():
        return None
    if visible.startswith("GPU-"):
        prefix_matches = [
            device["gpu_uuid"]
            for device in devices
            if isinstance(device.get("gpu_uuid"), str) and device["gpu_uuid"].startswith(visible)
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
    return None


def unknown_device_record(
    *,
    cuda_visible: str | None = None,
    driver_reported_cuda_api_max_version: str | None = None,
    cuda_toolkit_version: str | None = None,
) -> dict[str, Any]:
    return {
        "gpu_index": None,
        "gpu_uuid": None,
        "gpu_name": None,
        "gpu_vendor": "nvidia",
        "gpu_memory_mb": None,
        "compute_capability": None,
        "driver_version": None,
        "driver_reported_cuda_api_max_version": driver_reported_cuda_api_max_version,
        "cuda_toolkit_version": cuda_toolkit_version,
        "cuda_visible": cuda_visible,
        "ollama_nvidia_support": "unknown",
        "observation_status": "unavailable",
        "source_command": NVIDIA_SMI_GPU_QUERY,
    }


def normalize_device_record(
    raw: dict[str, str],
    *,
    policy: dict[str, Any] | None = None,
    driver_reported_cuda_api_max_version: str | None = None,
    cuda_toolkit_version: str | None = None,
    cuda_visible: str | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    driver_version = raw.get("driver_version") or None
    compute_capability = raw.get("compute_capability")
    memory_mb = _positive_int(raw.get("memory_total_mb"))
    return {
        "gpu_index": _non_negative_int(raw.get("gpu_index")),
        "gpu_uuid": raw.get("gpu_uuid") or None,
        "gpu_name": raw.get("gpu_name") or None,
        "gpu_vendor": "nvidia",
        "gpu_memory_mb": memory_mb,
        "compute_capability": compute_capability or None,
        "driver_version": driver_version,
        "driver_reported_cuda_api_max_version": driver_reported_cuda_api_max_version,
        "cuda_toolkit_version": cuda_toolkit_version,
        "cuda_visible": cuda_visible,
        "ollama_nvidia_support": evaluate_ollama_nvidia_support(
            compute_capability,
            driver_version,
            policy,
        ),
        "observation_status": "available",
        "source_command": NVIDIA_SMI_GPU_QUERY,
    }


def select_cuda_lane(
    os_family: str | None,
    provider_context: str | None,
    cuda_observation_available: bool,
) -> str | None:
    if not cuda_observation_available:
        return None
    family = (os_family or "unknown").lower()
    provider = (provider_context or "").lower() or None
    if family == "linux" and provider is None:
        return "ubuntu/cuda"
    if family == "windows" and provider is None:
        return "windows/cuda"
    if family == "linux" and provider == "digitalocean":
        return "cloud/digitalocean/gpu-droplet"
    if family == "linux" and provider == "aws-lightsail":
        return "cloud/aws-lightsail/gpu"
    return None


def build_observation_from_nvidia_smi(
    *,
    os_family: str,
    provider_context: str | None = None,
    nvidia_smi_csv: str | None = None,
    nvidia_smi_header: str | None = None,
    nvcc_output: str | None = None,
    cuda_visible_devices: str | None = None,
    nvidia_smi_version: str | None = None,
    observation_timestamp: str | None = None,
    observation_note: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    cuda_visible = sanitize_cuda_visible_devices(cuda_visible_devices)
    driver_cuda_api = parse_nvidia_smi_cuda_api_version(nvidia_smi_header)
    toolkit_version = parse_nvcc_toolkit_version(nvcc_output)

    devices: list[dict[str, Any]] = []
    if nvidia_smi_csv and nvidia_smi_csv.strip():
        for raw in parse_nvidia_smi_gpu_csv(nvidia_smi_csv):
            devices.append(
                normalize_device_record(
                    raw,
                    policy=policy,
                    driver_reported_cuda_api_max_version=driver_cuda_api,
                    cuda_toolkit_version=toolkit_version,
                    cuda_visible=cuda_visible,
                )
            )

    cuda_available = len(devices) > 0
    if not cuda_available:
        devices = [
            unknown_device_record(
                cuda_visible=cuda_visible,
                driver_reported_cuda_api_max_version=driver_cuda_api,
                cuda_toolkit_version=toolkit_version,
            )
        ]

    target_lane = select_cuda_lane(os_family, provider_context, cuda_available)
    return {
        "os_family": os_family,
        "provider_context": provider_context,
        "target_lane": target_lane if target_lane else "unknown",
        "devices": devices if cuda_available else [],
        "cuda_visible_devices_env": cuda_visible,
        "cuda_visible_resolved_uuid": resolve_cuda_visible_uuid(cuda_visible, devices) if cuda_available else None,
        "nvidia_smi_version": sanitize_observation_text(nvidia_smi_version),
        "observation_timestamp": observation_timestamp or utc_now_iso(),
        "observation_note": sanitize_observation_text(observation_note)
        or "nvidia-smi primary evidence; toolkit optional via nvcc",
        "observation_status": "available" if cuda_available else "unavailable",
        "cuda_runtime_ready": cuda_available,
        "mac_lane_forbidden": True,
        "rocm_vulkan_out_of_scope": True,
    }


def build_lane_categories() -> list[dict[str, Any]]:
    lane_specs = [
        ("ubuntu/cuda", "linux", None, "Linux bare-metal or non-provider host with successful nvidia-smi evidence."),
        (
            "windows/cuda",
            "windows",
            None,
            "Windows host with successful nvidia-smi evidence.",
        ),
        (
            "cloud/digitalocean/gpu-droplet",
            "linux",
            "digitalocean",
            "DigitalOcean provider context plus successful nvidia-smi evidence; provider must not be inferred from GPU.",
        ),
        (
            "cloud/aws-lightsail/gpu",
            "linux",
            "aws-lightsail",
            "AWS Lightsail provider context plus successful nvidia-smi evidence; provider must not be inferred from GPU.",
        ),
    ]
    categories: list[dict[str, Any]] = []
    for target_lane, os_family, provider_context, notes in lane_specs:
        categories.append(
            {
                "id": f"cuda-lane-{target_lane.replace('/', '-')}",
                "category_kind": "lane_routing",
                "target_lane": target_lane,
                "os_family": os_family,
                "provider_context": provider_context,
                "observation_state": None,
                "runtime_detection_required": True,
                "runtime_evidence_commands": [
                    NVIDIA_SMI_GPU_QUERY,
                    "nvidia-smi",
                    "nvcc --version",
                ],
                "gpu_vendor": None,
                "gpu_model": None,
                "gpu_memory_mb": None,
                "compute_capability": None,
                "driver_version": None,
                "driver_reported_cuda_api_max_version": None,
                "cuda_toolkit_version": None,
                "ollama_nvidia_support": None,
                "classification": "runtime-observed-host-category",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "unknown_fields": sorted(CAPACITY_FIELDS),
                "notes": notes,
            }
        )
    return categories


def build_observation_state_categories() -> list[dict[str, Any]]:
    specs = [
        (
            "cuda-observation-available",
            "nvidia-smi succeeded and at least one GPU record was normalized.",
        ),
        (
            "cuda-observation-unavailable",
            "nvidia-smi missing, failed, or reported no devices; do not label CUDA-ready.",
        ),
    ]
    categories: list[dict[str, Any]] = []
    for state, notes in specs:
        categories.append(
            {
                "id": f"cuda-state-{state}",
                "category_kind": "observation_state",
                "target_lane": None,
                "os_family": None,
                "provider_context": None,
                "observation_state": state,
                "runtime_detection_required": True,
                "runtime_evidence_commands": [NVIDIA_SMI_GPU_QUERY, "nvidia-smi"],
                "gpu_vendor": None,
                "gpu_model": None,
                "gpu_memory_mb": None,
                "compute_capability": None,
                "driver_version": None,
                "driver_reported_cuda_api_max_version": None,
                "cuda_toolkit_version": None,
                "ollama_nvidia_support": "unknown" if state.endswith("unavailable") else None,
                "classification": "runtime-observed-host-category",
                "model_fit_proven": False,
                "runtime_trial_required": True,
                "unknown_fields": sorted(CAPACITY_FIELDS | {"target_lane", "os_family", "provider_context"}),
                "notes": notes,
            }
        )
    return categories


def build_observation_contract_json(categories: list[dict[str, Any]]) -> dict[str, Any]:
    policy = load_policy()
    return {
        "schema_version": "c10.cuda-runtime-observation-contract.v1",
        "policy": {
            "policy_id": policy["policy_id"],
            "source_url": policy["source_url"],
            "retrieval_date": policy["retrieval_date"],
            "schema_version": policy["schema_version"],
        },
        "device_fields": list(DEVICE_FIELDS),
        "primary_evidence_command": NVIDIA_SMI_GPU_QUERY,
        "toolkit_evidence_command": "nvcc --version",
        "driver_cuda_api_field": "driver_reported_cuda_api_max_version",
        "toolkit_field": "cuda_toolkit_version",
        "cuda_visible_devices_rules": [
            "Record sanitized CUDA_VISIBLE_DEVICES when set.",
            "Resolve UUID only when mapping is unambiguous.",
            "Do not treat numeric device indices as persistent identity.",
        ],
        "forbidden_substitutes": [
            "lspci",
            "Device Manager display names",
            "provider-plan labels",
            "WMI adapter memory",
            "GPU product-name lookup tables",
        ],
        "mac_lane_forbidden": True,
        "rocm_vulkan_out_of_scope": True,
        "model_vram_fit_from_observation_forbidden": True,
        "category_count": len(categories),
        "canonical_lanes": list(CANONICAL_LANES),
    }


def build_lane_projection(categories: list[dict[str, Any]]) -> dict[str, Any]:
    lane_categories = [c for c in categories if c["category_kind"] == "lane_routing"]
    state_categories = [c for c in categories if c["category_kind"] == "observation_state"]

    def lane_entry(lane: str) -> dict[str, Any]:
        lane_cats = [c["id"] for c in lane_categories if c["target_lane"] == lane]
        return {
            "target_lane": lane,
            "lane_category_ids": lane_cats,
            "shared_observation_state_ids": [c["id"] for c in state_categories],
            "classification": "runtime-observed-host-category",
            "model_fit_proven": False,
            "runtime_trial_required": True,
            "provider_inference_forbidden": True,
            "notes": (
                "CUDA lane projection joins OS/provider context with nvidia-smi evidence. "
                "Host VRAM and driver facts do not change catalog model-size fit records."
            ),
        }

    return {
        "schema_version": "c10.cuda-lane-runtime-contract-projection.v1",
        "lanes": {lane: lane_entry(lane) for lane in CANONICAL_LANES},
        "mac_lanes_explicitly_excluded": list(MAC_LANES),
    }


def build_taxonomy_payload(categories: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "c10.cuda-runtime-capability-taxonomy.v1",
        "category_count": len(categories),
        "canonical_cuda_lanes": list(CANONICAL_LANES),
        "categories": categories,
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


def load_taxonomy(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / TAXONOMY_JSON.relative_to(REPO_ROOT)).read_text(encoding="utf-8"))


def build_report(categories: list[dict[str, Any]]) -> dict[str, Any]:
    policy = load_policy()
    lane_categories = [c for c in categories if c["category_kind"] == "lane_routing"]
    state_categories = [c for c in categories if c["category_kind"] == "observation_state"]
    return {
        "schema_version": "c10.cuda-capability-report.v1",
        "category_counts": {
            "lane_routing": len(lane_categories),
            "observation_state": len(state_categories),
            "total": len(categories),
        },
        "canonical_cuda_lane_count": len(CANONICAL_LANES),
        "canonical_install_lane_count": 10,
        "lane_category_ids": [c["id"] for c in lane_categories],
        "observation_state_ids": [c["id"] for c in state_categories],
        "target_lanes": list(CANONICAL_LANES),
        "mac_lanes_not_cuda": list(MAC_LANES),
        "policy_id": policy["policy_id"],
        "policy_source_url": policy["source_url"],
        "policy_retrieval_date": policy["retrieval_date"],
        "all_gpu_values_require_source_command": True,
        "provider_inference_forbidden": True,
        "model_requirements_from_gpu_observation_forbidden": True,
        "c10_index_expansion": False,
        "source_paths": [
            str(POLICY_JSON.relative_to(REPO_ROOT)),
            str(TAXONOMY_JSON.relative_to(REPO_ROOT)),
            str(CONTRACT_MD.relative_to(REPO_ROOT)),
            str(REPORT_JSON.relative_to(REPO_ROOT)),
            str(OBSERVE_LINUX.relative_to(REPO_ROOT)),
            str(OBSERVE_WINDOWS.relative_to(REPO_ROOT)),
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# C10.1-13 CUDA runtime capability report",
        "",
        "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_cuda_compatibility.py`.",
        "",
        "## Taxonomy inventory",
        "",
        f"- Lane routing categories: **{report['category_counts']['lane_routing']}**",
        f"- Observation-state categories: **{report['category_counts']['observation_state']}**",
        f"- Canonical CUDA lanes: **{report['canonical_cuda_lane_count']}**",
        f"- Canonical install lanes (unchanged): **{report['canonical_install_lane_count']}**",
        "",
        "## Policy",
        "",
        f"- Policy id: `{report['policy_id']}`",
        f"- Source: {report['policy_source_url']}",
        f"- Retrieval date: {report['policy_retrieval_date']}",
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
            f"- All GPU values require source_command: **{report['all_gpu_values_require_source_command']}**",
            f"- Provider inference forbidden: **{report['provider_inference_forbidden']}**",
            f"- Model requirements from GPU observation forbidden: **{report['model_requirements_from_gpu_observation_forbidden']}**",
            f"- Mac lanes classified CUDA: **false** (`{', '.join(report['mac_lanes_not_cuda'])}` stay non-CUDA)",
            f"- C10 index expansion: **{report['c10_index_expansion']}**",
            "",
            "Host VRAM and driver observations remain runtime facts only.",
            "ollama_nvidia_support is policy-derived and does not prove model VRAM fit.",
        ]
    )
    return "\n".join(lines) + "\n"


def update_provider_readme() -> None:
    readme = REPO_ROOT / "profiles" / "provider-compatibility" / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    marker = "## CUDA runtime hosts (C10.1-13)"
    if marker in text:
        return
    addition = "\n".join(
        [
            "",
            "## CUDA runtime hosts (C10.1-13)",
            "",
            "- `cuda/host-capability-categories.json` and `.csv` — CUDA lane and observation-state categories",
            "- `cuda/runtime-observation-contract.json` — cross-platform nvidia-smi evidence contract",
            "- `cuda/lane-runtime-contract-projection.json` — four canonical CUDA lane projections",
            "",
            "Source tables:",
            "- `AGENTS/data-science/profile-mapping/cuda/ollama-nvidia-support-policy.json`",
            "- `AGENTS/data-science/profile-mapping/cuda/runtime-capability-taxonomy.json`",
            "- `AGENTS/data-science/profile-mapping/cuda/runtime-observation-contract.md`",
            "- `scripts/cuda-observe-linux.sh`",
            "- `scripts/cuda-observe-windows.ps1`",
            "",
            "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
            "",
        ]
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")


def generate_cuda_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    categories = build_lane_categories() + build_observation_state_categories()
    taxonomy = build_taxonomy_payload(categories)
    contract_json = build_observation_contract_json(categories)
    lane_projection = build_lane_projection(categories)

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    TAXONOMY_JSON.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_taxonomy_csv(TAXONOMY_CSV, categories)

    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CATEGORIES_JSON.write_text(
        json.dumps({"categories": categories}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_taxonomy_csv(OUTPUT_CATEGORIES_CSV, categories)
    OUTPUT_CONTRACT_JSON.write_text(json.dumps(contract_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT_LANE_PROJECTION_JSON.write_text(
        json.dumps(lane_projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    update_provider_readme()

    report = build_report(categories)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report_markdown(report), encoding="utf-8")

    return {
        "category_count": len(categories),
        "lane_routing_count": len([c for c in categories if c["category_kind"] == "lane_routing"]),
        "observation_state_count": len([c for c in categories if c["category_kind"] == "observation_state"]),
        "canonical_cuda_lanes": list(CANONICAL_LANES),
    }


def _invalid_capacity_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "" or value == 0:
        return True
    return False


def validate_cuda_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []

    if not POLICY_JSON.is_file():
        errors.append(f"Missing policy: {POLICY_JSON}")
        return errors
    if not TAXONOMY_JSON.is_file():
        errors.append(f"Missing taxonomy: {TAXONOMY_JSON}")
        return errors
    if not CONTRACT_MD.is_file():
        errors.append(f"Missing observation contract markdown: {CONTRACT_MD}")
    if not OBSERVE_LINUX.is_file():
        errors.append(f"Missing Linux observation helper: {OBSERVE_LINUX}")
    if not OBSERVE_WINDOWS.is_file():
        errors.append(f"Missing Windows observation helper: {OBSERVE_WINDOWS}")

    policy = load_policy(repo_root)
    for key in ("source_url", "retrieval_date", "rules"):
        if key not in policy:
            errors.append(f"Policy missing required key: {key}")

    taxonomy = load_taxonomy(repo_root)
    categories = taxonomy.get("categories", [])
    if len(categories) != 6:
        errors.append(f"Expected 6 taxonomy categories, found {len(categories)}")

    lane_targets = {c["target_lane"] for c in categories if c["category_kind"] == "lane_routing"}
    if lane_targets != set(CANONICAL_LANES):
        errors.append(f"Lane routing targets mismatch: {lane_targets}")

    for lane in MAC_LANES:
        if select_cuda_lane("macos", None, True) is not None:
            errors.append("macOS must never select a CUDA lane")
        if lane in lane_targets:
            errors.append(f"Mac lane incorrectly present in CUDA taxonomy: {lane}")

    if evaluate_ollama_nvidia_support(5.0, "570", policy) != "supported":
        errors.append("Policy boundary: CC 5.0 + driver 570 must be supported")
    if evaluate_ollama_nvidia_support(5.0, "569", policy) != "unsupported":
        errors.append("Policy boundary: CC 5.0 + driver 569 must be unsupported")
    if evaluate_ollama_nvidia_support(6.3, "550", policy) != "supported":
        errors.append("Policy boundary: CC 6.3 + driver 550 must be supported")
    if evaluate_ollama_nvidia_support(4.9, "600", policy) != "unsupported":
        errors.append("Policy boundary: CC 4.9 must be unsupported")
    if evaluate_ollama_nvidia_support(None, "600", policy) != "unknown":
        errors.append("Missing compute capability must be unknown")
    if evaluate_ollama_nvidia_support(8.0, None, policy) != "unknown":
        errors.append("Missing driver must be unknown")

    unavailable = build_observation_from_nvidia_smi(os_family="linux", nvidia_smi_csv="")
    if unavailable["observation_status"] != "unavailable":
        errors.append("Empty nvidia-smi output must be unavailable")
    if unavailable["target_lane"] != "unknown":
        errors.append("Unavailable CUDA observation must not select a lane")
    if unavailable["cuda_runtime_ready"] is not False:
        errors.append("Unavailable CUDA observation must not be CUDA-ready")

    multi = build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv=(
            "0, GPU-1111, GPU A, 570.00, 8192, 8.0\n"
            "1, GPU-2222, GPU B, 570.00, 16384, 8.6\n"
        ),
        nvidia_smi_header="CUDA Version: 12.4",
    )
    if len(multi["devices"]) != 2:
        errors.append("Multi-GPU observation must retain all devices")
    uuids = {device["gpu_uuid"] for device in multi["devices"]}
    if uuids != {"GPU-1111", "GPU-2222"}:
        errors.append(f"Multi-GPU UUIDs mismatch: {uuids}")

    toolkit = build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-3333, GPU C, 570.00, 8192, 8.0",
        nvidia_smi_header="CUDA Version: 12.4",
        nvcc_output="Cuda compilation tools, release 12.2, V12.2.140",
    )
    device = toolkit["devices"][0]
    if device["driver_reported_cuda_api_max_version"] != "12.4":
        errors.append("Driver CUDA API version must come from nvidia-smi header")
    if device["cuda_toolkit_version"] != "12.2":
        errors.append("Toolkit version must come from nvcc only")
    if device["driver_reported_cuda_api_max_version"] == device["cuda_toolkit_version"]:
        errors.append("Driver API version must not be copied into toolkit version when they differ")

    visible = build_observation_from_nvidia_smi(
        os_family="linux",
        nvidia_smi_csv="0, GPU-aaaa, GPU A, 570.00, 8192, 8.0\n1, GPU-bbbb, GPU B, 570.00, 16384, 8.6",
        cuda_visible_devices="0",
    )
    if visible["cuda_visible_resolved_uuid"] is not None:
        errors.append("Numeric CUDA_VISIBLE_DEVICES must not resolve to UUID")

    if select_cuda_lane("linux", None, True) != "ubuntu/cuda":
        errors.append("Linux non-provider must map to ubuntu/cuda")
    if select_cuda_lane("windows", None, True) != "windows/cuda":
        errors.append("Windows must map to windows/cuda")
    if select_cuda_lane("linux", "digitalocean", True) != "cloud/digitalocean/gpu-droplet":
        errors.append("DigitalOcean context must map to cloud/digitalocean/gpu-droplet")
    if select_cuda_lane("linux", "aws-lightsail", True) != "cloud/aws-lightsail/gpu":
        errors.append("Lightsail context must map to cloud/aws-lightsail/gpu")
    if select_cuda_lane("linux", None, False) is not None:
        errors.append("CUDA unavailable must not select lane")

    for record in categories:
        if record.get("model_fit_proven") is True:
            errors.append(f"Category {record['id']} must not claim model_fit_proven")
        for field in CAPACITY_FIELDS:
            if _invalid_capacity_value(record.get(field)):
                errors.append(f"Category {record['id']} has invalid placeholder for {field}")

    contract_path = OUTPUT_CONTRACT_JSON
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if contract.get("model_vram_fit_from_observation_forbidden") is not True:
            errors.append("Observation contract must forbid model VRAM fit from GPU observation")
        if set(contract.get("canonical_lanes", [])) != set(CANONICAL_LANES):
            errors.append("Observation contract canonical lanes mismatch")

    projection_path = OUTPUT_LANE_PROJECTION_JSON
    if not projection_path.is_file():
        errors.append(f"Missing lane projection: {projection_path}")
    else:
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if set(projection.get("lanes", {})) != set(CANONICAL_LANES):
            errors.append("Lane projection must reference only canonical CUDA lanes")

    if not REPORT_JSON.is_file():
        errors.append(f"Missing CUDA capability report: {REPORT_JSON}")
    elif "capability-catalog/cuda/capability-report.json" not in str(REPORT_JSON):
        errors.append("CUDA capability report must live under capability-catalog/cuda/")

    index_csv = repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

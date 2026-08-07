"""Canonical C10 install lane manifest and matrix audit helpers."""
from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = REPO_ROOT / "profiles"
INSTALL_DIR = REPO_ROOT / "install"
LANES_MANIFEST_PATH = PROFILES_DIR / "lanes.json"
AUDIT_JSON_PATH = PROFILES_DIR / "_lane-matrix-audit.json"
AUDIT_CSV_PATH = PROFILES_DIR / "_lane-matrix-audit.csv"

REQUIRED_INSTALL_LANE_COUNT = 10
REQUIRED_INSTALL_PAYLOAD_FILE_COUNT = 50
REQUIRED_INSTALL_README_COUNT = 10
STAGE_PAYLOAD_FILES = (
    "3-cpu.json",
    "4-ram.json",
    "5-hard_disk.json",
    "6-CPU_only.json",
    "7-video_card.json",
)
PROFILE_LANE_FILES = ("lane.json", "profile-sizes.csv", *STAGE_PAYLOAD_FILES)

SHELL_PAYLOAD_ROLES: tuple[tuple[str, str], ...] = (
    ("trial_bootstrap", "trial-install.sh"),
    ("stage_8_1", "8.1.sh"),
    ("stage_8_2", "8.2.sh"),
    ("stage_8_3", "8.3.sh"),
    ("motd_asset", "assets/first-MOTD.txt"),
)

POWERSHELL_PAYLOAD_ROLES: tuple[tuple[str, str], ...] = (
    ("trial_bootstrap", "trial-install.ps1"),
    ("stage_8_1", "8.1.ps1"),
    ("stage_8_2", "8.2.ps1"),
    ("stage_8_3", "8.3.ps1"),
    ("motd_asset", "assets/first-MOTD.txt"),
)

CANONICAL_LANE_ROWS: tuple[dict[str, str], ...] = (
    {
        "lane_id": "ubuntu-cpu",
        "install_path": "install/ubuntu/cpu/",
        "profile_path": "ubuntu/cpu/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "ubuntu-cuda",
        "install_path": "install/ubuntu/cuda/",
        "profile_path": "ubuntu/cuda/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "mac-apple-silicon",
        "install_path": "install/mac/apple-silicon/",
        "profile_path": "mac/apple-silicon/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "mac-intel",
        "install_path": "install/mac/intel/",
        "profile_path": "mac/intel/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "windows-cpu",
        "install_path": "install/windows/cpu/",
        "profile_path": "windows/cpu/",
        "runtime_type": "PowerShell",
    },
    {
        "lane_id": "windows-cuda",
        "install_path": "install/windows/cuda/",
        "profile_path": "windows/cuda/",
        "runtime_type": "PowerShell",
    },
    {
        "lane_id": "digitalocean-cpu-droplet",
        "install_path": "install/cloud/digitalocean/cpu-droplet/",
        "profile_path": "cloud/digitalocean/cpu-droplet/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "digitalocean-gpu-droplet",
        "install_path": "install/cloud/digitalocean/gpu-droplet/",
        "profile_path": "cloud/digitalocean/gpu-droplet/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "aws-lightsail-cpu",
        "install_path": "install/cloud/aws-lightsail/cpu/",
        "profile_path": "cloud/aws-lightsail/cpu/",
        "runtime_type": "shell",
    },
    {
        "lane_id": "aws-lightsail-gpu",
        "install_path": "install/cloud/aws-lightsail/gpu/",
        "profile_path": "cloud/aws-lightsail/gpu/",
        "runtime_type": "shell",
    },
)

# Generator-only hardware metadata keyed by lane_id (not duplicated in lanes.json).
LANE_GENERATOR_META: dict[str, dict[str, Any]] = {
    "ubuntu-cpu": {
        "platform": "ubuntu",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "ubuntu",
        "detection_signals": ["os=linux", "distro=ubuntu|debian", "cuda=false"],
        "assumed_profile_id": "windows_cpu_16gb",
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "CPU-only Ubuntu lane; GPU stage not required for lane selection.",
        "source_csv": "AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv",
    },
    "ubuntu-cuda": {
        "platform": "ubuntu",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "ubuntu",
        "detection_signals": ["os=linux", "cuda=true", "nvidia-smi"],
        "assumed_profile_id": "cuda_mid_12_16gb",
        "fallback_profile_id": "cuda_entry_8gb",
        "stage7_applicable": True,
        "stage7_reason": "CUDA server lane; NVIDIA GPU and driver detection required.",
        "source_csv": "AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv",
    },
    "mac-apple-silicon": {
        "platform": "mac",
        "provider": None,
        "architecture": "arm64",
        "gpu_lane": True,
        "source_dir": "mac",
        "detection_signals": ["os=darwin", "arch=arm64", "apple-metal"],
        "assumed_profile_id": "mac_air_apple_silicon_16gb",
        "fallback_profile_id": "mac_air_apple_silicon_8gb",
        "stage7_applicable": True,
        "stage7_reason": "Apple Silicon unified memory; Metal GPU path.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    "mac-intel": {
        "platform": "mac",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "mac",
        "detection_signals": ["os=darwin", "arch=x86_64"],
        "assumed_profile_id": "mac_air_apple_silicon_8gb",
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "Intel Mac lane uses CPU-only fallback; discrete GPU not assumed.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    "windows-cpu": {
        "platform": "windows",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "windows",
        "detection_signals": ["os=windows", "cuda=false"],
        "assumed_profile_id": "windows_cpu_16gb",
        "fallback_profile_id": "windows_cpu_8gb",
        "stage7_applicable": False,
        "stage7_reason": "Windows CPU-only lane; no NVIDIA CUDA assumed.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    "windows-cuda": {
        "platform": "windows",
        "provider": None,
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "windows",
        "detection_signals": ["os=windows", "cuda=true", "nvidia-smi"],
        "assumed_profile_id": "windows_nvidia_32_64gb_vram_12_16gb",
        "fallback_profile_id": "windows_nvidia_16gb_vram_6_8gb",
        "stage7_applicable": True,
        "stage7_reason": "Windows NVIDIA CUDA lane.",
        "source_csv": "AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv",
    },
    "digitalocean-cpu-droplet": {
        "platform": "cloud",
        "provider": "digitalocean",
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "cloud/digitalocean-droplet",
        "detection_signals": ["provider=digitalocean", "droplet=true", "gpu=false"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "DigitalOcean CPU droplet lane; no GPU assumed.",
        "source_csv": "AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/general-purpose.json",
    },
    "digitalocean-gpu-droplet": {
        "platform": "cloud",
        "provider": "digitalocean",
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "cloud/digitalocean-droplet",
        "detection_signals": ["provider=digitalocean", "gpu-droplet=true", "nvidia"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": True,
        "stage7_reason": "DigitalOcean GPU droplet lane.",
        "source_csv": "AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv",
    },
    "aws-lightsail-cpu": {
        "platform": "cloud",
        "provider": "aws-lightsail",
        "architecture": "x86_64",
        "gpu_lane": False,
        "source_dir": "cloud/aws-lightsail",
        "detection_signals": ["provider=aws", "lightsail=true", "gpu=false"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": False,
        "stage7_reason": "AWS Lightsail CPU instance lane.",
        "source_csv": "AGENTS/data-science/P2-Provider-Datasets/providers/lightsail/linux-unix-public-ipv4-bundles.json",
    },
    "aws-lightsail-gpu": {
        "platform": "cloud",
        "provider": "aws-lightsail",
        "architecture": "x86_64",
        "gpu_lane": True,
        "source_dir": "cloud/aws-lightsail",
        "detection_signals": ["provider=aws", "lightsail=true", "gpu=true"],
        "assumed_profile_id": None,
        "fallback_profile_id": None,
        "stage7_applicable": True,
        "stage7_reason": "AWS Lightsail GPU instance lane when GPU bundles are available.",
        "source_csv": "AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv",
    },
}

CPU_LANE_IDS = frozenset(
    {
        "ubuntu-cpu",
        "mac-intel",
        "windows-cpu",
        "digitalocean-cpu-droplet",
        "aws-lightsail-cpu",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload_roles_for_runtime(runtime_type: str) -> tuple[tuple[str, str], ...]:
    if runtime_type.lower() == "powershell":
        return POWERSHELL_PAYLOAD_ROLES
    return SHELL_PAYLOAD_ROLES


def build_install_lanes() -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    for row in CANONICAL_LANE_ROWS:
        meta = LANE_GENERATOR_META[row["lane_id"]]
        lanes.append(
            {
                "lane_id": row["lane_id"],
                "lane_path": row["profile_path"].rstrip("/"),
                "install_path": row["install_path"],
                "profile_path": row["profile_path"],
                "runtime_type": row["runtime_type"],
                "shell": row["runtime_type"].lower() != "powershell",
                **meta,
            }
        )
    return lanes


def lanes_manifest_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "c10.lanes.v1",
        "generated_at": generated_at or utc_now(),
        "lanes": [dict(row) for row in CANONICAL_LANE_ROWS],
    }


def write_lanes_manifest(path: Path = LANES_MANIFEST_PATH, *, generated_at: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = lanes_manifest_payload(generated_at=generated_at)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_lanes_manifest(path: Path = LANES_MANIFEST_PATH) -> dict[str, Any]:
    if not path.is_file():
        return lanes_manifest_payload()
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_lane_rows_from_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    return list(manifest.get("lanes") or [])


def lane_rows_match_canonical(rows: list[dict[str, str]]) -> bool:
    if len(rows) != REQUIRED_INSTALL_LANE_COUNT:
        return False
    expected = [dict(row) for row in CANONICAL_LANE_ROWS]
    normalized = []
    for row in rows:
        normalized.append(
            {
                "lane_id": row.get("lane_id", ""),
                "install_path": row.get("install_path", ""),
                "profile_path": row.get("profile_path", ""),
                "runtime_type": row.get("runtime_type", ""),
            }
        )
    return normalized == expected


def install_lane_dir(lane: dict[str, str]) -> Path:
    return REPO_ROOT / lane["install_path"].rstrip("/")


def payload_paths_for_lane(lane: dict[str, str]) -> list[Path]:
    lane_dir = install_lane_dir(lane)
    roles = payload_roles_for_runtime(lane["runtime_type"])
    return [lane_dir / rel for _role, rel in roles]


def count_tracked_install_payloads() -> int:
    count = 0
    for lane in CANONICAL_LANE_ROWS:
        for path in payload_paths_for_lane(lane):
            if path.is_file() and path.stat().st_size > 0:
                count += 1
    return count


def git_ls_files(pattern: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", pattern],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def count_tracked_payload_files_git() -> dict[str, int]:
    patterns = {
        "trial_bootstrap": "install/**/trial-install.*",
        "stage_8_1": "install/**/8.1.*",
        "stage_8_2": "install/**/8.2.*",
        "stage_8_3": "install/**/8.3.*",
        "motd_asset": "install/**/assets/first-MOTD.txt",
    }
    counts: dict[str, int] = {}
    for key, pattern in patterns.items():
        counts[key] = len(git_ls_files(pattern))
    counts["total_payload_files"] = sum(counts.values())
    counts["readme_files"] = len(git_ls_files("install/**/README.md"))
    return counts


def build_lane_matrix_audit(
    *,
    model_slug_count: int,
    model_size_count: int,
    actual_profile_lane_count: int,
    profile_matrix_row_count: int,
    profile_stage_payload_file_count: int,
    unknown_limit_count: int,
    conflict_count: int,
    data_gaps: list[str] | None = None,
    twelve_k_claim: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actual_install_lane_count = sum(
        1 for lane in CANONICAL_LANE_ROWS if install_lane_dir(lane).is_dir()
    )
    actual_payload = count_tracked_install_payloads()
    actual_readme = sum(
        1
        for lane in CANONICAL_LANE_ROWS
        if (install_lane_dir(lane) / "README.md").is_file()
        and (install_lane_dir(lane) / "README.md").stat().st_size > 0
    )
    expected_profile_lane_count = model_slug_count * REQUIRED_INSTALL_LANE_COUNT
    return {
        "schema_version": "c10.lane-matrix-audit.v1",
        "generated_at": utc_now(),
        "lanes": [dict(row) for row in CANONICAL_LANE_ROWS],
        "counts": {
            "required_install_lane_count": REQUIRED_INSTALL_LANE_COUNT,
            "actual_install_lane_count": actual_install_lane_count,
            "required_install_payload_file_count": REQUIRED_INSTALL_PAYLOAD_FILE_COUNT,
            "actual_install_payload_file_count": actual_payload,
            "required_install_readme_count": REQUIRED_INSTALL_README_COUNT,
            "actual_install_readme_count": actual_readme,
            "model_slug_count": model_slug_count,
            "model_size_count": model_size_count,
            "expected_profile_lane_count": expected_profile_lane_count,
            "actual_profile_lane_count": actual_profile_lane_count,
            "profile_matrix_row_count": profile_matrix_row_count,
            "profile_stage_payload_file_count": profile_stage_payload_file_count,
            "unknown_limit_count": unknown_limit_count,
            "conflict_count": conflict_count,
        },
        "formulas": {
            "expected_profile_lane_count": "model_slug_count × 10",
            "profile_matrix_row_count": "model_size_count × 10 (profiles/index.csv rows)",
            "profile_stage_payload_file_count": "model_slug_count × 10 × 5 (stage 3–7 files per model lane)",
            "required_install_payload_file_count": "10 lanes × 5 payload roles",
        },
        "twelve_thousand_verification": twelve_k_claim
        or {
            "observed": False,
            "claimed_category": None,
            "formula": None,
            "observed_count": None,
            "discrepancy": "12,000 not claimed; verify against profile_matrix_row_count or profile_stage_payload_file_count",
        },
        "data_gaps": data_gaps or [],
    }


def write_lane_matrix_audit(audit: dict[str, Any]) -> None:
    AUDIT_JSON_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = audit.get("lanes", [])
    counts = audit.get("counts", {})
    with AUDIT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "key", "value"])
        for lane in rows:
            writer.writerow(["lane", lane["lane_id"], lane["install_path"]])
            writer.writerow(["lane_profile_path", lane["lane_id"], lane["profile_path"]])
        for key, value in counts.items():
            writer.writerow(["count", key, value])


def windows_ps1_stub(lane_id: str, lane_path: str, script_name: str) -> str:
    return "\n".join(
        [
            f"# {script_name} — public 8-BALL installer lane script (Windows / PowerShell)",
            f"# Lane: {lane_path} ({lane_id})",
            "$ErrorActionPreference = 'Stop'",
            f"$EIGHTBALL_INSTALL_LANE = '{lane_path}'",
            f"$EIGHTBALL_LANE_ID = '{lane_id}'",
            "Write-Host '8-BALL Windows installer lane is metadata-only in this repository.'",
            "Write-Host 'Use profiles/<model>/$EIGHTBALL_INSTALL_LANE/ for AGENTS-backed fit data.'",
            "Write-Host 'Full Windows installer execution is not yet available in trial payloads.'",
            "exit 1",
            "",
        ]
    )

"""Focused tests for C10.2 Windows installer lanes (static analysis on Linux CI)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WIN_LIB = REPO_ROOT / "install/windows/lib/Windows-Common.ps1"
CPU_LANE = REPO_ROOT / "install/windows/cpu"
CUDA_LANE = REPO_ROOT / "install/windows/cuda"
LANE_SCRIPTS = ("trial-install.ps1", "8.1.ps1", "8.2.ps1", "8.3.ps1")
ROOT_DISPATCH = REPO_ROOT / "install/windows/trial-install.ps1"
PUBLIC_WINDOWS_EXECUTABLES = (
    [ROOT_DISPATCH]
    + [CPU_LANE / name for name in LANE_SCRIPTS]
    + [CUDA_LANE / name for name in LANE_SCRIPTS]
)
PROTECTED_PATHS = (
    REPO_ROOT / "profiles/index.csv",
    REPO_ROOT / "profiles/provider-compatibility/windows/lane-runtime-contract-projection.json",
    REPO_ROOT / "AGENTS/data-science/profile-mapping/C10.1-1-executable-install-matrix/install-matrix.csv",
)
FORBIDDEN_UNIX_PATTERNS = (
    re.compile(r"\bapt-get\b"),
    re.compile(r"/etc/os-release"),
    re.compile(r"/proc/"),
    re.compile(r"\bnproc\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"ollama serve"),
    re.compile(r"curl .*ollama\.com/install"),
    re.compile(r"/opt/philosopher"),
    re.compile(r"#!/usr/bin/env bash"),
    re.compile(r"\bsw_vers\b"),
    re.compile(r"\bopen -a\b"),
)
LINUX_DOWNLOAD_PATTERNS = (
    re.compile(r"Invoke-WebRequest.*ollama", re.IGNORECASE),
    re.compile(r"Start-Process.*OllamaSetup", re.IGNORECASE),
    re.compile(r"ollama\.com/download", re.IGNORECASE),
)


def _lane_ps1_files(lane: Path) -> list[Path]:
    return [lane / name for name in LANE_SCRIPTS] + [WIN_LIB]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def protected_hashes() -> dict[str, str]:
    return {str(path): _sha256(path) for path in PROTECTED_PATHS if path.is_file()}


def _assert_protected_unchanged(before: dict[str, str]) -> None:
    for path_str, digest in before.items():
        path = Path(path_str)
        assert path.is_file(), f"Protected path missing: {path}"
        assert _sha256(path) == digest, f"Protected path changed: {path}"


@pytest.mark.parametrize("lane", [CPU_LANE, CUDA_LANE])
def test_wsl_rejection_message_present(lane: Path) -> None:
    text = WIN_LIB.read_text(encoding="utf-8")
    assert "WSL is not a native Windows install target" in text
    assert "install/ubuntu/cpu" in text


def test_elevated_execution_refused_before_state_writes() -> None:
    text = WIN_LIB.read_text(encoding="utf-8")
    assert "Assert-NonElevated" in text
    assert "Administrator" in text
    assert "Resolve-EightballRoot" in text


def test_missing_ollama_manual_install_without_download() -> None:
    text = WIN_LIB.read_text(encoding="utf-8")
    assert "docs.ollama.com/windows" in text
    assert "does not download or run OllamaSetup.exe automatically" in text
    for pattern in LINUX_DOWNLOAD_PATTERNS:
        assert not pattern.search(text), f"Unexpected download pattern {pattern.pattern}"


def test_loopback_api_only() -> None:
    text = WIN_LIB.read_text(encoding="utf-8")
    assert "Assert-LoopbackOllamaApi" in text
    assert "127.0.0.1" in text
    assert "localhost" in text


def test_cuda_lane_requires_nvidia_smi_not_adapter_ram() -> None:
    cuda_81 = (CUDA_LANE / "8.1.ps1").read_text(encoding="utf-8")
    assert "Assert-CudaLaneEligibility" in cuda_81
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "nvidia-smi" in lib
    assert "AdapterRAM" not in lib
    assert "Win32_VideoController.AdapterRAM" not in lib


def test_cuda_failure_points_to_cpu_lane_without_driver_install() -> None:
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "install/windows/cpu/trial-install.ps1" in lib
    assert "does not install NVIDIA drivers" in lib or "does not install drivers" in lib


def test_install_volume_measurement_or_unknown() -> None:
    text = WIN_LIB.read_text(encoding="utf-8")
    assert "EIGHTBALL_DISK_FREE_GB" in text
    assert "Write-WindowsObservation" in text


@pytest.mark.parametrize("lane", [CPU_LANE, CUDA_LANE])
def test_no_unix_commands_in_windows_payloads(lane: Path) -> None:
    for path in _lane_ps1_files(lane):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_UNIX_PATTERNS:
            assert not pattern.search(text), f"{pattern.pattern} found in {path}"


def test_cpu_lane_result_is_cpu_mode(protected_hashes: dict[str, str]) -> None:
    text = (CPU_LANE / "8.2.ps1").read_text(encoding="utf-8")
    assert "$acceleration = 'cpu'" in text
    _assert_protected_unchanged(protected_hashes)


def test_cuda_lane_uses_cuda_acceleration_when_available(protected_hashes: dict[str, str]) -> None:
    text = (CUDA_LANE / "8.2.ps1").read_text(encoding="utf-8")
    assert "$acceleration = 'cuda'" in text
    _assert_protected_unchanged(protected_hashes)


def test_fallback_preserves_existing_models() -> None:
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "Remove-ModelIfNew" in lib
    assert "Test-ModelWasInstalledBefore" in lib
    assert "Keeping pre-existing model" in lib


def test_failed_new_pull_can_be_removed() -> None:
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "Removing newly pulled model that failed verification" in lib


def test_explicit_model_no_fallback_in_trial_install() -> None:
    for lane in (CPU_LANE, CUDA_LANE):
        text = (lane / "trial-install.ps1").read_text(encoding="utf-8")
        assert "-Model" in text
        assert "8.2.ps1" in text


def test_status_helper_path_documented() -> None:
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "8ball-status.ps1" in lib
    readme = (CPU_LANE / "README.md").read_text(encoding="utf-8")
    assert "not added to PATH" in readme


def test_all_windows_lane_files_exist() -> None:
    for lane in (CPU_LANE, CUDA_LANE):
        for name in (*LANE_SCRIPTS, "README.md"):
            assert (lane / name).is_file(), f"Missing {lane}/{name}"
        assert (lane / "assets/first-MOTD.txt").is_file()


def test_all_public_executables_expose_help_switch() -> None:
    for path in PUBLIC_WINDOWS_EXECUTABLES:
        text = path.read_text(encoding="utf-8")
        assert "[switch]$Help" in text, f"Missing -Help switch in {path}"


RUNTIME_GUARD_MARKERS = (
    "Assert-NonElevated",
    "Assert-NativeWindows",
    "Resolve-EightballRoot",
    "Invoke-RestMethod",
    "& $exe pull",
)


def test_help_exits_before_installer_mutations() -> None:
    for path in PUBLIC_WINDOWS_EXECUTABLES:
        text = path.read_text(encoding="utf-8")
        help_idx = text.find("if ($Help)")
        assert help_idx != -1, f"Missing early -Help handler in {path}"
        exit_idx = text.find("exit 0", help_idx)
        assert exit_idx != -1, f"-Help path must exit 0 in {path}"
        for marker in RUNTIME_GUARD_MARKERS:
            marker_idx = text.find(marker)
            if marker_idx == -1:
                continue
            assert exit_idx < marker_idx, f"{path}: -Help must exit before {marker}"


def test_root_dispatch_uses_common_fallback_not_repo_scripts() -> None:
    text = ROOT_DISPATCH.read_text(encoding="utf-8")
    assert "Resolve-WindowsTrialLaneDispatch" in text
    assert "cuda-observe-windows.ps1" not in text
    assert "Find-RepoRoot" not in text


def test_dispatch_logic_prefers_cpu_for_unsupported_nvidia() -> None:
    lib = WIN_LIB.read_text(encoding="utf-8")
    assert "Get-CudaEvidenceReadOnly" in lib
    assert "Resolve-WindowsTrialLaneDispatch" in lib
    assert "ollama_nvidia_support -eq 'unsupported'" in lib
    assert "return 'cpu'" in lib
    assert "return 'cuda'" in lib

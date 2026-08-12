"""Focused tests for C10.2 macOS installer lanes (mocked on Linux CI)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAC_LIB = REPO_ROOT / "install/mac/lib/macos-common.sh"
APPLE_SILICON = REPO_ROOT / "install/mac/apple-silicon"
INTEL = REPO_ROOT / "install/mac/intel"
LANE_SCRIPTS = (
    "trial-install.sh",
    "8.1.sh",
    "8.2.sh",
    "8.3.sh",
)
PROTECTED_PATHS = (
    REPO_ROOT / "profiles/index.csv",
    REPO_ROOT / "profiles/provider-compatibility/macos/lane-runtime-contract-projection.json",
    REPO_ROOT / "AGENTS/data-science/profile-mapping/C10.1-1-executable-install-matrix/install-matrix.csv",
)


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


def _write_mock_bin(mock_bin: Path, arch: str, *, ollama_app_home: Path | None = None) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)

    (mock_bin / "uname").write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            case "$1" in
              -s) echo Darwin ;;
              -m) echo {arch} ;;
              *) command -v /usr/bin/uname >/dev/null && /usr/bin/uname "$@" || /bin/uname "$@" ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "sw_vers").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            case "$1" in
              -productVersion) echo "${MOCK_MACOS_VERSION:-14.5}" ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "open").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    (mock_bin / "id").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            case "$1" in
              -u) echo "${MOCK_ID_UID:-1000}" ;;
              -un) echo "${MOCK_ID_UN:-ubuntu}" ;;
              *) exit 1 ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "stat").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [[ "$1" == "-c" && "$2" == "%u" ]]; then
              echo "${MOCK_ID_UID:-1000}"
              exit 0
            fi
            if [[ "$1" == "-f" && "$2" == "%u" ]]; then
              echo "${MOCK_ID_UID:-1000}"
              exit 0
            fi
            command -v /usr/bin/stat >/dev/null && exec /usr/bin/stat "$@"
            exec /bin/stat "$@"
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "ollama").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            LOG="${MOCK_OLLAMA_LOG:-/tmp/ollama-mock.log}"
            case "${1:-}" in
              list)
                if [[ -f "${MOCK_OLLAMA_LIST_FILE:-}" ]]; then
                  cat "${MOCK_OLLAMA_LIST_FILE}"
                else
                  echo "NAME"
                fi
                ;;
              pull)
                echo "pull $2" >>"${LOG}"
                if [[ -n "${MOCK_OLLAMA_PULL_FAIL:-}" && "${MOCK_OLLAMA_PULL_FAIL}" == "$2" ]]; then
                  exit 1
                fi
                exit 0
                ;;
              rm)
                echo "rm $2" >>"${LOG}"
                exit 0
                ;;
              *)
                exit 0
                ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "curl").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            url=""
            for arg in "$@"; do
              case "${arg}" in
                http://*|https://*) url="${arg}" ;;
              esac
            done
            if [[ "${url}" == *"/api/tags" ]]; then
              echo '{"models":[]}'
              exit 0
            fi
            if [[ "${url}" == *"/api/generate" ]]; then
              if [[ -n "${MOCK_GENERATE_FAIL:-}" ]]; then
                exit 1
              fi
              echo '{"response":"8-BALL READY"}'
              exit 0
            fi
            exit 1
            """
        ),
        encoding="utf-8",
    )
    for name in ("uname", "sw_vers", "open", "id", "stat", "ollama", "curl"):
        (mock_bin / name).chmod(stat.S_IRWXU)


def _mac_env(
    tmp_path: Path,
    lane: Path,
    arch: str,
    *,
    home: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    mock_bin = tmp_path / "mock-bin"
    home_dir = home or tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    state_root = home_dir / "Library/Application Support/8-BALL"
    state_root.mkdir(parents=True, exist_ok=True)
    ollama_app = home_dir / "Applications/Ollama.app"
    ollama_app.mkdir(parents=True, exist_ok=True)
    _write_mock_bin(mock_bin, arch, ollama_app_home=home_dir)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{mock_bin}:{env.get('PATH', '')}",
            "HOME": str(home_dir),
            "EIGHTBALL_ROOT": str(state_root),
            "MOCK_OLLAMA_LOG": str(tmp_path / "ollama.log"),
            "MOCK_OLLAMA_LIST_FILE": str(tmp_path / "ollama-list.txt"),
            "MOCK_ID_UID": str(os.getuid()),
        }
    )
    if extra_env:
        env.update(extra_env)
    return env


def _run_bash(script: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=script.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_observation(state_root: Path, **overrides: object) -> None:
    payload = {
        "os_family": "macos",
        "architecture": "arm64",
        "target_lane": "mac/apple-silicon",
        "provider": "mac",
        "topology": "unknown",
        "os_version": "14.5",
        "cpu_brand": "Apple M2",
        "physical_memory_mb": 24576,
        "free_install_disk_mb": 102400,
        "cpu_threads": 8,
        "gpu_present": True,
        "gpu_name": "Apple M2",
        "gpu_memory_mb": None,
        "metal_status": "supported",
        "cuda_status": "not_applicable",
        "install_root": str(state_root),
        "observation_status": "observed",
    }
    payload.update(overrides)
    path = state_root / "runtime-observation.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("lane", [APPLE_SILICON, INTEL])
def test_root_refuses_before_state_writes(tmp_path: Path, lane: Path) -> None:
    arch = "arm64" if lane.name == "apple-silicon" else "x86_64"
    env = _mac_env(tmp_path, lane, arch)
    state_root = Path(env["EIGHTBALL_ROOT"])
    env["MOCK_ID_UID"] = "0"
    result = _run_bash(lane / "8.1.sh", env)
    assert result.returncode == 1
    assert "normal user" in result.stderr.lower() or "root" in result.stderr.lower()
    assert not (state_root / "runtime-observation.json").exists()


@pytest.mark.parametrize(
    ("lane", "expected_arch", "wrong_arch"),
    [
        (APPLE_SILICON, "arm64", "x86_64"),
        (INTEL, "x86_64", "arm64"),
    ],
)
def test_lane_accepts_only_matching_architecture(
    tmp_path: Path, lane: Path, expected_arch: str, wrong_arch: str
) -> None:
    env = _mac_env(tmp_path, lane, wrong_arch)
    result = _run_bash(lane / "8.1.sh", env)
    assert result.returncode == 1
    assert expected_arch in result.stderr
    assert wrong_arch in result.stderr


def test_non_macos_produces_clear_failure(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["EIGHTBALL_ROOT"] = str(tmp_path / "state")
    Path(env["EIGHTBALL_ROOT"]).mkdir(parents=True)
    result = _run_bash(APPLE_SILICON / "8.1.sh", env)
    assert result.returncode == 1
    assert "native macos only" in result.stderr.lower()


def test_missing_ollama_app_shows_manual_install_without_download(tmp_path: Path) -> None:
    mock_bin = tmp_path / "mock-bin"
    home_dir = tmp_path / "home-no-ollama"
    home_dir.mkdir()
    state_root = home_dir / "Library/Application Support/8-BALL"
    state_root.mkdir(parents=True)
    _write_mock_bin(mock_bin, "arm64")
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{mock_bin}:{env.get('PATH', '')}",
            "HOME": str(home_dir),
            "EIGHTBALL_ROOT": str(state_root),
            "MOCK_ID_UID": str(os.getuid()),
        }
    )
    result = _run_bash(APPLE_SILICON / "8.1.sh", env)
    assert result.returncode == 1
    combined = result.stderr + result.stdout
    assert "docs.ollama.com/macos" in combined
    assert "does not download Ollama automatically" in combined
    assert "curl" not in combined.lower() or "does not download" in combined


def test_non_loopback_ollama_api_is_rejected(tmp_path: Path) -> None:
    env = _mac_env(tmp_path, APPLE_SILICON, "arm64")
    env["OLLAMA_API"] = "http://192.168.1.10:11434"
    result = _run_bash(APPLE_SILICON / "8.1.sh", env)
    assert result.returncode == 1
    assert "loopback" in result.stderr.lower()


def test_loopback_ollama_api_override_is_accepted(tmp_path: Path) -> None:
    env = _mac_env(tmp_path, APPLE_SILICON, "arm64")
    env["OLLAMA_API"] = "http://127.0.0.1:11434"
    result = _run_bash(APPLE_SILICON / "8.1.sh", env)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("lane", [APPLE_SILICON, INTEL])
def test_lane_scripts_exclude_forbidden_commands(lane: Path) -> None:
    import re

    invocation_patterns = (
        re.compile(r"^\s*sudo\s"),
        re.compile(r"\bapt-get\b"),
        re.compile(r"\bsystemctl\b"),
        re.compile(r"/proc/meminfo"),
        re.compile(r"\bnproc\b"),
        re.compile(r"\bnvidia-smi\b"),
        re.compile(r"\bollama\s+serve\b"),
    )
    for name in LANE_SCRIPTS:
        path = lane / name
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for pattern in invocation_patterns:
                assert not pattern.search(line), f"{pattern.pattern!r} in {path}:{line_no}: {line}"


def test_apple_silicon_result_has_no_vram_or_cuda(tmp_path: Path, protected_hashes: dict[str, str]) -> None:
    env = _mac_env(tmp_path, APPLE_SILICON, "arm64")
    state_root = Path(env["EIGHTBALL_ROOT"])
    _write_observation(state_root, architecture="arm64", metal_status="supported", gpu_memory_mb=None)
    result = _run_bash(APPLE_SILICON / "8.2.sh", env)
    assert result.returncode == 0, result.stderr
    payload = json.loads((state_root / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["acceleration"] == "metal"
    assert payload["observation"]["gpu_memory_mb"] is None
    blob = json.dumps(payload).lower()
    assert "cuda" not in blob
    assert "vram" not in blob
    _assert_protected_unchanged(protected_hashes)


def test_intel_result_is_cpu_mode(tmp_path: Path, protected_hashes: dict[str, str]) -> None:
    env = _mac_env(tmp_path, INTEL, "x86_64")
    state_root = Path(env["EIGHTBALL_ROOT"])
    _write_observation(
        state_root,
        architecture="x86_64",
        target_lane="mac/intel",
        metal_status="unsupported",
        gpu_memory_mb=None,
    )
    result = _run_bash(INTEL / "8.2.sh", env)
    assert result.returncode == 0, result.stderr
    payload = json.loads((state_root / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["acceleration"] == "cpu"
    assert payload["lane"] == "mac/intel"
    _assert_protected_unchanged(protected_hashes)


def test_fallback_does_not_remove_preexisting_model(tmp_path: Path) -> None:
    env = _mac_env(
        tmp_path,
        APPLE_SILICON,
        "arm64",
        extra_env={
            "MOCK_OLLAMA_PULL_FAIL": "qwen3:14b",
            "MOCK_GENERATE_FAIL": "",
        },
    )
    state_root = Path(env["EIGHTBALL_ROOT"])
    _write_observation(state_root, physical_memory_mb=24576, free_install_disk_mb=102400)
    list_file = Path(env["MOCK_OLLAMA_LIST_FILE"])
    list_file.write_text("NAME\nqwen3:14b\n", encoding="utf-8")
    (state_root / ".models-before-trial").write_text("qwen3:14b\n", encoding="utf-8")
    result = _run_bash(APPLE_SILICON / "8.2.sh", env)
    assert result.returncode == 0, result.stderr
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "rm qwen3:14b" not in log


def test_failed_newly_pulled_candidate_is_removed_before_next_trial(tmp_path: Path) -> None:
    env = _mac_env(
        tmp_path,
        APPLE_SILICON,
        "arm64",
        extra_env={"MOCK_GENERATE_FAIL": "1"},
    )
    state_root = Path(env["EIGHTBALL_ROOT"])
    _write_observation(state_root, physical_memory_mb=8192, free_install_disk_mb=102400)
    (state_root / ".models-before-trial").write_text("", encoding="utf-8")
    result = _run_bash(APPLE_SILICON / "8.2.sh", env)
    assert result.returncode == 1
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "rm qwen3:4b" in log


def test_explicit_model_does_not_fallback(tmp_path: Path) -> None:
    env = _mac_env(
        tmp_path,
        APPLE_SILICON,
        "arm64",
        extra_env={"MOCK_GENERATE_FAIL": "1"},
    )
    state_root = Path(env["EIGHTBALL_ROOT"])
    _write_observation(state_root)
    result = _run_bash(APPLE_SILICON / "8.2.sh", env, "--model", "qwen3:0.6b")
    assert result.returncode == 1
    payload = json.loads((state_root / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["selected_model"] == "none"
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "pull qwen3:8b" not in log


def test_83_writes_status_helper(tmp_path: Path) -> None:
    env = _mac_env(tmp_path, APPLE_SILICON, "arm64")
    state_root = Path(env["EIGHTBALL_ROOT"])
    (state_root / "8ball-result.txt").write_text(
        "Model: qwen3:0.6b\nModel test: PASSED\n",
        encoding="utf-8",
    )
    result = _run_bash(APPLE_SILICON / "8.3.sh", env)
    assert result.returncode == 0, result.stderr
    status = state_root / "bin/8ball-status"
    assert status.is_file()
    text = status.read_text(encoding="utf-8")
    assert "ollama signin" in text
    assert "/usr/local/bin" not in text


def test_all_mac_shell_scripts_pass_bash_n() -> None:
    scripts = sorted((REPO_ROOT / "install/mac").rglob("*.sh"))
    assert scripts
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"bash -n failed for {script}: {result.stderr}"

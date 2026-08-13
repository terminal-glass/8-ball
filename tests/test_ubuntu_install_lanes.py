"""Focused tests for hardened Ubuntu installer lanes (mocked; no host mutation)."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CPU_LANE = REPO_ROOT / "install/ubuntu/cpu"
CUDA_LANE = REPO_ROOT / "install/ubuntu/cuda"
UBUNTU_LIB = REPO_ROOT / "install/ubuntu/lib"
LANE_SCRIPTS = ("trial-install.sh", "8.1.sh", "8.2.sh", "8.3.sh")
PROTECTED_PATHS = (
    REPO_ROOT / "profiles/manifest.json",
    REPO_ROOT / "profiles/index.csv",
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


def _write_mock_bin(mock_bin: Path) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    scripts = {
        "curl": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            url=""
            out=""
            args=("$@")
            i=0
            while [[ $i -lt ${#args[@]} ]]; do
              arg="${args[$i]}"
              case "${arg}" in
                http://*|https://*) url="${arg}" ;;
                -o)
                  i=$((i + 1))
                  out="${args[$i]}"
                  ;;
              esac
              i=$((i + 1))
            done
            if [[ "${url}" == *"/api/tags" ]]; then
              echo '{"models":[]}'
              exit 0
            fi
            if [[ "${url}" == *"/api/generate" ]]; then
              echo '{"response":"8-BALL READY"}'
              exit 0
            fi
            if [[ -n "${out}" ]]; then
              if [[ "${MOCK_REMOTE_PAYLOAD:-}" == "bad" ]]; then
                echo "tampered" >"${out}"
              else
                echo "verified-payload" >"${out}"
              fi
              exit 0
            fi
            exit 1
            """
        ),
        "ollama": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            case "${1:-}" in
              pull)
                if [[ "${MOCK_OLLAMA_PULL_FAIL:-}" == "$2" ]]; then
                  exit 1
                fi
                exit 0
                ;;
              rm) exit 0 ;;
              *) exit 0 ;;
            esac
            """
        ),
        "timeout": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            shift
            "$@"
            """
        ),
        "nproc": "#!/usr/bin/env bash\necho 4\n",
        "id": "#!/usr/bin/env bash\ncase \"$1\" in -u) echo 0 ;; *) echo 0 ;; esac\n",
        "sha256sum": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [[ "${MOCK_SHA256:-}" == "mismatch" ]]; then
              echo "deadbeef  $2"
            else
              echo "${MOCK_SHA256_ACTUAL:-0000000000000000000000000000000000000000000000000000000000000000}  $2"
            fi
            """
        ),
    }
    for name, body in scripts.items():
        path = mock_bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(stat.S_IRWXU)


def _ubuntu_env(tmp_path: Path, lane: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    mock_bin = tmp_path / "mock-bin"
    state_root = tmp_path / "philosopher"
    state_root.mkdir(parents=True, exist_ok=True)
    _write_mock_bin(mock_bin)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{mock_bin}:{env.get('PATH', '')}",
            "PHILO_ROOT": str(state_root),
            "PHILOSOPHER_ROOT": str(state_root),
            "EIGHTBALL_REPO_ROOT": str(REPO_ROOT),
            "EIGHTBALL_BIN_DIR": str(tmp_path / "bin"),
            "EIGHTBALL_MOTD_TARGET": str(tmp_path / "motd/99-8ball-trial"),
            "EIGHTBALL_NONINTERACTIVE_CONFIRM": "1",
            "EIGHTBALL_ACCEPT_OLLAMA_INSTALL_RISK": "1",
            "EIGHTBALL_USE_MEASURED_HARDWARE_ENV": "1",
            "EIGHTBALL_TEST_SKIP_ROOT": "1",
            "MOCK_SHA256_ACTUAL": "0000000000000000000000000000000000000000000000000000000000000000",
        }
    )
    if extra:
        env.update(extra)
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


@pytest.mark.parametrize("lane", [CPU_LANE, CUDA_LANE])
def test_bash_syntax_check(lane: Path) -> None:
    for name in LANE_SCRIPTS:
        result = subprocess.run(["bash", "-n", str(lane / name)], check=False)
        assert result.returncode == 0, name


def test_no_corrupt_assignment_suffixes() -> None:
    for lane in (CPU_LANE, CUDA_LANE):
        for name in LANE_SCRIPTS:
            text = (lane / name).read_text(encoding="utf-8")
            assert "åç" not in text, name
            assert 'SUITE_VERSION="8BALL-0.8.0"' in (UBUNTU_LIB / "ubuntu-common.sh").read_text(encoding="utf-8")
            assert "trial-log.txt" in (UBUNTU_LIB / "ubuntu-common.sh").read_text(encoding="utf-8")


def test_checksum_mismatch_fails_before_execution(tmp_path: Path) -> None:
    env = _ubuntu_env(
        tmp_path,
        CPU_LANE,
        {
            "MOCK_SHA256": "mismatch",
            "MOCK_SHA256_ACTUAL": "1111111111111111111111111111111111111111111111111111111111111111",
        },
    )
    harness = tmp_path / "verify.sh"
    harness.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            EIGHTBALL_INSTALL_LANE=ubuntu/cpu
            SCRIPT_DIR="{CPU_LANE}"
            source "{UBUNTU_LIB}/ubuntu-common.sh"
            ubuntu_verify_and_stage_remote_script "8.1.sh" >/dev/null
            """
        ),
        encoding="utf-8",
    )
    harness.chmod(0o755)
    result = subprocess.run(["bash", str(harness)], env=env, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "Checksum mismatch" in result.stderr


def test_local_bundle_uses_lane_scripts(tmp_path: Path, protected_hashes: dict[str, str]) -> None:
    env = _ubuntu_env(tmp_path, CPU_LANE)
    result = _run_bash(CPU_LANE / "8.3.sh", env)
    assert result.returncode == 0, result.stderr
    motd = Path(env["EIGHTBALL_MOTD_TARGET"])
    remember = Path(env["EIGHTBALL_BIN_DIR"]) / "remember"
    assert motd.is_file()
    assert remember.is_file()
    assert not Path("/etc/update-motd.d/99-8ball-trial").exists() or motd != Path(
        "/etc/update-motd.d/99-8ball-trial"
    )
    _assert_protected_unchanged(protected_hashes)


def test_public_path_refuses_missing_profile_slug(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path, CPU_LANE)
    result = _run_bash(CPU_LANE / "8.2.sh", env)
    assert result.returncode != 0
    assert "Missing model slug" in result.stderr


def test_model_cannot_bypass_profile_requirements(tmp_path: Path) -> None:
    env = _ubuntu_env(
        tmp_path,
        CPU_LANE,
        {
            "EIGHTBALL_SYSTEM_RAM_GB": "1.0",
            "EIGHTBALL_USABLE_MODEL_RAM_GB": "0.6",
            "EIGHTBALL_FREE_DISK_GB": "1.0",
            "EIGHTBALL_CPU_THREADS": "1",
            "EIGHTBALL_CUDA_AVAILABLE": "false",
            "EIGHTBALL_GPU_VRAM_GB": "0",
        },
    )
    result = _run_bash(
        CPU_LANE / "8.2.sh",
        env,
        "--model-slug",
        "gemma",
        "--model",
        "gemma:7b",
    )
    assert result.returncode != 0
    assert "does not fit measured hardware" in result.stderr


def test_profile_selection_happy_path(tmp_path: Path) -> None:
    env = _ubuntu_env(
        tmp_path,
        CPU_LANE,
        {
            "EIGHTBALL_SYSTEM_RAM_GB": "16.0",
            "EIGHTBALL_USABLE_MODEL_RAM_GB": "9.0",
            "EIGHTBALL_FREE_DISK_GB": "100.0",
            "EIGHTBALL_CPU_THREADS": "6",
            "EIGHTBALL_CUDA_AVAILABLE": "false",
            "EIGHTBALL_GPU_VRAM_GB": "0",
        },
    )
    result = _run_bash(CPU_LANE / "8.2.sh", env, "--model-slug", "gemma")
    assert result.returncode == 0, result.stderr
    result_env = Path(env["PHILOSOPHER_ROOT"]) / "profiles/90-result.env"
    assert result_env.is_file()
    text = result_env.read_text(encoding="utf-8")
    assert "MODEL_TEST=PASSED" in text


def test_raw_base_rejected_on_public_path(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path, CPU_LANE)
    result = _run_bash(
        CPU_LANE / "trial-install.sh",
        env,
        "--raw-base",
        "https://evil.example",
        "--yes",
        "--model-slug",
        "gemma",
    )
    assert result.returncode != 0
    assert "--raw-base is not supported" in result.stderr


def test_release_repo_points_to_terminal_glass() -> None:
    common = (UBUNTU_LIB / "ubuntu-common.sh").read_text(encoding="utf-8")
    assert 'EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-terminal-glass/8-ball}"' in common
    root = (REPO_ROOT / "trial-install.sh").read_text(encoding="utf-8")
    assert "terminal-glass/8-ball" in root
    assert "funtech64/8-ball" not in root

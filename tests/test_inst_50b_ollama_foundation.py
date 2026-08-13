"""INST-50B tests for 8.1 Ollama foundation / localhost safety."""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OLLAMA_HELPER = REPO_ROOT / "install/shared/ollama-localhost.sh"
UBUNTU_81 = REPO_ROOT / "install/ubuntu/8.1.sh"
CPU_81 = REPO_ROOT / "install/ubuntu/cpu/8.1.sh"
CUDA_81 = REPO_ROOT / "install/ubuntu/cuda/8.1.sh"


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _mock_ss(mock_bin: Path, lines: str) -> None:
    rendered = "".join(f'echo "{line.strip()}"\n' for line in lines.strip().splitlines())
    _write_executable(
        mock_bin / "ss",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            if [[ "${{1:-}}" == "-ltnH" || "${{1:-}}" == "-ltn" ]]; then
            {rendered}
            fi
            """
        ),
    )


def _run_helper(
    body: str,
    *,
    env: dict[str, str] | None = None,
    mock_bin: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        export OLLAMA_LOCAL_HOST=127.0.0.1
        export OLLAMA_LOCAL_PORT=11434
        export OLLAMA_API=http://127.0.0.1:11434
        # shellcheck source=/dev/null
        source "{OLLAMA_HELPER}"
        {body}
        """
    )
    run_env = os.environ.copy()
    if mock_bin is not None:
        run_env["PATH"] = f"{mock_bin}:{run_env.get('PATH', '')}"
    if env:
        run_env.update(env)
    return subprocess.run(
        ["/usr/bin/bash", "-c", script],
        cwd=REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0.0.0.0:11434", 0),
        ("[::]:11434", 0),
        (":11434", 0),
        ('"0.0.0.0:11434"', 0),
        ("127.0.0.1:11434", 1),
        ("localhost:11434", 1),
    ],
)
def test_public_host_value_detection(value: str, expected: int) -> None:
    result = _run_helper(
        f'if ollama_is_public_host_value "{value}"; then exit 0; else exit 1; fi'
    )
    assert result.returncode == expected


def test_scan_file_detects_environmentfile_public_bind(tmp_path: Path) -> None:
    env_file = tmp_path / "ollama.env"
    env_file.write_text('OLLAMA_HOST=0.0.0.0:11434\n', encoding="utf-8")
    unit = tmp_path / "ollama.service"
    unit.write_text(f"EnvironmentFile={env_file}\n", encoding="utf-8")
    result = _run_helper(f'ollama_scan_file_for_public_bind "{unit}"')
    assert result.returncode == 0


def test_scan_file_detects_bare_port_public_bind(tmp_path: Path) -> None:
    env_file = tmp_path / "default"
    env_file.write_text("OLLAMA_HOST=:11434\n", encoding="utf-8")
    result = _run_helper(f'ollama_scan_file_for_public_bind "{env_file}"')
    assert result.returncode == 0


def test_exclusive_listener_accepts_loopback_only(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    _mock_ss(mock_bin, "LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*\n")
    result = _run_helper("ollama_verify_exclusive_listener", mock_bin=mock_bin)
    assert result.returncode == 0, result.stderr


def test_exclusive_listener_rejects_public_bind(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    _mock_ss(mock_bin, "LISTEN 0 4096 0.0.0.0:11434 0.0.0.0:*\n")
    result = _run_helper("ollama_verify_exclusive_listener", mock_bin=mock_bin)
    assert result.returncode == 1
    assert "public or wildcard" in result.stderr


def test_exclusive_listener_rejects_ipv6_wildcard(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    _mock_ss(mock_bin, "LISTEN 0 4096 [::]:11434 [::]:*\n")
    result = _run_helper("ollama_verify_exclusive_listener", mock_bin=mock_bin)
    assert result.returncode == 1
    assert "public or wildcard" in result.stderr


def test_exclusive_listener_rejects_dual_bind(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    _mock_ss(
        mock_bin,
        "LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*\n"
        "LISTEN 0 4096 0.0.0.0:11434 0.0.0.0:*\n",
    )
    result = _run_helper("ollama_verify_exclusive_listener", mock_bin=mock_bin)
    assert result.returncode == 1
    assert "public or wildcard" in result.stderr


def test_exclusive_listener_fails_without_socket_tool(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    result = _run_helper(
        "ollama_verify_exclusive_listener",
        env={"PATH": str(mock_bin)},
    )
    assert result.returncode == 1
    assert "ss or netstat is required" in result.stderr


def test_dropin_configuration_is_idempotent(tmp_path: Path) -> None:
    dropin_dir = tmp_path / "ollama.service.d"
    body = textwrap.dedent(
        f"""\
        export OLLAMA_DROPIN_DIR="{dropin_dir}"
        if ollama_configure_localhost; then first=changed; else first=unchanged; fi
        if ollama_configure_localhost; then second=changed; else second=unchanged; fi
        if [[ "$first" == changed && "$second" == unchanged ]]; then
          exit 0
        fi
        echo "unexpected idempotency result: first=$first second=$second" >&2
        exit 1
        """
    )
    result = _run_helper(body)
    assert result.returncode == 0, result.stderr
    assert (dropin_dir / "8ball-localhost.conf").is_file()


def test_bash_syntax_for_81_and_helper() -> None:
    for path in (OLLAMA_HELPER, UBUNTU_81, CPU_81, CUDA_81):
        result = subprocess.run(["bash", "-n", str(path)], check=False)
        assert result.returncode == 0, path


def test_cpu_and_cuda_wrappers_delegate_to_canonical() -> None:
    for wrapper in (CPU_81, CUDA_81):
        text = wrapper.read_text(encoding="utf-8")
        assert 'exec "${SCRIPT_DIR}/../8.1.sh"' in text
        assert "installer-smoke-contract.sh" in text


def test_81_sources_ollama_localhost_helper() -> None:
    text = UBUNTU_81.read_text(encoding="utf-8")
    assert "ollama-localhost.sh" in text
    assert "ollama_verify_foundation" in text
    assert "ollama_ensure_localhost_config" in text


def test_81_has_no_model_selection_logic() -> None:
    text = UBUNTU_81.read_text(encoding="utf-8")
    for token in ("qwen", "MODEL_SLUG", "c10_select", "c10-hardware-resolve", "profiles/"):
        assert token not in text


@pytest.mark.parametrize("path", [UBUNTU_81, CPU_81, CUDA_81])
def test_81_help_is_non_mutating(path: Path) -> None:
    result = subprocess.run(
        ["bash", str(path), "--help"],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout

"""Regression tests for PR61 runtime bundle portability fixes."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_INSTALL = REPO_ROOT / "install/ubuntu/trial-install.sh"
GENERATE_ARCHIVE = REPO_ROOT / "scripts/generate-runtime-archive.sh"
EXTRACT_SCRIPT = REPO_ROOT / "scripts/extract-runtime-archive.py"


def _write_failing_curl(mock_bin: Path, log_file: Path) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        url=""
        args=("$@")
        for i in "${{!args[@]}}"; do
          case "${{args[$i]}}" in
            http://*|https://*)
              url="${{args[$i]}}"
              ;;
          esac
        done
        printf '%s\\n' "${{url}}" >>"{log_file}"
        echo "network forbidden in test: ${{url}}" >&2
        exit 99
        """
    )
    curl_path = mock_bin / "curl"
    curl_path.write_text(script, encoding="utf-8")
    curl_path.chmod(stat.S_IRWXU)


def test_clean_help_zero_network(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_failing_curl(mock_bin, curl_log)
    env = {
        "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path / "home"),
        "PHILOSOPHER_ROOT": str(tmp_path / "philosopher"),
    }
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Usage:" in result.stdout
    assert not curl_log.exists() or curl_log.read_text(encoding="utf-8").strip() == ""


def test_clean_preflight_zero_network(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    subprocess.run(
        ["cp", str(CANONICAL_INSTALL), str(entry_dir / "trial-install.sh")],
        check=True,
    )
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_failing_curl(mock_bin, curl_log)
    env = {
        "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path / "home"),
        "PHILOSOPHER_ROOT": str(tmp_path / "philosopher"),
        "EIGHTBALL_INSTALL_LANE": "ubuntu/cpu",
    }
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--preflight"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "lane: ubuntu/cpu" in result.stdout
    assert "preflight" in result.stdout.lower()
    assert not curl_log.exists() or curl_log.read_text(encoding="utf-8").strip() == ""


def test_runtime_archive_generation_is_deterministic() -> None:
    first = subprocess.run(["bash", str(GENERATE_ARCHIVE), "v0.8.0"], check=True, cwd=REPO_ROOT)
    del first
    archive_path = REPO_ROOT / "install/releases/v0.8.0/8ball-ubuntu-runtime.tar.gz"
    first_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    time.sleep(2)
    subprocess.run(["bash", str(GENERATE_ARCHIVE), "v0.8.0"], check=True, cwd=REPO_ROOT)
    second_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert first_hash == second_hash


def _build_malicious_archive(tmp_path: Path, member: tarfile.TarInfo, payload: bytes = b"x") -> Path:
    archive_path = tmp_path / "evil.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        tar.addfile(member, io.BytesIO(payload))
    archive_path.write_bytes(buf.getvalue())
    return archive_path


def test_safe_extraction_rejects_traversal(tmp_path: Path) -> None:
    member = tarfile.TarInfo(name="../escape.txt")
    member.size = 1
    member.mtime = 0
    member.mode = 0o644
    archive_path = _build_malicious_archive(tmp_path, member)
    dest = tmp_path / "dest"
    result = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), str(archive_path), str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Unsafe" in result.stderr or "escapes" in result.stderr


def test_safe_extraction_rejects_symlink(tmp_path: Path) -> None:
    member = tarfile.TarInfo(name="link")
    member.type = tarfile.SYMTYPE
    member.linkname = "/etc/passwd"
    member.size = 0
    member.mtime = 0
    archive_path = _build_malicious_archive(tmp_path, member, b"")
    dest = tmp_path / "dest"
    result = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), str(archive_path), str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Unsupported archive member type" in result.stderr


def test_safe_extraction_without_tarfile_filter(tmp_path: Path) -> None:
    member = tarfile.TarInfo(name="ok.txt")
    member.size = 5
    member.mtime = 0
    member.mode = 0o644
    archive_path = _build_malicious_archive(tmp_path, member, b"hello")
    dest = tmp_path / "dest"
    result = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), str(archive_path), str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (dest / "ok.txt").read_text(encoding="utf-8") == "hello"
    source = EXTRACT_SCRIPT.read_text(encoding="utf-8")
    assert 'filter="data"' not in source
    assert "extractall" not in source

"""Canonical Ubuntu trial-install entrypoint tests (PR57)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_INSTALL = REPO_ROOT / "install/ubuntu/trial-install.sh"
CUSTOMER_URL = (
    "https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh"
)
RELEASE_MANIFEST = REPO_ROOT / "install/releases/v0.8.0/manifest.json"
RELEASE_REF = "810b37dcd61e97de38860056f36e2061b6feeba9"


def _restore_release_tree() -> None:
    subprocess.run(
        ["git", "checkout", "--", "profiles/"],
        cwd=REPO_ROOT,
        check=False,
    )
    subprocess.run(
        ["bash", "scripts/generate-release-manifest.sh", "v0.8.0"],
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(autouse=True)
def restore_release_tree_fixture() -> None:
    _restore_release_tree()


def _manifest() -> dict:
    return json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))


def _build_release_snapshot(root: Path) -> Path:
    snap = root / "release_snapshot"
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    for rel_path in manifest["artifacts"]:
        src = REPO_ROOT / rel_path
        dest = snap / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    manifest_dest = snap / "install/releases/v0.8.0/manifest.json"
    manifest_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RELEASE_MANIFEST, manifest_dest)
    return snap


def _write_mock_curl(
    mock_bin: Path,
    manifest: dict,
    snapshot: Path,
    *,
    ref: str = RELEASE_REF,
    corrupt: str = "",
) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    manifest_json = json.dumps(manifest)
    manifest_for_shell = manifest_json.replace("'", "'\"'\"'")
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        url=""
        output=""
        args=("$@")
        for i in "${{!args[@]}}"; do
          case "${{args[$i]}}" in
            -o)
              output="${{args[$((i + 1))]}}"
              ;;
            http://*|https://*)
              url="${{args[$i]}}"
              ;;
          esac
        done
        case "${{url}}" in
          */install/releases/*/manifest.json)
            printf '%s' '{manifest_for_shell}' >"${{output}}"
            ;;
          */install/shared/installer-smoke-contract.sh)
            cp "{snapshot}/install/shared/installer-smoke-contract.sh" "${{output}}" 2>/dev/null || cp "{REPO_ROOT}/install/shared/installer-smoke-contract.sh" "${{output}}"
            ;;
          *)
            rel="${{url#*8-ball/{ref}/}}"
            src="{snapshot}/${{rel}}"
            if [[ ! -f "${{src}}" ]]; then
              exit 22
            fi
            if [[ "${{rel}}" == "{corrupt}" ]]; then
              echo corrupt >"${{output}}"
              exit 0
            fi
            cp "${{src}}" "${{output}}"
            ;;
        esac
        """
    )
    curl_path = mock_bin / "curl"
    curl_path.write_text(script, encoding="utf-8")
    curl_path.chmod(stat.S_IRWXU)


def _trial_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    philo = tmp_path / "philosopher"
    philo.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PHILOSOPHER_ROOT": str(philo),
        "EIGHTBALL_RELEASE": "v0.8.0",
        "EIGHTBALL_RELEASE_REF": RELEASE_REF,
        "EIGHTBALL_TEST_SKIP_ROOT": "1",
        "EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS": "0",
        "HOME": str(tmp_path / "home"),
    }
    env.update(overrides)
    return env


def test_root_trial_install_does_not_exist() -> None:
    assert not (REPO_ROOT / "trial-install.sh").exists()
    assert not (REPO_ROOT / "install/trial-install.sh").exists()


def test_ubuntu_has_single_canonical_customer_trial_installer() -> None:
    assert CANONICAL_INSTALL.is_file()
    assert not (REPO_ROOT / "install/ubuntu/cpu/trial-install.sh").exists()
    assert not (REPO_ROOT / "install/ubuntu/cuda/trial-install.sh").exists()
    ubuntu_trials = list((REPO_ROOT / "install/ubuntu").glob("**/trial-install.sh"))
    assert ubuntu_trials == [CANONICAL_INSTALL]


def test_customer_url_is_main_install_ubuntu_trial_install() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert CUSTOMER_URL in readme
    assert "main/trial-install.sh" not in readme
    text = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert "EIGHTBALL_RELEASE_REF" in text


def test_logical_release_is_not_used_as_git_ref() -> None:
    trial = CANONICAL_INSTALL.read_text(encoding="utf-8")
    release = (REPO_ROOT / "install/shared/8ball-release.sh").read_text(encoding="utf-8")
    assert "EIGHTBALL_RELEASE_REF is required" in trial
    assert "logical ${EIGHTBALL_RELEASE} is not a Git ref" in release
    assert 'printf \'https://raw.githubusercontent.com/%s/%s\' \\\n    "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE}"' not in release


def test_stdin_execution_does_not_require_bash_source(tmp_path: Path) -> None:
    snapshot = _build_release_snapshot(tmp_path)
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest(), snapshot)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    script = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert "eightball_resolve_entry_context" in script

    result = subprocess.run(
        ["bash", "-c", f"cat '{CANONICAL_INSTALL}' | bash"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "unbound variable" not in (result.stderr + result.stdout).lower()


def test_downloaded_file_execution_works(tmp_path: Path) -> None:
    snapshot = _build_release_snapshot(tmp_path)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest(), snapshot)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_clean_host_does_not_require_repository_checkout(tmp_path: Path) -> None:
    snapshot = _build_release_snapshot(tmp_path)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    assert not (tmp_path / "install").exists()
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest(), snapshot)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    staging = tmp_path / "philosopher" / ".8ball-release" / "v0.8.0"
    assert (staging / "profiles/qwen3/model.json").is_file()


def test_runtime_still_sha256_verified(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(
        mock_bin,
        _manifest(),
        _build_release_snapshot(tmp_path),
        corrupt="install/shared/8ball-version.sh",
    )
    env = _trial_env(tmp_path)
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "sha-256 mismatch" in combined or "unverified" in combined


def test_arguments_pass_through() -> None:
    text = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert "--model" in text
    assert "--model-slug" in text
    assert "--no-motd" in text
    assert 'parse_args "$@"' in text


def test_canonical_installer_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(CANONICAL_INSTALL)], check=False)
    assert result.returncode == 0

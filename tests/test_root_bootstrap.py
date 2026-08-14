"""Tests for the public root trial-install.sh bootstrap channel."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_TRIAL_INSTALL = REPO_ROOT / "trial-install.sh"
RELEASE_MANIFEST = REPO_ROOT / "install/releases/v0.8.0/manifest.json"
CUSTOMER_URL = "https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh"
APPROVED_REF = "8c07c5844cdabd6c14c1b3b30919c71bffd18597"


def _restore_release_tree() -> None:
    subprocess.run(
        [
            "git",
            "checkout",
            "--",
            "profiles/",
            "install/releases/v0.8.0/manifest.json",
            "install/releases/v0.8.0/install-manifest.json",
        ],
        cwd=REPO_ROOT,
        check=False,
    )


def _build_release_snapshot(root: Path) -> Path:
    snap = root / "release_snapshot"
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
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
    ref: str = APPROVED_REF,
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
          *)
            rel="${{url#*8-ball/{ref}/}}"
            src="{snapshot}/${{rel}}"
            if [[ ! -f "${{src}}" ]]; then
              exit 22
            fi
            cp "${{src}}" "${{output}}"
            ;;
        esac
        """
    )
    curl_path = mock_bin / "curl"
    curl_path.write_text(script, encoding="utf-8")
    curl_path.chmod(stat.S_IRWXU)


def _root_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    philo = tmp_path / "philosopher"
    philo.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PHILOSOPHER_ROOT": str(philo),
        "EIGHTBALL_TEST_SKIP_ROOT": "1",
        "HOME": str(tmp_path / "home"),
        "EIGHTBALL_APPROVED_REF": APPROVED_REF,
    }
    env.update(overrides)
    return env


def test_customer_url_is_main_trial_install_only() -> None:
    text = ROOT_TRIAL_INSTALL.read_text(encoding="utf-8")
    assert CUSTOMER_URL.replace("https://", "") in text or "main/trial-install.sh" in text
    assert "EIGHTBALL_APPROVED_REF" in text
    assert "EIGHTBALL_APPROVED_RELEASE" in text
    assert "raw.githubusercontent.com/terminal-glass/8-ball/v0.8.0/trial-install.sh" not in text
    assert "Clone https://github.com" not in text


def test_root_script_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(ROOT_TRIAL_INSTALL)], check=False)
    assert result.returncode == 0


def test_clean_host_root_bootstrap_stages_verified_ubuntu_installer(tmp_path: Path) -> None:
    _restore_release_tree()
    release_snapshot = _build_release_snapshot(tmp_path)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(ROOT_TRIAL_INSTALL, entry_dir / "trial-install.sh")

    manifest = json.loads((release_snapshot / "install/releases/v0.8.0/manifest.json").read_text(encoding="utf-8"))
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, manifest, release_snapshot)
    env = _root_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    installer = (result.stdout or "").strip().splitlines()[-1]
    assert installer.endswith("/install/ubuntu/trial-install.sh")
    staging = tmp_path / "philosopher" / ".8ball-release" / "v0.8.0"
    assert (staging / "install/ubuntu/trial-install.sh").is_file()
    assert (staging / "profiles/qwen3/model.json").is_file()
    assert (staging / "install/shared/8ball-release.sh").is_file()


def test_root_bootstrap_passes_arguments_through_to_ubuntu_installer() -> None:
    text = ROOT_TRIAL_INSTALL.read_text(encoding="utf-8")
    assert 'exec "${installer}" "$@"' in text
    assert 'run_ubuntu_installer "${lane}" "$@"' in text


def test_root_bootstrap_does_not_require_repository_checkout(tmp_path: Path) -> None:
    _restore_release_tree()
    release_snapshot = _build_release_snapshot(tmp_path)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(ROOT_TRIAL_INSTALL, entry_dir / "trial-install.sh")
    assert not (tmp_path / "install").exists()
    assert not (tmp_path / "profiles").exists()

    manifest = json.loads((release_snapshot / "install/releases/v0.8.0/manifest.json").read_text(encoding="utf-8"))
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, manifest, release_snapshot)
    env = _root_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout

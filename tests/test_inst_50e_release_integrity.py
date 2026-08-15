"""INST-50E tests for trial-install release/bootstrap integrity (mocked)."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST = REPO_ROOT / "install/releases/v0.8.0/manifest.json"
TRIAL_INSTALL = REPO_ROOT / "install/ubuntu/trial-install.sh"
RELEASE_SH = REPO_ROOT / "install/shared/8ball-release.sh"


def _pinned_runtime_ref() -> str:
    trial = TRIAL_INSTALL.read_text(encoding="utf-8")
    match = re.search(
        r'EIGHTBALL_RELEASE_REF="\$\{EIGHTBALL_RELEASE_REF:-([0-9a-f]+)\}"',
        trial,
    )
    assert match, "installer must pin EIGHTBALL_RELEASE_REF"
    return match.group(1)


RELEASE_REF = _pinned_runtime_ref()


@pytest.fixture(autouse=True)
def _restore_release_profile_files() -> None:
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))


def _manifest_for_mock() -> dict:
    manifest = _manifest()
    archive_bytes = _build_deterministic_archive(manifest)
    patched = json.loads(json.dumps(manifest))
    patched["runtime_archive"]["sha256"] = hashlib.sha256(archive_bytes).hexdigest()
    return patched


def _build_deterministic_archive(manifest: dict) -> bytes:
    buf = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar,
    ):
        for rel in sorted(manifest["artifacts"]):
            src = REPO_ROOT / rel
            data = src.read_bytes()
            info = tarfile.TarInfo(name=rel)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mode = 0o755 if rel.endswith((".sh", ".py")) else 0o644
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _write_mock_curl(
    mock_bin: Path,
    manifest: dict,
    *,
    corrupt_archive: bool = False,
    omit_archive: bool = False,
    ref: str = RELEASE_REF,
) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    manifest_json = json.dumps(manifest)
    manifest_for_shell = manifest_json.replace("'", "'\"'\"'")
    archive_rel = manifest["runtime_archive"]["path"]
    archive_path = mock_bin / "runtime-archive.tar.gz"
    archive_path.write_bytes(_build_deterministic_archive(manifest))
    if corrupt_archive:
        archive_action = 'echo corrupt >"${output}"'
    elif omit_archive:
        archive_action = "exit 22"
    else:
        archive_action = f'cp "{archive_path}" "${{output}}"'
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
          */{archive_rel.split("/")[-1]})
            {archive_action}
            ;;
          */profiles/*|*/install/shared/*|*/install/ubuntu/*.sh)
            exit 22
            ;;
          *)
            exit 22
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


def _isolated_install_tree(tmp_path: Path) -> Path:
    install_root = tmp_path / "install"
    shutil.copytree(REPO_ROOT / "install/ubuntu", install_root / "ubuntu")
    shutil.copytree(REPO_ROOT / "install/shared", install_root / "shared")
    shutil.copytree(
        REPO_ROOT / "install/releases",
        install_root / "releases",
    )
    return install_root / "ubuntu"


def _patch_manifest_for_stub(install_dir: Path, script_name: str, body: str) -> None:
    manifest_path = install_dir.parent / "releases/v0.8.0/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rel = f"install/ubuntu/{script_name}"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    manifest["artifacts"][rel] = digest
    manifest["scripts"][script_name] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    target = install_dir / script_name
    target.write_text(body, encoding="utf-8")
    target.chmod(stat.S_IRWXU)


def _noop_stub() -> str:
    return '#!/usr/bin/env bash\nset -euo pipefail\nEIGHTBALL_SCRIPT_VERSION="0.8.0"\n'


def _fail_stub() -> str:
    return _noop_stub() + "exit 1\n"


def _run_trial(
    install_dir: Path,
    mock_bin: Path,
    env: dict[str, str],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    run_env = env.copy()
    run_env["PATH"] = f"{mock_bin}:{run_env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(install_dir / "trial-install.sh"), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=install_dir,
        env=run_env,
    )


def test_release_manifest_checksums_match_repository() -> None:
    manifest = _manifest()
    assert manifest["release_tag"] == "v0.8.0"
    for rel_path, expected in manifest["artifacts"].items():
        path = REPO_ROOT / rel_path
        assert path.is_file(), rel_path
        assert _sha256(path) == expected, rel_path


def test_all_runtime_artifacts_share_one_release_identity() -> None:
    manifest = _manifest()
    assert manifest["repository"] == "terminal-glass/8-ball"
    assert manifest["runtime_bundle"] == "install/releases/v0.8.0/runtime-bundle.json"
    assert manifest["runtime_archive"]["path"] == "install/releases/v0.8.0/8ball-ubuntu-runtime.tar.gz"
    script_paths = {f"install/ubuntu/{name}" for name in manifest["scripts"]}
    assert script_paths.issubset(set(manifest["artifacts"]))
    assert any(path.startswith("profiles/qwen3/") for path in manifest["artifacts"])
    assert "scripts/c10_common.py" in manifest["artifacts"]


def test_profile_runtime_subset_is_bounded() -> None:
    manifest = _manifest()
    profile_artifacts = [path for path in manifest["artifacts"] if path.startswith("profiles/")]
    assert len(profile_artifacts) < 200
    assert not any(path.endswith("index.csv") for path in profile_artifacts)


def test_verify_artifact_sha_passes_for_valid_file(tmp_path: Path) -> None:
    rel = "install/ubuntu/8.1.sh"
    digest = _manifest()["artifacts"][rel]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"artifacts": {rel: digest}}),
        encoding="utf-8",
    )
    target = tmp_path / "8.1.sh"
    shutil.copy(REPO_ROOT / rel, target)
    result = subprocess.run(
        ["bash", "-c", f'source "{RELEASE_SH}"; eightball_verify_artifact_sha "{rel}" "{target}" "{manifest_path}"'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_verify_artifact_sha_fails_closed_on_bad_checksum(tmp_path: Path) -> None:
    rel = "install/ubuntu/8.1.sh"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"artifacts": {rel: "0" * 64}}),
        encoding="utf-8",
    )
    target = tmp_path / "8.1.sh"
    target.write_text("#!/bin/bash\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", f'source "{RELEASE_SH}"; eightball_verify_artifact_sha "{rel}" "{target}" "{manifest_path}"'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SHA-256 mismatch" in result.stderr


def test_missing_artifact_download_fails_closed(tmp_path: Path) -> None:
    install_dir = _isolated_install_tree(tmp_path)
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_mock(), omit_archive=True)
    env = _trial_env(tmp_path)
    result = _run_trial(install_dir, mock_bin, env)
    assert result.returncode != 0
    assert "Failed to download" in result.stderr + result.stdout


def test_corrupt_artifact_download_fails_closed(tmp_path: Path) -> None:
    install_dir = _isolated_install_tree(tmp_path)
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_mock(), corrupt_archive=True)
    env = _trial_env(tmp_path)
    result = _run_trial(install_dir, mock_bin, env)
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "sha-256 mismatch" in combined or "integrity" in combined or "unverified" in combined


def test_partial_download_is_not_executed(tmp_path: Path) -> None:
    install_dir = _isolated_install_tree(tmp_path)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir(parents=True, exist_ok=True)
    (mock_bin / "curl").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            output=""
            args=("$@")
            for i in "${!args[@]}"; do
              if [[ "${args[$i]}" == "-o" ]]; then
                output="${args[$((i + 1))]}"
              fi
            done
            printf 'partial' >"${output}"
            """
        ),
        encoding="utf-8",
    )
    (mock_bin / "curl").chmod(stat.S_IRWXU)
    env = _trial_env(tmp_path)
    result = _run_trial(install_dir, mock_bin, env)
    assert result.returncode != 0


def test_bootstrap_stages_profiles_from_same_release(tmp_path: Path) -> None:
    install_dir = _isolated_install_tree(tmp_path)
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_mock())
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    result = _run_trial(install_dir, mock_bin, env)
    assert result.returncode == 0, result.stderr + result.stdout
    staging = tmp_path / "philosopher" / ".8ball-release" / "v0.8.0"
    assert (staging / "profiles/qwen3/model.json").is_file()
    assert (staging / "scripts/c10_common.py").is_file()
    assert (staging / "install/ubuntu/8.2.sh").is_file()
    bootstrap = subprocess.run(
        [
            "bash",
            "-c",
            (
                f'source "{install_dir.parent / "shared" / "8ball-release.sh"}"; '
                "eightball_bootstrap_release_runtime "
                f'"{install_dir}"'
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            **env,
            "PATH": f"{mock_bin}:{env['PATH']}",
            "EIGHTBALL_REPO_ROOT": str(staging),
            "EIGHTBALL_RELEASE_STAGING": str(staging),
            "EIGHTBALL_RELEASE_MANIFEST": str(staging / "manifest.json"),
        },
    )
    assert bootstrap.returncode == 0, bootstrap.stderr


def test_local_development_bundle_skips_remote_bootstrap(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    shutil.copytree(REPO_ROOT / "install", bundle_root / "install")
    shutil.copytree(REPO_ROOT / "profiles", bundle_root / "profiles")
    shutil.copytree(REPO_ROOT / "scripts", bundle_root / "scripts")
    shutil.copytree(REPO_ROOT / "AGENTS", bundle_root / "AGENTS")
    shutil.copytree(REPO_ROOT / "data", bundle_root / "data")
    install_dir = bundle_root / "install/ubuntu"
    env = _trial_env(tmp_path, EIGHTBALL_REPO_ROOT=str(bundle_root))
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f'source "{install_dir.parent / "shared" / "8ball-version.sh"}"; '
                f'source "{install_dir.parent / "shared" / "8ball-release.sh"}"; '
                f'eightball_local_bundle_ready "{install_dir}"'
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0


def test_explicit_model_passes_through() -> None:
    text = TRIAL_INSTALL.read_text(encoding="utf-8")
    assert 'model_args=(--model "${REQUESTED_MODEL}")' in text
    assert "MODEL_SLUG=qwen3" not in text


def test_default_bootstrap_does_not_force_qwen() -> None:
    text = TRIAL_INSTALL.read_text(encoding="utf-8")
    assert "MODEL_SLUG=qwen3" not in text
    assert 'MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"' in text


def test_no_motd_flag_is_preserved() -> None:
    text = TRIAL_INSTALL.read_text(encoding="utf-8")
    assert "--no-motd" in text
    assert 'if [[ "${SKIP_MOTD}" -eq 0 ]]; then' in text


def _local_dev_bundle(tmp_path: Path, *, fail_81: bool = False) -> Path:
    bundle = tmp_path / "bundle"
    shutil.copytree(REPO_ROOT / "install", bundle / "install")
    shutil.copytree(REPO_ROOT / "profiles", bundle / "profiles")
    shutil.copytree(REPO_ROOT / "scripts", bundle / "scripts")
    shutil.copytree(REPO_ROOT / "AGENTS", bundle / "AGENTS")
    shutil.copytree(REPO_ROOT / "data", bundle / "data")
    install_dir = bundle / "install/ubuntu"
    for name in ("8.1.sh", "8.2.sh", "8.3.sh"):
        body = _fail_stub() if fail_81 and name == "8.1.sh" else _noop_stub()
        path = install_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(stat.S_IRWXU)
    return bundle


def test_failed_stage_does_not_write_completion_marker(tmp_path: Path) -> None:
    bundle = _local_dev_bundle(tmp_path, fail_81=True)
    install_dir = bundle / "install/ubuntu"
    env = _trial_env(tmp_path, EIGHTBALL_REPO_ROOT=str(bundle))
    result = subprocess.run(
        ["bash", str(install_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        cwd=install_dir,
        env=env,
    )
    assert result.returncode != 0
    marker = tmp_path / "philosopher" / "trial-installed"
    assert not marker.exists()


def test_successful_chain_writes_completion_marker(tmp_path: Path) -> None:
    bundle = _local_dev_bundle(tmp_path)
    install_dir = bundle / "install/ubuntu"
    env = _trial_env(tmp_path, EIGHTBALL_REPO_ROOT=str(bundle))
    result = subprocess.run(
        ["bash", str(install_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        cwd=install_dir,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    marker = tmp_path / "philosopher" / "trial-installed"
    assert marker.is_file()
    assert "release_tag=v0.8.0" in marker.read_text(encoding="utf-8")


def test_rerun_remains_safe_after_success(tmp_path: Path) -> None:
    bundle = _local_dev_bundle(tmp_path)
    install_dir = bundle / "install/ubuntu"
    env = _trial_env(tmp_path, EIGHTBALL_REPO_ROOT=str(bundle))
    first = subprocess.run(
        ["bash", str(install_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        cwd=install_dir,
        env=env,
    )
    second = subprocess.run(
        ["bash", str(install_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        cwd=install_dir,
        env=env,
    )
    assert first.returncode == 0
    assert second.returncode == 0


def test_development_main_override_skips_checksum_enforcement() -> None:
    result = subprocess.run(
        ["bash", "-c", f'source "{RELEASE_SH}"; EIGHTBALL_RELEASE=main eightball_release_is_development'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_clean_entrypoint_bootstraps_shared_helpers(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(TRIAL_INSTALL, entry_dir / "trial-install.sh")
    shared_dir = entry_dir.parent / "shared"
    assert not shared_dir.exists()

    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_mock())
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert (shared_dir / "8ball-version.sh").is_file()
    assert (shared_dir / "8ball-release.sh").is_file()


def test_clean_entrypoint_acquires_release_runtime(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(TRIAL_INSTALL, entry_dir / "trial-install.sh")
    shared_dir = entry_dir.parent / "shared"

    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_mock())
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
    assert (shared_dir / "8ball-version.sh").is_file()
    assert (shared_dir / "8ball-release.sh").is_file()
    staging = tmp_path / "philosopher" / ".8ball-release" / "v0.8.0"
    assert (staging / "profiles/qwen3/model.json").is_file()
    assert (staging / "scripts/c10_common.py").is_file()
    assert (staging / "install/shared/c10-hardware-resolve.py").is_file()


def test_unpublished_release_ref_fails_closed(tmp_path: Path) -> None:
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(TRIAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir(parents=True, exist_ok=True)
    (mock_bin / "curl").write_text(
        "#!/usr/bin/env bash\nexit 22\n",
        encoding="utf-8",
    )
    (mock_bin / "curl").chmod(stat.S_IRWXU)
    env = _trial_env(tmp_path, EIGHTBALL_RELEASE_REF="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "Failed to download release manifest" in combined

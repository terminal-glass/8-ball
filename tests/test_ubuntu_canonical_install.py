"""Canonical Ubuntu trial-install entrypoint tests (PR57+)."""

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
CANONICAL_INSTALL = REPO_ROOT / "install/ubuntu/trial-install.sh"
CUSTOMER_URL = (
    "https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh"
)
RELEASE_MANIFEST = REPO_ROOT / "install/releases/v0.8.0/manifest.json"


def _pinned_runtime_ref() -> str:
    trial = CANONICAL_INSTALL.read_text(encoding="utf-8")
    match = re.search(
        r'EIGHTBALL_RELEASE_REF="\$\{EIGHTBALL_RELEASE_REF:-([0-9a-f]+)\}"',
        trial,
    )
    assert match, "installer must pin EIGHTBALL_RELEASE_REF"
    return match.group(1)


def _ensure_git_ref_available(ref: str) -> None:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        return
    fetch = subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", ref],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if fetch.returncode != 0:
        raise RuntimeError(
            f"Pinned runtime ref {ref} is not available locally and could not be fetched."
        )


def _git_show_bytes(ref: str, rel_path: str) -> bytes:
    _ensure_git_ref_available(ref)
    return subprocess.check_output(["git", "show", f"{ref}:{rel_path}"])


def _manifest_at_ref(ref: str) -> dict:
    return json.loads(_git_show_bytes(ref, "install/releases/v0.8.0/manifest.json"))


def _manifest_mismatches_at_ref(ref: str) -> list[tuple[str, str, str]]:
    manifest = _manifest_at_ref(ref)
    mismatches: list[tuple[str, str, str]] = []
    for rel_path, expected in manifest["artifacts"].items():
        actual = hashlib.sha256(_git_show_bytes(ref, rel_path)).hexdigest()
        if actual != expected:
            mismatches.append((rel_path, expected, actual))
    return mismatches


def _restore_release_tree() -> None:
    subprocess.run(
        ["git", "checkout", "--", "profiles/"],
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(autouse=True)
def restore_release_tree_fixture() -> None:
    _restore_release_tree()


def _build_deterministic_archive(snapshot: Path, manifest: dict) -> bytes:
    buf = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar,
    ):
        for rel in sorted(manifest["artifacts"]):
            src = snapshot / rel
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


def _manifest_for_tests(ref: str | None = None) -> dict:
    runtime_ref = ref or _pinned_runtime_ref()
    try:
        return _manifest_at_ref(runtime_ref)
    except subprocess.CalledProcessError:
        return json.loads((REPO_ROOT / "install/releases/v0.8.0/manifest.json").read_text(encoding="utf-8"))


def _build_release_snapshot(root: Path, ref: str | None = None) -> Path:
    runtime_ref = ref or _pinned_runtime_ref()
    manifest = _manifest_for_tests(runtime_ref)
    snap = root / "release_snapshot"
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True, exist_ok=True)
    for rel_path in manifest["artifacts"]:
        dest = snap / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(_git_show_bytes(runtime_ref, rel_path))
        except subprocess.CalledProcessError:
            dest.write_bytes((REPO_ROOT / rel_path).read_bytes())
    archive_info = manifest.get("runtime_archive", {})
    archive_rel = archive_info.get("path", "")
    if archive_rel:
        archive_dest = snap / archive_rel
        archive_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            archive_bytes = _git_show_bytes(runtime_ref, archive_rel)
        except subprocess.CalledProcessError:
            archive_bytes = _build_deterministic_archive(snap, manifest)
        archive_dest.write_bytes(archive_bytes)
    manifest_dest = snap / "install/releases/v0.8.0/manifest.json"
    manifest_dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        manifest_dest.write_bytes(_git_show_bytes(runtime_ref, "install/releases/v0.8.0/manifest.json"))
    except subprocess.CalledProcessError:
        manifest_dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return snap


def _mock_curl_script_body(
    *,
    manifest: dict,
    snapshot: Path,
    ref: str,
    log_file: str = "",
    corrupt_archive: bool = False,
) -> str:
    manifest_json = json.dumps(manifest)
    manifest_for_shell = manifest_json.replace("'", "'\"'\"'")
    archive_rel = manifest["runtime_archive"]["path"]
    log_line = f'printf \'%s\\n\' "${{url}}" >>"{log_file}"' if log_file else ""
    corrupt_block = 'echo corrupt >"${output}"' if corrupt_archive else f'cp "{snapshot}/{archive_rel}" "${{output}}"'
    return textwrap.dedent(
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
        {log_line}
        case "${{url}}" in
          */install/releases/*/manifest.json)
            printf '%s' '{manifest_for_shell}' >"${{output}}"
            ;;
          */{archive_rel.split("/")[-1]})
            {corrupt_block}
            ;;
          */profiles/*|*/install/shared/*|*/install/ubuntu/*.sh)
            echo "forbidden per-file runtime download: ${{url}}" >&2
            exit 22
            ;;
          *)
            echo "unexpected download URL: ${{url}}" >&2
            exit 22
            ;;
        esac
        """
    )


def _write_mock_curl(
    mock_bin: Path,
    manifest: dict,
    snapshot: Path,
    *,
    ref: str,
    corrupt_archive: bool = False,
) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    script = _mock_curl_script_body(
        manifest=manifest,
        snapshot=snapshot,
        ref=ref,
        corrupt_archive=corrupt_archive,
    )
    curl_path = mock_bin / "curl"
    curl_path.write_text(script, encoding="utf-8")
    curl_path.chmod(stat.S_IRWXU)


def _write_mock_curl_with_log(
    mock_bin: Path,
    manifest: dict,
    snapshot: Path,
    log_file: Path,
    *,
    ref: str,
    corrupt_archive: bool = False,
) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    script = _mock_curl_script_body(
        manifest=manifest,
        snapshot=snapshot,
        ref=ref,
        log_file=str(log_file),
        corrupt_archive=corrupt_archive,
    )
    curl_path = mock_bin / "curl"
    curl_path.write_text(script, encoding="utf-8")
    curl_path.chmod(stat.S_IRWXU)


def _staging_root(tmp_path: Path, ref: str | None = None) -> Path:
    runtime_ref = ref or _pinned_runtime_ref()
    return tmp_path / "philosopher" / ".8ball-release" / "v0.8.0" / runtime_ref


def _measured_env(**overrides: str) -> dict[str, str]:
    base = {
        "EIGHTBALL_USE_MEASURED_HARDWARE_ENV": "1",
        "EIGHTBALL_SYSTEM_RAM_GB": "16.0",
        "EIGHTBALL_USABLE_MODEL_RAM_GB": "9.0",
        "EIGHTBALL_FREE_DISK_GB": "100.0",
        "EIGHTBALL_CPU_THREADS": "6",
        "EIGHTBALL_CUDA_AVAILABLE": "false",
        "EIGHTBALL_GPU_VRAM_GB": "0",
    }
    base.update(overrides)
    return base


def _run_c10_resolver(repo_root: Path, lane: str, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    resolver = repo_root / "install/shared/c10-hardware-resolve.py"
    env = os.environ.copy()
    env["EIGHTBALL_REPO_ROOT"] = str(repo_root)
    env.update(_measured_env())
    env.update(env_overrides)
    return subprocess.run(
        ["python3", str(resolver), "plan", "--slug", "qwen3", "--lane", lane],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        env=env,
    )

def _trial_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    philo = tmp_path / "philosopher"
    philo.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PHILOSOPHER_ROOT": str(philo),
        "EIGHTBALL_RELEASE": "v0.8.0",
        "EIGHTBALL_RELEASE_REF": _pinned_runtime_ref(),
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


def test_pinned_commit_manifest_is_self_consistent() -> None:
    ref = _pinned_runtime_ref()
    mismatches = _manifest_mismatches_at_ref(ref)
    assert mismatches == []


def test_runtime_manifest_excludes_trial_install() -> None:
    manifest = _manifest_at_ref(_pinned_runtime_ref())
    assert "install/ubuntu/trial-install.sh" not in manifest["artifacts"]
    assert "trial-install.sh" not in manifest.get("scripts", {})


def test_customer_path_every_artifact_matches_manifest() -> None:
    ref = _pinned_runtime_ref()
    manifest = _manifest_at_ref(ref)
    for rel_path, expected in manifest["artifacts"].items():
        actual = hashlib.sha256(_git_show_bytes(ref, rel_path)).hexdigest()
        assert actual == expected, rel_path


def test_customer_path_8ball_release_matches_manifest() -> None:
    ref = _pinned_runtime_ref()
    manifest = _manifest_at_ref(ref)
    rel = "install/shared/8ball-release.sh"
    actual = hashlib.sha256(_git_show_bytes(ref, rel)).hexdigest()
    assert actual == manifest["artifacts"][rel]


def test_runtime_manifest_includes_runtime_archive() -> None:
    manifest = _manifest_for_tests()
    archive = manifest.get("runtime_archive") or {}
    assert archive.get("path") == "install/releases/v0.8.0/8ball-ubuntu-runtime.tar.gz"
    assert archive.get("sha256")
    assert archive.get("artifact_count") == len(manifest["artifacts"])


def test_stdin_execution_does_not_require_bash_source(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_tests(ref), snapshot, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

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
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_tests(ref), snapshot, ref=ref)
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
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    assert not (tmp_path / "install").exists()
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_tests(ref), snapshot, ref=ref)
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
    staging = _staging_root(tmp_path, ref)
    assert (staging / "profiles/qwen3/model.json").is_file()


def test_runtime_still_sha256_verified(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(
        mock_bin,
        _manifest_for_tests(ref),
        _build_release_snapshot(tmp_path, ref),
        ref=ref,
        corrupt_archive=True,
    )
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
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


def test_no_patch_stale_release_helper() -> None:
    trial = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert "eightball_patch_stale_release_helper" not in trial


def test_runtime_snapshot_excludes_trial_install() -> None:
    release = (REPO_ROOT / "install/shared/8ball-release.sh").read_text(encoding="utf-8")
    runtime_block = release.split("ubuntu_runtime_scripts=(")[1].split(")")[0]
    assert "trial-install.sh" not in runtime_block
    assert "eightball_download_verified_artifact" not in release
    manifest = _manifest_for_tests()
    assert "install/ubuntu/trial-install.sh" not in manifest["artifacts"]


def test_installer_pins_immutable_runtime_ref() -> None:
    ref = _pinned_runtime_ref()
    manifest = _manifest_at_ref(ref)
    assert _manifest_mismatches_at_ref(ref) == []
    assert "install/ubuntu/trial-install.sh" not in manifest["artifacts"]


def test_bootstrap_never_downloads_trial_install_url(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_mock_curl_with_log(mock_bin, _manifest_for_tests(ref), snapshot, curl_log, ref=ref)
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
    urls = curl_log.read_text(encoding="utf-8") if curl_log.is_file() else ""
    assert "/install/ubuntu/trial-install.sh" not in urls


def test_bootstrap_never_execs_second_trial_install() -> None:
    trial = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert 'eightball_bootstrap_release_runtime "${SCRIPT_DIR}" "${ENTRY_SCRIPT}"' not in trial
    assert "eightball_patch_stale_release_helper" not in trial


def test_customer_bootstrap_uses_runtime_archive_only(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    manifest = _manifest_for_tests(ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_mock_curl_with_log(mock_bin, manifest, snapshot, curl_log, ref=ref)
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
    urls = [line for line in curl_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(urls) == 2
    assert any("manifest.json" in url for url in urls)
    assert any("8ball-ubuntu-runtime.tar.gz" in url for url in urls)
    assert not any("/profiles/" in url for url in urls)
    assert not any(url.endswith(("/8.1.sh", "/8.2.sh", "/8.3.sh")) for url in urls)


def test_single_release_ref_controls_runtime_downloads(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_mock_curl_with_log(mock_bin, _manifest_for_tests(ref), snapshot, curl_log, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1", EIGHTBALL_RELEASE_REF=ref)
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    urls = [line for line in curl_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert urls
    assert all(f"/{ref}/" in url for url in urls)


def test_downloaded_helpers_not_mutated_after_verify(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    manifest = _manifest_for_tests(ref)
    rel = "install/shared/8ball-release.sh"
    expected_release = manifest["artifacts"][rel]
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, manifest, snapshot, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    bootstrap_root = tmp_path / "philosopher" / ".8ball-bootstrap" / "ubuntu" / "install" / "shared"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    release_path = entry_dir.parent / "shared" / "8ball-release.sh"
    if not release_path.is_file():
        release_path = bootstrap_root / "8ball-release.sh"
    if not release_path.is_file():
        release_path = _staging_root(tmp_path, ref) / rel
    assert release_path.is_file(), result.stderr + result.stdout
    actual = hashlib.sha256(release_path.read_bytes()).hexdigest()
    assert actual == expected_release
    assert actual == hashlib.sha256(_git_show_bytes(ref, rel)).hexdigest()


def test_default_staging_path_is_sha_namespaced() -> None:
    trial = CANONICAL_INSTALL.read_text(encoding="utf-8")
    assert (
        'staging_root="${EIGHTBALL_RELEASE_STAGING:-${PHILOSOPHER_ROOT}/.8ball-release/${EIGHTBALL_RELEASE}/${EIGHTBALL_RELEASE_REF}}"'
        in trial
    )


def test_cache_isolation_different_refs_use_different_roots(tmp_path: Path) -> None:
    ref_a = _pinned_runtime_ref()
    ref_b = "0000000000000000000000000000000000000001"
    assert ref_a != ref_b
    root_a = _staging_root(tmp_path, ref_a)
    root_b = _staging_root(tmp_path, ref_b)
    assert root_a != root_b


def test_same_ref_reuses_verified_cache(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_mock_curl_with_log(mock_bin, _manifest_for_tests(ref), snapshot, curl_log, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"

    first = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert first.returncode == 0, first.stderr + first.stdout
    first_urls = [line for line in curl_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(first_urls) == 2

    second = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert second.returncode == 0, second.stderr + second.stdout
    all_urls = [line for line in curl_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(all_urls) == 2
    staging = _staging_root(tmp_path, ref)
    assert (staging / "profiles/qwen3/model.json").is_file()


def test_c10_cpu_profile_resolution_from_namespaced_runtime(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_tests(ref), snapshot, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    bootstrap = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr + bootstrap.stdout
    staging = _staging_root(tmp_path, ref)
    assert (staging / "profiles/provider-assumptions").is_dir()
    assert (staging / "scripts/c10_common.py").is_file()
    assert (staging / "profiles/qwen3/ubuntu/cpu/lane.json").is_file()
    result = _run_c10_resolver(staging, "ubuntu/cpu")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["profile_id"] == "qwen3/ubuntu/cpu"


def test_c10_cuda_profile_resolution_from_namespaced_runtime(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    _write_mock_curl(mock_bin, _manifest_for_tests(ref), snapshot, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_BOOTSTRAP_STOP="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    bootstrap = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr + bootstrap.stdout
    staging = _staging_root(tmp_path, ref)
    assert (staging / "profiles/qwen3/ubuntu/cuda/lane.json").is_file()
    result = _run_c10_resolver(
        staging,
        "ubuntu/cuda",
        EIGHTBALL_CUDA_AVAILABLE="true",
        EIGHTBALL_GPU_VRAM_GB="12.0",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["profile_id"] == "qwen3/ubuntu/cuda"


def test_customer_path_resolves_runtime_scripts_without_per_file_http(tmp_path: Path) -> None:
    ref = _pinned_runtime_ref()
    snapshot = _build_release_snapshot(tmp_path, ref)
    manifest = _manifest_for_tests(ref)
    entry_dir = tmp_path / "customer"
    entry_dir.mkdir()
    shutil.copy(CANONICAL_INSTALL, entry_dir / "trial-install.sh")
    mock_bin = tmp_path / "bin"
    curl_log = tmp_path / "curl.log"
    _write_mock_curl_with_log(mock_bin, manifest, snapshot, curl_log, ref=ref)
    env = _trial_env(tmp_path, EIGHTBALL_TEST_RESOLVE_SCRIPTS="1")
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(entry_dir / "trial-install.sh"), "--no-motd"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    staging = _staging_root(tmp_path, ref)
    output = result.stdout
    for script in ("8.1.sh", "8.2.sh", "8.3.sh"):
        line = f"resolved_script:{script}="
        assert line in output
        resolved = output.split(line, 1)[1].splitlines()[0]
        expected = staging / "install/ubuntu" / script
        assert resolved == str(expected)
        assert str(staging) in resolved
    assert f"EIGHTBALL_REPO_ROOT={staging}" in output
    urls = [line for line in curl_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(urls) == 2
    assert not any(url.endswith(("/8.1.sh", "/8.2.sh", "/8.3.sh")) for url in urls)
    assert not any("/profiles/" in url for url in urls)
    assert not any("/install/shared/" in url for url in urls)

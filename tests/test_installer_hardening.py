"""Tests for 8-BALL 0.8 installer hardening helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_hardware_resolve_plan_has_lane_candidates() -> None:
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "install/shared/c10-hardware-resolve.py"), "plan"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["lane_path"]
    assert payload["candidates"]
    assert "qwen3" in payload["model_slug"] or payload["model_slug"] == "qwen3"


def test_release_manifest_matches_scripts() -> None:
    manifest_path = REPO_ROOT / "install/releases/v0.8.0/manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["suite_version"] == "0.8.0"
    for name in ("trial-install.sh", "8.1.sh", "8.2.sh", "8.3.sh"):
        assert name in manifest["scripts"]


def test_version_contract_declared_in_scripts() -> None:
    for rel in (
        "install/ubuntu/trial-install.sh",
        "install/ubuntu/8.1.sh",
        "install/ubuntu/8.2.sh",
        "install/ubuntu/8.3.sh",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert 'EIGHTBALL_SCRIPT_VERSION="0.8.0"' in text

#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_c10_validator_passes() -> None:
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "scripts/validate-c10-profiles.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload["valid"] is True
    assert payload["stats"]["model_pages"] >= 200
    assert payload["stats"]["install_lanes"] == 10


def test_model_page_shape() -> None:
    page_path = REPO_ROOT / "profiles/qwen3.json"
    assert page_path.is_file()
    page = json.loads(page_path.read_text(encoding="utf-8"))
    assert page["model_slug"] == "qwen3"
    assert page["sizes"][0]["parameter_count"] >= page["sizes"][1]["parameter_count"]


def test_provider_assumptions_exist() -> None:
    expected = REPO_ROOT / "profiles/provider-assumptions/ubuntu-cpu.json"
    assert expected.is_file()
    payload = json.loads(expected.read_text(encoding="utf-8"))
    assert payload["detection_signals"]

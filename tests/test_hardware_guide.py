from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

from eight_ball.generate.hardware_guide import render_hardware_guide

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    "data/normalized/hardware-assumed-profiles.json",
    "data/normalized/hardware-measured-hosts.json",
    "data/normalized/hardware-provider-instances.json",
    "data/normalized/hardware-accelerator-classes.json",
    "profiles/lanes.json",
    "profiles/manifest.json",
)


@pytest.fixture
def fixture_root(tmp_path):
    for name in INPUTS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    return tmp_path


def test_committed_guide_matches_canonical_records():
    assert (ROOT / "hardware/README.md").read_text() == render_hardware_guide(ROOT)


def test_unknown_capacity_is_not_zero_or_inference_success(fixture_root):
    path = fixture_root / "data/normalized/hardware-measured-hosts.json"
    measured = json.loads(path.read_text())
    measured[0].update(system_ram_gb=None, total_vram_gb=0, ollama_inference_verified=False)
    path.write_text(json.dumps(measured))
    page = render_hardware_guide(fixture_root)
    row = next(
        line for line in page.splitlines() if line.startswith("| " + measured[0]["host_profile_id"])
    )
    assert "| Unknown |" in row
    assert "| 0 | No |" in row


def test_render_is_stable_across_input_order_and_escapes_source_text(fixture_root):
    path = fixture_root / "data/normalized/hardware-assumed-profiles.json"
    rows = json.loads(path.read_text())
    rows[0]["display_name"] = "Test | capacity\ncontinued"
    path.write_text(json.dumps(rows))
    first = render_hardware_guide(fixture_root)
    path.write_text(json.dumps(list(reversed(rows))))
    assert render_hardware_guide(fixture_root) == first
    assert r"Test \| capacity continued" in first


def test_check_mode_detects_stale_page_without_overwriting(fixture_root, monkeypatch, capsys):
    script = ROOT / "scripts/generate-hardware-guide.py"
    spec = importlib.util.spec_from_file_location("hardware_guide_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = fixture_root / "hardware/README.md"
    target.parent.mkdir()
    target.write_text("stale page\n")
    monkeypatch.setattr(module, "ROOT", fixture_root)
    monkeypatch.setattr(sys, "argv", [str(script), "--check"])
    assert module.main() == 1
    assert target.read_text() == "stale page\n"
    assert "stale" in capsys.readouterr().err


@pytest.mark.parametrize(
    "name",
    [
        "README.md",
        "hardware/README.md",
        "profiles/README.md",
        "AGENTS/data-science/README.md",
        "docs/repository-layout.md",
    ],
)
def test_navigation_links_resolve_locally(name):
    page = ROOT / name
    for href in re.findall(r"\]\(([^)]+)\)", page.read_text()):
        if href.startswith(("https:", "http:", "mailto:", "#")):
            continue
        target = unquote(href.split("#", 1)[0])
        assert (page.parent / target).exists(), f"{name}: {href}"

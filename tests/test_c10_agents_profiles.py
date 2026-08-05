from __future__ import annotations

import json
import subprocess

from eight_ball.paths import PROFILES_DIR, REPO_ROOT


def test_c10_agents_profiles_validate() -> None:
    report_path = PROFILES_DIR / "_agent-generation-report.json"
    if not report_path.is_file():
        subprocess.run(
            ["python3", "scripts/generate-profiles-from-agents.py"],
            cwd=REPO_ROOT,
            check=True,
        )
    result = subprocess.run(
        ["python3", "scripts/validate-profiles-from-agents.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    report = json.loads((PROFILES_DIR / "_agent-generation-report.json").read_text(encoding="utf-8"))
    assert report["model count"] == 437
    assert report["matrix row count"] == 72710
    assert (PROFILES_DIR / "index.csv").is_file()
    assert (PROFILES_DIR / "lanes.json").is_file()

    sample_model = PROFILES_DIR / "qwen3-0-6b"
    assert (sample_model / "model.json").is_file()
    assert (sample_model / "sizes").is_dir()
    assert (sample_model / "ubuntu" / "cpu" / "3.sh").is_file()
    assert (sample_model / "windows" / "cpu" / "3.ps1").is_file()

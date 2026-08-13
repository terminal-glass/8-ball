#!/usr/bin/env python3
"""Offline, non-destructive smoke harness for public installer lanes (C10.2-5)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_OUT = REPO_ROOT / "reports" / "installer-smoke-results.json"
TIMEOUT_SECONDS = 30

STUB_COMMANDS = (
    "apt",
    "apt-get",
    "curl",
    "wget",
    "sudo",
    "systemctl",
    "ollama",
    "nvidia-smi",
    "yum",
    "dnf",
    "pip",
    "pip3",
    "snap",
)

FORBIDDEN_HELP_PATTERNS = [
    re.compile(r"\bsudo\b"),
    re.compile(r"\bapt-get\b"),
    re.compile(r"\bapt\s+install\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"\bollama\s+(pull|serve|run)\b"),
    re.compile(r"\bnvidia-smi\b"),
]


def load_lane_matrix() -> Any:
    validator_path = REPO_ROOT / "scripts" / "validate-install-lanes.py"
    spec = importlib.util.spec_from_file_location("validate_install_lanes", validator_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rel_posix(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def write_stub_commands(stub_dir: Path, log_file: Path) -> None:
    stub_dir.mkdir(parents=True, exist_ok=True)
    wrapper = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "STUB_INVOKED name=$(basename "$0") args=$*" >>"{log_file}"
        echo "blocked stub command: $(basename "$0")" >&2
        exit 97
        """
    )
    for name in STUB_COMMANDS:
        target = stub_dir / name
        target.write_text(wrapper, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_shell_env(work_dir: Path, stub_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(work_dir / "home")
    env["TMPDIR"] = str(work_dir / "tmp")
    env["XDG_CONFIG_HOME"] = str(work_dir / "config")
    env["EIGHTBALL_ROOT"] = str(work_dir / "eightball")
    env["PHILOSOPHER_ROOT"] = str(work_dir / "philosopher")
    env["PATH"] = f"{stub_dir}:{env.get('PATH', '/usr/bin:/bin')}"
    for key in list(env):
        if key.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
            env.pop(key, None)
    env.pop("AWS_ACCESS_KEY_ID", None)
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    env.pop("AWS_SESSION_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env.pop("OLLAMA_API_KEY", None)
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_CONFIG_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["EIGHTBALL_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(env["PHILOSOPHER_ROOT"]).mkdir(parents=True, exist_ok=True)
    return env


def classify_exit(mode: str, returncode: int, lane: str, script_kind: str) -> str:
    if mode == "help":
        return "pass" if returncode == 0 else "fail"
    if mode == "preflight":
        if returncode == 0:
            return "pass"
        if returncode == 2:
            if script_kind == "shell" and lane.startswith("mac/"):
                return "unsupported"
            if script_kind == "powershell":
                return "unsupported"
            return "unsupported"
        return "fail"
    return "fail"


def analyze_help_output(stdout: str, stderr: str, stub_log: Path) -> list[str]:
    issues: list[str] = []
    combined = f"{stdout}\n{stderr}"
    for pattern in FORBIDDEN_HELP_PATTERNS:
        if pattern.search(combined):
            issues.append(f"help output matched forbidden pattern: {pattern.pattern}")
    if stub_log.is_file() and stub_log.read_text(encoding="utf-8").strip():
        issues.append("help path invoked a blocked command stub")
    if "Usage:" not in combined and "usage" not in combined.lower():
        issues.append("help output missing usage text")
    return issues


def analyze_preflight_output(stdout: str, stderr: str, lane: str, stub_log: Path) -> list[str]:
    issues: list[str] = []
    combined = f"{stdout}\n{stderr}"
    if f"lane: {lane}" not in combined:
        issues.append("preflight output missing lane identifier")
    if "preflight" not in combined.lower():
        issues.append("preflight output missing mode marker")
    if "installation succeeded" in combined.lower() or "install complete" in combined.lower():
        issues.append("preflight may claim installation succeeded")
    if stub_log.is_file() and stub_log.read_text(encoding="utf-8").strip():
        issues.append("preflight path invoked a blocked command stub")
    if lane.startswith("mac/"):
        for token in ("/etc/os-release", "apt-get", "systemctl", "/proc/", "nvidia-smi"):
            if token in combined:
                issues.append(f"mac preflight referenced linux-only token: {token}")
    if lane == "windows/cpu":
        if "nvidia-smi" in combined.lower() and "not required" not in combined.lower():
            issues.append("windows/cpu preflight must not require CUDA evidence")
    if lane == "windows/cuda" and "cuda" not in combined.lower():
        issues.append("windows/cuda preflight should mention CUDA evidence requirement")
    return issues


def run_shell_mode(
    *,
    script_path: Path,
    mode: str,
    env: dict[str, str],
    stub_log: Path,
) -> dict[str, Any]:
    args = ["bash", str(script_path), "--help"] if mode == "help" else ["bash", str(script_path), "--preflight"]
    if stub_log.is_file():
        stub_log.unlink()
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    return {
        "command": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "stub_invocations": stub_log.read_text(encoding="utf-8").strip() if stub_log.is_file() else "",
    }


def run_powershell_mode(
    *,
    script_path: Path,
    mode: str,
    env: dict[str, str],
    stub_log: Path,
) -> dict[str, Any]:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        return {
            "command": [],
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "stub_invocations": "",
            "not_run_reason": "pwsh unavailable",
        }
    flag = "-Help" if mode == "help" else "-Preflight"
    args = [pwsh, "-NoProfile", "-File", str(script_path), flag]
    if stub_log.is_file():
        stub_log.unlink()
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    return {
        "command": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "stub_invocations": "",
        "not_run_reason": "",
    }


def evaluate_mode(
    *,
    lane: str,
    stem: str,
    script_path: Path,
    script_kind: str,
    mode: str,
    work_dir: Path,
) -> dict[str, Any]:
    stub_dir = work_dir / "stubs"
    stub_log = work_dir / "stub-invocations.log"
    write_stub_commands(stub_dir, stub_log)
    env = build_shell_env(work_dir, stub_dir)

    if script_kind == "powershell":
        run = run_powershell_mode(script_path=script_path, mode=mode, env=env, stub_log=stub_log)
        if run.get("not_run_reason"):
            return {
                "lane": lane,
                "stem": stem,
                "mode": mode,
                "path": rel_posix(script_path),
                "status": "not_run",
                "reason": run["not_run_reason"],
            }
    else:
        run = run_shell_mode(script_path=script_path, mode=mode, env=env, stub_log=stub_log)

    status = classify_exit(mode, int(run["returncode"]), lane, script_kind)
    issues: list[str] = []
    if mode == "help":
        issues.extend(analyze_help_output(run["stdout"], run["stderr"], stub_log))
    else:
        issues.extend(analyze_preflight_output(run["stdout"], run["stderr"], lane, stub_log))

    if issues and status == "pass":
        status = "fail"

    result: dict[str, Any] = {
        "lane": lane,
        "stem": stem,
        "mode": mode,
        "path": rel_posix(script_path),
        "status": status,
        "returncode": run["returncode"],
    }
    if status in {"fail", "unsupported"}:
        result["stdout"] = run["stdout"][-2000:]
        result["stderr"] = run["stderr"][-2000:]
    if issues:
        result["issues"] = issues
    if status == "unsupported":
        result["reason"] = (run["stderr"] or run["stdout"]).strip().splitlines()[-1] if (run["stderr"] or run["stdout"]) else "unsupported host"
    if run.get("stub_invocations"):
        result["stub_invocations"] = run["stub_invocations"]
    return result


def build_report(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    lane_module = load_lane_matrix()
    install_dir = root / "install"
    checks: list[dict[str, Any]] = []

    for spec in lane_module.LANE_SPECS:
        lane = spec["lane"]
        script_kind = spec["script_kind"]
        ext = ".ps1" if script_kind == "powershell" else ".sh"
        lane_dir = install_dir / lane
        for stem in lane_module.OPERATIONAL_STEMS:
            script_path = lane_dir / f"{stem}{ext}"
            work_dir = Path(tempfile.mkdtemp(prefix=f"smoke-{lane.replace('/', '_')}-{stem}-"))
            for mode in ("help", "preflight"):
                checks.append(
                    evaluate_mode(
                        lane=lane,
                        stem=stem,
                        script_path=script_path,
                        script_kind=script_kind,
                        mode=mode,
                        work_dir=work_dir / mode,
                    )
                )

    status_totals: dict[str, int] = {"pass": 0, "fail": 0, "not_run": 0, "unsupported": 0}
    for check in checks:
        status_totals[check["status"]] = status_totals.get(check["status"], 0) + 1

    overall = "pass" if status_totals.get("fail", 0) == 0 else "fail"

    checks_sorted = sorted(checks, key=lambda item: (item["lane"], item["stem"], item["mode"]))
    return {
        "schema_version": "c10.installer-smoke.v1",
        "status": overall,
        "lane_count": len(lane_module.LANE_SPECS),
        "summary": status_totals,
        "checks": checks_sorted,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"Installer smoke harness: {report['status'].upper()}")
    print(f"Lanes: {report['lane_count']}")
    for key in ("pass", "fail", "not_run", "unsupported"):
        print(f"  {key}: {report['summary'].get(key, 0)}")
    not_run = [c for c in report["checks"] if c["status"] == "not_run"]
    if not_run:
        print("\nNot run:")
        for entry in not_run:
            print(f"- {entry['lane']} {entry['stem']} {entry['mode']}: {entry.get('reason', 'unknown')}")
    failures = [c for c in report["checks"] if c["status"] == "fail"]
    if failures:
        print("\nFailures:")
        for entry in failures:
            print(f"- {entry['lane']} {entry['stem']} {entry['mode']}")
            for issue in entry.get("issues", []):
                print(f"  {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline installer smoke harness for public lanes.")
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help="Write deterministic JSON report (default: reports/installer-smoke-results.json)",
    )
    args = parser.parse_args(argv)

    report = build_report()
    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_human(report)
    try:
        display = json_path.relative_to(REPO_ROOT)
    except ValueError:
        display = json_path
    print(f"\nJSON report: {display}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

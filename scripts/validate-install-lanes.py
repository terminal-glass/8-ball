#!/usr/bin/env python3
"""Deterministic installer-lane conformance gate for the ten public runtime lanes."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIR = REPO_ROOT / "install"
DEFAULT_JSON_OUT = REPO_ROOT / "reports" / "installer-lane-conformance.json"

OPERATIONAL_STEMS = ("trial-install", "8.1", "8.2", "8.3")
MOTD_REL = Path("assets") / "first-MOTD.txt"

SHELL_EXTENSIONS = {".sh"}
POWERSHELL_EXTENSIONS = {".ps1"}

LANE_SPECS: list[dict[str, str]] = [
    {"lane": "ubuntu/cpu", "family": "ubuntu", "script_kind": "shell", "boundary": "linux"},
    {"lane": "ubuntu/cuda", "family": "ubuntu", "script_kind": "shell", "boundary": "linux"},
    {"lane": "mac/apple-silicon", "family": "mac", "script_kind": "shell", "boundary": "mac"},
    {"lane": "mac/intel", "family": "mac", "script_kind": "shell", "boundary": "mac"},
    {"lane": "windows/cpu", "family": "windows", "script_kind": "powershell", "boundary": "windows_cpu"},
    {"lane": "windows/cuda", "family": "windows", "script_kind": "powershell", "boundary": "windows_cuda"},
    {
        "lane": "cloud/digitalocean/cpu-droplet",
        "family": "digitalocean",
        "script_kind": "shell",
        "boundary": "linux",
    },
    {
        "lane": "cloud/digitalocean/gpu-droplet",
        "family": "digitalocean",
        "script_kind": "shell",
        "boundary": "linux",
    },
    {"lane": "cloud/aws-lightsail/cpu", "family": "lightsail", "script_kind": "shell", "boundary": "linux"},
    {"lane": "cloud/aws-lightsail/gpu", "family": "lightsail", "script_kind": "shell", "boundary": "linux"},
]

# Exact legacy debt entries only. No wildcards. Mac/Windows entries must fail validation.
LEGACY_DEBT_SPECS: list[dict[str, str]] = [
    {
        "lane": "cloud/digitalocean/cpu-droplet",
        "path": "install/cloud/digitalocean/cpu-droplet/trial-install.sh",
        "rule": "unreviewed_remote_payload_fetch",
        "rationale": "Legacy trial-install may download sibling scripts from GitHub RAW_BASE when local copies are missing.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when the lane bundle is self-contained without runtime GitHub script fetch.",
    },
    {
        "lane": "cloud/digitalocean/cpu-droplet",
        "path": "install/cloud/digitalocean/cpu-droplet/8.1.sh",
        "rule": "unreviewed_remote_ollama_install",
        "rationale": "Legacy 8.1 uses the remote ollama.com/install.sh pipeline instead of a reviewed manual-install contract.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when 8.1 stops piping a remote shell installer.",
    },
    {
        "lane": "cloud/digitalocean/gpu-droplet",
        "path": "install/cloud/digitalocean/gpu-droplet/trial-install.sh",
        "rule": "unreviewed_remote_payload_fetch",
        "rationale": "Legacy trial-install may download sibling scripts from GitHub RAW_BASE when local copies are missing.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when the lane bundle is self-contained without runtime GitHub script fetch.",
    },
    {
        "lane": "cloud/digitalocean/gpu-droplet",
        "path": "install/cloud/digitalocean/gpu-droplet/8.1.sh",
        "rule": "unreviewed_remote_ollama_install",
        "rationale": "Legacy 8.1 uses the remote ollama.com/install.sh pipeline instead of a reviewed manual-install contract.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when 8.1 stops piping a remote shell installer.",
    },
    {
        "lane": "cloud/aws-lightsail/cpu",
        "path": "install/cloud/aws-lightsail/cpu/trial-install.sh",
        "rule": "unreviewed_remote_payload_fetch",
        "rationale": "Legacy trial-install may download sibling scripts from GitHub RAW_BASE when local copies are missing.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when the lane bundle is self-contained without runtime GitHub script fetch.",
    },
    {
        "lane": "cloud/aws-lightsail/cpu",
        "path": "install/cloud/aws-lightsail/cpu/8.1.sh",
        "rule": "unreviewed_remote_ollama_install",
        "rationale": "Legacy 8.1 uses the remote ollama.com/install.sh pipeline instead of a reviewed manual-install contract.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when 8.1 stops piping a remote shell installer.",
    },
    {
        "lane": "cloud/aws-lightsail/gpu",
        "path": "install/cloud/aws-lightsail/gpu/trial-install.sh",
        "rule": "unreviewed_remote_payload_fetch",
        "rationale": "Legacy trial-install may download sibling scripts from GitHub RAW_BASE when local copies are missing.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when the lane bundle is self-contained without runtime GitHub script fetch.",
    },
    {
        "lane": "cloud/aws-lightsail/gpu",
        "path": "install/cloud/aws-lightsail/gpu/8.1.sh",
        "rule": "unreviewed_remote_ollama_install",
        "rationale": "Legacy 8.1 uses the remote ollama.com/install.sh pipeline instead of a reviewed manual-install contract.",
        "follow_up": "C10.2-Linux-lanes",
        "removal_condition": "Remove when 8.1 stops piping a remote shell installer.",
    },
]

FORBIDDEN_MAC_WINDOWS_LINUX_BEHAVIOR: list[tuple[str, re.Pattern[str]]] = [
    ("linux_os_release", re.compile(r"/etc/os-release")),
    ("apt", re.compile(r"\bapt-get\b|\bapt\s+install\b")),
    ("systemd", re.compile(r"\bsystemctl\b")),
    ("proc", re.compile(r"/proc/")),
    ("sudo_invoke", re.compile(r"^\s*sudo\s", re.MULTILINE)),
    ("ollama_serve", re.compile(r"\bollama\s+serve\b")),
    ("remote_ollama_install", re.compile(r"curl\s+.*ollama\.com/install\.sh\s*\|\s*sh")),
    ("remote_shell_install_pipeline", re.compile(r"curl\s+.*\|\s*(sh|bash)\b")),
    ("privileged_driver_install", re.compile(r"\bapt-get\s+install\b.*\bnvidia\b", re.I)),
    ("auto_ollama_signin", re.compile(r"^\s*ollama\s+signin\b", re.MULTILINE)),
]

MAC_EXTRA: list[tuple[str, re.Pattern[str]]] = [
    ("nproc", re.compile(r"\bnproc\b")),
    ("nvidia_smi", re.compile(r"\bnvidia-smi\b")),
    ("philosopher_root", re.compile(r"/opt/philosopher")),
    ("usr_local_bin_write", re.compile(r"/usr/local/bin")),
    ("dedicated_vram_claim", re.compile(r"\bVRAM\b")),
]

WINDOWS_CPU_EXTRA: list[tuple[str, re.Pattern[str]]] = [
    ("nvidia_smi_required", re.compile(r"\bnvidia-smi\b")),
    ("cuda_lane_helper", re.compile(r"Assert-CudaLaneEligibility")),
]

REMOTE_FETCH_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("unreviewed_remote_payload_fetch", re.compile(r"curl\s+-fsSL\s+.*(\$\{RAW_BASE\}|RAW_BASE|raw\.githubusercontent\.com)", re.I)),
    ("unreviewed_remote_ollama_install", re.compile(r"curl\s+.*ollama\.com/install\.sh\s*\|\s*sh")),
    ("unreviewed_remote_powershell_fetch", re.compile(r"Invoke-WebRequest.*\|\s*(iex|Invoke-Expression)", re.I)),
]

SHELL_HELP_REQUIRED = re.compile(r"-h\|--help|usage\(\)|\bUsage:")
PS_HELP_REQUIRED = re.compile(r"\[switch\]\$Help|\-Help\b")


@dataclass(frozen=True)
class Violation:
    lane: str
    path: str
    rule: str
    message: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "lane": self.lane,
            "path": self.path,
            "rule": self.rule,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class RepoContext:
    root: Path

    @property
    def install_dir(self) -> Path:
        return self.root / "install"


def rel_posix(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def executable_lines(content: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((index, line))
    return lines


def scan_patterns(
    *,
    lane: str,
    path: Path,
    repo_root: Path,
    patterns: list[tuple[str, re.Pattern[str]]],
    content: str,
    remediation: str,
) -> list[Violation]:
    rel = rel_posix(path, repo_root)
    hits: list[Violation] = []
    for line_no, line in executable_lines(content):
        for rule, pattern in patterns:
            if pattern.search(line):
                hits.append(
                    Violation(
                        lane=lane,
                        path=rel,
                        rule=rule,
                        message=f"Line {line_no}: {line.strip()}",
                        remediation=remediation,
                    )
                )
    return hits


def legacy_key(lane: str, path: str, rule: str) -> tuple[str, str, str]:
    return (lane, path, rule)


def validate_legacy_debt_specs() -> list[Violation]:
    violations: list[Violation] = []
    for entry in LEGACY_DEBT_SPECS:
        lane = entry["lane"]
        if lane.startswith("mac/") or lane.startswith("windows/"):
            violations.append(
                Violation(
                    lane=lane,
                    path=entry["path"],
                    rule="invalid_legacy_debt_lane",
                    message="Legacy debt is not allowed for Mac or Windows lanes.",
                    remediation="Remove the legacy_debt entry and fix the payload.",
                )
            )
        if "*" in entry["path"] or "?" in entry["path"]:
            violations.append(
                Violation(
                    lane=lane,
                    path=entry["path"],
                    rule="invalid_legacy_debt_wildcard",
                    message="Legacy debt paths must be exact file paths.",
                    remediation="Use an exact install/<lane>/<file> path with no wildcards.",
                )
            )
        expected_lane = entry["path"].removeprefix("install/")
        if not entry["path"].startswith(f"install/{lane}/"):
            violations.append(
                Violation(
                    lane=lane,
                    path=entry["path"],
                    rule="invalid_legacy_debt_path",
                    message=f"Legacy debt path does not match lane prefix install/{lane}/.",
                    remediation="Align lane and path fields exactly.",
                )
            )
    return violations


def expected_script_paths(lane_dir: Path, script_kind: str) -> dict[str, Path]:
    ext = ".ps1" if script_kind == "powershell" else ".sh"
    wrong_ext = ".sh" if script_kind == "powershell" else ".ps1"
    resolved: dict[str, Path] = {}
    for stem in OPERATIONAL_STEMS:
        expected = lane_dir / f"{stem}{ext}"
        resolved[stem] = expected
        wrong = lane_dir / f"{stem}{wrong_ext}"
        if wrong.is_file():
            resolved[f"{stem}_wrong_platform"] = wrong
    resolved["first-MOTD"] = lane_dir / MOTD_REL
    resolved["README"] = lane_dir / "README.md"
    return resolved


def bash_syntax_status(path: Path) -> dict[str, str]:
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    status = "pass" if result.returncode == 0 else "fail"
    detail = "" if status == "pass" else (result.stderr.strip() or "bash -n reported a syntax error")
    return {"status": status, "detail": detail}


def powershell_syntax_status(path: Path) -> dict[str, str]:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        return {"status": "not_run", "detail": "pwsh unavailable"}
    parse_cmd = (
        f"$tokens=$null; $errors=$null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{path.as_posix()}', [ref]$tokens, [ref]$errors); "
        f"if ($errors) {{ $errors | ForEach-Object {{ $_.ToString() }}; exit 1 }}"
    )
    result = subprocess.run([pwsh, "-NoProfile", "-Command", parse_cmd], capture_output=True, text=True)
    status = "pass" if result.returncode == 0 else "fail"
    detail = "" if status == "pass" else (result.stderr.strip() or result.stdout.strip() or "PowerShell parser reported a syntax error")
    return {"status": status, "detail": detail}


def has_help(path: Path, script_kind: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if script_kind == "powershell":
        return bool(PS_HELP_REQUIRED.search(text))
    return bool(SHELL_HELP_REQUIRED.search(text))


def is_legacy_debt(lane: str, path: str, rule: str) -> dict[str, str] | None:
    for entry in LEGACY_DEBT_SPECS:
        if legacy_key(entry["lane"], entry["path"], entry["rule"]) == legacy_key(lane, path, rule):
            return dict(entry)
    return None


def apply_boundary_checks(
    *,
    lane: str,
    boundary: str,
    path: Path,
    repo_root: Path,
    content: str,
    violations: list[Violation],
    legacy_debt_hits: list[dict[str, str]],
) -> None:
    rel = rel_posix(path, repo_root)
    patterns: list[tuple[str, re.Pattern[str]]] = []
    remediation = "Remove the platform-inappropriate behavior from the executable payload."

    if boundary == "mac":
        patterns = FORBIDDEN_MAC_WINDOWS_LINUX_BEHAVIOR + MAC_EXTRA
    elif boundary in {"windows_cpu", "windows_cuda", "windows_shared"}:
        patterns = list(FORBIDDEN_MAC_WINDOWS_LINUX_BEHAVIOR)
    elif boundary == "linux":
        patterns = []

    for hit in scan_patterns(
        lane=lane,
        path=path,
        repo_root=repo_root,
        patterns=patterns,
        content=content,
        remediation=remediation,
    ):
        debt = is_legacy_debt(lane, rel, hit.rule)
        if debt:
            legacy_debt_hits.append(debt | {"observed": hit.message})
            continue
        violations.append(hit)

    for rule, pattern in REMOTE_FETCH_RULES:
        for line_no, line in executable_lines(content):
            if not pattern.search(line):
                continue
            debt = is_legacy_debt(lane, rel, rule)
            if debt:
                legacy_debt_hits.append(debt | {"observed": f"Line {line_no}: {line.strip()}"})
                continue
            violations.append(
                Violation(
                    lane=lane,
                    path=rel,
                    rule=rule,
                    message=f"Line {line_no}: {line.strip()}",
                    remediation="Use local lane payloads or an explicit manual-install README instruction instead of fetching executables.",
                )
            )


def validate_lane(
    spec: dict[str, str],
    repo: RepoContext,
) -> tuple[dict[str, Any], list[Violation], list[dict[str, str]]]:
    lane = spec["lane"]
    lane_dir = repo.install_dir / lane
    script_kind = spec["script_kind"]
    boundary = spec["boundary"]
    violations: list[Violation] = []
    legacy_debt_hits: list[dict[str, str]] = []

    files_report: dict[str, Any] = {
        "readme": rel_posix(lane_dir / "README.md", repo.root),
        "motd": rel_posix(lane_dir / MOTD_REL, repo.root),
        "scripts": {},
    }

    if not lane_dir.is_dir():
        violations.append(
            Violation(
                lane=lane,
                path=rel_posix(lane_dir, repo.root),
                rule="missing_lane_directory",
                message="Lane directory is missing.",
                remediation=f"Create install/{lane}/ with the required public payload set.",
            )
        )
        return {"lane": lane, "status": "fail", "files": files_report, "syntax": {}}, violations, legacy_debt_hits

    expected = expected_script_paths(lane_dir, script_kind)
    readme_text = ""
    if expected["README"].is_file():
        readme_text = expected["README"].read_text(encoding="utf-8")
    else:
        violations.append(
            Violation(
                lane=lane,
                path=files_report["readme"],
                rule="missing_readme",
                message="README.md is missing.",
                remediation="Add a customer-facing README.md for the lane.",
            )
        )

    if not expected["first-MOTD"].is_file():
        violations.append(
            Violation(
                lane=lane,
                path=files_report["motd"],
                rule="missing_motd_asset",
                message="assets/first-MOTD.txt is missing.",
                remediation="Add the lane completion card template under assets/.",
            )
        )

    syntax_report: dict[str, dict[str, str]] = {}
    for stem in OPERATIONAL_STEMS:
        wrong_key = f"{stem}_wrong_platform"
        if wrong_key in expected and expected[wrong_key].is_file():
            violations.append(
                Violation(
                    lane=lane,
                    path=rel_posix(expected[wrong_key], repo.root),
                    rule="wrong_platform_extension",
                    message=f"Found {expected[wrong_key].name} but this lane requires {script_kind} payloads.",
                    remediation=f"Replace with {stem}{'.ps1' if script_kind == 'powershell' else '.sh'}.",
                )
            )

        script_path = expected[stem]
        rel_script = rel_posix(script_path, repo.root)
        files_report["scripts"][stem] = rel_script
        if not script_path.is_file():
            violations.append(
                Violation(
                    lane=lane,
                    path=rel_script,
                    rule="missing_operational_payload",
                    message=f"Required payload {script_path.name} is missing.",
                    remediation=f"Add install/{lane}/{script_path.name}.",
                )
            )
            syntax_report[stem] = {"path": rel_script, "status": "missing", "detail": "file not found"}
            continue

        if script_kind == "powershell":
            syntax_result = powershell_syntax_status(script_path)
        else:
            syntax_result = bash_syntax_status(script_path)
        syntax_report[stem] = {"path": rel_script, **syntax_result}
        if syntax_result["status"] == "fail":
            violations.append(
                Violation(
                    lane=lane,
                    path=rel_script,
                    rule="syntax_check_failed",
                    message=f"Syntax check failed for {script_path.name}.",
                    remediation="Fix shell syntax errors reported by bash -n or the PowerShell parser.",
                )
            )

        if not has_help(script_path, script_kind):
            violations.append(
                Violation(
                    lane=lane,
                    path=rel_script,
                    rule="missing_help_path",
                    message=f"{script_path.name} lacks discoverable --help/-Help in the executable payload.",
                    remediation="Add --help/-Help handling directly in the script; README text is not sufficient.",
                )
            )

        content = script_path.read_text(encoding="utf-8")
        apply_boundary_checks(
            lane=lane,
            boundary=boundary,
            path=script_path,
            repo_root=repo.root,
            content=content,
            violations=violations,
            legacy_debt_hits=legacy_debt_hits,
        )
        if boundary == "windows_cpu":
            for hit in scan_patterns(
                lane=lane,
                path=script_path,
                repo_root=repo.root,
                patterns=WINDOWS_CPU_EXTRA,
                content=content,
                remediation="Keep CUDA-only logic in install/windows/cuda only.",
            ):
                violations.append(hit)

    if boundary in {"windows_cpu", "windows_cuda"}:
        lib = repo.install_dir / "windows" / "lib" / "Windows-Common.ps1"
        if lib.is_file():
            apply_boundary_checks(
                lane=lane,
                boundary="windows_shared",
                path=lib,
                repo_root=repo.root,
                content=lib.read_text(encoding="utf-8"),
                violations=violations,
                legacy_debt_hits=legacy_debt_hits,
            )

    status = "pass" if not violations else "fail"
    return {
        "lane": lane,
        "status": status,
        "script_kind": script_kind,
        "boundary": boundary,
        "files": files_report,
        "syntax": syntax_report,
    }, violations, legacy_debt_hits


def validate_repo(repo_root: Path | None = None) -> dict[str, Any]:
    return build_report(repo_root)


def build_report(repo_root: Path | None = None) -> dict[str, Any]:
    repo = RepoContext(root=repo_root or REPO_ROOT)
    violations: list[Violation] = []
    legacy_debt: list[dict[str, str]] = []
    lanes_report: list[dict[str, Any]] = []

    violations.extend(validate_legacy_debt_specs())

    for spec in LANE_SPECS:
        lane_report, lane_violations, lane_debt = validate_lane(spec, repo)
        lane_report["violations"] = [item.as_dict() for item in lane_violations]
        lane_report["legacy_debt"] = sorted(
            ({k: debt[k] for k in debt if k != "observed"} for debt in lane_debt),
            key=lambda item: (item["path"], item["rule"]),
        )
        lanes_report.append(lane_report)
        violations.extend(lane_violations)
        for debt in lane_debt:
            key = legacy_key(debt["lane"], debt["path"], debt["rule"])
            if not any(legacy_key(d["lane"], d["path"], d["rule"]) == key for d in legacy_debt):
                legacy_debt.append({k: debt[k] for k in debt if k != "observed"})

    # Every recorded legacy debt entry must match observed behavior in the tree.
    for entry in LEGACY_DEBT_SPECS:
        path = repo.root / entry["path"]
        if not path.is_file():
            violations.append(
                Violation(
                    lane=entry["lane"],
                    path=entry["path"],
                    rule="stale_legacy_debt",
                    message="Legacy debt entry points at a missing file.",
                    remediation="Remove the stale legacy_debt entry or restore the referenced payload.",
                )
            )
            continue
        rule_pattern = next((pattern for name, pattern in REMOTE_FETCH_RULES if name == entry["rule"]), None)
        if rule_pattern and not any(rule_pattern.search(line) for _, line in executable_lines(path.read_text(encoding="utf-8"))):
            violations.append(
                Violation(
                    lane=entry["lane"],
                    path=entry["path"],
                    rule="stale_legacy_debt",
                    message=f"Legacy debt rule {entry['rule']} no longer matches the payload.",
                    remediation="Remove the legacy debt entry after modernization.",
                )
            )

    legacy_debt_sorted = sorted(legacy_debt, key=lambda item: (item["lane"], item["path"], item["rule"]))
    violations_sorted = sorted(violations, key=lambda item: (item.lane, item.path, item.rule, item.message))

    overall = "pass" if not violations_sorted else "fail"
    return {
        "schema_version": "c10.installer-lane-conformance.v1",
        "status": overall,
        "lane_count": len(LANE_SPECS),
        "summary": {
            "lane_count": len(LANE_SPECS),
            "failure_count": len(violations_sorted),
            "legacy_debt_count": len(legacy_debt_sorted),
        },
        "lanes": lanes_report,
        "violations": [item.as_dict() for item in violations_sorted],
        "legacy_debt": legacy_debt_sorted,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"Installer lane conformance: {report['status'].upper()}")
    print(f"Lanes inspected: {report['lane_count']}")
    for lane in report["lanes"]:
        print(f"- {lane['lane']}: {lane['status']} ({lane['script_kind']})")
    if report["legacy_debt"]:
        print("\nLegacy debt (waived, not ignored):")
        for entry in report["legacy_debt"]:
            print(f"- {entry['lane']} {entry['path']} [{entry['rule']}] -> {entry['follow_up']}")
    if report["violations"]:
        print("\nViolations:")
        for entry in report["violations"]:
            print(f"- {entry['lane']} {entry['path']} [{entry['rule']}]")
            print(f"  {entry['message']}")
            print(f"  Remediation: {entry['remediation']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the ten public installer runtime lanes.")
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help="Write deterministic JSON report to this path (default: reports/installer-lane-conformance.json)",
    )
    args = parser.parse_args(argv)

    report = build_report()
    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print_human(report)
    try:
        json_display = json_path.relative_to(REPO_ROOT)
    except ValueError:
        json_display = json_path
    print(f"\nJSON report: {json_display}")
    print("Exit 0 on pass, 1 on conformance failure.")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

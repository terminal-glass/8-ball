from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.config import load_yaml
from eight_ball.paths import CONFIG_DIR, REPO_ROOT

STATUSES = {"implemented", "planned", "unresolved"}
COVERAGE = {"tested", "planned", "unresolved", "untested"}


def load_alignment(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONFIG_DIR / "osamp-alignment.yaml")


def alignment_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schema") != "terminal-glass.8-ball.osamp-alignment/1":
        errors.append("osamp alignment schema id mismatch")
    if "OSAMP" not in str(document.get("protocol_name")):
        errors.append("osamp alignment must keep the OSAMP name")
    seen: set[str] = set()
    for row in document.get("rows") or []:
        row_id = row.get("id")
        if row_id in seen:
            errors.append(f"osamp alignment duplicate row {row_id}")
        seen.add(row_id)
        if row.get("status") not in STATUSES:
            errors.append(f"osamp alignment {row_id} has an unknown status")
    for row in document.get("pilot") or []:
        if row.get("coverage") not in COVERAGE:
            errors.append(f"osamp pilot {row.get('id')} has unknown coverage")
    return errors


def render_alignment(document: dict[str, Any]) -> str:
    lines = [
        "<!-- Generated from config/osamp-alignment.yaml by eight_ball.osamp.alignment. Do not edit by hand. -->",
        "",
        "# OSAMP alignment",
        "",
        document["protocol_name"].strip(),
        "",
        f"White paper: `{document['white_paper']}` ({document['white_paper_date']}).",
        document["white_paper_status"].strip(),
        "",
        "Status values are implemented, planned, or unresolved.",
        "Implemented means a local check or document in this repository.",
        "It does not mean a deployed federation.",
        "",
        "| Item | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for row in document["rows"]:
        lines.append(f"| {row['item']} | {row['status']} | {row['evidence']} |")
    lines.extend(
        [
            "",
            "## Pilot acceptance",
            "",
            "| Check | Coverage |",
            "| --- | --- |",
        ]
    )
    for row in document["pilot"]:
        lines.append(f"| {row['check']} | {row['coverage']} |")
    lines.append("")
    return "\n".join(lines)


def write_alignment(path: Path | None = None) -> Path:
    document = load_alignment()
    errors = alignment_errors(document)
    if errors:
        raise ValueError("; ".join(errors))
    target = path or REPO_ROOT / "docs" / "osamp-alignment.md"
    target.write_text(render_alignment(document), encoding="utf-8")
    return target

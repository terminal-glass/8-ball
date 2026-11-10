from __future__ import annotations

from pathlib import Path

from eight_ball.config import load_yaml, repo_relative
from eight_ball.paths import CONFIG_DIR, REPO_ROOT

GENERATED_BANNER = (
    "<!-- Generated from config/components.yaml by "
    "eight_ball.generate.component_display. Do not edit by hand. -->"
)


def load_component_inventory(path: Path | None = None) -> dict:
    return load_yaml(path or CONFIG_DIR / "components.yaml")


def render_component_inventory(document: dict) -> str:
    lines = [
        GENERATED_BANNER,
        "",
        "# 8-BALL component inventory",
        "",
        "This page is generated from `config/components.yaml`.",
        "It is the display record for runtime, UI, manager, installer, catalog,",
        "and optional agent adapters. It is not a second model catalog.",
        "",
        f"Canonical catalog version: `{document['catalog_version']}` in `data/normalized/`.",
        (
            f"Size unit policy: `{document['size_unit_policy']}` "
            "(1 KB = 1000 bytes). Download size is not RAM or VRAM."
        ),
        "",
        "The basic Independent AI workflow does not require a paid license.",
        "Planned and untested parts are labeled that way.",
        "",
        "| Component | Role | Required | Placement | License | Source | Status | Tested |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in document["components"]:
        required = "required" if item["required"] else "optional"
        lines.append(
            "| {name} | {role} | {required} | {placement} | {license_status} | {source} | {status} | {tested} |".format(
                name=item["display_name"],
                role=item["role"],
                required=required,
                placement=item["placement"],
                license_status=item["license_status"],
                source=item["source"],
                status=item["status"],
                tested=item["tested"],
            )
        )
    lines.extend(["", "## Notes", ""])
    for item in document["components"]:
        lines.append(f"- **{item['display_name']}** (`{item['id']}`): {item['notes']}")
        lines.append(f"  License text: {item['license']}")
    lines.append("")
    return "\n".join(lines)


def write_component_inventory(path: Path | None = None, *, source: Path | None = None) -> Path:
    document = load_component_inventory(source)
    target = path or REPO_ROOT / "docs" / "component-inventory.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_component_inventory(document), encoding="utf-8")
    return target


def inventory_output_path() -> str:
    return repo_relative(REPO_ROOT / "docs" / "component-inventory.md")

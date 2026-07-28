from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from eight_ball.paths import CONFIG_DIR, REPO_ROOT


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def catalog_policy() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "catalog-policy.yaml")


def sources_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "sources.yaml")


def capabilities_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "capabilities.yaml")


def hardware_profiles_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "hardware_profiles.yaml")


def publishers_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "publishers.yaml")


def deployment_tiers_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "deployment_tiers.yaml")


def repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)

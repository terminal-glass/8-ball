from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eight_ball.config import agents_csv_namespaces_config


@dataclass(frozen=True)
class SourceSpec:
    id: str
    path: str
    namespace: str
    format: str
    importable: bool
    options: dict[str, Any]


def _source_importable(namespace: str, namespaces: dict[str, Any]) -> bool:
    return bool(namespaces.get(namespace, {}).get("importable", False))


def load_registry() -> dict[str, Any]:
    return agents_csv_namespaces_config()


def source_specs() -> list[SourceSpec]:
    config = load_registry()
    namespaces = config.get("namespaces", {})
    specs: list[SourceSpec] = []
    for row in config.get("sources", []):
        namespace = row["namespace"]
        options = {key: value for key, value in row.items() if key not in {"id", "path", "namespace", "format"}}
        specs.append(
            SourceSpec(
                id=row["id"],
                path=row["path"],
                namespace=namespace,
                format=row["format"],
                importable=_source_importable(namespace, namespaces),
                options=options,
            )
        )
    return specs


def namespace_config(namespace: str) -> dict[str, Any]:
    config = load_registry()
    namespaces = config.get("namespaces", {})
    if namespace not in namespaces:
        raise KeyError(f"unknown namespace {namespace}")
    return namespaces[namespace]


def precedence_rank(status: str | None) -> int:
    if not status:
        return 0
    config = load_registry()
    precedence = config.get("precedence", {})
    normalized = status.strip().lower()
    if normalized in precedence:
        return int(precedence[normalized])
    for key, value in precedence.items():
        if normalized.startswith(key.lower()):
            return int(value)
    if "provider_published" in normalized:
        return int(precedence.get("provider_published", 40))
    if "assumed" in normalized or "assumption" in normalized:
        return int(precedence.get("assumed_client_class", 20))
    if "measured" in normalized:
        return int(precedence.get("measured_host_inventory", 50))
    return int(precedence.get("unknown", 10))

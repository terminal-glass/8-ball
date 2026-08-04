from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eight_ball.agents_csv.registry import SourceSpec
from eight_ball.config import load_json, load_yaml
from eight_ball.paths import REPO_ROOT


@dataclass(frozen=True)
class LoadedRow:
    source: SourceSpec
    row_number: int
    record: dict[str, Any]


def _resolve_path(path: str, *, repo_root: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _load_csv_rows(path: Path, source: SourceSpec) -> list[LoadedRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header row")
        rows: list[LoadedRow] = []
        for index, record in enumerate(reader, start=2):
            rows.append(LoadedRow(source=source, row_number=index, record=dict(record)))
        return rows


def _load_json_array_rows(path: Path, source: SourceSpec) -> list[LoadedRow]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise TypeError(f"{path} must contain a JSON array")
    rows: list[LoadedRow] = []
    for index, record in enumerate(payload, start=1):
        if not isinstance(record, dict):
            raise TypeError(f"{path} row {index} must be an object")
        rows.append(LoadedRow(source=source, row_number=index, record=record))
    return rows


def _load_deployment_types_rows(path: Path, source: SourceSpec) -> list[LoadedRow]:
    payload = load_yaml(path)
    deployment_types = payload.get("deployment_types", [])
    rows: list[LoadedRow] = []
    for index, record in enumerate(deployment_types, start=1):
        rows.append(LoadedRow(source=source, row_number=index, record=record))
    return rows


def load_source_rows(source: SourceSpec, *, repo_root: Path = REPO_ROOT) -> list[LoadedRow]:
    path = _resolve_path(source.path, repo_root=repo_root)
    if not path.exists():
        raise FileNotFoundError(f"missing source file {path}")

    if source.format == "csv":
        return _load_csv_rows(path, source)
    if source.format == "json_array":
        return _load_json_array_rows(path, source)
    if source.format == "deployment_types_yaml":
        return _load_deployment_types_rows(path, source)
    raise ValueError(f"unsupported source format {source.format} for {source.id}")


def load_all_sources(
    sources: list[SourceSpec] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, list[LoadedRow]]:
    from eight_ball.agents_csv.registry import source_specs

    selected = sources or source_specs()
    grouped: dict[str, list[LoadedRow]] = {}
    for source in selected:
        grouped.setdefault(source.namespace, []).extend(load_source_rows(source, repo_root=repo_root))
    return grouped

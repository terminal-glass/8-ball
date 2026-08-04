from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eight_ball.agents_csv.keys import (
    provenance_status,
    record_dedup_key,
    relationship_overlap_key,
)
from eight_ball.agents_csv.loader import LoadedRow, load_source_rows
from eight_ball.agents_csv.registry import SourceSpec, precedence_rank, source_specs
from eight_ball.paths import REPO_ROOT


class AgentsCsvValidationError(Exception):
    def __init__(
        self,
        errors: list[str],
        *,
        duplicate_keys: list[dict[str, Any]] | None = None,
        intentional_overlaps: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ):
        self.errors = errors
        self.duplicate_keys = duplicate_keys or []
        self.intentional_overlaps = intentional_overlaps or []
        self.warnings = warnings or []
        super().__init__(f"{len(errors)} AGENTS CSV validation error(s)")


@dataclass
class KeyOccurrence:
    namespace: str
    dedup_key: str
    source_id: str
    source_path: str
    row_number: int
    provenance_status: str | None
    precedence: int
    importable: bool


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_keys: list[dict[str, Any]] = field(default_factory=list)
    intentional_overlaps: list[dict[str, Any]] = field(default_factory=list)
    namespace_counts: dict[str, int] = field(default_factory=dict)
    source_counts: dict[str, int] = field(default_factory=dict)


def _control_reference_tokens(row: LoadedRow) -> set[str]:
    tokens: set[str] = set()
    for value in row.record.values():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.endswith((".csv", ".json", ".yaml")):
            tokens.add(text)
        for part in text.replace(",", " ").split():
            part = part.strip()
            if part.endswith(".csv"):
                tokens.add(part)
    return tokens


def _row_looks_like_data_record(row: LoadedRow) -> bool:
    record = row.record
    data_fields = (
        "provider_plan_id",
        "internal_plan_id",
        "plan_slug",
        "bundle_id",
        "profile_id",
        "host_profile_id",
        "accelerator_class_id",
    )
    return any(record.get(field) for field in data_fields)


def _collect_occurrences(
    sources: list[SourceSpec],
    *,
    repo_root: Path,
) -> tuple[list[KeyOccurrence], list[LoadedRow], list[str]]:
    occurrences: list[KeyOccurrence] = []
    all_rows: list[LoadedRow] = []
    errors: list[str] = []

    for source in sources:
        try:
            rows = load_source_rows(source, repo_root=repo_root)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"{source.path}: {exc}")
            continue

        all_rows.extend(rows)

        if not source.importable:
            continue

        for row in rows:
            try:
                dedup_key = record_dedup_key(row.record, source)
            except ValueError as exc:
                errors.append(f"{source.path}:{row.row_number}: {exc}")
                continue

            status = provenance_status(row.record, source)
            occurrences.append(
                KeyOccurrence(
                    namespace=source.namespace,
                    dedup_key=dedup_key,
                    source_id=source.id,
                    source_path=source.path,
                    row_number=row.row_number,
                    provenance_status=status,
                    precedence=precedence_rank(status),
                    importable=True,
                )
            )

    return occurrences, all_rows, errors


def _find_duplicate_keys(occurrences: list[KeyOccurrence]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[KeyOccurrence]] = defaultdict(list)
    for item in occurrences:
        grouped[(item.namespace, item.dedup_key)].append(item)

    duplicates: list[dict[str, Any]] = []
    for (namespace, dedup_key), items in sorted(grouped.items()):
        if len(items) < 2:
            continue
        duplicates.append(
            {
                "namespace": namespace,
                "dedup_key": dedup_key,
                "occurrences": [
                    {
                        "source_id": item.source_id,
                        "source_path": item.source_path,
                        "row_number": item.row_number,
                        "provenance_status": item.provenance_status,
                        "precedence": item.precedence,
                    }
                    for item in items
                ],
            }
        )
    return duplicates


def _find_precedence_conflicts(duplicates: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for duplicate in duplicates:
        occurrences = duplicate["occurrences"]
        precedences = [item["precedence"] for item in occurrences]
        statuses = [item["provenance_status"] for item in occurrences]
        if max(precedences) == min(precedences):
            continue
        if max(precedences) > min(precedences):
            low = min(precedences)
            high = max(precedences)
            low_sources = [
                item["source_path"]
                for item in occurrences
                if item["precedence"] == low
            ]
            high_sources = [
                item["source_path"]
                for item in occurrences
                if item["precedence"] == high
            ]
            errors.append(
                "lower-confidence record would overwrite higher-confidence data for "
                f"{duplicate['namespace']} key {duplicate['dedup_key']}: "
                f"{statuses} ({low_sources} vs {high_sources})"
            )
    return errors


def _find_cross_source_contamination(
    all_rows: list[LoadedRow],
) -> list[str]:
    errors: list[str] = []

    for row in all_rows:
        source = row.source
        if source.importable:
            continue

        if _row_looks_like_data_record(row):
            errors.append(
                f"{source.path}:{row.row_number}: control/provenance file contains "
                "importable data-row identifiers; do not re-import records from "
                "checklists, inventories, counts files, or summaries"
            )

    return errors


def _collect_intentional_overlaps(
    all_rows: list[LoadedRow],
    occurrences: list[KeyOccurrence],
) -> list[dict[str, Any]]:
    row_keys: dict[tuple[str, int], str] = {
        (item.source_id, item.row_number): item.dedup_key for item in occurrences
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in all_rows:
        if not row.source.importable:
            continue
        overlap_key = relationship_overlap_key(row.record, row.source)
        if not overlap_key:
            continue
        grouped[overlap_key].append(
            {
                "source_id": row.source.id,
                "source_path": row.source.path,
                "row_number": row.row_number,
                "namespace": row.source.namespace,
                "dedup_key": row_keys.get((row.source.id, row.row_number)),
                "deployment_type_id": row.record.get("deployment_type_id"),
                "provenance_status": provenance_status(row.record, row.source),
            }
        )

    overlaps: list[dict[str, Any]] = []
    for overlap_key, members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        dedup_keys = {member["dedup_key"] for member in members if member["dedup_key"]}
        if len(dedup_keys) <= 1:
            continue
        overlaps.append(
            {
                "relationship_key": overlap_key,
                "member_count": len(members),
                "namespaces": sorted({member["namespace"] for member in members}),
                "members": members,
                "note": (
                    "Intentional conceptual overlap; dedup keys differ and rows must "
                    "not be merged solely on RAM, VRAM, deployment type, menu label, "
                    "or GPU model."
                ),
            }
        )
    return overlaps


def validate_agents_csv_collection(
    *,
    repo_root: Path = REPO_ROOT,
    sources: list[SourceSpec] | None = None,
) -> ValidationReport:
    selected_sources = sources or source_specs()
    report = ValidationReport(ok=True)

    occurrences, all_rows, load_errors = _collect_occurrences(selected_sources, repo_root=repo_root)
    report.errors.extend(load_errors)

    duplicates = _find_duplicate_keys(occurrences)
    report.duplicate_keys = duplicates

    for duplicate in duplicates:
        paths = ", ".join(
            sorted({item["source_path"] for item in duplicate["occurrences"]})
        )
        report.errors.append(
            f"duplicate {duplicate['namespace']} key {duplicate['dedup_key']} ({paths})"
        )

    report.errors.extend(_find_precedence_conflicts(duplicates))
    report.errors.extend(_find_cross_source_contamination(all_rows))

    for source in selected_sources:
        try:
            rows = load_source_rows(source, repo_root=repo_root)
            report.source_counts[source.id] = len(rows)
        except (FileNotFoundError, ValueError):
            report.source_counts[source.id] = 0

    grouped_rows: dict[str, int] = defaultdict(int)
    for source in selected_sources:
        if not source.importable:
            continue
        grouped_rows[source.namespace] += report.source_counts.get(source.id, 0)
    report.namespace_counts = dict(grouped_rows)

    report.intentional_overlaps = _collect_intentional_overlaps(all_rows, occurrences)

    report.ok = not report.errors
    return report

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from eight_ball.collect.manifest import (
    CollectionManifest,
    load_manifest,
    read_verified_snapshot,
)
from eight_ball.collect.parse_ollama import (
    ParseError,
    parse_family_tags_page,
    parse_library_index,
)
from eight_ball.config import (
    deployment_tiers_config,
    hardware_profiles_config,
    load_json,
    write_json,
)
from eight_ball.paths import (
    CANDIDATE_GENERATED_DIR,
    CANDIDATE_NORMALIZED_DIR,
    LEGACY_FAMILIES_DIR,
    NORMALIZED_DIR,
    RAW_DIR,
    REPO_ROOT,
    REPORTS_DIR,
)

Disposition = Literal[
    "live_absent",
    "renamed_aliased_digest_merged",
    "regrouped",
    "source_unparseable",
    "ambiguous_review",
]


@dataclass
class CandidateMapping:
    collection_id: str | None
    catalog_version: str
    generated_at: str
    index_family_count: int
    normalized_family_count: int
    model_count: int
    tag_count: int
    deployment_count: int
    families: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "catalog_version": self.catalog_version,
            "generated_at": self.generated_at,
            "index_family_count": self.index_family_count,
            "normalized_family_count": self.normalized_family_count,
            "model_count": self.model_count,
            "tag_count": self.tag_count,
            "deployment_count": self.deployment_count,
            "families": self.families,
        }


@dataclass
class ReconciliationReport:
    catalog_version: str
    generated_at: str
    collection_id: str | None
    index_family_count: int
    normalized_family_count: int
    model_count: int
    tag_count: int
    deployment_count: int
    alias_digest_merge_count: int
    alias_digest_merges: list[dict[str, Any]] = field(default_factory=list)
    legacy_comparison: dict[str, Any] = field(default_factory=dict)
    live_absences: list[dict[str, Any]] = field(default_factory=list)
    source_exceptions: list[dict[str, Any]] = field(default_factory=list)
    review_queue: list[dict[str, Any]] = field(default_factory=list)
    mapping: CandidateMapping | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_version": self.catalog_version,
            "generated_at": self.generated_at,
            "collection_id": self.collection_id,
            "live_counts": {
                "index_families": self.index_family_count,
                "normalized_families": self.normalized_family_count,
                "models": self.model_count,
                "tags": self.tag_count,
                "deployments": self.deployment_count,
            },
            "alias_digest_merge_count": self.alias_digest_merge_count,
            "alias_digest_merges": self.alias_digest_merges,
            "legacy_comparison": self.legacy_comparison,
            "live_absence_count": len(self.live_absences),
            "live_absences": self.live_absences,
            "source_exception_count": len(self.source_exceptions),
            "source_exceptions": self.source_exceptions,
            "review_queue_count": len(self.review_queue),
            "review_queue": self.review_queue,
            "mapping": self.mapping.to_dict() if self.mapping else None,
        }


def _resolve_manifest_path(manifest_path: Path | None) -> Path:
    if manifest_path is not None:
        return manifest_path
    latest_path = RAW_DIR / "latest-manifest.json"
    if latest_path.exists():
        latest = load_json(latest_path)
        path = Path(latest["path"])
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.exists():
            return path
    raise FileNotFoundError(
        "No collection manifest found. Pass --manifest or run collect first."
    )


def _index_family_slugs(manifest: CollectionManifest) -> list[str]:
    entry = manifest.find_entry("library_index")
    if entry is None:
        raise FileNotFoundError("Manifest is missing library_index entry")
    html = read_verified_snapshot(entry)
    return [item.slug for item in parse_library_index(html)]


def _parse_family_tags_from_manifest(
    manifest: CollectionManifest,
    family_slug: str,
) -> list[dict[str, Any]]:
    entry = manifest.find_entry("family_tags", family_slug=family_slug)
    if entry is None:
        raise ParseError(f"Manifest missing family_tags entry for {family_slug}")
    tags = parse_family_tags_page(read_verified_snapshot(entry), family_slug)
    return [
        {
            "ollama_identifier": tag.ollama_identifier,
            "digest": tag.digest,
            "alias_target": tag.alias_target,
            "parameter_label": tag.parameter_label,
            "tag_suffix": tag.tag_suffix,
        }
        for tag in tags
    ]


def _legacy_tag_digests() -> dict[str, str]:
    digests: dict[str, str] = {}
    if not LEGACY_FAMILIES_DIR.exists():
        return digests
    for family_path in LEGACY_FAMILIES_DIR.glob("*.json"):
        payload = load_json(family_path)
        for variant in payload.get("variants", []):
            tag = variant.get("exact_tag")
            digest = variant.get("manifest_digest")
            if isinstance(tag, str) and isinstance(digest, str) and digest:
                digests[tag] = digest
    return digests


def _deployment_count(candidate_dir: Path, tag_count: int) -> int:
    deployments_path = CANDIDATE_GENERATED_DIR / "deployment_recommendations.json"
    if deployments_path.exists():
        return len(load_json(deployments_path))
    profiles = len(hardware_profiles_config().get("profiles", []))
    policies = len(deployment_tiers_config().get("runtime_policies", []))
    return tag_count * profiles * policies


def build_candidate_mapping(
    *,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    manifest: CollectionManifest | None = None,
) -> CandidateMapping:
    families = load_json(candidate_dir / "families.json")
    models = load_json(candidate_dir / "models.json")
    tags = load_json(candidate_dir / "tags.json")
    meta = load_json(candidate_dir / "catalog-meta.json")

    models_by_family: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        models_by_family.setdefault(model["family_id"], []).append(model)

    tags_by_model: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        tags_by_model.setdefault(tag["model_id"], []).append(tag)

    family_rows: list[dict[str, Any]] = []
    for family in sorted(families, key=lambda item: item["id"]):
        family_models = sorted(models_by_family.get(family["id"], []), key=lambda item: item["id"])
        model_rows: list[dict[str, Any]] = []
        family_tag_count = 0
        for model in family_models:
            model_tags = sorted(
                tags_by_model.get(model["id"], []),
                key=lambda item: item["ollama_identifier"],
            )
            family_tag_count += len(model_tags)
            model_rows.append(
                {
                    "model_id": model["id"],
                    "tag_count": len(model_tags),
                    "tags": [tag["ollama_identifier"] for tag in model_tags],
                    "default_tag": model.get("default_tag"),
                }
            )
        family_rows.append(
            {
                "family_id": family["id"],
                "model_count": len(model_rows),
                "tag_count": family_tag_count,
                "models": model_rows,
            }
        )

    index_count = len(families)
    if manifest is not None:
        index_count = len(_index_family_slugs(manifest))

    tag_count = len(tags)
    return CandidateMapping(
        collection_id=manifest.collection_id if manifest else None,
        catalog_version=meta.get("catalog_version", "unknown"),
        generated_at=meta.get("generated_at", "unknown"),
        index_family_count=index_count,
        normalized_family_count=len(families),
        model_count=len(models),
        tag_count=tag_count,
        deployment_count=_deployment_count(candidate_dir, tag_count),
        families=family_rows,
    )


def discover_source_exceptions(
    manifest: CollectionManifest,
    *,
    normalized_family_ids: set[str],
) -> list[dict[str, Any]]:
    exceptions: list[dict[str, Any]] = []
    collected_slugs = sorted(
        {
            entry.family_slug
            for entry in manifest.entries
            if entry.snapshot_kind == "family" and entry.family_slug
        }
    )
    for slug in collected_slugs:
        if slug in normalized_family_ids:
            continue
        family_entry = manifest.find_entry("family", family_slug=slug)
        tags_entry = manifest.find_entry("family_tags", family_slug=slug)
        if family_entry is None or tags_entry is None:
            exceptions.append(
                {
                    "family_slug": slug,
                    "disposition": "source_unparseable",
                    "reason": "missing_family_or_tags_snapshot",
                    "evidence": {
                        "has_family_snapshot": family_entry is not None,
                        "has_tags_snapshot": tags_entry is not None,
                    },
                    "recommended_disposition": "retry_collection_or_manual_snapshot",
                }
            )
            continue
        try:
            _parse_family_tags_from_manifest(manifest, slug)
        except ParseError as exc:
            exceptions.append(
                {
                    "family_slug": slug,
                    "disposition": "source_unparseable",
                    "reason": "static_html_parse_failure",
                    "evidence": {"error": str(exc)},
                    "recommended_disposition": "parser_update_or_manual_review",
                }
            )
    return exceptions


def _collect_alias_digest_merges(
    tags: list[dict[str, Any]],
    manifest: CollectionManifest | None,
) -> list[dict[str, Any]]:
    merges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for tag in tags:
        alias_target = tag.get("alias_target")
        if not alias_target:
            continue
        key = (tag["ollama_identifier"], alias_target)
        if key in seen:
            continue
        seen.add(key)
        merges.append(
            {
                "alias_tag": tag["ollama_identifier"],
                "canonical_tag": alias_target,
                "model_id": tag.get("model_id"),
                "merge_kind": "alias_target",
            }
        )

    if manifest is None:
        return merges

    for family in {tag["ollama_identifier"].split(":", 1)[0] for tag in tags}:
        try:
            parsed_tags = _parse_family_tags_from_manifest(manifest, family)
        except ParseError:
            continue
        by_digest: dict[str, list[dict[str, Any]]] = {}
        for parsed in parsed_tags:
            digest = parsed.get("digest")
            if digest:
                by_digest.setdefault(digest, []).append(parsed)
        for digest, group in by_digest.items():
            if len(group) < 2:
                continue
            identifiers = sorted(item["ollama_identifier"] for item in group)
            canonical = next(
                (item["ollama_identifier"] for item in group if item.get("alias_target") is None),
                identifiers[0],
            )
            for item in group:
                if item["ollama_identifier"] == canonical:
                    continue
                key = (item["ollama_identifier"], canonical)
                if key in seen:
                    continue
                seen.add(key)
                merges.append(
                    {
                        "alias_tag": item["ollama_identifier"],
                        "canonical_tag": canonical,
                        "digest": digest,
                        "merge_kind": "identical_digest",
                    }
                )
    return merges


def _classify_legacy_tag(
    tag_id: str,
    *,
    candidate_tag_ids: set[str],
    candidate_tags_by_id: dict[str, dict[str, Any]],
    candidate_digest_to_tags: dict[str, list[str]],
    legacy_digest: str | None,
    index_families: set[str],
    unparseable_families: set[str],
    legacy_model_id: str,
) -> dict[str, Any]:
    family_slug, _suffix = tag_id.split(":", 1)
    if tag_id in candidate_tag_ids:
        candidate_model = candidate_tags_by_id[tag_id].get("model_id")
        if candidate_model and candidate_model != legacy_model_id:
            return {
                "ollama_identifier": tag_id,
                "disposition": "regrouped",
                "evidence": {
                    "legacy_model_id": legacy_model_id,
                    "candidate_model_id": candidate_model,
                },
                "recommended_disposition": "accept_candidate_grouping",
            }
        return {
            "ollama_identifier": tag_id,
            "disposition": "renamed_aliased_digest_merged",
            "evidence": {"note": "tag present in candidate catalog"},
            "recommended_disposition": "no_action",
        }

    if family_slug in unparseable_families:
        return {
            "ollama_identifier": tag_id,
            "disposition": "source_unparseable",
            "evidence": {"family_slug": family_slug},
            "recommended_disposition": "parser_update_or_manual_review",
        }

    if family_slug not in index_families:
        return {
            "ollama_identifier": tag_id,
            "disposition": "live_absent",
            "evidence": {"family_not_in_live_index": True},
            "recommended_disposition": "archive_legacy_only",
        }

    if legacy_digest and legacy_digest in candidate_digest_to_tags:
        matches = candidate_digest_to_tags[legacy_digest]
        return {
            "ollama_identifier": tag_id,
            "disposition": "renamed_aliased_digest_merged",
            "evidence": {
                "legacy_digest": legacy_digest,
                "candidate_tags_with_digest": matches,
            },
            "recommended_disposition": "map_to_candidate_tag",
        }

    candidate_family_tags = [
        tag
        for candidate_id, tag in candidate_tags_by_id.items()
        if candidate_id.startswith(f"{family_slug}:")
    ]
    if candidate_family_tags:
        return {
            "ollama_identifier": tag_id,
            "disposition": "ambiguous_review",
            "evidence": {
                "family_in_live_index": True,
                "candidate_family_tag_count": len(candidate_family_tags),
                "legacy_digest": legacy_digest,
            },
            "recommended_disposition": "human_review",
        }

    return {
        "ollama_identifier": tag_id,
        "disposition": "live_absent",
        "evidence": {"tag_missing_from_candidate_and_family_has_no_parsed_tags": True},
        "recommended_disposition": "verify_live_ollama_page",
    }


def _candidate_digest_index(
    manifest: CollectionManifest,
    normalized_family_ids: set[str],
) -> dict[str, list[str]]:
    digest_to_tags: dict[str, list[str]] = {}
    for slug in sorted(normalized_family_ids):
        try:
            parsed_tags = _parse_family_tags_from_manifest(manifest, slug)
        except ParseError:
            continue
        for parsed in parsed_tags:
            digest = parsed.get("digest")
            if not digest:
                continue
            digest_to_tags.setdefault(digest, []).append(parsed["ollama_identifier"])
    for identifiers in digest_to_tags.values():
        identifiers.sort()
    return digest_to_tags


def reconcile_candidate_catalog(
    *,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    legacy_dir: Path = NORMALIZED_DIR,
    manifest_path: Path | None = None,
) -> ReconciliationReport:
    manifest = load_manifest(_resolve_manifest_path(manifest_path))
    mapping = build_candidate_mapping(candidate_dir=candidate_dir, manifest=manifest)

    families = load_json(candidate_dir / "families.json")
    normalized_family_ids = {family["id"] for family in families}
    tags = load_json(candidate_dir / "tags.json")
    candidate_tags_by_id = {tag["ollama_identifier"]: tag for tag in tags}
    candidate_tag_ids = set(candidate_tags_by_id)

    source_exceptions = discover_source_exceptions(
        manifest,
        normalized_family_ids=normalized_family_ids,
    )
    unparseable_families = {item["family_slug"] for item in source_exceptions}
    index_families = set(_index_family_slugs(manifest))

    alias_digest_merges = _collect_alias_digest_merges(tags, manifest)
    candidate_digest_to_tags = _candidate_digest_index(manifest, normalized_family_ids)
    legacy_digests = _legacy_tag_digests()

    legacy_tags = load_json(legacy_dir / "tags.json")
    legacy_models = {model["id"]: model for model in load_json(legacy_dir / "models.json")}
    legacy_tag_ids = {tag["ollama_identifier"] for tag in legacy_tags}
    legacy_only_tags = sorted(legacy_tag_ids - candidate_tag_ids)

    disposition_counts: dict[str, int] = {
        "live_absent": 0,
        "renamed_aliased_digest_merged": 0,
        "regrouped": 0,
        "source_unparseable": 0,
        "ambiguous_review": 0,
    }
    classified_legacy_tags: list[dict[str, Any]] = []
    live_absences: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []

    for tag_id in legacy_only_tags:
        legacy_tag = next(tag for tag in legacy_tags if tag["ollama_identifier"] == tag_id)
        legacy_model_id = legacy_tag.get("model_id", tag_id.split(":", 1)[0])
        classification = _classify_legacy_tag(
            tag_id,
            candidate_tag_ids=candidate_tag_ids,
            candidate_tags_by_id=candidate_tags_by_id,
            candidate_digest_to_tags=candidate_digest_to_tags,
            legacy_digest=legacy_digests.get(tag_id),
            index_families=index_families,
            unparseable_families=unparseable_families,
            legacy_model_id=legacy_model_id,
        )
        classified_legacy_tags.append(classification)
        disposition = classification["disposition"]
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if disposition == "live_absent":
            live_absences.append(classification)
        elif disposition == "ambiguous_review":
            review_queue.append(classification)

    candidate_only_tags = sorted(candidate_tag_ids - legacy_tag_ids)
    legacy_model_ids = set(legacy_models)
    candidate_model_ids = {model["id"] for model in load_json(candidate_dir / "models.json")}
    legacy_only_models = sorted(legacy_model_ids - candidate_model_ids)
    regrouped_models = 0
    for model_id in legacy_only_models:
        model_tags = [
            tag["ollama_identifier"]
            for tag in legacy_tags
            if tag.get("model_id") == model_id
        ]
        if model_tags and all(tag_id in candidate_tag_ids for tag_id in model_tags):
            regrouped_models += 1
            continue
        tag_dispositions = {
            item["disposition"]
            for item in classified_legacy_tags
            if item["ollama_identifier"] in model_tags
        }
        if tag_dispositions and tag_dispositions <= {"regrouped", "renamed_aliased_digest_merged"}:
            regrouped_models += 1

    meta = load_json(candidate_dir / "catalog-meta.json")
    return ReconciliationReport(
        catalog_version=meta.get("catalog_version", mapping.catalog_version),
        generated_at=meta.get("generated_at", mapping.generated_at),
        collection_id=manifest.collection_id,
        index_family_count=mapping.index_family_count,
        normalized_family_count=mapping.normalized_family_count,
        model_count=mapping.model_count,
        tag_count=mapping.tag_count,
        deployment_count=mapping.deployment_count,
        alias_digest_merge_count=len(alias_digest_merges),
        alias_digest_merges=alias_digest_merges,
        legacy_comparison={
            "legacy_tag_count": len(legacy_tags),
            "candidate_tag_count": len(tags),
            "shared_tags": len(legacy_tag_ids & candidate_tag_ids),
            "legacy_only_tags": len(legacy_only_tags),
            "candidate_only_tags": len(candidate_only_tags),
            "legacy_only_models": len(legacy_only_models),
            "legacy_only_models_likely_regrouped": regrouped_models,
            "legacy_only_models_not_explained_by_regrouping": len(legacy_only_models) - regrouped_models,
            "disposition_counts": disposition_counts,
            "note": (
                "Legacy-only model IDs are usually digest regrouping, not live removals. "
                "See disposition_counts for per-tag classification."
            ),
        },
        live_absences=live_absences,
        source_exceptions=source_exceptions,
        review_queue=review_queue,
        mapping=mapping,
    )


def write_reconciliation_reports(
    report: ReconciliationReport,
    *,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    output_dir = output_dir or REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "candidate-reconciliation.json"
    md_path = output_dir / "candidate-reconciliation.md"
    review_path = output_dir / "candidate-review-queue.json"
    exceptions_path = output_dir / "candidate-source-exceptions.json"
    mapping_path = output_dir / "candidate-mapping.json"

    write_json(json_path, report.to_dict())
    write_json(
        review_path,
        {
            "generated_at": report.generated_at,
            "catalog_version": report.catalog_version,
            "count": len(report.review_queue),
            "items": report.review_queue,
        },
    )
    write_json(
        exceptions_path,
        {
            "generated_at": report.generated_at,
            "catalog_version": report.catalog_version,
            "count": len(report.source_exceptions),
            "items": report.source_exceptions,
        },
    )
    if report.mapping is not None:
        write_json(mapping_path, report.mapping.to_dict())

    lines = [
        "# Candidate Catalog Reconciliation",
        "",
        f"- Catalog version: `{report.catalog_version}`",
        f"- Generated at: {report.generated_at}",
        f"- Collection ID: `{report.collection_id}`",
        "",
        "## Authoritative live candidate counts",
        f"- Index families (live Ollama library): **{report.index_family_count}**",
        f"- Normalized families: **{report.normalized_family_count}**",
        f"- Canonical candidate models: **{report.model_count}**",
        f"- Tags / deployments: **{report.tag_count}** tags, **{report.deployment_count}** deployment combinations",
        "",
        "## Alias and digest merges (candidate)",
        f"- Merge records: **{report.alias_digest_merge_count}**",
        "",
        "## Legacy comparison (informational only)",
    ]
    legacy = report.legacy_comparison
    lines.extend(
        [
            f"- Legacy tags: {legacy.get('legacy_tag_count', 0)}",
            f"- Candidate tags: {legacy.get('candidate_tag_count', 0)}",
            f"- Shared tags: {legacy.get('shared_tags', 0)}",
            f"- Legacy-only tags: {legacy.get('legacy_only_tags', 0)}",
            f"- Candidate-only tags: {legacy.get('candidate_only_tags', 0)}",
            (
                f"- Legacy-only model IDs: {legacy.get('legacy_only_models', 0)} "
                f"({legacy.get('legacy_only_models_likely_regrouped', 0)} likely regrouped)"
            ),
            "",
            "### Legacy-only tag disposition",
        ]
    )
    for disposition, count in sorted(legacy.get("disposition_counts", {}).items()):
        lines.append(f"- `{disposition}`: {count}")
    lines.extend(
        [
            "",
            f"> {legacy.get('note', '')}",
            "",
            "## True live absences",
            f"- Count: **{len(report.live_absences)}**",
            "",
            "## Source exceptions (unparseable snapshots)",
            f"- Count: **{len(report.source_exceptions)}**",
        ]
    )
    for item in report.source_exceptions:
        lines.append(f"- `{item['family_slug']}`: {item['reason']}")
    lines.extend(
        [
            "",
            "## Ambiguous human-review queue",
            f"- Count: **{len(report.review_queue)}**",
            "",
            "Artifacts:",
            f"- `{json_path}`",
            f"- `{review_path}`",
            f"- `{exceptions_path}`",
            f"- `{mapping_path}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "json": json_path,
        "markdown": md_path,
        "review_queue": review_path,
        "source_exceptions": exceptions_path,
        "mapping": mapping_path,
    }

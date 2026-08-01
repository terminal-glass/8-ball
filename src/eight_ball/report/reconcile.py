from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from eight_ball.collect.manifest import (
    CollectionManifest,
    load_manifest,
    read_verified_snapshot,
    snapshot_policy,
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
    MANIFESTS_DIR,
    NORMALIZED_DIR,
    RAW_DIR,
    REPO_ROOT,
    REPORTS_DIR,
)
from eight_ball.report.source_exceptions import (
    SOURCE_EXCEPTION_RETENTION_POLICY,
    known_source_exception_slugs,
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
    source_indexed_families: int
    parseable_source_families: int
    source_exception_families: int
    collected_snapshots: int
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
            "live_counts": {
                "source_indexed_families": self.source_indexed_families,
                "parseable_source_families": self.parseable_source_families,
                "source_exception_families": self.source_exception_families,
                "collected_snapshots": self.collected_snapshots,
                "normalized_candidate_families": self.normalized_family_count,
                "candidate_canonical_models": self.model_count,
                "tags": self.tag_count,
                "deployment_combinations": self.deployment_count,
            },
            "families": self.families,
        }


@dataclass
class ReconciliationReport:
    catalog_version: str
    generated_at: str
    collection_id: str | None
    live_counts: dict[str, int]
    alias_digest_merge_count: int
    alias_digest_merges: list[dict[str, Any]] = field(default_factory=list)
    collection_stats: dict[str, Any] = field(default_factory=dict)
    legacy_comparison: dict[str, Any] = field(default_factory=dict)
    legacy_model_evidence: dict[str, Any] = field(default_factory=dict)
    classified_items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    live_absences: list[dict[str, Any]] = field(default_factory=list)
    regrouped_items: list[dict[str, Any]] = field(default_factory=list)
    renamed_or_merged_items: list[dict[str, Any]] = field(default_factory=list)
    candidate_only_items: list[dict[str, Any]] = field(default_factory=list)
    source_exceptions: list[dict[str, Any]] = field(default_factory=list)
    grouping_integrity: dict[str, Any] = field(default_factory=dict)
    promotion_review: dict[str, Any] = field(default_factory=dict)
    review_queue: list[dict[str, Any]] = field(default_factory=list)
    enrichment_backlog: list[dict[str, Any]] = field(default_factory=list)
    mapping: CandidateMapping | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_version": self.catalog_version,
            "generated_at": self.generated_at,
            "collection_id": self.collection_id,
            "live_counts": self.live_counts,
            "alias_digest_merge_count": self.alias_digest_merge_count,
            "alias_digest_merges": self.alias_digest_merges,
            "collection_stats": self.collection_stats,
            "legacy_comparison": self.legacy_comparison,
            "legacy_model_evidence": self.legacy_model_evidence,
            "classified_items": self.classified_items,
            "live_absence_count": len(self.live_absences),
            "live_absences": self.live_absences,
            "regrouped_count": len(self.regrouped_items),
            "regrouped_items_sample": self.regrouped_items[:25],
            "renamed_or_merged_count": len(self.renamed_or_merged_items),
            "renamed_or_merged_items_sample": self.renamed_or_merged_items[:25],
            "candidate_only_count": len(self.candidate_only_items),
            "candidate_only_items": self.candidate_only_items,
            "source_exception_count": len(self.source_exceptions),
            "source_exceptions": self.source_exceptions,
            "source_exception_retention_policy": SOURCE_EXCEPTION_RETENTION_POLICY,
            "grouping_integrity": self.grouping_integrity,
            "promotion_review": self.promotion_review,
            "review_queue_count": len(self.review_queue),
            "review_queue": self.review_queue,
            "enrichment_backlog_count": len(self.enrichment_backlog),
            "enrichment_backlog": self.enrichment_backlog,
            "mapping": self.mapping.to_dict() if self.mapping else None,
        }


def _resolve_manifest_path(manifest_path: Path | None) -> Path:
    if manifest_path is not None:
        return manifest_path

    candidate_manifests = sorted(MANIFESTS_DIR.glob("candidate-*.json"))
    if candidate_manifests:
        return candidate_manifests[-1]

    latest_path = RAW_DIR / "latest-manifest.json"
    if latest_path.exists():
        latest = load_json(latest_path)
        path = Path(latest["path"])
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.exists() and len(latest.get("entries", [])) > 1:
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


def _source_indexed_family_count(
    manifest: CollectionManifest,
    *,
    source_exception_families: set[str],
) -> int:
    index_slugs = set(_index_family_slugs(manifest))
    return len(index_slugs | source_exception_families)


def build_candidate_mapping(
    *,
    candidate_dir: Path = CANDIDATE_NORMALIZED_DIR,
    manifest: CollectionManifest | None = None,
    source_exception_count: int = 0,
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

    parseable_source_families = len(families)
    collected_snapshots = 0
    source_exception_slugs = known_source_exception_slugs()
    source_indexed_families = parseable_source_families + source_exception_count
    if manifest is not None:
        collected_snapshots = len(manifest.entries)
        source_indexed_families = _source_indexed_family_count(
            manifest,
            source_exception_families=source_exception_slugs,
        )

    tag_count = len(tags)
    return CandidateMapping(
        collection_id=manifest.collection_id if manifest else None,
        catalog_version=meta.get("catalog_version", "unknown"),
        generated_at=meta.get("generated_at", "unknown"),
        source_indexed_families=source_indexed_families,
        parseable_source_families=parseable_source_families,
        source_exception_families=source_exception_count,
        collected_snapshots=collected_snapshots,
        normalized_family_count=parseable_source_families,
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


def _known_static_parse_failures() -> list[dict[str, Any]]:
    return list(snapshot_policy().get("known_static_parse_failures", []))


def _merge_known_source_exceptions(
    manifest: CollectionManifest,
    *,
    normalized_family_ids: set[str],
    discovered: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(discovered)
    seen = {item["family_slug"] for item in merged}
    for entry in _known_static_parse_failures():
        slug = entry.get("family_slug")
        if not isinstance(slug, str) or not slug or slug in normalized_family_ids:
            continue
        if slug in seen:
            continue
        evidence: dict[str, Any] = {"configured_known_failure": True}
        if entry.get("notes"):
            evidence["notes"] = entry["notes"]
        family_entry = manifest.find_entry("family", family_slug=slug)
        tags_entry = manifest.find_entry("family_tags", family_slug=slug)
        if family_entry and tags_entry:
            try:
                _parse_family_tags_from_manifest(manifest, slug)
                evidence["unexpected_parse_success"] = True
            except ParseError as exc:
                evidence["error"] = str(exc)
        else:
            evidence["snapshots_collected"] = False
            evidence["in_live_index"] = slug in set(_index_family_slugs(manifest))
        merged.append(
            {
                "family_slug": slug,
                "disposition": "source_unparseable",
                "reason": entry.get("reason", "static_html_parse_failure"),
                "evidence": evidence,
                "recommended_disposition": "parser_update_or_manual_review",
            }
        )
        seen.add(slug)
    merged.sort(key=lambda item: item["family_slug"])
    return merged


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


def _classify_shared_tag(
    tag_id: str,
    *,
    legacy_model_id: str,
    candidate_model_id: str | None,
) -> dict[str, Any]:
    if candidate_model_id and candidate_model_id != legacy_model_id:
        return {
            "ollama_identifier": tag_id,
            "disposition": "regrouped",
            "evidence": {
                "legacy_model_id": legacy_model_id,
                "candidate_model_id": candidate_model_id,
            },
            "recommended_disposition": "accept_candidate_grouping",
        }
    return {
        "ollama_identifier": tag_id,
        "disposition": "renamed_aliased_digest_merged",
        "evidence": {"note": "shared tag with unchanged candidate presence"},
        "recommended_disposition": "no_action",
    }


def _build_legacy_model_evidence(
    *,
    legacy_models: dict[str, dict[str, Any]],
    legacy_tags: list[dict[str, Any]],
    candidate_tag_ids: set[str],
    candidate_model_ids: set[str],
    source_exception_families: set[str],
) -> dict[str, Any]:
    legacy_model_ids = set(legacy_models)
    legacy_only_models = sorted(legacy_model_ids - candidate_model_ids)
    digest_regrouped: list[str] = []
    source_exception_models: list[str] = []
    unexplained: list[str] = []

    for model_id in legacy_only_models:
        model_tags = [
            tag["ollama_identifier"]
            for tag in legacy_tags
            if tag.get("model_id") == model_id
        ]
        family_id = legacy_models[model_id].get("family_id")
        if family_id in source_exception_families:
            source_exception_models.append(model_id)
        elif model_tags and all(tag_id in candidate_tag_ids for tag_id in model_tags):
            digest_regrouped.append(model_id)
        else:
            unexplained.append(model_id)

    return {
        "legacy_only_model_count": len(legacy_only_models),
        "explained_by_digest_regrouping": len(digest_regrouped),
        "explained_by_source_exception": len(source_exception_models),
        "unexplained_model_count": len(unexplained),
        "digest_regrouped_model_ids_sample": digest_regrouped[:25],
        "source_exception_model_ids": source_exception_models,
        "unexplained_model_ids": unexplained,
    }


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


def _manifest_collection_stats(
    manifest: CollectionManifest,
    *,
    source_exception_families: set[str],
    normalized_family_count: int,
) -> dict[str, Any]:
    collected_families = sorted(
        {
            entry.family_slug
            for entry in manifest.entries
            if entry.snapshot_kind == "family" and entry.family_slug
        }
    )
    index_family_count = len(_index_family_slugs(manifest))
    return {
        "snapshot_count": len(manifest.entries),
        "collected_family_count": len(collected_families),
        "index_family_count": index_family_count,
        "source_indexed_families": _source_indexed_family_count(
            manifest,
            source_exception_families=source_exception_families,
        ),
        "parseable_source_families": normalized_family_count,
        "source_exception_families": len(source_exception_families),
    }


def _classify_candidate_only_tag(tag_id: str) -> dict[str, Any]:
    family_slug = tag_id.split(":", 1)[0]
    return {
        "ollama_identifier": tag_id,
        "family_slug": family_slug,
        "disposition": "candidate_only_new_live",
        "evidence": {"present_in_candidate_catalog": True, "absent_from_legacy_canonical": True},
        "recommended_disposition": "accept_as_new_live_tag",
    }


def _verify_grouping_integrity(
    tags: list[dict[str, Any]],
    alias_digest_merges: list[dict[str, Any]],
) -> dict[str, Any]:
    tag_ids = {tag["ollama_identifier"] for tag in tags}
    alias_targets = [tag.get("alias_target") for tag in tags if tag.get("alias_target")]
    missing_alias_targets = sorted({target for target in alias_targets if target not in tag_ids})
    deployment_tags = [tag for tag in tags if not tag.get("alias_target")]
    merge_pairs = {
        (item["alias_tag"], item["canonical_tag"])
        for item in alias_digest_merges
        if item.get("alias_tag") and item.get("canonical_tag")
    }
    preserved_variants = len(deployment_tags)
    return {
        "valid": not missing_alias_targets,
        "total_tags": len(tags),
        "deployment_variant_tags": preserved_variants,
        "alias_target_tags": len(alias_targets),
        "alias_digest_merge_pairs": len(merge_pairs),
        "missing_alias_targets": missing_alias_targets,
        "note": (
            "Alias and digest merges collapse model grouping only; each non-alias tag "
            "remains a distinct deployment variant."
        ),
    }


def _build_human_review_queue(
    *,
    source_exceptions: list[dict[str, Any]],
    ambiguous_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in source_exceptions:
        queue.append(
            {
                "kind": "source_exception",
                "id": item["family_slug"],
                "disposition": item["disposition"],
                "reason": item["reason"],
                "evidence": item.get("evidence", {}),
                "recommended_disposition": item.get("recommended_disposition"),
            }
        )
    for item in ambiguous_items:
        queue.append(
            {
                "kind": "legacy_tag",
                "id": item["ollama_identifier"],
                "disposition": item["disposition"],
                "evidence": item.get("evidence", {}),
                "recommended_disposition": item.get("recommended_disposition"),
            }
        )
    return queue


def _build_enrichment_backlog(candidate_dir: Path) -> list[dict[str, Any]]:
    families = load_json(candidate_dir / "families.json")
    models = load_json(candidate_dir / "models.json")
    backlog: list[dict[str, Any]] = []

    publisher_review_families = sorted(
        family["id"] for family in families if family.get("review_reasons")
    )
    if publisher_review_families:
        backlog.append(
            {
                "kind": "publisher_mapping",
                "id": "publisher_mapping_batch",
                "disposition": "unverified_editorial_enrichment",
                "blocking": False,
                "evidence": {
                    "family_count": len(publisher_review_families),
                    "sample_families": publisher_review_families[:10],
                },
                "recommended_disposition": (
                    "Review config/publishers.yaml overrides when convenient; "
                    "does not block promotion of structurally valid live inventory"
                ),
            }
        )

    unverified_models = sorted(
        model["id"]
        for model in models
        if model.get("review_reasons")
        and model.get("validation_status") == "valid"
    )
    if unverified_models:
        backlog.append(
            {
                "kind": "publisher_model_enrichment",
                "id": "publisher_model_enrichment_batch",
                "disposition": "unverified_editorial_enrichment",
                "blocking": False,
                "evidence": {
                    "model_count": len(unverified_models),
                    "sample_models": unverified_models[:10],
                },
                "recommended_disposition": (
                    "Publisher metadata remains visible for later enrichment"
                ),
            }
        )
    return backlog


def _build_promotion_review(
    *,
    candidate_dir: Path,
    legacy_dir: Path,
    report: ReconciliationReport,
) -> dict[str, Any]:
    from eight_ball.recreate.promote import _promotion_gates

    gates, blockers = _promotion_gates(
        candidate_dir=candidate_dir,
        target_dir=legacy_dir,
        allow_review_items=False,
        allow_removals=False,
    )
    interpretations: list[dict[str, Any]] = []
    for blocker in blockers:
        if "would remove canonical records" in blocker:
            interpretations.append(
                {
                    "blocker": blocker,
                    "interpretation": (
                        "Legacy grouping delta after excluding source exceptions and "
                        "digest regrouping. "
                        f"{report.legacy_model_evidence.get('explained_by_digest_regrouping', 0)} "
                        "legacy model IDs are explained by digest regrouping; "
                        f"{report.legacy_model_evidence.get('explained_by_source_exception', 0)} "
                        "are source exceptions; "
                        f"{len(report.live_absences)} tags are true live absences."
                    ),
                    "recommended_disposition": (
                        "Review candidate-reconciliation.md, then acknowledge with "
                        "--allow-removals only if blocking removals remain."
                    ),
                }
            )
        elif "unresolved structural review records" in blocker:
            interpretations.append(
                {
                    "blocker": blocker,
                    "interpretation": "Unresolved structural data-quality review flags.",
                    "recommended_disposition": "Resolve before promotion.",
                }
            )
        else:
            interpretations.append(
                {
                    "blocker": blocker,
                    "interpretation": "Unresolved promotion gate.",
                    "recommended_disposition": "Resolve before promotion.",
                }
            )

    enrichment_backlog = report.enrichment_backlog
    eligible = not blockers
    decision_summary = (
        "Promotion is eligible based on structural data quality."
        if eligible
        else "Promotion remains blocked by structural gates."
    )
    decision_summary += (
        f" The candidate catalog reflects current live Ollama metadata size "
        f"({report.live_counts.get('normalized_candidate_families', 0)} families, "
        f"{report.live_counts.get('candidate_canonical_models', 0)} models, "
        f"{report.live_counts.get('tags', 0)} tags)."
    )
    if enrichment_backlog:
        decision_summary += (
            f" {len(enrichment_backlog)} publisher-enrichment backlog item(s) "
            "are documented and non-blocking."
        )

    return {
        "eligible": eligible,
        "dry_run_required": True,
        "blockers": blockers,
        "blocker_interpretations": interpretations,
        "gates": gates,
        "enrichment_backlog_count": len(enrichment_backlog),
        "decision_summary": decision_summary,
    }


def _bucket_classified_items(
    classified_legacy_tags: list[dict[str, Any]],
    candidate_only_items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "live_absent": [],
        "renamed_aliased_digest_merged": [],
        "regrouped": [],
        "source_unparseable": [],
        "ambiguous_review": [],
        "candidate_only_new_live": [],
    }
    for item in classified_legacy_tags:
        buckets.setdefault(item["disposition"], []).append(item)
    buckets["candidate_only_new_live"] = candidate_only_items
    return buckets


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

    families = load_json(candidate_dir / "families.json")
    normalized_family_ids = {family["id"] for family in families}
    tags = load_json(candidate_dir / "tags.json")
    candidate_tags_by_id = {tag["ollama_identifier"]: tag for tag in tags}
    candidate_tag_ids = set(candidate_tags_by_id)

    source_exceptions = _merge_known_source_exceptions(
        manifest,
        normalized_family_ids=normalized_family_ids,
        discovered=discover_source_exceptions(
            manifest,
            normalized_family_ids=normalized_family_ids,
        ),
    )
    source_exception_families = {item["family_slug"] for item in source_exceptions}
    mapping = build_candidate_mapping(
        candidate_dir=candidate_dir,
        manifest=manifest,
        source_exception_count=len(source_exceptions),
    )
    unparseable_families = source_exception_families
    index_families = set(_index_family_slugs(manifest)) | source_exception_families

    alias_digest_merges = _collect_alias_digest_merges(tags, manifest)
    candidate_digest_to_tags = _candidate_digest_index(manifest, normalized_family_ids)
    legacy_digests = _legacy_tag_digests()

    legacy_tags = load_json(legacy_dir / "tags.json")
    legacy_models = {model["id"]: model for model in load_json(legacy_dir / "models.json")}
    legacy_tag_ids = {tag["ollama_identifier"] for tag in legacy_tags}
    legacy_only_tags = sorted(legacy_tag_ids - candidate_tag_ids)
    shared_tag_ids = sorted(legacy_tag_ids & candidate_tag_ids)

    disposition_counts: dict[str, int] = {
        "live_absent": 0,
        "renamed_aliased_digest_merged": 0,
        "regrouped": 0,
        "source_unparseable": 0,
        "ambiguous_review": 0,
    }
    classified_legacy_tags: list[dict[str, Any]] = []
    live_absences: list[dict[str, Any]] = []
    regrouped_items: list[dict[str, Any]] = []
    renamed_or_merged_items: list[dict[str, Any]] = []
    ambiguous_items: list[dict[str, Any]] = []

    def _record_classification(classification: dict[str, Any]) -> None:
        classified_legacy_tags.append(classification)
        disposition = classification["disposition"]
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if disposition == "live_absent":
            live_absences.append(classification)
        elif disposition == "regrouped":
            regrouped_items.append(classification)
        elif disposition == "renamed_aliased_digest_merged":
            renamed_or_merged_items.append(classification)
        elif disposition == "ambiguous_review":
            ambiguous_items.append(classification)

    for tag_id in shared_tag_ids:
        legacy_tag = next(tag for tag in legacy_tags if tag["ollama_identifier"] == tag_id)
        legacy_model_id = legacy_tag.get("model_id", tag_id.split(":", 1)[0])
        candidate_model_id = candidate_tags_by_id[tag_id].get("model_id")
        _record_classification(
            _classify_shared_tag(
                tag_id,
                legacy_model_id=legacy_model_id,
                candidate_model_id=candidate_model_id,
            )
        )

    for tag_id in legacy_only_tags:
        legacy_tag = next(tag for tag in legacy_tags if tag["ollama_identifier"] == tag_id)
        legacy_model_id = legacy_tag.get("model_id", tag_id.split(":", 1)[0])
        _record_classification(
            _classify_legacy_tag(
                tag_id,
                candidate_tag_ids=candidate_tag_ids,
                candidate_tags_by_id=candidate_tags_by_id,
                candidate_digest_to_tags=candidate_digest_to_tags,
                legacy_digest=legacy_digests.get(tag_id),
                index_families=index_families,
                unparseable_families=unparseable_families,
                legacy_model_id=legacy_model_id,
            )
        )

    candidate_only_tags = sorted(candidate_tag_ids - legacy_tag_ids)
    candidate_only_items = [_classify_candidate_only_tag(tag_id) for tag_id in candidate_only_tags]
    candidate_model_ids = {model["id"] for model in load_json(candidate_dir / "models.json")}
    legacy_model_evidence = _build_legacy_model_evidence(
        legacy_models=legacy_models,
        legacy_tags=legacy_tags,
        candidate_tag_ids=candidate_tag_ids,
        candidate_model_ids=candidate_model_ids,
        source_exception_families=source_exception_families,
    )

    meta = load_json(candidate_dir / "catalog-meta.json")
    collection_stats = _manifest_collection_stats(
        manifest,
        source_exception_families=source_exception_families,
        normalized_family_count=mapping.normalized_family_count,
    )
    live_counts = {
        "source_indexed_families": mapping.source_indexed_families,
        "parseable_source_families": mapping.parseable_source_families,
        "source_exception_families": mapping.source_exception_families,
        "collected_snapshots": mapping.collected_snapshots,
        "normalized_candidate_families": mapping.normalized_family_count,
        "candidate_canonical_models": mapping.model_count,
        "tags": mapping.tag_count,
        "deployment_combinations": mapping.deployment_count,
    }
    grouping_integrity = _verify_grouping_integrity(tags, alias_digest_merges)
    classified_items = _bucket_classified_items(classified_legacy_tags, candidate_only_items)
    review_queue = _build_human_review_queue(
        source_exceptions=source_exceptions,
        ambiguous_items=ambiguous_items,
    )
    enrichment_backlog = _build_enrichment_backlog(candidate_dir)
    report = ReconciliationReport(
        catalog_version=meta.get("catalog_version", mapping.catalog_version),
        generated_at=meta.get("generated_at", mapping.generated_at),
        collection_id=manifest.collection_id,
        live_counts=live_counts,
        alias_digest_merge_count=len(alias_digest_merges),
        alias_digest_merges=alias_digest_merges,
        collection_stats=collection_stats,
        legacy_comparison={
            "legacy_tag_count": len(legacy_tags),
            "candidate_tag_count": len(tags),
            "shared_tags": len(shared_tag_ids),
            "legacy_only_tags": len(legacy_only_tags),
            "candidate_only_tags": len(candidate_only_items),
            "disposition_counts": disposition_counts,
            "note": (
                "Disposition counts include shared tags with digest regrouping and "
                "legacy-only tags. Legacy-only model IDs are explained in "
                "legacy_model_evidence."
            ),
        },
        legacy_model_evidence=legacy_model_evidence,
        classified_items=classified_items,
        live_absences=live_absences,
        regrouped_items=regrouped_items,
        renamed_or_merged_items=renamed_or_merged_items,
        candidate_only_items=candidate_only_items,
        source_exceptions=source_exceptions,
        grouping_integrity=grouping_integrity,
        review_queue=review_queue,
        enrichment_backlog=enrichment_backlog,
        mapping=mapping,
    )
    report.promotion_review = _build_promotion_review(
        candidate_dir=candidate_dir,
        legacy_dir=legacy_dir,
        report=report,
    )
    return report


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
    promotion_path = output_dir / "candidate-promotion-review.json"

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
    write_json(promotion_path, report.promotion_review)
    if report.mapping is not None:
        write_json(mapping_path, report.mapping.to_dict())

    stats = report.collection_stats
    counts = report.live_counts
    lines = [
        "# Candidate Catalog Reconciliation",
        "",
        (
            "Decision-ready summary for Phase 3E promotion review. The July legacy canonical "
            "catalog is continuity baseline only; live candidate counts below are authoritative."
        ),
        "",
        f"- Catalog version: `{report.catalog_version}`",
        f"- Generated at: {report.generated_at}",
        f"- Collection ID: `{report.collection_id}`",
        "",
        "## Live inventory (authoritative)",
        f"- Source-indexed families: **{counts.get('source_indexed_families', 0)}**",
        f"- Parseable source families: **{counts.get('parseable_source_families', 0)}**",
        f"- Source-exception families: **{counts.get('source_exception_families', 0)}**",
        f"- Collected snapshots: **{counts.get('collected_snapshots', 0)}**",
        f"- Families with snapshots: **{stats.get('collected_family_count', 0)}**",
        f"- Normalized candidate families: **{counts.get('normalized_candidate_families', 0)}**",
        f"- Candidate canonical models: **{counts.get('candidate_canonical_models', 0)}**",
        f"- Tags: **{counts.get('tags', 0)}**",
        f"- Deployment combinations: **{counts.get('deployment_combinations', 0)}**",
        f"- Alias/digest merges: **{report.alias_digest_merge_count}**",
        "",
        "## Grouping integrity",
        f"- Valid: **{report.grouping_integrity.get('valid', False)}**",
        f"- Deployment variant tags (non-alias): **{report.grouping_integrity.get('deployment_variant_tags', 0)}**",
        f"- Alias-target tags: **{report.grouping_integrity.get('alias_target_tags', 0)}**",
        f"- {report.grouping_integrity.get('note', '')}",
        "",
        "## Legacy delta classification",
    ]
    legacy = report.legacy_comparison
    model_evidence = report.legacy_model_evidence
    lines.extend(
        [
            f"- Shared tags: {legacy.get('shared_tags', 0)}",
            f"- Candidate-only tags (new live): {legacy.get('candidate_only_tags', 0)}",
            f"- Legacy-only tags: {legacy.get('legacy_only_tags', 0)}",
            (
                "- Legacy-only model IDs: "
                f"{model_evidence.get('legacy_only_model_count', 0)} "
                f"({model_evidence.get('explained_by_digest_regrouping', 0)} digest regrouping, "
                f"{model_evidence.get('explained_by_source_exception', 0)} source exceptions)"
            ),
            "",
            "### Disposition counts",
        ]
    )
    for disposition, count in sorted(legacy.get("disposition_counts", {}).items()):
        lines.append(f"- `{disposition}`: {count}")
    lines.extend(
        [
            "",
            f"> {legacy.get('note', '')}",
            "",
            "## Legacy model evidence",
            f"- Digest regrouping: **{model_evidence.get('explained_by_digest_regrouping', 0)}**",
            f"- Source exceptions: **{model_evidence.get('explained_by_source_exception', 0)}**",
            f"- Unexplained: **{model_evidence.get('unexplained_model_count', 0)}**",
            "",
            "## True current-live absences",
            f"- Count: **{len(report.live_absences)}**",
        ]
    )
    for item in report.live_absences[:10]:
        lines.append(f"- `{item['ollama_identifier']}`")
    lines.extend(
        [
            "",
            "## Regrouped or renamed (not removals)",
            f"- Regrouped tag records: **{len(report.regrouped_items)}**",
            f"- Renamed/alias/digest-merged: **{len(report.renamed_or_merged_items)}**",
            f"- Candidate-only new live tags: **{len(report.candidate_only_items)}**",
            "",
            "## Source exceptions",
            f"- Count: **{len(report.source_exceptions)}**",
            f"- Retention policy: {SOURCE_EXCEPTION_RETENTION_POLICY}",
        ]
    )
    for item in report.source_exceptions:
        lines.append(f"- `{item['family_slug']}`: {item['reason']}")
    lines.extend(
        [
            "",
            "## Promotion decision",
            f"- Eligible: **{report.promotion_review.get('eligible', False)}**",
            f"- {report.promotion_review.get('decision_summary', '')}",
            "",
            "### Blocker interpretations",
        ]
    )
    for item in report.promotion_review.get("blocker_interpretations", []):
        lines.append(f"- {item['interpretation']}")
        lines.append(f"  - Recommended: {item['recommended_disposition']}")
    lines.extend(
        [
            "",
            "## Structural review queue",
            f"- Count: **{len(report.review_queue)}**",
        ]
    )
    for item in report.review_queue:
        lines.append(
            f"- {item['kind']} `{item.get('id', '')}`: {item.get('recommended_disposition', '')}"
        )
    lines.extend(
        [
            "",
            "## Publisher enrichment backlog (non-blocking)",
            f"- Count: **{len(report.enrichment_backlog)}**",
        ]
    )
    for item in report.enrichment_backlog:
        lines.append(
            f"- {item['kind']} `{item.get('id', '')}`: {item.get('recommended_disposition', '')}"
        )
    lines.extend(
        [
            "",
            "Artifacts:",
            f"- `{json_path}`",
            f"- `{promotion_path}`",
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
        "promotion_review": promotion_path,
    }

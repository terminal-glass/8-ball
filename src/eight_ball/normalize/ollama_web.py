from __future__ import annotations

from pathlib import Path
from typing import Any

from eight_ball.collect.manifest import (
    CollectionManifest,
    ManifestVerificationError,
    load_manifest,
    read_verified_snapshot,
)
from eight_ball.collect.parse_ollama import (
    ParsedFamilyPage,
    ParsedTag,
    parse_family_page,
    parse_family_tags_page,
)
from eight_ball.config import capabilities_config, write_json
from eight_ball.normalize.capabilities import (
    capabilities_from_tokens,
    family_tokens_from_badges,
    refine_capabilities,
    tag_tokens_from_input_capabilities,
)
from eight_ball.normalize.provenance_fields import (
    build_family_provenance,
    build_tag_provenance,
)
from eight_ball.normalize.publishers import (
    build_publisher_records,
    default_catalog_source_id,
    infer_publisher_id,
    publisher_mapping_needs_review,
)
from eight_ball.paths import CANDIDATE_NORMALIZED_DIR


def _tag_id(ollama_identifier: str) -> str:
    return ollama_identifier.replace(":", "__")


def _infer_model_id(family_slug: str, tag: ParsedTag) -> str:
    if tag.parameter_label:
        return f"{family_slug}-{tag.parameter_label}"
    return family_slug


def _canonical_model_id(family_slug: str, group: list[ParsedTag]) -> str:
    with_params = [tag for tag in group if tag.parameter_label]
    if with_params:
        return _infer_model_id(family_slug, with_params[0])
    return family_slug


def _resolve_model_id_map(family_slug: str, tags: list[ParsedTag]) -> dict[str, str]:
    model_ids = {tag.ollama_identifier: _infer_model_id(family_slug, tag) for tag in tags}
    by_digest: dict[str, list[ParsedTag]] = {}
    for tag in tags:
        if tag.digest:
            by_digest.setdefault(tag.digest, []).append(tag)

    for digest_tags in by_digest.values():
        canonical = _canonical_model_id(family_slug, digest_tags)
        for tag in digest_tags:
            model_ids[tag.ollama_identifier] = canonical

    return model_ids


def _actionable_review_reasons(
    *,
    publisher_id: str,
    publisher_inference: Any,
    description: str | None,
) -> list[str]:
    reasons: list[str] = []
    if publisher_id == "unknown":
        reasons.append("unknown_publisher")
    if publisher_mapping_needs_review(publisher_inference):
        reasons.append("publisher_mapping_needs_review")
    if not description:
        reasons.append("missing_family_description")
    return reasons


def _unknown_field_flags(capability_map: dict[str, str]) -> list[str]:
    if any(value == "unknown" for value in capability_map.values()):
        return ["unknown_capabilities"]
    return []


def _validation_status(actionable_reasons: list[str]) -> str:
    if actionable_reasons:
        return "needs_review"
    return "valid"


def build_candidate_catalog(
    *,
    families: list[ParsedFamilyPage],
    tags_by_family: dict[str, list[ParsedTag]],
    retrieved_at: str,
    retrieved_at_by_family: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    catalog_source_id = default_catalog_source_id()
    normalized_families: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    model_ids_seen: set[str] = set()
    publisher_ids: set[str] = set()
    family_times = retrieved_at_by_family or {}

    for family in families:
        slug = family.slug
        family_tags = tags_by_family.get(slug, [])
        times = family_times.get(slug, {})
        family_retrieved_at = times.get("family", retrieved_at)
        tags_retrieved_at = times.get("tags", retrieved_at)
        family_source_url = family.source_url or f"https://ollama.com/library/{slug}"

        publisher_inference = infer_publisher_id(
            family_slug=slug,
            display_name=family.display_name,
            description=family.description,
        )
        publisher_ids.add(publisher_inference.publisher_id)

        badge_tokens = family_tokens_from_badges(family.capability_badges)
        family_caps = capabilities_from_tokens(badge_tokens)
        actionable_reasons = _actionable_review_reasons(
            publisher_id=publisher_inference.publisher_id,
            publisher_inference=publisher_inference,
            description=family.description,
        )
        unknown_flags = _unknown_field_flags(family_caps)

        normalized_families.append(
            {
                "id": slug,
                "catalog_source_id": catalog_source_id,
                "publisher_id": publisher_inference.publisher_id,
                "name": family.display_name or slug,
                "aliases": [],
                "description": family.description,
                "primary_capabilities": family_caps,
                "ollama_url": family_source_url,
                "source_url": family_source_url,
                "retrieved_at": family_retrieved_at,
                "provenance": build_family_provenance(
                    publisher_inference=publisher_inference,
                    catalog_source_id=catalog_source_id,
                    source_url=family_source_url,
                    retrieved_at=family_retrieved_at,
                ),
                "review_reasons": actionable_reasons,
                "unknown_field_flags": unknown_flags,
            }
        )

        model_id_map = _resolve_model_id_map(slug, family_tags)
        model_ids_for_family = sorted(set(model_id_map.values()) or {slug})
        for model_id in model_ids_for_family:
            if model_id in model_ids_seen:
                continue
            model_ids_seen.add(model_id)
            model_tags = [
                tag
                for tag in family_tags
                if model_id_map[tag.ollama_identifier] == model_id
            ]
            model_tag_tokens = tag_tokens_from_input_capabilities(
                [item for tag in model_tags for item in tag.input_capabilities]
            )
            model_caps = refine_capabilities(family_caps, model_tag_tokens)
            model_unknown_flags = _unknown_field_flags(model_caps)
            models.append(
                {
                    "id": model_id,
                    "ollama_name": model_id,
                    "display_name": family.display_name or slug,
                    "catalog_source_id": catalog_source_id,
                    "publisher_id": publisher_inference.publisher_id,
                    "family_id": slug,
                    "description": family.description,
                    "availability": _model_availability(model_tags, is_cloud_family=family.is_cloud_family),
                    "capabilities": model_caps,
                    "default_tag": _default_tag(model_tags),
                    "source_url": family_source_url,
                    "retrieved_at": family_retrieved_at,
                    "validation_status": _validation_status(actionable_reasons),
                    "review_reasons": actionable_reasons,
                    "unknown_field_flags": sorted(set(unknown_flags + model_unknown_flags)),
                    "provenance": build_family_provenance(
                        publisher_inference=publisher_inference,
                        catalog_source_id=catalog_source_id,
                        source_url=family_source_url,
                        retrieved_at=family_retrieved_at,
                    ),
                }
            )

        tags_source_url = f"https://ollama.com/library/{slug}/tags"
        for tag in family_tags:
            model_id = model_id_map[tag.ollama_identifier]
            tag_tokens = tag_tokens_from_input_capabilities(tag.input_capabilities)
            tag_caps = refine_capabilities(family_caps, tag_tokens)
            tag_record = {
                "id": _tag_id(tag.ollama_identifier),
                "ollama_identifier": tag.ollama_identifier,
                "model_id": model_id,
                "tag": tag.tag_suffix,
                "parameter_count": tag.parameter_count,
                "parameter_unit": tag.parameter_label,
                "quantization": tag.quantization,
                "architecture": None,
                "context_window_tokens": tag.context_window_tokens,
                "download_size_bytes": tag.download_size_bytes,
                "download_size_text": tag.download_size_text,
                "installed_storage_bytes_estimated": None,
                "availability": _tag_availability(tag, is_cloud_family=family.is_cloud_family),
                "capabilities": tag_caps,
                "pull_command": f"ollama pull {tag.ollama_identifier}",
                "run_command": f"ollama run {tag.ollama_identifier}",
                "alias_target": tag.alias_target,
                "source_url": tags_source_url,
                "retrieved_at": tags_retrieved_at,
            }
            tag_record["provenance"] = build_tag_provenance(
                tag=tag_record,
                parsed_tag=tag,
                source_url=tags_source_url,
                retrieved_at=tags_retrieved_at,
                capabilities=tag_caps,
            )
            tags.append(tag_record)

    return {
        "catalog_version": retrieved_at[:10].replace("-", "."),
        "generated_at": retrieved_at,
        "catalog_source_id": catalog_source_id,
        "publishers": build_publisher_records(publisher_ids=publisher_ids),
        "families": normalized_families,
        "models": models,
        "tags": tags,
        "capabilities": capabilities_config().get("capabilities", []),
    }


def _default_tag(model_tags: list[ParsedTag]) -> str | None:
    for tag in model_tags:
        if tag.is_latest:
            return tag.ollama_identifier
    for tag in model_tags:
        if tag.tag_suffix in {"latest", "8b", "70b"}:
            return tag.ollama_identifier
    return model_tags[0].ollama_identifier if model_tags else None


def _tag_availability(tag: ParsedTag, *, is_cloud_family: bool = False) -> str:
    if tag.download_size_bytes is None and is_cloud_family:
        return "cloud_only"
    if tag.download_size_bytes is None:
        return "unknown"
    if is_cloud_family:
        return "both"
    return "local"


def _model_availability(model_tags: list[ParsedTag], *, is_cloud_family: bool = False) -> str:
    values = {_tag_availability(tag, is_cloud_family=is_cloud_family) for tag in model_tags}
    if values <= {"cloud_only"}:
        return "cloud"
    if values <= {"cloud_only", "unknown"}:
        return "cloud"
    if "cloud_only" in values or "both" in values:
        if "local" in values or "both" in values:
            return "both"
        return "cloud"
    if values == {"unknown"}:
        return "unknown"
    return "local"


def write_candidate_catalog(catalog: dict[str, Any]) -> Path:
    CANDIDATE_NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CANDIDATE_NORMALIZED_DIR / "publishers.json", catalog["publishers"])
    write_json(CANDIDATE_NORMALIZED_DIR / "families.json", catalog["families"])
    write_json(CANDIDATE_NORMALIZED_DIR / "models.json", catalog["models"])
    write_json(CANDIDATE_NORMALIZED_DIR / "tags.json", catalog["tags"])
    write_json(CANDIDATE_NORMALIZED_DIR / "capabilities.json", catalog["capabilities"])
    write_json(
        CANDIDATE_NORMALIZED_DIR / "catalog-meta.json",
        {
            "catalog_version": catalog["catalog_version"],
            "generated_at": catalog["generated_at"],
            "catalog_source_id": catalog["catalog_source_id"],
            "source": "ollama_web",
            "candidate": True,
        },
    )
    return CANDIDATE_NORMALIZED_DIR


def normalize_ollama_snapshots(
    *,
    family_slugs: list[str],
    snapshot_dir: Path,
    retrieved_at: str,
    manifest: CollectionManifest | None = None,
) -> dict[str, Any]:
    families: list[ParsedFamilyPage] = []
    tags_by_family: dict[str, list[ParsedTag]] = {}
    retrieved_at_by_family: dict[str, dict[str, str]] = {}

    for slug in family_slugs:
        family_html: str
        tags_html: str
        family_retrieved = retrieved_at
        tags_retrieved = retrieved_at

        if manifest is not None:
            family_entry = manifest.find_entry("family", family_slug=slug)
            tags_entry = manifest.find_entry("family_tags", family_slug=slug)
            if family_entry is None or tags_entry is None:
                raise ManifestVerificationError(
                    f"Manifest missing family or tags entry for {slug}"
                )
            family_html = read_verified_snapshot(family_entry)
            tags_html = read_verified_snapshot(tags_entry)
            family_retrieved = family_entry.retrieved_at
            tags_retrieved = tags_entry.retrieved_at
        else:
            family_html = (snapshot_dir / f"{slug}.html").read_text(encoding="utf-8")
            tags_html = (snapshot_dir / f"{slug}-tags.html").read_text(encoding="utf-8")

        families.append(parse_family_page(family_html, slug))
        tags_by_family[slug] = parse_family_tags_page(tags_html, slug)
        retrieved_at_by_family[slug] = {
            "family": family_retrieved,
            "tags": tags_retrieved,
        }

    catalog = build_candidate_catalog(
        families=families,
        tags_by_family=tags_by_family,
        retrieved_at=retrieved_at,
        retrieved_at_by_family=retrieved_at_by_family,
    )
    write_candidate_catalog(catalog)
    return catalog


def normalize_ollama_from_manifest(
    manifest_path: Path,
    *,
    family_slugs: list[str] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    slugs = family_slugs or sorted(
        {
            entry.family_slug
            for entry in manifest.entries
            if entry.family_slug and entry.snapshot_kind == "family"
        }
    )
    if not slugs:
        raise ManifestVerificationError("No family slugs found in manifest")
    retrieved_at = max(entry.retrieved_at for entry in manifest.entries)
    return normalize_ollama_snapshots(
        family_slugs=slugs,
        snapshot_dir=Path("."),
        retrieved_at=retrieved_at,
        manifest=manifest,
    )

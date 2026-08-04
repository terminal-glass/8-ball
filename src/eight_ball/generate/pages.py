from __future__ import annotations

import hashlib
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eight_ball.agents_csv.enrichment import (
    compact_hardware_catalog,
    enrich_deployment_hardware,
    load_canonical_hardware,
)
from eight_ball.config import deployment_types_config, repo_relative, write_json
from eight_ball.paths import GENERATED_PAGES_DIR, GENERATED_PAGES_MODELS_DIR, NORMALIZED_DIR
from eight_ball.provenance import utc_now_iso

FAMILY_PAGE_SCHEMA = "c5.family-page.v1"
DEPLOYMENT_TYPE_PAGE_SCHEMA = "c5.deployment-type-page.v1"
MODEL_PAGE_SCHEMA = "c5.model-page.v1"
MODEL_DEPLOYMENT_PAGE_SCHEMA = "c5.model-deployment-page.v1"
INSTALL_MANIFEST_SCHEMA = "c5.install-manifest.v1"

ASSESSMENT_RANK: dict[str, int] = {
    "recommended": 0,
    "full_gpu_fit": 1,
    "cpu_only_practical": 2,
    "partial_gpu_offload": 3,
    "runs_with_constraints": 4,
    "cloud_only": 5,
    "unknown": 6,
    "insufficient_memory": 7,
}


def filesystem_slug(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[/:]+", "-", slug)
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "unknown"


def build_unique_slug_map(records: list[dict[str, Any]], *, id_key: str = "id") -> dict[str, str]:
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for record in sorted(records, key=lambda item: item[id_key]):
        record_id = record[id_key]
        base = filesystem_slug(record_id)
        slug = base
        if slug in used:
            suffix = hashlib.sha256(record_id.encode()).hexdigest()[:8]
            slug = f"{base}-{suffix}"
        used.add(slug)
        mapping[record_id] = slug
    return mapping


def _capability_summary(capabilities: dict[str, str] | None) -> dict[str, int]:
    if not capabilities:
        return {}
    return {
        key: 1
        for key, value in capabilities.items()
        if str(value).lower() in {"true", "yes", "1"}
    }


def _merge_capability_summaries(items: list[dict[str, str] | None]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        for key in _capability_summary(item):
            counts[key] += 1
    return dict(sorted(counts.items()))


def _default_tag_id(model: dict[str, Any], tags_by_id: dict[str, dict[str, Any]]) -> str | None:
    default_tag = model.get("default_tag")
    if not default_tag:
        return None
    for tag in tags_by_id.values():
        if tag.get("model_id") == model["id"] and tag.get("ollama_identifier") == default_tag:
            return tag["id"]
    return None


def _select_deployment_row(
    *,
    model: dict[str, Any],
    model_tags: list[dict[str, Any]],
    deployments_by_tag_id: dict[str, list[dict[str, Any]]],
    deployment_type: dict[str, Any],
    default_tag_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    allowed_profiles = set(deployment_type.get("hardware_profile_ids", []))
    allowed_policies = set(deployment_type.get("runtime_policy_ids", []))
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for tag in model_tags:
        for deployment in deployments_by_tag_id.get(tag["id"], []):
            if deployment["hardware_profile_id"] not in allowed_profiles:
                continue
            if deployment["runtime_policy_id"] not in allowed_policies:
                continue
            candidates.append((tag, deployment))
    if not candidates:
        return None

    def sort_key(item: tuple[dict[str, Any], dict[str, Any]]) -> tuple[Any, ...]:
        tag, deployment = item
        assessment = deployment.get("assessment", "unknown")
        storage = tag.get("installed_storage_bytes_estimated")
        storage_sort = storage if isinstance(storage, int) else 10**18
        return (
            ASSESSMENT_RANK.get(assessment, 99),
            0 if tag["id"] == default_tag_id else 1,
            storage_sort,
            tag["id"],
            deployment["hardware_profile_id"],
            deployment["runtime_policy_id"],
        )

    return min(candidates, key=sort_key)


def _deployment_helper_path(model_slug: str, deployment_type_id: str) -> str:
    return repo_relative(
        GENERATED_PAGES_MODELS_DIR / model_slug / deployment_type_id / "info.json"
    )


def _build_model_deployment_info(
    *,
    model: dict[str, Any],
    family: dict[str, Any],
    model_slug: str,
    family_slug: str,
    tag: dict[str, Any],
    deployment: dict[str, Any],
    deployment_type: dict[str, Any],
    hardware_enrichment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deployment_type_id = deployment_type["deployment_type_id"]
    payload = {
        "schema_version": MODEL_DEPLOYMENT_PAGE_SCHEMA,
        "model_id": model["id"],
        "model_slug": model_slug,
        "model_display_name": model.get("display_name") or model["id"],
        "family_id": family["id"],
        "family_slug": family_slug,
        "tag_id": tag["id"],
        "ollama_identifier": tag.get("ollama_identifier"),
        "deployment_type_id": deployment_type_id,
        "hardware_profile_id": deployment["hardware_profile_id"],
        "runtime_policy_id": deployment["runtime_policy_id"],
        "availability": tag.get("availability", "unknown"),
        "assessment": deployment.get("assessment"),
        "reason_codes": deployment.get("reason_codes", []),
        "explanation": deployment.get("explanation"),
        "download_size_bytes": tag.get("download_size_bytes"),
        "installed_storage_bytes_estimated": tag.get("installed_storage_bytes_estimated"),
        "min_system_ram_gb_estimated": deployment.get("min_system_ram_gb_estimated"),
        "recommended_system_ram_gb_estimated": deployment.get(
            "recommended_system_ram_gb_estimated"
        ),
        "min_vram_gb_estimated": deployment.get("min_vram_gb_estimated"),
        "recommended_vram_gb_estimated": deployment.get("recommended_vram_gb_estimated"),
        "cpu_suitability": deployment_type.get("cpu_suitability"),
        "gpu_suitability": deployment_type.get("gpu_suitability"),
        "disk_estimate_gb": deployment_type.get("disk_estimate_gb"),
        "pull_command": tag.get("pull_command"),
        "run_command": tag.get("run_command"),
        "source_url": tag.get("source_url"),
        "retrieved_at": tag.get("retrieved_at"),
    }
    if hardware_enrichment:
        payload["hardware_enrichment"] = hardware_enrichment
    return payload


def _build_manifest_deployment(
    *,
    model: dict[str, Any],
    model_slug: str,
    family: dict[str, Any],
    family_slug: str,
    tag: dict[str, Any],
    deployment: dict[str, Any],
    deployment_type: dict[str, Any],
    hardware_enrichment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deployment_type_id = deployment_type["deployment_type_id"]
    payload = {
        "model_id": model["id"],
        "model_slug": model_slug,
        "family_id": family["id"],
        "family_slug": family_slug,
        "deployment_type_id": deployment_type_id,
        "selected_tag_id": tag["id"],
        "selected_tag": tag.get("tag"),
        "ollama_identifier": tag.get("ollama_identifier"),
        "hardware_profile_id": deployment["hardware_profile_id"],
        "runtime_policy_id": deployment["runtime_policy_id"],
        "assessment": deployment.get("assessment"),
        "reason_codes": deployment.get("reason_codes", []),
        "explanation": deployment.get("explanation"),
        "installed_storage_bytes_estimated": tag.get("installed_storage_bytes_estimated"),
        "min_system_ram_gb_estimated": deployment.get("min_system_ram_gb_estimated"),
        "recommended_system_ram_gb_estimated": deployment.get(
            "recommended_system_ram_gb_estimated"
        ),
        "min_vram_gb_estimated": deployment.get("min_vram_gb_estimated"),
        "recommended_vram_gb_estimated": deployment.get("recommended_vram_gb_estimated"),
        "cpu_suitability": deployment_type.get("cpu_suitability"),
        "gpu_suitability": deployment_type.get("gpu_suitability"),
        "disk_estimate_gb": deployment_type.get("disk_estimate_gb"),
        "pull_command": tag.get("pull_command"),
        "run_command": tag.get("run_command"),
        "helper_path": _deployment_helper_path(model_slug, deployment_type_id),
    }
    if hardware_enrichment:
        payload["hardware_enrichment"] = hardware_enrichment
    return payload


def _family_readme(family: dict[str, Any], *, model_count: int, tag_count: int, summary: dict[str, int]) -> str:
    caps = ", ".join(f"{key} ({count})" for key, count in summary.items()) or "none recorded"
    return "\n".join(
        [
            f"# {family.get('name') or family['id']}",
            "",
            family.get("description") or "_No description available._",
            "",
            f"- Models: {model_count}",
            f"- Tags: {tag_count}",
            f"- Capabilities: {caps}",
            "",
            "Deployment coverage is summarized per model under `data/generated/pages/models/`.",
        ]
    )


def _deployment_type_readme(
    deployment_type: dict[str, Any],
    *,
    compatible_count: int,
    constrained_count: int,
    unsuitable_count: int,
    assessment_breakdown: dict[str, int],
) -> str:
    breakdown = ", ".join(f"{key}: {value}" for key, value in sorted(assessment_breakdown.items())) or "none"
    return "\n".join(
        [
            f"# Deployment Type {deployment_type['deployment_type_id']}: {deployment_type['display_name']}",
            "",
            deployment_type.get("description", "").strip(),
            "",
            "## Hardware class",
            "",
            f"- Minimum RAM (GB): {deployment_type.get('minimum_ram_gb')}",
            f"- Recommended RAM (GB): {deployment_type.get('recommended_ram_gb')}",
            f"- Minimum VRAM (GB): {deployment_type.get('minimum_vram_gb')}",
            f"- Recommended VRAM (GB): {deployment_type.get('recommended_vram_gb')}",
            f"- Disk estimate (GB): {deployment_type.get('disk_estimate_gb')}",
            f"- CPU suitability: {deployment_type.get('cpu_suitability')}",
            f"- GPU suitability: {deployment_type.get('gpu_suitability')}",
            "",
            "## Model coverage",
            "",
            f"- Compatible models: {compatible_count}",
            f"- Constrained models: {constrained_count}",
            f"- Unsuitable models: {unsuitable_count}",
            f"- Assessment breakdown: {breakdown}",
        ]
    )


def _model_readme(
    model: dict[str, Any],
    *,
    family_name: str,
    deployment_rows: dict[str, dict[str, Any] | None],
) -> str:
    lines = [
        f"# {model.get('display_name') or model['id']}",
        "",
        f"- Family: {family_name}",
        f"- Default tag: {model.get('default_tag') or 'unknown'}",
        f"- Availability: {model.get('availability', 'unknown')}",
        "",
        "## Deployment types",
        "",
        "| Type | Assessment | Tag | Status |",
        "| ---: | --- | --- | --- |",
    ]
    for deployment_type_id in sorted(deployment_rows, key=int):
        row = deployment_rows[deployment_type_id]
        if row is None:
            lines.append(f"| {deployment_type_id} | — | — | unavailable |")
            continue
        lines.append(
            f"| {deployment_type_id} | {row.get('assessment', 'unknown')} | "
            f"{row.get('ollama_identifier', 'unknown')} | available |"
        )
    return "\n".join(lines)


def _model_deployment_readme(info: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {info['model_display_name']} — Deployment Type {info['deployment_type_id']}",
            "",
            f"- Ollama identifier: `{info.get('ollama_identifier')}`",
            f"- Assessment: {info.get('assessment')}",
            f"- Hardware profile: {info.get('hardware_profile_id')}",
            f"- Runtime policy: {info.get('runtime_policy_id')}",
            "",
            "## Sizing",
            "",
            f"- Installed storage (bytes est.): {info.get('installed_storage_bytes_estimated')}",
            f"- Min system RAM (GB est.): {info.get('min_system_ram_gb_estimated')}",
            f"- Recommended system RAM (GB est.): {info.get('recommended_system_ram_gb_estimated')}",
            f"- Min VRAM (GB est.): {info.get('min_vram_gb_estimated')}",
            f"- Recommended VRAM (GB est.): {info.get('recommended_vram_gb_estimated')}",
            f"- CPU suitability: {info.get('cpu_suitability')}",
            f"- GPU suitability: {info.get('gpu_suitability')}",
            "",
            info.get("explanation") or "",
            "",
            f"- Pull: `{info.get('pull_command')}`" if info.get("pull_command") else "- Pull: unavailable",
            f"- Run: `{info.get('run_command')}`" if info.get("run_command") else "- Run: unavailable",
        ]
    )


def generate_pages(
    *,
    families: list[dict[str, Any]],
    models: list[dict[str, Any]],
    tags: list[dict[str, Any]],
    deployments: list[dict[str, Any]],
    output_root: Path = GENERATED_PAGES_DIR,
) -> dict[str, int]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    deployment_types = deployment_types_config().get("deployment_types", [])
    canonical_hardware = load_canonical_hardware()
    hardware_catalog = compact_hardware_catalog(canonical_hardware)
    import_meta_path = NORMALIZED_DIR / "hardware-import-meta.json"
    hardware_data_version = None
    if import_meta_path.is_file():
        from eight_ball.config import load_json

        hardware_data_version = load_json(import_meta_path).get("generated_at")
    families_by_id = {family["id"]: family for family in families}
    tags_by_id = {tag["id"]: tag for tag in tags}
    tags_by_model_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        tags_by_model_id[tag["model_id"]].append(tag)
    for model_tags in tags_by_model_id.values():
        model_tags.sort(key=lambda item: item["id"])

    deployments_by_tag_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for deployment in deployments:
        deployments_by_tag_id[deployment["tag_id"]].append(deployment)

    family_slug_map = build_unique_slug_map(families)
    model_slug_map = build_unique_slug_map(models)
    models_by_family_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for model in models:
        models_by_family_id[model["family_id"]].append(model)

    manifest_models: dict[str, Any] = {}
    manifest_deployment_types: dict[str, Any] = {}
    deployment_type_assessments: dict[str, Counter[str]] = {
        item["deployment_type_id"]: Counter() for item in deployment_types
    }
    deployment_type_compatible: dict[str, int] = defaultdict(int)
    deployment_type_constrained: dict[str, int] = defaultdict(int)
    deployment_type_unsuitable: dict[str, int] = defaultdict(int)

    family_pages = 0
    deployment_type_pages = 0
    model_pages = 0
    model_deployment_pages = 0
    install_manifest_deployments = 0

    families_dir = output_root / "families"
    models_dir = output_root / "models"
    deployment_types_dir = output_root / "deployment-types"
    manifest_path = output_root / "install-manifest.json"

    for family in sorted(families, key=lambda item: item["id"]):
        family_slug = family_slug_map[family["id"]]
        family_models = sorted(models_by_family_id.get(family["id"], []), key=lambda item: item["id"])
        family_tags = [tag for model in family_models for tag in tags_by_model_id.get(model["id"], [])]
        family_path = families_dir / family_slug
        family_path.mkdir(parents=True, exist_ok=True)
        capability_summary = _merge_capability_summaries(
            [model.get("capabilities") for model in family_models]
            + [tag.get("capabilities") for tag in family_tags]
        )
        family_info = {
            "schema_version": FAMILY_PAGE_SCHEMA,
            "family_id": family["id"],
            "family_slug": family_slug,
            "publisher_id": family.get("publisher_id"),
            "name": family.get("name") or family["id"],
            "description": family.get("description"),
            "source_url": family.get("source_url"),
            "retrieved_at": family.get("retrieved_at"),
            "model_count": len(family_models),
            "tag_count": len(family_tags),
            "deployment_type_ids": [item["deployment_type_id"] for item in deployment_types],
            "capability_summary": capability_summary,
        }
        write_json(family_path / "info.json", family_info)
        (family_path / "README.md").write_text(
            _family_readme(
                family,
                model_count=len(family_models),
                tag_count=len(family_tags),
                summary=capability_summary,
            ),
            encoding="utf-8",
        )
        family_pages += 1

    model_selections: dict[str, dict[str, dict[str, Any] | None]] = defaultdict(dict)

    for model in sorted(models, key=lambda item: item["id"]):
        family = families_by_id.get(model["family_id"])
        if family is None:
            continue
        model_slug = model_slug_map[model["id"]]
        family_slug = family_slug_map[family["id"]]
        model_tags = tags_by_model_id.get(model["id"], [])
        default_tag_id = _default_tag_id(model, tags_by_id)
        model_path = models_dir / model_slug
        model_path.mkdir(parents=True, exist_ok=True)
        deployment_summaries: dict[str, dict[str, Any] | None] = {}

        manifest_entry = {
            "model_id": model["id"],
            "model_slug": model_slug,
            "family_id": family["id"],
            "family_slug": family_slug,
            "default_tag_id": default_tag_id,
            "deployments": {},
        }

        for deployment_type in deployment_types:
            deployment_type_id = deployment_type["deployment_type_id"]
            selected = _select_deployment_row(
                model=model,
                model_tags=model_tags,
                deployments_by_tag_id=deployments_by_tag_id,
                deployment_type=deployment_type,
                default_tag_id=default_tag_id,
            )
            if selected is None:
                deployment_summaries[deployment_type_id] = None
                continue
            tag, deployment = selected
            hardware_enrichment = enrich_deployment_hardware(
                deployment_type_id=deployment_type_id,
                hardware_profile_id=deployment["hardware_profile_id"],
                hardware=canonical_hardware,
            )
            if hardware_data_version:
                hardware_enrichment["hardware_data_version"] = hardware_data_version
            info = _build_model_deployment_info(
                model=model,
                family=family,
                model_slug=model_slug,
                family_slug=family_slug,
                tag=tag,
                deployment=deployment,
                deployment_type=deployment_type,
                hardware_enrichment=hardware_enrichment,
            )
            manifest_deployment = _build_manifest_deployment(
                model=model,
                model_slug=model_slug,
                family=family,
                family_slug=family_slug,
                tag=tag,
                deployment=deployment,
                deployment_type=deployment_type,
                hardware_enrichment=hardware_enrichment,
            )
            deployment_summaries[deployment_type_id] = manifest_deployment
            manifest_entry["deployments"][deployment_type_id] = manifest_deployment
            install_manifest_deployments += 1

            assessment = deployment.get("assessment", "unknown")
            deployment_type_assessments[deployment_type_id][assessment] += 1
            if assessment in {"recommended", "full_gpu_fit", "cpu_only_practical"}:
                deployment_type_compatible[deployment_type_id] += 1
            elif assessment in {"partial_gpu_offload", "runs_with_constraints", "cloud_only", "unknown"}:
                deployment_type_constrained[deployment_type_id] += 1
            else:
                deployment_type_unsuitable[deployment_type_id] += 1

            deployment_dir = model_path / deployment_type_id
            deployment_dir.mkdir(parents=True, exist_ok=True)
            write_json(deployment_dir / "info.json", info)
            (deployment_dir / "README.md").write_text(_model_deployment_readme(info), encoding="utf-8")
            model_deployment_pages += 1

        model_selections[model["id"]] = deployment_summaries
        manifest_models[model["id"]] = manifest_entry

        model_json = {
            "schema_version": MODEL_PAGE_SCHEMA,
            "model_id": model["id"],
            "model_slug": model_slug,
            "family_id": family["id"],
            "family_slug": family_slug,
            "display_name": model.get("display_name") or model["id"],
            "default_tag": model.get("default_tag"),
            "default_tag_id": default_tag_id,
            "availability": model.get("availability", "unknown"),
            "deployments": {
                deployment_type_id: {
                    "deployment_type_id": deployment_type_id,
                    "available": summary is not None,
                    "assessment": summary.get("assessment") if summary else None,
                    "ollama_identifier": summary.get("ollama_identifier") if summary else None,
                    "helper_path": summary.get("helper_path") if summary else None,
                }
                for deployment_type_id, summary in deployment_summaries.items()
            },
        }
        write_json(model_path / "model.json", model_json)
        (model_path / "README.md").write_text(
            _model_readme(
                model,
                family_name=family.get("name") or family["id"],
                deployment_rows=deployment_summaries,
            ),
            encoding="utf-8",
        )
        model_pages += 1

    for deployment_type in deployment_types:
        deployment_type_id = deployment_type["deployment_type_id"]
        dt_path = deployment_types_dir / deployment_type_id
        dt_path.mkdir(parents=True, exist_ok=True)
        assessment_breakdown = dict(sorted(deployment_type_assessments[deployment_type_id].items()))
        dt_info = {
            "schema_version": DEPLOYMENT_TYPE_PAGE_SCHEMA,
            "deployment_type_id": deployment_type_id,
            "display_name": deployment_type.get("display_name"),
            "description": deployment_type.get("description"),
            "hardware_profile_ids": deployment_type.get("hardware_profile_ids", []),
            "runtime_policy_ids": deployment_type.get("runtime_policy_ids", []),
            "minimum_ram_gb": deployment_type.get("minimum_ram_gb"),
            "recommended_ram_gb": deployment_type.get("recommended_ram_gb"),
            "minimum_vram_gb": deployment_type.get("minimum_vram_gb"),
            "recommended_vram_gb": deployment_type.get("recommended_vram_gb"),
            "disk_estimate_gb": deployment_type.get("disk_estimate_gb"),
            "cpu_suitability": deployment_type.get("cpu_suitability"),
            "gpu_suitability": deployment_type.get("gpu_suitability"),
            "compatible_model_count": deployment_type_compatible[deployment_type_id],
            "constrained_model_count": deployment_type_constrained[deployment_type_id],
            "unsuitable_model_count": deployment_type_unsuitable[deployment_type_id],
            "assessment_breakdown": assessment_breakdown,
        }
        write_json(dt_path / "info.json", dt_info)
        (dt_path / "README.md").write_text(
            _deployment_type_readme(
                deployment_type,
                compatible_count=deployment_type_compatible[deployment_type_id],
                constrained_count=deployment_type_constrained[deployment_type_id],
                unsuitable_count=deployment_type_unsuitable[deployment_type_id],
                assessment_breakdown=assessment_breakdown,
            ),
            encoding="utf-8",
        )
        deployment_type_pages += 1
        manifest_deployment_types[deployment_type_id] = {
            "deployment_type_id": deployment_type_id,
            "display_name": deployment_type.get("display_name"),
            "hardware_profile_ids": deployment_type.get("hardware_profile_ids", []),
            "runtime_policy_ids": deployment_type.get("runtime_policy_ids", []),
            "minimum_disk_gb": deployment_type.get("disk_estimate_gb"),
            "minimum_ram_gb": deployment_type.get("minimum_ram_gb"),
            "recommended_ram_gb": deployment_type.get("recommended_ram_gb"),
            "minimum_cpu_threads": None,
            "gpu_required": deployment_type.get("gpu_suitability") == "preferred_or_required",
            "minimum_vram_gb": deployment_type.get("minimum_vram_gb"),
            "recommended_vram_gb": deployment_type.get("recommended_vram_gb"),
        }

    write_json(
        manifest_path,
        {
            "schema_version": INSTALL_MANIFEST_SCHEMA,
            "generated_at": utc_now_iso(),
            "hardware_data_version": hardware_data_version,
            "hardware_catalog": hardware_catalog,
            "deployment_types": manifest_deployment_types,
            "models": manifest_models,
        },
    )

    return {
        "family_pages": family_pages,
        "deployment_type_pages": deployment_type_pages,
        "model_pages": model_pages,
        "model_deployment_pages": model_deployment_pages,
        "install_manifest_models": len(manifest_models),
        "install_manifest_deployments": install_manifest_deployments,
    }


def validate_generated_pages(output_root: Path = GENERATED_PAGES_DIR) -> dict[str, Any]:
    errors: list[str] = []
    if not output_root.is_dir():
        errors.append(f"missing generated pages root: {output_root}")

    bad_02_models = output_root / "02-models"
    if bad_02_models.exists():
        errors.append(f"forbidden path exists: {bad_02_models}")

    families_dir = output_root / "families"
    deployment_types_dir = output_root / "deployment-types"
    models_dir = output_root / "models"
    manifest_path = output_root / "install-manifest.json"

    family_count = len(list(families_dir.iterdir())) if families_dir.is_dir() else 0
    deployment_type_count = len(list(deployment_types_dir.iterdir())) if deployment_types_dir.is_dir() else 0
    model_count = len(list(models_dir.iterdir())) if models_dir.is_dir() else 0

    model_deployment_count = 0
    if models_dir.is_dir():
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
            for child in model_dir.iterdir():
                if child.is_dir() and child.name in {"3", "4", "5", "6", "7"}:
                    model_deployment_count += 1
                    info_path = child / "info.json"
                    if not info_path.is_file():
                        errors.append(f"missing info.json: {info_path}")

    manifest_model_count = 0
    manifest_deployment_count = 0
    if manifest_path.is_file():
        from eight_ball.config import load_json

        manifest = load_json(manifest_path)
        models = manifest.get("models", {})
        manifest_model_count = len(models)
        for model_entry in models.values():
            manifest_deployment_count += len(model_entry.get("deployments", {}))
    else:
        errors.append(f"missing install manifest: {manifest_path}")

    if family_count <= 0:
        errors.append("family page count must be > 0")
    if deployment_type_count != 5:
        errors.append(f"deployment type page count must be 5, got {deployment_type_count}")
    if model_count <= 0:
        errors.append("model page count must be > 0")
    if model_deployment_count <= 0:
        errors.append("numbered model deployment page count must be > 0")

    return {
        "valid": not errors,
        "errors": errors,
        "family_pages": family_count,
        "deployment_type_pages": deployment_type_count,
        "model_pages": model_count,
        "model_deployment_pages": model_deployment_count,
        "install_manifest_models": manifest_model_count,
        "install_manifest_deployments": manifest_deployment_count,
        "forbidden_02_models_exists": bad_02_models.exists(),
    }

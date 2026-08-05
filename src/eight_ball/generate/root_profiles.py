from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import (
    GENERATED_PAGES_DEPLOYMENT_TYPES_DIR,
    GENERATED_PAGES_DIR,
    GENERATED_PAGES_FAMILIES_DIR,
    GENERATED_PAGES_MODELS_DIR,
    NORMALIZED_DIR,
    PROFILES_DIR,
    REPO_ROOT,
)
from eight_ball.provenance import utc_now_iso

ROOT_PROFILES_SCHEMA_VERSION = "profiles.manifest.v1"
ROOT_PROFILES_GENERATOR_COMMAND = "eight-ball generate-root-profiles"
ROOT_PROFILES_GENERATOR_VERSION = "1.0.0"
DEPLOYMENT_CLASS_IDS = ("3", "4", "5", "6", "7")

PRESERVED_PROFILE_FILES = frozenset(
    {
        "README.md",
        "environment.profile.example.env",
    }
)

INDEX_COLUMNS = (
    "row_type",
    "entity_id",
    "slug",
    "family_id",
    "deployment_class_id",
    "profile_path",
    "source_path",
    "source_schema_version",
    "provenance_status",
)


class RootProfilesError(Exception):
    def __init__(self, missing_files: list[str]) -> None:
        self.missing_files = missing_files
        message = "Missing canonical generated data:\n" + "\n".join(f"  - {path}" for path in missing_files)
        super().__init__(message)


@dataclass
class RootProfilesSummary:
    family_count: int = 0
    model_count: int = 0
    deployment_class_count: int = 0
    model_deployment_count: int = 0
    provider_assumption_count: int = 0
    index_row_count: int = 0
    missing_files: list[str] = field(default_factory=list)


def _relative_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _require_file(path: Path, missing: list[str]) -> None:
    if not path.is_file():
        missing.append(_relative_repo_path(path))


def _profile_envelope(
    *,
    schema_version: str,
    source_path: Path,
    payload: dict[str, Any],
    provenance_status: str = "derived_from_c5_pages",
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "provenance_status": provenance_status,
        "source_path": _relative_repo_path(source_path),
        "source_schema_version": payload.get("schema_version"),
        "profile": payload,
    }


def _assumption_envelope(record: dict[str, Any], *, source_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "profiles.provider-assumption.v1",
        "provenance_status": "assumption",
        "data_class": "provider_assumption",
        "source_path": _relative_repo_path(source_path),
        "source_reference": record.get("source_reference") or record.get("source_file"),
        "assumption": record,
    }


def _validate_canonical_pages(*, pages_root: Path, install_manifest: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    _require_file(pages_root / "install-manifest.json", missing)

    deployment_types = install_manifest.get("deployment_types", {})
    for deployment_class_id in DEPLOYMENT_CLASS_IDS:
        if deployment_class_id not in deployment_types:
            missing.append(_relative_repo_path(pages_root / "deployment-types" / deployment_class_id / "info.json"))
            continue
        info_path = pages_root / "deployment-types" / deployment_class_id / "info.json"
        _require_file(info_path, missing)

    models = install_manifest.get("models", {})
    for model_id, model_entry in models.items():
        model_slug = model_entry.get("model_slug") or model_id
        model_path = pages_root / "models" / model_slug / "model.json"
        _require_file(model_path, missing)
        deployments = model_entry.get("deployments", {})
        for deployment_class_id, deployment_entry in deployments.items():
            helper_path = deployment_entry.get("helper_path")
            if helper_path:
                helper = REPO_ROOT / helper_path
                _require_file(helper, missing)
            else:
                fallback = pages_root / "models" / model_slug / deployment_class_id / "info.json"
                _require_file(fallback, missing)

    if not GENERATED_PAGES_FAMILIES_DIR.is_dir():
        missing.append(_relative_repo_path(GENERATED_PAGES_FAMILIES_DIR))
    else:
        for family_dir in sorted(GENERATED_PAGES_FAMILIES_DIR.iterdir()):
            if family_dir.is_dir():
                _require_file(family_dir / "info.json", missing)

    return missing


def _clean_generated_profiles(profiles_dir: Path) -> None:
    for child in profiles_dir.iterdir():
        if child.name in PRESERVED_PROFILE_FILES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_index_row(
    rows: list[dict[str, str]],
    *,
    row_type: str,
    entity_id: str,
    slug: str,
    family_id: str,
    deployment_class_id: str,
    profile_path: str,
    source_path: str,
    source_schema_version: str,
    provenance_status: str,
) -> None:
    rows.append(
        {
            "row_type": row_type,
            "entity_id": entity_id,
            "slug": slug,
            "family_id": family_id,
            "deployment_class_id": deployment_class_id,
            "profile_path": profile_path,
            "source_path": source_path,
            "source_schema_version": source_schema_version,
            "provenance_status": provenance_status,
        }
    )


def _emit_provider_assumptions(
    profiles_dir: Path,
    index_rows: list[dict[str, str]],
) -> tuple[int, list[dict[str, Any]]]:
    assumptions_path = NORMALIZED_DIR / "hardware-assumed-profiles.json"
    if not assumptions_path.is_file():
        return 0, []

    assumptions = load_json(assumptions_path)
    if not isinstance(assumptions, list):
        return 0, []

    output_dir = profiles_dir / "provider-assumptions"
    output_dir.mkdir(parents=True, exist_ok=True)
    emitted: list[dict[str, Any]] = []

    for record in assumptions:
        if not isinstance(record, dict):
            continue
        profile_id = str(record.get("profile_id") or record.get("id") or "").strip()
        if not profile_id:
            continue
        safe_name = profile_id.replace("/", "_")
        profile_rel = f"provider-assumptions/{safe_name}.json"
        envelope = _assumption_envelope(record, source_path=assumptions_path)
        write_json(output_dir / f"{safe_name}.json", envelope)
        emitted.append(
            {
                "profile_id": profile_id,
                "profile_path": profile_rel,
                "source_reference": envelope["source_reference"],
                "provenance_status": "assumption",
            }
        )
        _write_index_row(
            index_rows,
            row_type="provider_assumption",
            entity_id=profile_id,
            slug=safe_name,
            family_id="",
            deployment_class_id=str(record.get("deployment_type_id") or ""),
            profile_path=profile_rel,
            source_path=_relative_repo_path(assumptions_path),
            source_schema_version="hardware-assumed-profile.v1",
            provenance_status="assumption",
        )

    manifest_payload = {
        "schema_version": "profiles.provider-assumptions-manifest.v1",
        "provenance_status": "assumption",
        "data_class": "provider_assumption_index",
        "source_path": _relative_repo_path(assumptions_path),
        "secondary_sources": sorted(
            {
                str(record.get("source_reference") or record.get("source_file"))
                for record in assumptions
                if isinstance(record, dict) and (record.get("source_reference") or record.get("source_file"))
            }
        ),
        "assumption_count": len(emitted),
        "assumptions": emitted,
        "notice": (
            "These records are planning assumptions from AGENTS CSV research files. "
            "They are not measured benchmarks or authoritative provider specifications."
        ),
    }
    write_json(output_dir / "manifest.json", manifest_payload)
    return len(emitted), emitted


def generate_root_profiles(
    *,
    pages_root: Path = GENERATED_PAGES_DIR,
    profiles_dir: Path = PROFILES_DIR,
    include_provider_assumptions: bool = True,
) -> RootProfilesSummary:
    summary = RootProfilesSummary()
    install_manifest_path = pages_root / "install-manifest.json"
    _require_file(install_manifest_path, summary.missing_files)
    if summary.missing_files:
        raise RootProfilesError(summary.missing_files)

    install_manifest = load_json(install_manifest_path)
    summary.missing_files = _validate_canonical_pages(
        pages_root=pages_root,
        install_manifest=install_manifest,
    )
    if summary.missing_files:
        raise RootProfilesError(summary.missing_files)

    profiles_dir.mkdir(parents=True, exist_ok=True)
    _clean_generated_profiles(profiles_dir)

    index_rows: list[dict[str, str]] = []

    families_dir = profiles_dir / "families"
    families_dir.mkdir(parents=True, exist_ok=True)
    for family_dir in sorted(GENERATED_PAGES_FAMILIES_DIR.iterdir()):
        if not family_dir.is_dir():
            continue
        source_path = family_dir / "info.json"
        payload = load_json(source_path)
        family_slug = payload.get("family_slug") or family_dir.name
        profile_rel = f"families/{family_slug}/profile.json"
        write_json(
            families_dir / family_slug / "profile.json",
            _profile_envelope(
                schema_version="profiles.family.v1",
                source_path=source_path,
                payload=payload,
            ),
        )
        summary.family_count += 1
        _write_index_row(
            index_rows,
            row_type="family",
            entity_id=str(payload.get("family_id") or family_slug),
            slug=family_slug,
            family_id=str(payload.get("family_id") or family_slug),
            deployment_class_id="",
            profile_path=profile_rel,
            source_path=_relative_repo_path(source_path),
            source_schema_version=str(payload.get("schema_version") or ""),
            provenance_status="derived_from_c5_pages",
        )

    deployment_classes_dir = profiles_dir / "deployment-classes"
    deployment_classes_dir.mkdir(parents=True, exist_ok=True)
    for deployment_class_id in DEPLOYMENT_CLASS_IDS:
        source_path = GENERATED_PAGES_DEPLOYMENT_TYPES_DIR / deployment_class_id / "info.json"
        payload = load_json(source_path)
        profile_rel = f"deployment-classes/{deployment_class_id}/profile.json"
        write_json(
            deployment_classes_dir / deployment_class_id / "profile.json",
            _profile_envelope(
                schema_version="profiles.deployment-class.v1",
                source_path=source_path,
                payload=payload,
            ),
        )
        summary.deployment_class_count += 1
        _write_index_row(
            index_rows,
            row_type="deployment_class",
            entity_id=deployment_class_id,
            slug=deployment_class_id,
            family_id="",
            deployment_class_id=deployment_class_id,
            profile_path=profile_rel,
            source_path=_relative_repo_path(source_path),
            source_schema_version=str(payload.get("schema_version") or ""),
            provenance_status="derived_from_c5_pages",
        )

    models_dir = profiles_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    manifest_models = install_manifest.get("models", {})
    for model_id in sorted(manifest_models):
        model_entry = manifest_models[model_id]
        model_slug = model_entry.get("model_slug") or model_id
        source_model_path = GENERATED_PAGES_MODELS_DIR / model_slug / "model.json"
        model_payload = load_json(source_model_path)
        model_profile_rel = f"models/{model_slug}/model.json"
        write_json(
            models_dir / model_slug / "model.json",
            _profile_envelope(
                schema_version="profiles.model.v1",
                source_path=source_model_path,
                payload=model_payload,
            ),
        )
        summary.model_count += 1
        _write_index_row(
            index_rows,
            row_type="model",
            entity_id=str(model_payload.get("model_id") or model_id),
            slug=model_slug,
            family_id=str(model_payload.get("family_id") or model_entry.get("family_id") or ""),
            deployment_class_id="",
            profile_path=model_profile_rel,
            source_path=_relative_repo_path(source_model_path),
            source_schema_version=str(model_payload.get("schema_version") or ""),
            provenance_status="derived_from_c5_pages",
        )

        deployments = model_entry.get("deployments", {})
        for deployment_class_id in DEPLOYMENT_CLASS_IDS:
            deployment_entry = deployments.get(deployment_class_id)
            if not deployment_entry:
                continue
            helper_path = deployment_entry.get("helper_path")
            source_deployment_path = (
                REPO_ROOT / helper_path
                if helper_path
                else GENERATED_PAGES_MODELS_DIR / model_slug / deployment_class_id / "info.json"
            )
            deployment_payload = load_json(source_deployment_path)
            deployment_profile_rel = f"models/{model_slug}/{deployment_class_id}/profile.json"
            write_json(
                models_dir / model_slug / deployment_class_id / "profile.json",
                _profile_envelope(
                    schema_version="profiles.model-deployment.v1",
                    source_path=source_deployment_path,
                    payload=deployment_payload,
                ),
            )
            summary.model_deployment_count += 1
            _write_index_row(
                index_rows,
                row_type="model_deployment",
                entity_id=f"{model_id}:{deployment_class_id}",
                slug=model_slug,
                family_id=str(deployment_payload.get("family_id") or model_entry.get("family_id") or ""),
                deployment_class_id=deployment_class_id,
                profile_path=deployment_profile_rel,
                source_path=_relative_repo_path(source_deployment_path),
                source_schema_version=str(deployment_payload.get("schema_version") or ""),
                provenance_status="derived_from_c5_pages",
            )

    if include_provider_assumptions:
        summary.provider_assumption_count, _ = _emit_provider_assumptions(profiles_dir, index_rows)

    index_path = profiles_dir / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(index_rows)
    summary.index_row_count = len(index_rows)

    manifest_payload = {
        "schema_version": ROOT_PROFILES_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "generator": {
            "command": ROOT_PROFILES_GENERATOR_COMMAND,
            "version": ROOT_PROFILES_GENERATOR_VERSION,
        },
        "primary_source": {
            "install_manifest_path": _relative_repo_path(install_manifest_path),
            "install_manifest_schema": install_manifest.get("schema_version"),
            "install_manifest_generated_at": install_manifest.get("generated_at"),
            "pages_root": _relative_repo_path(pages_root),
        },
        "lookup_contract": "manifest.models[model_id].deployments[deployment_class_id]",
        "deployment_class_ids": list(DEPLOYMENT_CLASS_IDS),
        "counts": {
            "families": summary.family_count,
            "models": summary.model_count,
            "deployment_classes": summary.deployment_class_count,
            "model_deployments": summary.model_deployment_count,
            "provider_assumptions": summary.provider_assumption_count,
            "index_rows": summary.index_row_count,
        },
        "paths": {
            "index_csv": "profiles/index.csv",
            "families": "profiles/families/",
            "models": "profiles/models/",
            "deployment_classes": "profiles/deployment-classes/",
            "provider_assumptions": (
                "profiles/provider-assumptions/" if summary.provider_assumption_count else None
            ),
        },
    }
    write_json(profiles_dir / "manifest.json", manifest_payload)
    return summary

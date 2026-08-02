from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.paths import (
    P4_PUBLIC_CATALOG_DIR,
    PROFILES_DIR,
    REPO_ROOT,
)
from eight_ball.provenance import utc_now_iso
from eight_ball.publish.display_names import (
    resolve_projection_family_display_name,
    resolve_projection_model_display_name,
)

PROFILE_SCHEMA_VERSION = 1
PROFILE_GENERATOR_COMMAND = "eight-ball generate-profiles"
PROFILE_GENERATOR_VERSION = "1.0.0"

DOCKER_RESERVED_FIELDS = (
    "openwebui_docker_family",
    "openwebui_docker_model",
    "docker_profile_hint",
    "docker_image_channel",
    "docker_compose_profile",
    "records_core_release_key",
)

DEPLOYMENT_TYPE_SPECS: tuple[dict[str, str], ...] = (
    {
        "id": "canary",
        "filename": "canary.md",
        "display_name": "Canary",
        "summary": "Internal canary lane for validating profile artifact loading and installer sequencing.",
    },
    {
        "id": "bare-metal",
        "filename": "bare-metal.md",
        "display_name": "Bare Metal",
        "summary": "Self-hosted Linux or private-server deployment lane.",
    },
    {
        "id": "aws-lightsail",
        "filename": "aws-lightsail.md",
        "display_name": "AWS Lightsail",
        "summary": "AWS Lightsail Linux instance deployment lane.",
    },
    {
        "id": "digitalocean-droplets",
        "filename": "digitalocean-droplets.md",
        "display_name": "DigitalOcean Droplets",
        "summary": "DigitalOcean Droplet deployment lane.",
    },
    {
        "id": "jet",
        "filename": "jet.md",
        "display_name": "Jet",
        "summary": "Cloud Jet / remote inference deployment lane for cloud-capable models.",
    },
    {
        "id": "mac",
        "filename": "Mac.md",
        "display_name": "Mac",
        "summary": "macOS native importer deployment lane.",
    },
    {
        "id": "windows",
        "filename": "Windows.md",
        "display_name": "Windows",
        "summary": "Windows native importer deployment lane.",
    },
)

VARIANT_IDENTITY_KEYS = (
    "ollama_identifier",
    "tag",
    "parameter_count",
    "parameter_unit",
    "quantization",
    "architecture",
    "context_window_tokens",
    "download_size_bytes",
    "download_size_text",
    "availability",
    "pull_command",
    "run_command",
    "alias_target",
    "source_url",
    "retrieved_at",
)


def _relative_repo_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _is_source_exception(record: dict[str, Any]) -> bool:
    return record.get("source_status") == "stale_source_exception"


def _installable_flag(record: dict[str, Any]) -> bool | None:
    if _is_source_exception(record):
        return False
    return None


def _reserved_docker_fields() -> dict[str, str | None]:
    return {field: None for field in DOCKER_RESERVED_FIELDS}


def _variant_identity(variant: dict[str, Any]) -> dict[str, Any]:
    return {key: variant.get(key) for key in VARIANT_IDENTITY_KEYS}


def _family_markdown(family: dict[str, Any], *, catalog_version: str) -> str:
    display_name = resolve_projection_family_display_name(family)
    installable = _installable_flag(family)
    installable_text = (
        "no (stale source exception retained)"
        if installable is False
        else "pending C3 qualification gates"
    )
    lines = [
        f"# {display_name}",
        "",
        f"- **Family ID:** `{family['id']}`",
        f"- **Catalog version:** {catalog_version}",
        f"- **Source status:** {family.get('source_status', 'unknown')}",
        f"- **Installable:** {installable_text}",
        f"- **Source URL:** {family.get('source_url') or 'unknown'}",
        f"- **Retrieved at:** {family.get('retrieved_at') or 'unknown'}",
    ]
    if family.get("source_exception_explanation"):
        lines.extend(
            [
                "",
                "## Source exception",
                "",
                family["source_exception_explanation"],
            ]
        )
    model_ids = family.get("model_ids") or []
    if model_ids:
        lines.extend(["", "## Model IDs", ""])
        lines.extend(f"- `{model_id}`" for model_id in model_ids)
    return "\n".join(lines) + "\n"


def _family_metadata(family: dict[str, Any], *, catalog_version: str) -> dict[str, Any]:
    display_name = resolve_projection_family_display_name(family)
    metadata = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "family_id": family["id"],
        "display_name": display_name,
        "catalog_version": catalog_version,
        "source_exception": _is_source_exception(family),
        "installable": _installable_flag(family),
        "source_status": family.get("source_status"),
        "source_url": family.get("source_url"),
        "retrieved_at": family.get("retrieved_at"),
        "model_ids": list(family.get("model_ids") or []),
        "notes": [],
    }
    metadata.update(_reserved_docker_fields())
    if family.get("source_exception_explanation"):
        metadata["notes"].append(family["source_exception_explanation"])
    return metadata


def _model_markdown(
    model: dict[str, Any],
    *,
    catalog_version: str,
    family_display_name: str,
) -> str:
    display_name = resolve_projection_model_display_name(
        model,
        family_display_name=family_display_name,
    )
    installable = _installable_flag(model)
    installable_text = (
        "no (stale source exception retained)"
        if installable is False
        else "pending C3 qualification gates"
    )
    lines = [
        f"# {display_name}",
        "",
        f"- **Model ID:** `{model['id']}`",
        f"- **Family ID:** `{model['family_id']}`",
        f"- **Ollama name:** {model.get('ollama_name') or model['id']}",
        f"- **Catalog version:** {catalog_version}",
        f"- **Availability:** {model.get('availability') or 'unknown'}",
        f"- **Default tag:** {model.get('default_tag') or 'unknown'}",
        f"- **Source status:** {model.get('source_status', 'unknown')}",
        f"- **Installable:** {installable_text}",
        f"- **Source URL:** {model.get('source_url') or 'unknown'}",
        f"- **Retrieved at:** {model.get('retrieved_at') or 'unknown'}",
    ]
    variants = model.get("deployment_variants") or []
    if variants:
        lines.extend(["", "## Deployment variants (identity only)", ""])
        for variant in variants:
            lines.append(
                f"- `{variant.get('ollama_identifier')}` "
                f"(tag `{variant.get('tag')}`, availability `{variant.get('availability')}`)"
            )
    if model.get("source_exception_explanation"):
        lines.extend(
            [
                "",
                "## Source exception",
                "",
                model["source_exception_explanation"],
            ]
        )
    return "\n".join(lines) + "\n"


def _model_metadata(
    model: dict[str, Any],
    *,
    catalog_version: str,
    family_display_name: str,
) -> dict[str, Any]:
    display_name = resolve_projection_model_display_name(
        model,
        family_display_name=family_display_name,
    )
    metadata = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "model_id": model["id"],
        "family_id": model["family_id"],
        "display_name": display_name,
        "ollama_name": model.get("ollama_name"),
        "catalog_version": catalog_version,
        "source_exception": _is_source_exception(model),
        "installable": _installable_flag(model),
        "source_status": model.get("source_status"),
        "availability": model.get("availability"),
        "default_tag": model.get("default_tag"),
        "source_url": model.get("source_url"),
        "retrieved_at": model.get("retrieved_at"),
        "deployment_variant_count": len(model.get("deployment_variants") or []),
        "deployment_variants": [
            _variant_identity(variant) for variant in (model.get("deployment_variants") or [])
        ],
        "notes": [],
    }
    metadata.update(_reserved_docker_fields())
    if model.get("source_exception_explanation"):
        metadata["notes"].append(model["source_exception_explanation"])
    return metadata


def _deployment_type_markdown(spec: dict[str, str]) -> str:
    return "\n".join(
        [
            f"# {spec['display_name']}",
            "",
            f"- **Deployment type ID:** `{spec['id']}`",
            f"- **Lane:** {spec['summary']}",
            "- **Sizing gates:** deferred to C3 (no RAM/CPU/GPU/disk thresholds in C2)",
            "- **Docker/OpenWebUI routing:** reserved; values remain null until verified",
            "",
            "This file documents deployment-lane identity only. Installers should consume",
            "`profiles/generated/deployment-types.json` rather than parsing this Markdown.",
            "",
        ]
    )


def _write_deployment_type_files(*, deployment_types_dir: Path) -> list[dict[str, Any]]:
    deployment_types_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for spec in DEPLOYMENT_TYPE_SPECS:
        path = deployment_types_dir / spec["filename"]
        path.write_text(_deployment_type_markdown(spec), encoding="utf-8")
        records.append(
            {
                "id": spec["id"],
                "display_name": spec["display_name"],
                "markdown_file": _relative_repo_path(path),
                "summary": spec["summary"],
            }
        )
    return records


def _clean_generated_tree(root: Path, *, keep_names: set[str]) -> None:
    if not root.exists():
        return
    for child in root.iterdir():
        if child.name in keep_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _load_catalog_projection(catalog_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = load_json(catalog_dir / "manifest.json")
    families = load_json(catalog_dir / manifest["indexes"]["families"])
    models = load_json(catalog_dir / manifest["indexes"]["models"])
    return manifest, families, models


def _validate_catalog_counts(
    manifest: dict[str, Any],
    families: list[dict[str, Any]],
    models: list[dict[str, Any]],
) -> dict[str, int]:
    counts = manifest.get("counts") or {}
    expected_families = int(counts.get("families", 0))
    expected_models = int(counts.get("models", 0))
    actual_families = len(families)
    actual_models = len(models)
    if actual_families != expected_families:
        raise ValueError(
            f"Family count mismatch: manifest reports {expected_families}, "
            f"index contains {actual_families}"
        )
    if actual_models != expected_models:
        raise ValueError(
            f"Model count mismatch: manifest reports {expected_models}, "
            f"index contains {actual_models}"
        )
    deployment_variants = sum(len(model.get("deployment_variants") or []) for model in models)
    expected_variants = int(counts.get("deployment_variants", 0))
    if deployment_variants != expected_variants:
        raise ValueError(
            f"Deployment variant count mismatch: manifest reports {expected_variants}, "
            f"models contain {deployment_variants}"
        )
    return {
        "families": actual_families,
        "models": actual_models,
        "deployment_variants": deployment_variants,
        "source_exception_families": sum(1 for family in families if _is_source_exception(family)),
        "source_exception_models": sum(1 for model in models if _is_source_exception(model)),
    }


def generate_profile_artifacts(
    *,
    catalog_dir: Path = P4_PUBLIC_CATALOG_DIR,
    profiles_dir: Path = PROFILES_DIR,
) -> dict[str, Any]:
    manifest, families, models = _load_catalog_projection(catalog_dir)
    counts = _validate_catalog_counts(manifest, families, models)
    catalog_version = manifest.get("canonical_catalog_version") or "unknown"

    families_dir = profiles_dir / "01-families"
    models_dir = profiles_dir / "02-models"
    deployment_types_dir = profiles_dir / "03-deployment-types"
    generated_dir = profiles_dir / "generated"
    families_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)

    expected_family_ids = {family["id"] for family in families}
    _clean_generated_tree(families_dir, keep_names=expected_family_ids)
    expected_model_paths = {
        f"{model['family_id']}/{model['id']}" for model in models
    }
    if models_dir.exists():
        for family_dir in list(models_dir.iterdir()):
            if not family_dir.is_dir():
                continue
            family_id = family_dir.name
            for model_dir in list(family_dir.iterdir()):
                rel = f"{family_id}/{model_dir.name}"
                if rel not in expected_model_paths:
                    shutil.rmtree(model_dir)
            if not any(family_dir.iterdir()):
                shutil.rmtree(family_dir)

    family_index: list[dict[str, Any]] = []
    family_display_names: dict[str, str] = {}
    for family in sorted(families, key=lambda item: item["id"]):
        family_display_name = resolve_projection_family_display_name(family)
        family_display_names[family["id"]] = family_display_name
        family_dir = families_dir / family["id"]
        family_dir.mkdir(parents=True, exist_ok=True)
        (family_dir / "family.md").write_text(
            _family_markdown(family, catalog_version=catalog_version),
            encoding="utf-8",
        )
        write_json(family_dir / "metadata.json", _family_metadata(family, catalog_version=catalog_version))
        family_index.append(
            {
                "family_id": family["id"],
                "display_name": family_display_name,
                "installable": _installable_flag(family),
                "source_exception": _is_source_exception(family),
                "model_ids": list(family.get("model_ids") or []),
                "metadata_path": _relative_repo_path(family_dir / "metadata.json"),
            }
        )

    model_index: list[dict[str, Any]] = []
    for model in sorted(models, key=lambda item: (item["family_id"], item["id"])):
        family_display_name = family_display_names[model["family_id"]]
        model_display_name = resolve_projection_model_display_name(
            model,
            family_display_name=family_display_name,
        )
        model_dir = models_dir / model["family_id"] / model["id"]
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "model.md").write_text(
            _model_markdown(
                model,
                catalog_version=catalog_version,
                family_display_name=family_display_name,
            ),
            encoding="utf-8",
        )
        write_json(
            model_dir / "metadata.json",
            _model_metadata(
                model,
                catalog_version=catalog_version,
                family_display_name=family_display_name,
            ),
        )
        model_index.append(
            {
                "model_id": model["id"],
                "family_id": model["family_id"],
                "display_name": model_display_name,
                "installable": _installable_flag(model),
                "source_exception": _is_source_exception(model),
                "default_tag": model.get("default_tag"),
                "deployment_variant_count": len(model.get("deployment_variants") or []),
                "metadata_path": _relative_repo_path(model_dir / "metadata.json"),
            }
        )

    deployment_types = _write_deployment_type_files(deployment_types_dir=deployment_types_dir)

    family_model_index = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generator_version": PROFILE_GENERATOR_VERSION,
        "generator_command": PROFILE_GENERATOR_COMMAND,
        "generated_at": utc_now_iso(),
        "catalog_version": catalog_version,
        "catalog_projection": {
            "manifest_path": _relative_repo_path(catalog_dir / "manifest.json"),
            "families_index_path": _relative_repo_path(catalog_dir / manifest["indexes"]["families"]),
            "models_index_path": _relative_repo_path(catalog_dir / manifest["indexes"]["models"]),
        },
        "counts": counts,
        "families": family_index,
        "models": model_index,
    }
    deployment_types_index = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generator_version": PROFILE_GENERATOR_VERSION,
        "generator_command": PROFILE_GENERATOR_COMMAND,
        "generated_at": utc_now_iso(),
        "deployment_types": deployment_types,
    }
    environment_artifact_index = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generator_version": PROFILE_GENERATOR_VERSION,
        "generator_command": PROFILE_GENERATOR_COMMAND,
        "generated_at": utc_now_iso(),
        "catalog_version": catalog_version,
        "catalog_projection": family_model_index["catalog_projection"],
        "counts": counts,
        "steps_completed": ["family", "model", "deployment_type"],
        "steps_deferred": ["hard_disk", "ram", "cpu", "gpu"],
        "artifacts": {
            "families_dir": _relative_repo_path(families_dir),
            "models_dir": _relative_repo_path(models_dir),
            "deployment_types_dir": _relative_repo_path(deployment_types_dir),
            "generated_files": [
                "profiles/generated/family-model-index.json",
                "profiles/generated/deployment-types.json",
                "profiles/generated/environment-artifact-index.json",
            ],
        },
        "deployment_type_ids": [item["id"] for item in deployment_types],
    }

    write_json(generated_dir / "family-model-index.json", family_model_index)
    write_json(generated_dir / "deployment-types.json", deployment_types_index)
    write_json(generated_dir / "environment-artifact-index.json", environment_artifact_index)

    return {
        "catalog_dir": _relative_repo_path(catalog_dir),
        "catalog_version": catalog_version,
        "counts": counts,
        "deployment_type_files": [item["markdown_file"] for item in deployment_types],
        "generated_files": [
            _relative_repo_path(generated_dir / "family-model-index.json"),
            _relative_repo_path(generated_dir / "deployment-types.json"),
            _relative_repo_path(generated_dir / "environment-artifact-index.json"),
        ],
    }

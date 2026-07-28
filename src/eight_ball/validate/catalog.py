from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from eight_ball.config import (
    capabilities_config,
    hardware_profiles_config,
    load_json,
    load_yaml,
)
from eight_ball.paths import CONFIG_DIR, GENERATED_DIR, INDEXES_DIR, NORMALIZED_DIR, SCHEMAS_DIR

ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CAPABILITY_VALUES = {"true", "false", "unknown"}
MODEL_AVAILABILITY = {"local", "cloud", "both", "unknown"}
TAG_AVAILABILITY = {"local", "cloud", "both", "cloud_only", "unknown"}


class ValidationError(Exception):
    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__(f"{len(errors)} validation error(s)")


def _schema(name: str) -> dict[str, Any]:
    return load_json(SCHEMAS_DIR / name)


def _validate_records(records: list[dict[str, Any]], schema_name: str, label: str) -> list[str]:
    schema = _schema(schema_name)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for record in records:
        for error in sorted(validator.iter_errors(record), key=lambda e: e.path):
            errors.append(f"{label} {record.get('id', '?')}: {error.message}")
    return errors


def _is_valid_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_valid_timestamp(value: str | None) -> bool:
    if value is None:
        return True
    return bool(ISO_TIMESTAMP_RE.match(value))


def _known_quantizations() -> set[str]:
    data = load_yaml(CONFIG_DIR / "quantizations.yaml")
    return set(data.get("known_quantizations", []))


def _known_capability_ids() -> set[str]:
    return {item["id"] for item in capabilities_config().get("capabilities", [])}


def _known_hardware_profile_ids() -> set[str]:
    return {item["id"] for item in hardware_profiles_config().get("profiles", [])}


def _duplicate_ids(records: list[dict[str, Any]], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for record in records:
        record_id = record.get("id")
        if record_id in seen:
            errors.append(f"duplicate {label} id {record_id}")
        seen.add(record_id)
    return errors


def _load_catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    if catalog is not None:
        return catalog
    return {
        "publishers": load_json(NORMALIZED_DIR / "publishers.json"),
        "families": load_json(NORMALIZED_DIR / "families.json"),
        "models": load_json(NORMALIZED_DIR / "models.json"),
        "tags": load_json(NORMALIZED_DIR / "tags.json"),
    }


def validate_catalog(
    catalog: dict[str, Any] | None = None,
    *,
    include_artifacts: bool | None = None,
) -> dict[str, Any]:
    catalog_provided = catalog is not None
    catalog = _load_catalog(catalog)
    if include_artifacts is None:
        include_artifacts = not catalog_provided
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_duplicate_ids(catalog["publishers"], "publisher"))
    errors.extend(_duplicate_ids(catalog["families"], "family"))
    errors.extend(_duplicate_ids(catalog["models"], "model"))
    errors.extend(_duplicate_ids(catalog["tags"], "tag"))

    errors.extend(_validate_records(catalog["publishers"], "publisher.schema.json", "publisher"))
    errors.extend(_validate_records(catalog["families"], "model-family.schema.json", "family"))
    errors.extend(_validate_records(catalog["models"], "model.schema.json", "model"))
    errors.extend(_validate_records(catalog["tags"], "tag.schema.json", "tag"))

    publisher_ids = {p["id"] for p in catalog["publishers"]}
    family_ids = {f["id"] for f in catalog["families"]}
    model_ids = {m["id"] for m in catalog["models"]}
    ollama_ids = {t["ollama_identifier"] for t in catalog["tags"]}
    tag_ids = {t["id"] for t in catalog["tags"]}
    known_caps = _known_capability_ids()
    known_quants = _known_quantizations()

    for publisher in catalog["publishers"]:
        if publisher.get("official_url") and not _is_valid_url(publisher["official_url"]):
            errors.append(f"publisher {publisher['id']}: invalid official_url")

    for family in catalog["families"]:
        if family["publisher_id"] not in publisher_ids:
            errors.append(
                f"family {family['id']} references missing publisher {family['publisher_id']}"
            )
        for url_field in ("ollama_url", "source_url"):
            if family.get(url_field) and not _is_valid_url(family[url_field]):
                errors.append(f"family {family['id']}: invalid {url_field}")
        if family.get("retrieved_at") and not _is_valid_timestamp(family["retrieved_at"]):
            errors.append(f"family {family['id']}: invalid retrieved_at")
        for cap_id, value in family.get("primary_capabilities", {}).items():
            if cap_id not in known_caps:
                errors.append(f"family {family['id']}: unsupported capability {cap_id}")
            elif value not in CAPABILITY_VALUES:
                errors.append(f"family {family['id']}: invalid capability value for {cap_id}")

    tags_by_model: dict[str, list[dict[str, Any]]] = {}
    seen_ollama: set[str] = set()
    for tag in catalog["tags"]:
        tags_by_model.setdefault(tag["model_id"], []).append(tag)
        if tag["ollama_identifier"] in seen_ollama:
            errors.append(f"duplicate ollama identifier {tag['ollama_identifier']}")
        seen_ollama.add(tag["ollama_identifier"])
        if tag["model_id"] not in model_ids:
            errors.append(f"tag {tag['id']} references missing model {tag['model_id']}")
        for url_field in ("source_url",):
            if tag.get(url_field) and not _is_valid_url(tag[url_field]):
                errors.append(f"tag {tag['id']}: invalid {url_field}")
        if tag.get("retrieved_at") and not _is_valid_timestamp(tag["retrieved_at"]):
            errors.append(f"tag {tag['id']}: invalid retrieved_at")
        if tag.get("download_size_bytes") is not None and tag["download_size_bytes"] < 0:
            errors.append(f"tag {tag['id']}: negative download_size_bytes")
        if tag.get("parameter_count") is not None and tag["parameter_count"] < 0:
            errors.append(f"tag {tag['id']}: negative parameter_count")
        quant = tag.get("quantization")
        if quant is not None and quant not in known_quants:
            errors.append(f"tag {tag['id']}: unsupported quantization {quant}")
        availability = tag.get("availability")
        if availability not in TAG_AVAILABILITY:
            errors.append(f"tag {tag['id']}: invalid availability {availability}")
        if availability == "cloud_only" and tag.get("download_size_bytes") not in (None, 0):
            errors.append(f"tag {tag['id']}: cloud_only tag has download size")
        if availability == "local" and tag.get("download_size_bytes") is None:
            errors.append(f"tag {tag['id']}: local tag missing download_size_bytes")
        expected_pull = f"ollama pull {tag['ollama_identifier']}"
        expected_run = f"ollama run {tag['ollama_identifier']}"
        if tag.get("pull_command") and tag["pull_command"] != expected_pull:
            errors.append(f"tag {tag['id']}: pull_command does not match exact tag")
        if tag.get("run_command") and tag["run_command"] != expected_run:
            errors.append(f"tag {tag['id']}: run_command does not match exact tag")
        alias_target = tag.get("alias_target")
        if alias_target and alias_target not in ollama_ids:
            errors.append(f"tag {tag['id']}: alias_target {alias_target} does not exist")
        provenance = tag.get("provenance") or {}
        if not provenance:
            errors.append(f"tag {tag['id']}: missing provenance")
        else:
            for field in ("download_size_bytes", "parameter_count"):
                if field not in provenance:
                    errors.append(f"tag {tag['id']}: missing provenance for {field}")
                elif provenance[field].get("confidence") not in {
                    "observed",
                    "derived",
                    "estimated",
                    "manual",
                    "unknown",
                }:
                    errors.append(f"tag {tag['id']}: invalid provenance confidence for {field}")

    manual_review_count = 0
    for model in catalog["models"]:
        manual_review_count += int(model.get("validation_status") == "needs_review")
        if model["publisher_id"] not in publisher_ids:
            errors.append(f"model {model['id']} references missing publisher {model['publisher_id']}")
        if model["family_id"] not in family_ids:
            errors.append(f"model {model['id']} references missing family {model['family_id']}")
        if model.get("availability") not in MODEL_AVAILABILITY:
            errors.append(f"model {model['id']}: invalid availability")
        for url_field in ("source_url",):
            if model.get(url_field) and not _is_valid_url(model[url_field]):
                errors.append(f"model {model['id']}: invalid {url_field}")
        if model.get("retrieved_at") and not _is_valid_timestamp(model["retrieved_at"]):
            errors.append(f"model {model['id']}: invalid retrieved_at")
        for cap_id, value in model.get("capabilities", {}).items():
            if cap_id not in known_caps:
                errors.append(f"model {model['id']}: unsupported capability {cap_id}")
            elif value not in CAPABILITY_VALUES:
                errors.append(f"model {model['id']}: invalid capability value for {cap_id}")
        default_tag = model.get("default_tag")
        if not default_tag:
            errors.append(f"model {model['id']}: missing default_tag")
        elif default_tag not in ollama_ids:
            errors.append(f"model {model['id']}: default_tag {default_tag} does not exist")

    hardware_profiles = hardware_profiles_config().get("profiles", [])
    errors.extend(
        _validate_records(hardware_profiles, "hardware-profile.schema.json", "hardware_profile")
    )
    for profile in hardware_profiles:
        if profile["id"] not in _known_hardware_profile_ids():
            errors.append(f"hardware_profile {profile['id']}: unknown configured profile")

    generation_summary: dict[str, Any] = {"present": False, "deployment_combinations": 0}
    index_summary: dict[str, Any] = {"present": False}
    if include_artifacts:
        generation_errors, generation_summary = _validate_generated(tag_ids)
        errors.extend(generation_errors)
        index_errors, index_summary = _validate_indexes(catalog)
        errors.extend(index_errors)

    report = {
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "publishers": len(catalog["publishers"]),
            "families": len(catalog["families"]),
            "models": len(catalog["models"]),
            "tags": len(catalog["tags"]),
            "manual_review": manual_review_count,
        },
        "generation": generation_summary,
        "indexes": index_summary,
    }
    if errors:
        raise ValidationError(errors, warnings)
    return report


def _validate_generated(tag_ids: set[str]) -> tuple[list[str], dict[str, Any]]:
    summary: dict[str, Any] = {"present": False, "deployment_combinations": 0}
    deployment_path = GENERATED_DIR / "deployment_recommendations.json"
    if not deployment_path.exists():
        return [], summary

    summary["present"] = True
    deployments = load_json(deployment_path)
    summary["deployment_combinations"] = len(deployments)
    errors: list[str] = []
    seen_ids: set[str] = set()
    profile_ids = _known_hardware_profile_ids()
    validator = Draft202012Validator(_schema("deployment-recommendation.schema.json"))

    for row in deployments:
        for error in validator.iter_errors(row):
            errors.append(f"deployment {row.get('id', '?')}: {error.message}")
        row_id = row.get("id")
        if row_id in seen_ids:
            errors.append(f"duplicate deployment recommendation id {row_id}")
        seen_ids.add(row_id)
        if row.get("tag_id") not in tag_ids:
            errors.append(f"deployment {row_id}: references missing tag {row.get('tag_id')}")
        if row.get("hardware_profile_id") not in profile_ids:
            errors.append(
                f"deployment {row_id}: references missing hardware profile "
                f"{row.get('hardware_profile_id')}"
            )
    return errors, summary


def _validate_indexes(catalog: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    summary: dict[str, Any] = {"present": False}
    local_path = INDEXES_DIR / "local-tags.json"
    if not local_path.exists():
        return [], summary

    summary["present"] = True
    local_index = load_json(local_path)
    cloud_index = load_json(INDEXES_DIR / "cloud-tags.json")
    ollama_ids = {t["ollama_identifier"] for t in catalog["tags"]}
    errors: list[str] = []
    for tag_id in local_index:
        if tag_id not in ollama_ids:
            errors.append(f"index local-tags references unknown tag {tag_id}")
    for tag_id in cloud_index:
        if tag_id not in ollama_ids:
            errors.append(f"index cloud-tags references unknown tag {tag_id}")
    expected_local = sorted(
        t["ollama_identifier"]
        for t in catalog["tags"]
        if t.get("availability") in {"local", "both"}
    )
    if sorted(local_index) != expected_local:
        errors.append("index local-tags inconsistent with normalized tag availability")
    summary["local_tags"] = len(local_index)
    summary["cloud_tags"] = len(cloud_index)
    return errors, summary

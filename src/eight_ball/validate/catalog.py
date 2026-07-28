from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from eight_ball.config import load_json
from eight_ball.paths import NORMALIZED_DIR, SCHEMAS_DIR


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
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


def validate_catalog(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    if catalog is None:
        catalog = {
            "publishers": load_json(NORMALIZED_DIR / "publishers.json"),
            "families": load_json(NORMALIZED_DIR / "families.json"),
            "models": load_json(NORMALIZED_DIR / "models.json"),
            "tags": load_json(NORMALIZED_DIR / "tags.json"),
        }

    errors: list[str] = []
    errors.extend(_validate_records(catalog["publishers"], "publisher.schema.json", "publisher"))
    errors.extend(_validate_records(catalog["families"], "model-family.schema.json", "family"))
    errors.extend(_validate_records(catalog["models"], "model.schema.json", "model"))
    errors.extend(_validate_records(catalog["tags"], "tag.schema.json", "tag"))

    publisher_ids = {p["id"] for p in catalog["publishers"]}
    family_ids = {f["id"] for f in catalog["families"]}
    model_ids = {m["id"] for m in catalog["models"]}
    tag_ids: set[str] = set()
    ollama_ids: set[str] = set()

    for family in catalog["families"]:
        if family["publisher_id"] not in publisher_ids:
            errors.append(f"family {family['id']} references missing publisher {family['publisher_id']}")

    for model in catalog["models"]:
        if model["publisher_id"] not in publisher_ids:
            errors.append(f"model {model['id']} references missing publisher {model['publisher_id']}")
        if model["family_id"] not in family_ids:
            errors.append(f"model {model['id']} references missing family {model['family_id']}")

    for tag in catalog["tags"]:
        if tag["id"] in tag_ids:
            errors.append(f"duplicate tag id {tag['id']}")
        tag_ids.add(tag["id"])
        if tag["ollama_identifier"] in ollama_ids:
            errors.append(f"duplicate ollama identifier {tag['ollama_identifier']}")
        ollama_ids.add(tag["ollama_identifier"])
        if tag["model_id"] not in model_ids:
            errors.append(f"tag {tag['id']} references missing model {tag['model_id']}")
        if tag.get("download_size_bytes") is not None and tag["download_size_bytes"] < 0:
            errors.append(f"tag {tag['id']} has negative download size")
        availability = tag.get("availability")
        if availability == "cloud_only" and tag.get("download_size_bytes") not in (None, 0):
            errors.append(f"tag {tag['id']} is cloud_only but has download size")
        if availability == "local" and tag.get("download_size_bytes") is None:
            errors.append(f"tag {tag['id']} is local but missing download size")

    report = {
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
        "counts": {
            "publishers": len(catalog["publishers"]),
            "families": len(catalog["families"]),
            "models": len(catalog["models"]),
            "tags": len(catalog["tags"]),
        },
    }
    if errors:
        raise ValidationError(errors)
    return report

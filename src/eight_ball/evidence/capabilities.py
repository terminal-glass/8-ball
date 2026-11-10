from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from eight_ball.config import load_json
from eight_ball.paths import NORMALIZED_DIR, SCHEMAS_DIR

MEASURED_FIELDS = ("method", "runtime_version", "hardware", "limitations")


def load_evidence_registry(path=None) -> dict[str, Any]:
    return load_json(path or NORMALIZED_DIR / "capability-evidence.json")


def evidence_errors(registry: dict[str, Any], *, known_tags: set[str] | None = None) -> list[str]:
    schema = load_json(SCHEMAS_DIR / "capability-evidence.schema.json")
    validator = Draft202012Validator(schema)
    errors = [
        f"capability-evidence: {error.message}"
        for error in sorted(validator.iter_errors(registry), key=lambda item: list(item.path))
    ]
    for index, record in enumerate(registry.get("records") or []):
        if not isinstance(record, dict):
            continue
        label = f"capability-evidence[{index}]"
        kind = record.get("kind")
        if known_tags is not None and record.get("ollama_identifier") not in known_tags:
            errors.append(f"{label}: unknown tag {record.get('ollama_identifier')}")
        if kind == "source_claim" and not record.get("source_url"):
            errors.append(f"{label}: a source claim needs source_url")
        if kind == "source_claim" and record.get("status") == "tested":
            errors.append(f"{label}: a source claim is not a measured test")
        if kind == "measured_test":
            if record.get("status") != "tested":
                errors.append(f"{label}: a measured test must be status tested")
            for field in MEASURED_FIELDS:
                if not record.get(field):
                    errors.append(f"{label}: measured test needs {field}")
        if kind == "unknown" and record.get("value") != "unknown":
            errors.append(f"{label}: unknown evidence must keep value unknown")
    return errors


def agent_ready(records: list[dict[str, Any]], *, display_name: str | None = None, parameter_count: int | None = None) -> dict[str, Any]:
    """Measured tool-use evidence is required. Name and size are ignored."""
    del display_name, parameter_count
    measured = [
        record
        for record in records
        if record.get("capability_id") == "tool_use"
        and record.get("kind") == "measured_test"
        and record.get("value") == "true"
        and record.get("status") == "tested"
    ]
    if measured:
        return {
            "agent_ready": True,
            "reason": "A measured tool-use test recorded value true.",
            "evidence_kind": "measured_test",
        }
    source_claims = [record for record in records if record.get("kind") == "source_claim"]
    if source_claims:
        reason = "Only a source claim is recorded. That is not a measured test."
    else:
        reason = "No measured tool-use test is recorded."
    return {"agent_ready": False, "reason": reason, "evidence_kind": "untested"}

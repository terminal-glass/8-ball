from __future__ import annotations

import re
from typing import Any

from eight_ball.agents_csv.registry import SourceSpec

_KEY_PART_RE = re.compile(r"\s+")


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return _KEY_PART_RE.sub(" ", text)


def provider_composite_key(
    record: dict[str, Any],
    *,
    provider_field: str = "provider",
    product_line_field: str = "product_line",
    plan_id_field: str | None = None,
    provider_value: str | None = None,
    product_line_value: str | None = None,
) -> str:
    provider = _norm(provider_value if provider_value is not None else record.get(provider_field))
    product_line = _norm(
        product_line_value if product_line_value is not None else record.get(product_line_field)
    )
    plan_id = ""
    if plan_id_field:
        plan_id = _norm(record.get(plan_id_field))
    if not plan_id:
        for field in ("provider_plan_id", "internal_plan_id", "plan_slug", "bundle_id"):
            plan_id = _norm(record.get(field))
            if plan_id:
                break
    if not provider or not product_line or not plan_id:
        raise ValueError(
            "provider composite key requires provider, product_line, and plan_id "
            f"(got provider={provider!r}, product_line={product_line!r}, plan_id={plan_id!r})"
        )
    return f"provider_instance:{provider}|{product_line}|{plan_id}"


def profile_key(record: dict[str, Any], *, field: str = "profile_id") -> str:
    value = _norm(record.get(field))
    if not value:
        raise ValueError(f"assumed hardware profile key requires {field}")
    return f"assumed_profile:{value}"


def host_profile_key(record: dict[str, Any], *, field: str = "host_profile_id") -> str:
    value = _norm(record.get(field))
    if not value:
        raise ValueError(f"measured host key requires {field}")
    return f"measured_host:{value}"


def accelerator_class_key(record: dict[str, Any], *, field: str = "accelerator_class_id") -> str:
    value = _norm(record.get(field))
    if not value:
        raise ValueError(f"accelerator class key requires {field}")
    return f"accelerator_class:{value}"


def deployment_type_key(record: dict[str, Any], *, field: str = "deployment_type_id") -> str:
    value = _norm(record.get(field))
    if not value:
        raise ValueError(f"deployment type key requires {field}")
    return f"deployment_type:{value}"


def control_row_key(*, source_file: str, row_number: int) -> str:
    return f"control:{source_file}|row:{row_number}"


def record_dedup_key(record: dict[str, Any], source: SourceSpec) -> str:
    namespace = source.namespace
    options = source.options

    if namespace == "provider_instance_data":
        return provider_composite_key(
            record,
            provider_field=options.get("provider_field", "provider"),
            product_line_field=options.get("product_line_field", "product_line"),
            plan_id_field=options.get("plan_id_field"),
            provider_value=options.get("provider_value"),
            product_line_value=options.get("product_line_value"),
        )

    if namespace == "assumed_hardware_profiles":
        return profile_key(record, field=options.get("profile_id_field", "profile_id"))

    if namespace == "measured_hardware_inventory":
        return host_profile_key(record, field=options.get("host_profile_id_field", "host_profile_id"))

    if namespace == "classification_data":
        kind = options.get("classification_kind")
        if kind == "accelerator":
            return accelerator_class_key(
                record,
                field=options.get("accelerator_class_id_field", "accelerator_class_id"),
            )
        if kind == "deployment":
            return deployment_type_key(record, field=options.get("deployment_field", "deployment_type_id"))
        raise ValueError(f"classification source {source.id} missing classification_kind")

    if namespace == "control_and_provenance":
        raise ValueError("control rows do not produce importable dedup keys")

    raise ValueError(f"unsupported namespace {namespace}")


def provenance_status(record: dict[str, Any], source: SourceSpec) -> str | None:
    for field in namespace_provenance_fields(source.namespace):
        if record.get(field):
            return str(record[field])
    return None


def namespace_provenance_fields(namespace: str) -> list[str]:
    from eight_ball.agents_csv.registry import namespace_config

    config = namespace_config(namespace)
    return list(config.get("provenance_fields", []))


def relationship_overlap_key(record: dict[str, Any], source: SourceSpec) -> str | None:
    """Non-unique relationship fingerprint for intentional overlap reporting."""
    deployment_type_id = _norm(record.get("deployment_type_id"))
    if deployment_type_id:
        return f"deployment_type:{deployment_type_id}"

    if source.namespace == "classification_data":
        accelerator = _norm(record.get("accelerator_class_id"))
        if accelerator:
            return f"accelerator_class:{accelerator}"

    return None

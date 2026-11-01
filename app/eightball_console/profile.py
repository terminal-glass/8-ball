"""Host profile snapshot loading and validation. Never runs a hidden scan."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .producer import PROFILE_SCHEMA

REQUIRED = ("schema_version", "state", "profile_id", "created_at", "captured_at", "platform",
            "capacity", "lane", "classification", "unknowns", "catalog")


def load(path: Path, max_age_days: int = 30) -> dict[str, Any]:
    """Return {status, problems[], profile|None, path}. status: valid|missing|corrupt|invalid|incomplete|stale|unauthorized."""
    res: dict[str, Any] = {"path": str(path), "status": "valid", "problems": [], "profile": None}
    if not path.is_file():
        res.update(status="missing", problems=["no profile snapshot at this path"])
        return res
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        res.update(status="corrupt", problems=[f"cannot parse: {exc.__class__.__name__}"])
        return res
    if not isinstance(doc, dict):
        res.update(status="corrupt", problems=["not a JSON object"])
        return res
    missing = [k for k in REQUIRED if k not in doc]
    if doc.get("schema_version") != PROFILE_SCHEMA:
        res.update(status="invalid", problems=[f"schema_version is not {PROFILE_SCHEMA}"])
        return res
    if missing:
        res.update(status="invalid", problems=[f"missing {', '.join(missing)}"])
        return res
    res["profile"] = doc
    if doc.get("state") != "complete":
        res.update(status="incomplete", problems=[f"state is {doc.get('state')!r}"])
        return res
    if not doc["platform"].get("authorized"):
        res.update(status="unauthorized", problems=[f"platform {doc['platform'].get('id')} is not supported"])
        return res
    try:
        cap = dt.datetime.fromisoformat(str(doc["captured_at"]).replace("Z", "+00:00"))
        age = dt.datetime.now(dt.timezone.utc) - cap
        res["age_days"] = round(age.total_seconds() / 86400, 2)
        if age > dt.timedelta(days=max_age_days):
            res.update(status="stale", problems=[f"captured {res['age_days']} days ago (max {max_age_days})"])
    except ValueError:
        res.update(status="invalid", problems=["captured_at is not ISO-8601"])
    return res

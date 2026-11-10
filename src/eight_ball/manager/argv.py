from __future__ import annotations

import re
from typing import Any

TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
HOSTED_ONLY = {"cloud", "cloud_only"}


class ArgvRejected(ValueError):
    """A catalog string was not safe to place in an argument array."""


def lookup_tag(catalog: dict[str, Any], tag: str) -> dict[str, Any]:
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
        raise ArgvRejected("tag does not match the allowed Ollama tag pattern")
    for record in catalog.get("tags", []):
        if record.get("ollama_identifier") == tag:
            return record
    raise ArgvRejected("tag is not in the validated catalog")


def ollama_argv(command: str, catalog: dict[str, Any], tag: str | None = None) -> list[str]:
    """Build an argument array. The caller must execute it with shell disabled."""
    if command == "list":
        return ["ollama", "list"]
    if command == "ps":
        return ["ollama", "ps"]
    if command not in {"pull", "rm", "show"}:
        raise ArgvRejected(f"command {command} is not allowed")
    record = lookup_tag(catalog, tag or "")
    if command == "pull" and record.get("availability") in HOSTED_ONLY:
        raise ArgvRejected("cloud-only models are not local downloads")
    return ["ollama", command, record["ollama_identifier"]]

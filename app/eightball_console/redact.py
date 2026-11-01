"""Redaction for anything written to job logs or events."""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*\S+(\s+\S+)?"), r"\1: [redacted]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [redacted]"),
    (re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key|access[_-]?key)(\"?\s*[:=]\s*\"?)[^\s\",]+"), r"\1\2[redacted]"),
    (re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1[redacted]@"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})\b"), "[redacted]"),
]


def redact(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text

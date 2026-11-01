"""Console tokens and the read-only job log viewer run by ttyd.

The browser asks the API for a short-lived token bound to ONE job id, then opens the ttyd page
with ?arg=<token>. ttyd starts `eightball-console console-view <token>`, which verifies the HMAC,
prints that job's redacted log and follows it until the job ends. No shell is ever started and
no input is read: ttyd runs without -W (read-only) and the viewer ignores stdin.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

from .jobs import TERMINAL


def ensure_secret(path: Path) -> bytes:
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    return path.read_text().strip().encode()


def make_token(secret: bytes, job_id: str, ttl: int) -> str:
    exp = int(time.time()) + ttl
    msg = f"{job_id}.{exp}"
    sig = hmac.new(secret, msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{msg}.{sig}"


def check_token(secret: bytes, token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != 3 or not all(c in "0123456789abcdef-" for c in parts[0]) or not parts[1].isdigit():
        return None
    job_id, exp, sig = parts
    good = hmac.new(secret, f"{job_id}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(good, sig) or int(exp) < time.time():
        return None
    return job_id


def view(jobs_dir: Path, secret_file: Path, argv: list[str]) -> int:
    out = sys.stdout
    if len(argv) != 1:
        out.write("8-Ball console: open a job from the Console page.\r\n")
        return 2
    try:
        secret = secret_file.read_text().strip().encode()
    except OSError:
        out.write("8-Ball console: not configured.\r\n")
        return 2
    job_id = check_token(secret, argv[0])
    if not job_id:
        out.write("8-Ball console: this console link expired. Press Reconnect on the Console page.\r\n")
        return 2
    d = jobs_dir / job_id
    log = d / "console.log"
    job_file = d / "job.json"
    if not job_file.is_file():
        out.write("8-Ball console: job not found.\r\n")
        return 2
    job = json.loads(job_file.read_text())
    out.write(f"\x1b[1m8-Ball job {job['kind']} {job['params'].get('model') or job['params'].get('workflow')}"
              f" ({job_id[:8]})\x1b[0m  read-only view; closing this tab does not stop the job\r\n")
    out.flush()
    pos = 0
    while True:
        if log.is_file():
            with log.open(encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
            if chunk:
                out.write(chunk.replace("\n", "\r\n"))
                out.flush()
        try:
            state = json.loads(job_file.read_text()).get("state")
        except (OSError, ValueError):
            state = None
        if state in TERMINAL:
            with log.open(encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                rest = fh.read()
            if rest:
                out.write(rest.replace("\n", "\r\n"))
            out.write(f"\r\n\x1b[1mjob {state}\x1b[0m\r\n")
            out.flush()
            time.sleep(1)
            return 0
        time.sleep(0.5)

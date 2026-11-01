"""Authentication and request guards.

basic          the console's own users file (scrypt hashes), HTTP Basic over a TLS reverse proxy
trusted-proxy  a same-host reverse proxy authenticates and sets the user/role headers; the console
               accepts them only from configured proxy addresses (loopback by default)

Every state-changing request also needs: the admin role, a JSON body, the custom header
X-8Ball: 1, and no cross-site Sec-Fetch-Site / foreign Origin (CSRF guard).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from .config import Config


@dataclass
class User:
    name: str
    role: str  # admin | viewer


def hash_password(pw: str, n: int = 2**14, r: int = 8, p: int = 1) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


class Users:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime = -1.0
        self._users: dict[str, dict[str, Any]] = {}

    def _reload(self) -> None:
        try:
            m = self.path.stat().st_mtime
        except OSError:
            self._users = {}
            return
        if m != self._mtime:
            data = json.loads(self.path.read_text())
            self._users = {u["name"]: u for u in data.get("users", [])}
            self._mtime = m

    def check(self, name: str, pw: str) -> User | None:
        self._reload()
        u = self._users.get(name)
        if u and verify_password(pw, u.get("scrypt", "")):
            return User(name, "admin" if u.get("role") == "admin" else "viewer")
        verify_password(pw, "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        return None

    def add(self, name: str, role: str, pw: str) -> None:
        self._reload()
        data = {"users": [u for u in self._users.values() if u["name"] != name]}
        data["users"].append({"name": name, "role": role, "scrypt": hash_password(pw)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, self.path)


class Authenticator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.users = Users(cfg.users_file)

    def user(self, request: Request) -> User:
        if self.cfg.auth_mode == "trusted-proxy":
            peer = request.client.host if request.client else ""
            name = request.headers.get(self.cfg.proxy_user_header, "")
            if peer not in self.cfg.trusted_proxies or not name or len(name) > 64:
                raise HTTPException(401, "authentication required")
            role = request.headers.get(self.cfg.proxy_role_header, "viewer")
            return User(name, "admin" if role == "admin" else "viewer")
        hdr = request.headers.get("authorization", "")
        if hdr.lower().startswith("basic "):
            try:
                name, _, pw = base64.b64decode(hdr[6:]).decode().partition(":")
            except (ValueError, UnicodeDecodeError):
                name, pw = "", ""
            u = self.users.check(name, pw) if name else None
            if u:
                return u
        raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": 'Basic realm="8-Ball"'})


def guard_mutation(request: Request, user: User) -> None:
    if user.role != "admin":
        raise HTTPException(403, "admin role required")
    if request.headers.get("x-8ball") != "1":
        raise HTTPException(403, "missing X-8Ball header")
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "JSON body required")
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        raise HTTPException(403, "cross-site request refused")
    origin = request.headers.get("origin")
    if origin:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if origin.split("://", 1)[-1].rstrip("/") != host:
            raise HTTPException(403, "foreign origin refused")

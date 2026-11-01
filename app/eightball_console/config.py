"""Configuration: defaults < TOML file < environment. Nothing here is caller-controlled at runtime."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = "/etc/8ball/console.toml"


@dataclass(frozen=True)
class Instance:
    id: str
    label: str
    base_url: str


@dataclass
class Config:
    listen_host: str = "127.0.0.1"
    listen_port: int = 8788
    root_path: str = ""  # path prefix when served behind a reverse proxy (e.g. /apps/8ball)
    state_dir: Path = Path("/var/lib/8ball/console")
    profile_path: Path = Path("/var/lib/8ball/profile.v1.json")
    catalog_root: Path = Path("/opt/8ball/catalog")
    catalog_commit: str = ""
    # auth: "basic" (own users file) or "trusted-proxy" (a same-host reverse proxy authenticates)
    auth_mode: str = "basic"
    users_file: Path = Path("/etc/8ball/users.json")
    proxy_user_header: str = "X-8Ball-User"
    proxy_role_header: str = "X-8Ball-Role"
    trusted_proxies: tuple[str, ...] = ("127.0.0.1", "::1")
    instances: tuple[Instance, ...] = (Instance("local", "This machine", "http://127.0.0.1:11434"),)
    models_dir: Path = Path("/usr/share/ollama/.ollama/models")
    # offline: "auto" probes the registry; "on" forces offline; "off" assumes online
    offline: str = "auto"
    registry_probe_url: str = "https://registry.ollama.ai/v2/"
    profile_max_age_days: int = 30
    # console (ttyd) as seen by the browser, relative to the page (empty disables the terminal view)
    console_path: str = ""  # e.g. "tty/" when a read-only ttyd is proxied next to the app
    console_token_ttl: int = 300
    max_parallel_jobs: int = 1
    workflows_file: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def jobs_dir(self) -> Path:
        return self.state_dir / "jobs"

    @property
    def secret_file(self) -> Path:
        return self.state_dir / "console.secret"


def _apply(cfg: Config, data: dict[str, Any]) -> None:
    simple = {
        "listen_host": str, "listen_port": int, "root_path": str, "state_dir": Path, "profile_path": Path,
        "catalog_root": Path, "catalog_commit": str, "auth_mode": str, "users_file": Path,
        "proxy_user_header": str, "proxy_role_header": str, "models_dir": Path, "offline": str,
        "registry_probe_url": str, "profile_max_age_days": int, "console_path": str,
        "console_token_ttl": int, "max_parallel_jobs": int, "workflows_file": Path,
    }
    for key, typ in simple.items():
        if key in data and data[key] is not None:
            setattr(cfg, key, typ(data[key]))
    if "trusted_proxies" in data:
        cfg.trusted_proxies = tuple(str(x) for x in data["trusted_proxies"])
    if "instances" in data:
        out = []
        for raw in data["instances"]:
            iid = str(raw["id"])
            if not iid.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"bad instance id {iid!r}")
            out.append(Instance(iid, str(raw.get("label") or iid), str(raw["base_url"]).rstrip("/")))
        if not out:
            raise ValueError("at least one Ollama instance is required")
        cfg.instances = tuple(out)


ENV_MAP = {
    "EIGHTBALL_LISTEN_HOST": "listen_host", "EIGHTBALL_LISTEN_PORT": "listen_port",
    "EIGHTBALL_ROOT_PATH": "root_path", "EIGHTBALL_STATE_DIR": "state_dir",
    "EIGHTBALL_PROFILE": "profile_path", "EIGHTBALL_CATALOG_ROOT": "catalog_root",
    "EIGHTBALL_CATALOG_COMMIT": "catalog_commit", "EIGHTBALL_AUTH_MODE": "auth_mode",
    "EIGHTBALL_USERS_FILE": "users_file", "EIGHTBALL_OFFLINE": "offline",
    "EIGHTBALL_MODELS_DIR": "models_dir", "EIGHTBALL_CONSOLE_PATH": "console_path",
    "EIGHTBALL_WORKFLOWS_FILE": "workflows_file",
}


def load(path: str | os.PathLike[str] | None = None) -> Config:
    cfg = Config()
    p = Path(path or os.environ.get("EIGHTBALL_CONFIG") or DEFAULT_CONFIG)
    if p.is_file():
        with p.open("rb") as fh:
            _apply(cfg, tomllib.load(fh))
    env = {ENV_MAP[k]: v for k, v in os.environ.items() if k in ENV_MAP}
    _apply(cfg, env)
    if cfg.auth_mode not in {"basic", "trusted-proxy"}:
        raise ValueError("auth_mode must be basic or trusted-proxy")
    if cfg.offline not in {"auto", "on", "off"}:
        raise ValueError("offline must be auto, on or off")
    if cfg.root_path and not cfg.root_path.startswith("/"):
        raise ValueError("root_path must start with /")
    cfg.root_path = cfg.root_path.rstrip("/")
    return cfg

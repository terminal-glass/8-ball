from __future__ import annotations

import os
from pathlib import Path

ROOT_HOME = Path("/root")


def assert_user_home(home: Path) -> Path:
    """State and credentials belong in the installing user's home, never /root."""
    resolved = home.expanduser().resolve()
    if resolved == ROOT_HOME or ROOT_HOME in resolved.parents:
        raise PermissionError("refusing to store 8-BALL state or credentials under /root")
    return resolved


def write_private_file(path: Path, data: bytes, *, home: Path) -> Path:
    """Write a file as mode 600 inside a mode 700 directory under ``home``."""
    root = assert_user_home(home)
    target = path.expanduser()
    if not target.is_absolute():
        target = root / target
    resolved = target.resolve()
    if root != resolved and root not in resolved.parents:
        raise PermissionError("refusing to write a private 8-BALL file outside the user home")
    if resolved == ROOT_HOME or ROOT_HOME in resolved.parents:
        raise PermissionError("refusing to store 8-BALL state or credentials under /root")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(resolved.parent, 0o700)
    fd = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(resolved, 0o600)
    return resolved

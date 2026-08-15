#!/usr/bin/env python3
"""Safely extract a verified 8-BALL runtime tar.gz archive (no tarfile filter=)."""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path


def _is_safe_member_path(name: str) -> bool:
    if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
        return False
    return True


def _target_under_root(dest: Path, name: str) -> Path:
    target = (dest / name).resolve()
    dest_resolved = dest.resolve()
    if target != dest_resolved and not str(target).startswith(f"{dest_resolved}/"):
        raise ValueError(f"Archive path escapes staging root: {name}")
    return target


def extract_runtime_archive(archive_path: Path, dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not member.isreg():
                raise ValueError(f"Unsupported archive member type: {member.name}")
            name = member.name
            if not _is_safe_member_path(name):
                raise ValueError(f"Unsafe archive member path: {name}")
            target = _target_under_root(dest_root, name)
            src = tar.extractfile(member)
            if src is None:
                raise ValueError(f"Could not extract archive member: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read())


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: extract-runtime-archive.py ARCHIVE DEST", file=sys.stderr)
        return 2
    archive_path = Path(args[0])
    dest_root = Path(args[1])
    try:
        extract_runtime_archive(archive_path, dest_root)
    except ValueError as exc:
        print(f"[release] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

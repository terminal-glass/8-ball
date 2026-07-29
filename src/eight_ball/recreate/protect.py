from __future__ import annotations

from pathlib import Path

from eight_ball.config import load_yaml
from eight_ball.paths import CONFIG_DIR, LEGACY_FAMILIES_DIR, NORMALIZED_DIR, REPO_ROOT


def protected_legacy_paths() -> list[Path]:
    policy = load_yaml(CONFIG_DIR / "snapshot-policy.yaml")
    configured = policy.get("protected_legacy_paths", ["data/families", "data/normalized"])
    return [(REPO_ROOT / path).resolve() for path in configured]


def assert_candidate_output_path(path: Path) -> None:
    """Refuse writes that would land under protected legacy catalog paths."""
    resolved = path.resolve()
    for protected in protected_legacy_paths():
        try:
            resolved.relative_to(protected)
        except ValueError:
            continue
        raise PermissionError(
            f"Refusing to write candidate catalog under protected legacy path: {protected}"
        )


def assert_not_touching_legacy_families(path: Path) -> None:
    resolved = path.resolve()
    families = LEGACY_FAMILIES_DIR.resolve()
    try:
        resolved.relative_to(families)
    except ValueError:
        return
    raise PermissionError(f"Refusing to modify legacy family observations: {families}")


def assert_promote_target_is_normalized(path: Path) -> None:
    if path.resolve() != NORMALIZED_DIR.resolve():
        raise ValueError(f"Promote target must be {NORMALIZED_DIR}, got {path}")

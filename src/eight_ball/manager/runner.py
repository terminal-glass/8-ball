from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from eight_ball.config import load_json, write_json
from eight_ball.manager.secrets import assert_user_home, write_private_file

StageFunc = Callable[[], None]
HealthFunc = Callable[[str], bool]


class StageInterrupted(Exception):
    """A stage stopped before it finished."""


def run_stages(
    stages: list[dict[str, Any]],
    *,
    state_path: Path,
    home: Path,
    healthcheck: HealthFunc,
    force: bool = False,
) -> dict[str, Any]:
    """Run stages in order. Successful stages are skipped on rerun.

    A failed or interrupted stage stays failed until a later attempt succeeds.
    Overall success requires every stage health check to pass.
    """
    assert_user_home(home)
    state = _load_state(state_path)
    state.setdefault("stages", {})
    for stage in stages:
        stage_id = stage["id"]
        previous = state["stages"].get(stage_id)
        if previous and previous.get("status") == "success" and not force:
            state["stages"][stage_id] = {
                "status": "skipped",
                "recovery": None,
                "detail": "Already satisfied.",
                "last_success": True,
            }
            _save_state(state_path, state, home)
            continue
        try:
            stage["run"]()
            if not healthcheck(stage_id):
                raise RuntimeError("health check failed")
        except StageInterrupted:
            state["stages"][stage_id] = {
                "status": "interrupted",
                "recovery": stage["recovery"],
                "detail": "The stage was interrupted.",
                "last_success": False,
            }
            _save_state(state_path, state, home)
            return _failed(state, stage_id, stage["recovery"])
        except Exception as exc:  # noqa: BLE001 - record any stage failure and its recovery
            state["stages"][stage_id] = {
                "status": "failure",
                "recovery": stage["recovery"],
                "detail": str(exc),
                "last_success": False,
            }
            _save_state(state_path, state, home)
            return _failed(state, stage_id, stage["recovery"])
        state["stages"][stage_id] = {
            "status": "success",
            "recovery": None,
            "detail": "Health check passed.",
            "last_success": True,
        }
        _save_state(state_path, state, home)

    unhealthy = [stage["id"] for stage in stages if not healthcheck(stage["id"])]
    if unhealthy:
        recovery = "A completed stage failed its health check. Rerun that stage."
        return {
            "ok": False,
            "failed_stage": unhealthy[0],
            "recovery": recovery,
            "state": state,
        }
    return {"ok": True, "failed_stage": None, "recovery": None, "state": state}


def _failed(state: dict[str, Any], stage_id: str, recovery: str) -> dict[str, Any]:
    return {"ok": False, "failed_stage": stage_id, "recovery": recovery, "state": state}


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"stages": {}}
    return load_json(path)


def _save_state(path: Path, state: dict[str, Any], home: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, state)
    write_private_file(path, temporary.read_bytes(), home=home)
    temporary.unlink(missing_ok=True)

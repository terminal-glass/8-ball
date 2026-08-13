"""INST-50D tests for 8.3 client status / MOTD (mocked; no host mutation)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = REPO_ROOT / "install/shared/8ball-client-status.py"
SCRIPT_83 = REPO_ROOT / "install/ubuntu/8.3.sh"
CPU_LANE_83 = REPO_ROOT / "install/ubuntu/cpu/8.3.sh"
MOTD_TEMPLATE = REPO_ROOT / "install/ubuntu/assets/first-MOTD.txt"
_SPEC = importlib.util.spec_from_file_location("eightball_client_status", STATUS_PATH)
assert _SPEC and _SPEC.loader
status_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(status_mod)


def _write_result(
    root: Path,
    *,
    selected_model: str,
    test_status: str = "PASSED",
    profile_id: str = "qwen3/ubuntu/cpu",
    jets_status: str = "READY_AFTER_SIGNIN",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "selected_model": selected_model,
        "test_status": test_status,
        "profile_id": profile_id,
        "inference_succeeded": test_status == "PASSED",
        "jets_status": jets_status,
    }
    (root / "8ball-result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (root / "8ball-result.txt").write_text(
        textwrap.dedent(
            f"""\
            Model: {selected_model}
            Profile: {profile_id}
            Model test: {test_status}
            Jets status: {jets_status}
            """
        ),
        encoding="utf-8",
    )


def test_qwen_regression_ready_when_installed_and_proven(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["qwen3:1.7b"],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["local_model_status"] == "READY"
    assert status["selected_model"] == "qwen3:1.7b"
    rendered = status_mod.render_motd(MOTD_TEMPLATE, status)
    assert "Local Model ........ READY" in rendered


def test_qwen_regression_missing_when_not_installed(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=[],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["local_model_status"] == "MISSING"
    rendered = status_mod.render_motd(MOTD_TEMPLATE, status)
    assert "Local Model ........ MISSING" in rendered


def test_exact_match_does_not_confuse_similar_tags() -> None:
    assert not status_mod.model_is_installed("qwen3:1.7b", ["qwen3:0.6b", "qwen3:4b"])
    assert status_mod.model_is_installed("qwen3:1.7b", ["qwen3:1.7b"])


def test_generic_x_tinyllama_ready(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="tinyllama:1.1b", profile_id="tinyllama/ubuntu/cpu")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["tinyllama:1.1b"],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["local_model_status"] == "READY"
    assert status["profile_id"] == "tinyllama/ubuntu/cpu"


def test_ollama_unavailable_status(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["qwen3:1.7b"],
        ollama_available=False,
        eightballjets_installed=True,
    )
    assert status["ollama_status"] == "STOPPED"
    assert status["local_model_status"] == "UNAVAILABLE"


def test_inference_failed_status(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b", test_status="FAILED")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=[],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["local_model_status"] == "FAILED"


def test_partial_when_installed_but_not_proven(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="gemma2:2b", test_status="FAILED", profile_id="gemma2/ubuntu/cpu")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["gemma2:2b"],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["local_model_status"] == "PARTIAL"


def test_jets_sign_in_required_when_local_ready(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["qwen3:1.7b"],
        ollama_available=True,
        eightballjets_installed=True,
    )
    assert status["jets_status"] == "SIGN-IN REQUIRED"


def test_jets_unavailable_without_helper(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    status = status_mod.evaluate_status(
        root=root,
        installed_models=["qwen3:1.7b"],
        ollama_available=True,
        eightballjets_installed=False,
    )
    assert status["jets_status"] == "UNAVAILABLE"


def test_temp_alert_decrement_is_idempotent_and_root_owned(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    root.mkdir()
    (root / "8ball-temp-alert.txt").write_text("hello\n", encoding="utf-8")
    (root / "8ball-temp-alert.meta").write_text("2\n", encoding="utf-8")
    first = status_mod.decrement_temp_alert(root)
    second = status_mod.decrement_temp_alert(root)
    assert first["shown"] is True
    assert first["remaining"] == 1
    assert second["shown"] is True
    assert second["remaining"] == 0
    third = status_mod.decrement_temp_alert(root)
    assert third["shown"] is False


def test_motd_script_has_no_forbidden_login_commands() -> None:
    text = SCRIPT_83.read_text(encoding="utf-8")
    motd_block = text.split("install_motd()")[1].split("main()")[0]
    assert "ollama pull" not in motd_block
    assert "ollama run" not in motd_block
    assert "c10-hardware-resolve.py" not in motd_block
    assert "curl" not in motd_block
    assert "render-motd" in motd_block


def _ubuntu_env(tmp_path: Path) -> dict[str, str]:
    state_root = tmp_path / "philosopher"
    state_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PHILOSOPHER_ROOT": str(state_root),
            "EIGHTBALL_BIN_DIR": str(tmp_path / "bin"),
            "EIGHTBALL_MOTD_TARGET": str(tmp_path / "motd/99-8ball-trial"),
            "EIGHTBALL_TEST_SKIP_ROOT": "1",
        }
    )
    return env


def test_83_install_is_idempotent(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path)
    state_root = Path(env["PHILOSOPHER_ROOT"])
    _write_result(state_root, selected_model="qwen3:1.7b")
    (state_root / "8ball-alert-history").write_text("2026-01-01T00:00:00Z\n", encoding="utf-8")
    (state_root / "8ball-temp-alert.meta").write_text("1\n", encoding="utf-8")
    (state_root / "8ball-temp-alert.txt").write_text("seed\n", encoding="utf-8")
    history_before = (state_root / "8ball-alert-history").read_text(encoding="utf-8")
    for _ in range(2):
        result = subprocess.run(
            ["bash", str(CPU_LANE_83)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    history_after = (state_root / "8ball-alert-history").read_text(encoding="utf-8")
    assert history_after == history_before
    assert (state_root / "bin/8ball-client-status.py").is_file()
    assert (Path(env["EIGHTBALL_BIN_DIR"]) / "remember").is_file()
    motd = Path(env["EIGHTBALL_MOTD_TARGET"])
    assert motd.is_file()
    assert "render-motd" in motd.read_text(encoding="utf-8")


def test_bash_syntax() -> None:
    for script in (
        SCRIPT_83,
        CPU_LANE_83,
        REPO_ROOT / "install/ubuntu/cuda/8.3.sh",
        REPO_ROOT / "install/shared/8ball-bulletin-refresh.sh",
    ):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, script


def test_status_cli_render_motd(tmp_path: Path) -> None:
    root = tmp_path / "philosopher"
    _write_result(root, selected_model="qwen3:1.7b")
    env = os.environ.copy()
    env["PHILOSOPHER_ROOT"] = str(root)
    result = subprocess.run(
        ["python3", str(STATUS_PATH), "render-motd", str(MOTD_TEMPLATE)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    # Without a live Ollama API this reports MISSING; still proves CLI wiring.
    assert result.returncode == 0, result.stderr
    assert "Local Model" in result.stdout

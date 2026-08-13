"""INST-50C tests for 8.2 profile/model integration (mocked; no host mutation)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_RESOLVER = REPO_ROOT / "install/shared/c10-hardware-resolve.py"
CANONICAL_82 = REPO_ROOT / "install/ubuntu/8.2.sh"
CPU_LANE = REPO_ROOT / "install/ubuntu/cpu/8.2.sh"
CUDA_LANE = REPO_ROOT / "install/ubuntu/cuda/8.2.sh"
MANIFEST = REPO_ROOT / "data/generated/pages/install-manifest.json"


def _run_resolver(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["EIGHTBALL_REPO_ROOT"] = str(REPO_ROOT)
    if env:
        run_env.update(env)
    return subprocess.run(
        ["python3", str(SHARED_RESOLVER), "plan", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=run_env,
    )


def _measured_env(**overrides: str) -> dict[str, str]:
    base = {
        "EIGHTBALL_USE_MEASURED_HARDWARE_ENV": "1",
        "EIGHTBALL_SYSTEM_RAM_GB": "16.0",
        "EIGHTBALL_USABLE_MODEL_RAM_GB": "9.0",
        "EIGHTBALL_FREE_DISK_GB": "100.0",
        "EIGHTBALL_CPU_THREADS": "6",
        "EIGHTBALL_CUDA_AVAILABLE": "false",
        "EIGHTBALL_GPU_VRAM_GB": "0",
    }
    base.update(overrides)
    return base


def _write_mock_bin(mock_bin: Path) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    scripts = {
        "curl": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            url=""
            args=("$@")
            for arg in "${args[@]}"; do
              case "${arg}" in
                http://*|https://*) url="${arg}" ;;
              esac
            done
            if [[ "${url}" == *"/api/tags" ]]; then
              echo '{"models":[]}'
              exit 0
            fi
            if [[ "${url}" == *"/api/generate" ]]; then
              if [[ "${MOCK_GENERATE_FAIL:-}" == "1" ]]; then
                echo '{"response":"nope"}'
                exit 0
              fi
              echo '{"response":"8-BALL READY"}'
              exit 0
            fi
            exit 1
            """
        ),
        "ollama": textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            LOG="${MOCK_OLLAMA_LOG:-/dev/null}"
            case "${1:-}" in
              list)
                if [[ -f "${MOCK_OLLAMA_LIST_FILE:-}" ]]; then
                  cat "${MOCK_OLLAMA_LIST_FILE}"
                else
                  echo "NAME"
                fi
                ;;
              pull)
                echo "pull $2" >>"${LOG}"
                if [[ "${MOCK_OLLAMA_PULL_FAIL:-}" == "$2" ]]; then
                  exit 1
                fi
                ;;
              rm)
                echo "rm $2" >>"${LOG}"
                ;;
            esac
            exit 0
            """
        ),
    }
    for name, body in scripts.items():
        path = mock_bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(stat.S_IRWXU)


def _ubuntu_env(tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    mock_bin = tmp_path / "mock-bin"
    state_root = tmp_path / "philosopher"
    state_root.mkdir(parents=True, exist_ok=True)
    _write_mock_bin(mock_bin)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{mock_bin}:{env.get('PATH', '')}",
            "PHILOSOPHER_ROOT": str(state_root),
            "EIGHTBALL_REPO_ROOT": str(REPO_ROOT),
            "EIGHTBALL_INSTALL_LANE": "ubuntu/cpu",
            "EIGHTBALL_BIN_DIR": str(tmp_path / "bin"),
            "MOCK_OLLAMA_LOG": str(tmp_path / "ollama.log"),
            "MOCK_OLLAMA_LIST_FILE": str(tmp_path / "ollama-list.txt"),
            **_measured_env(),
        }
    )
    if extra:
        env.update(extra)
    return env


def _run_82(script: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=script.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_resolver_syntax() -> None:
    result = subprocess.run(["python3", "-m", "py_compile", str(SHARED_RESOLVER)], check=False)
    assert result.returncode == 0


def test_qwen_y_path_uses_runtime_profile_fit() -> None:
    result = _run_resolver("--slug", "qwen3", "--lane", "ubuntu/cpu", env=_measured_env())
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["model_slug"] == "qwen3"
    assert payload["profile_id"] == "qwen3/ubuntu/cpu"
    assert payload["selection_source"] == "profile-runtime-fit"
    assert payload["candidates"]
    assert all(ref.startswith("qwen3:") for ref in payload["candidates"])


def test_tinyllama_x_path_without_qwen_branch() -> None:
    result = _run_resolver("--slug", "tinyllama", "--lane", "ubuntu/cpu", env=_measured_env())
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["model_slug"] == "tinyllama"
    assert payload["candidates"]
    assert all(ref.startswith("tinyllama:") for ref in payload["candidates"])
    assert "qwen3" not in payload["candidates"]


def test_reference_slug_without_explicit_slug() -> None:
    result = _run_resolver("--lane", "ubuntu/cpu", env=_measured_env())
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["model_slug"] == "qwen3"
    assert payload["model_slug_source"] == "data:base-pilot-menu.reference"


def test_ordered_candidates_largest_fit_first() -> None:
    result = _run_resolver("--slug", "tinyllama", "--lane", "ubuntu/cpu", env=_measured_env())
    payload = json.loads(result.stdout)
    chain = {row["ollama_ref"]: row for row in payload["fallback_chain"]}
    counts = [chain[ref]["parameter_count"] for ref in payload["candidates"] if ref in chain]
    assert counts == sorted(counts, reverse=True)


def test_ram_gate_excludes_oversized_candidates() -> None:
    env = _measured_env(
        EIGHTBALL_SYSTEM_RAM_GB="1.0",
        EIGHTBALL_USABLE_MODEL_RAM_GB="0.6",
        EIGHTBALL_FREE_DISK_GB="100.0",
    )
    result = _run_resolver("--slug", "tinyllama", "--lane", "ubuntu/cpu", env=env)
    assert result.returncode != 0
    assert "No approved profile candidates" in result.stderr


def test_manual_model_rejected_when_gates_fail() -> None:
    env = _measured_env(
        EIGHTBALL_SYSTEM_RAM_GB="1.0",
        EIGHTBALL_USABLE_MODEL_RAM_GB="0.6",
        EIGHTBALL_FREE_DISK_GB="1.0",
    )
    result = _run_resolver(
        "--slug",
        "tinyllama",
        "--lane",
        "ubuntu/cpu",
        "--model",
        "tinyllama:1.1b",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["manual_selection_status"] == "rejected-by-gates"
    assert payload["candidates"] == ["tinyllama:1.1b"]


def test_manual_model_unknown_metadata_is_explicit() -> None:
    result = _run_resolver(
        "--slug",
        "tinyllama",
        "--lane",
        "ubuntu/cpu",
        "--model",
        "tinyllama:does-not-exist",
        env=_measured_env(),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["manual_selection_status"] == "unknown-metadata"


def test_missing_slug_fails_closed() -> None:
    empty = REPO_ROOT / "tests" / "fixtures" / "inst_50c_empty_repo"
    empty.mkdir(parents=True, exist_ok=True)
    (empty / "profiles").mkdir(exist_ok=True)
    (empty / "install").mkdir(exist_ok=True)
    result = _run_resolver(
        "--lane",
        "ubuntu/cpu",
        env={"EIGHTBALL_REPO_ROOT": str(empty)},
    )
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "Missing model slug" in combined


def test_disk_thresholds_come_from_profile_sizes() -> None:
    result = _run_resolver("--slug", "tinyllama", "--lane", "ubuntu/cpu", env=_measured_env())
    payload = json.loads(result.stdout)
    assert payload["minimum_disk_mib"]
    for mib in payload["minimum_disk_mib"].values():
        assert mib > 0


def test_canonical_82_bash_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(CANONICAL_82)], check=False)
    assert result.returncode == 0


@pytest.mark.parametrize("lane_script", [CPU_LANE, CUDA_LANE])
def test_lane_wrappers_delegate_and_pass_syntax(lane_script: Path) -> None:
    result = subprocess.run(["bash", "-n", str(lane_script)], check=False)
    assert result.returncode == 0
    text = lane_script.read_text(encoding="utf-8")
    assert 'exec "${SCRIPT_DIR}/../8.2.sh"' in text


def test_82_automatic_happy_path_mocked(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path)
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 0, result.stderr
    payload = json.loads((Path(env["PHILOSOPHER_ROOT"]) / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["test_status"] == "PASSED"
    assert payload["profile_id"] == "tinyllama/ubuntu/cpu"
    assert payload["inference_succeeded"] is True
    assert payload["selected_model"].startswith("tinyllama:")


def test_82_manual_model_no_fallback(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path, {"MOCK_GENERATE_FAIL": "1"})
    result = _run_82(CPU_LANE, env, "--model", "tinyllama:1.1b")
    assert result.returncode == 1
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "pull tinyllama:1.1b" in log
    assert "pull qwen3" not in log


def test_82_pull_failure_falls_back_to_next_candidate(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path, {"MOCK_OLLAMA_PULL_FAIL": "tinyllama:1.1b-chat-v0.6-fp16"})
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 0, result.stderr
    payload = json.loads((Path(env["PHILOSOPHER_ROOT"]) / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["selected_model"] != "tinyllama:1.1b-chat-v0.6-fp16"
    assert len(payload["attempts"]) >= 2


def test_82_inference_failure_falls_back_mocked(tmp_path: Path) -> None:
    env = _ubuntu_env(
        tmp_path,
        {
            "MOCK_GENERATE_FAIL": "1",
            "MOCK_OLLAMA_PULL_FAIL": "",
        },
    )
    (Path(env["MOCK_OLLAMA_LIST_FILE"])).write_text("NAME\n", encoding="utf-8")
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 1
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "rm tinyllama:" in log


def test_82_preexisting_model_not_removed_on_fallback(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path, {"MOCK_OLLAMA_PULL_FAIL": "tinyllama:1.1b-chat-v0.6-fp16"})
    list_file = Path(env["MOCK_OLLAMA_LIST_FILE"])
    list_file.write_text("NAME\ntinyllama:1.1b-chat-v0.6-fp16\n", encoding="utf-8")
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 0, result.stderr
    log = Path(env["MOCK_OLLAMA_LOG"]).read_text(encoding="utf-8")
    assert "rm tinyllama:1.1b-chat-v0.6-fp16" not in log


def test_disk_gate_excludes_candidates_at_resolver() -> None:
    env = _measured_env(
        EIGHTBALL_SYSTEM_RAM_GB="16.0",
        EIGHTBALL_USABLE_MODEL_RAM_GB="9.0",
        EIGHTBALL_FREE_DISK_GB="1.0",
    )
    result = _run_resolver("--slug", "tinyllama", "--lane", "ubuntu/cpu", env=env)
    assert result.returncode != 0
    assert "No approved profile candidates" in result.stderr


def test_82_chain_uses_profile_disk_metadata(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path)
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 0, result.stderr
    payload = json.loads((Path(env["PHILOSOPHER_ROOT"]) / "8ball-result.json").read_text(encoding="utf-8"))
    assert payload["attempts"]
    assert payload["attempts"][0]["resource_gate"] == "PASSED"


def test_82_manual_gate_rejection(tmp_path: Path) -> None:
    env = _ubuntu_env(
        tmp_path,
        {
            "EIGHTBALL_SYSTEM_RAM_GB": "1.0",
            "EIGHTBALL_USABLE_MODEL_RAM_GB": "0.6",
            "EIGHTBALL_FREE_DISK_GB": "1.0",
        },
    )
    result = _run_82(
        CPU_LANE,
        env,
        "--model-slug",
        "tinyllama",
        "--model",
        "tinyllama:1.1b",
    )
    assert result.returncode == 1
    assert "does not fit measured hardware" in result.stderr


def test_82_result_artifact_fields_for_83(tmp_path: Path) -> None:
    env = _ubuntu_env(tmp_path)
    result = _run_82(CPU_LANE, env, "--model-slug", "tinyllama")
    assert result.returncode == 0, result.stderr
    payload = json.loads((Path(env["PHILOSOPHER_ROOT"]) / "8ball-result.json").read_text(encoding="utf-8"))
    for key in (
        "selected_model",
        "test_status",
        "profile_id",
        "selection_source",
        "inference_succeeded",
        "attempts",
        "fallback_chain",
    ):
        assert key in payload


def test_manifest_fallback_when_profile_has_no_runtime_fits(tmp_path: Path) -> None:
    env = _measured_env(
        EIGHTBALL_SYSTEM_RAM_GB="0.5",
        EIGHTBALL_USABLE_MODEL_RAM_GB="0.3",
        EIGHTBALL_FREE_DISK_GB="0.1",
    )
    result = _run_resolver(
        "--slug",
        "qwen3",
        "--lane",
        "ubuntu/cpu",
        "--manifest",
        str(MANIFEST),
        env=env,
    )
    # Too little RAM for any profile fit; should fail closed rather than hidden Qwen ladder.
    assert result.returncode != 0

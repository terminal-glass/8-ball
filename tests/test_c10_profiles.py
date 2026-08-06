from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_C10_COMMON_PATH = REPO_ROOT / "scripts" / "c10_common.py"
_SPEC = importlib.util.spec_from_file_location("c10_common", _C10_COMMON_PATH)
assert _SPEC and _SPEC.loader
c10_common = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = c10_common
_SPEC.loader.exec_module(c10_common)


def test_c10_test_module_has_no_shebang() -> None:
    text = (REPO_ROOT / "tests" / "test_c10_profiles.py").read_text(encoding="utf-8")
    assert not text.startswith("#!"), "pytest modules must not include a shebang"


def test_c10_validator_passes() -> None:
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "scripts/validate-c10-profiles.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload["valid"] is True
    assert payload["stats"]["model_pages"] >= 200
    assert payload["stats"]["install_lanes"] == 10


def test_model_page_shape() -> None:
    page_path = REPO_ROOT / "profiles/qwen3.json"
    assert page_path.is_file()
    page = json.loads(page_path.read_text(encoding="utf-8"))
    assert page["model_slug"] == "qwen3"
    assert page["sizes"][0]["parameter_count"] >= page["sizes"][1]["parameter_count"]


def test_provider_assumptions_exist() -> None:
    expected = REPO_ROOT / "profiles/provider-assumptions/ubuntu-cpu.json"
    assert expected.is_file()
    payload = json.loads(expected.read_text(encoding="utf-8"))
    assert payload["detection_signals"]
    hardware = payload["hardware"]
    assert hardware.get("cuda_available") is False
    assert hardware.get("total_vram_gb") in (None, 0)


def test_digitalocean_gpu_csv_headers_map_to_capacity() -> None:
    plans = c10_common.load_digitalocean_gpu_plans(REPO_ROOT)
    assert plans
    baseline = c10_common.smallest_digitalocean_gpu_plan(plans)
    assert baseline is not None
    assert baseline["ram_gb"] == 32
    assert baseline["disk_gb"] == 500
    assert baseline["total_vram_gb"] == 20
    assert baseline["vram_gb_per_gpu"] == 20


def test_digitalocean_total_vram_uses_gpu_count() -> None:
    plans = c10_common.load_digitalocean_gpu_plans(REPO_ROOT)
    h100 = next(plan for plan in plans if plan["plan_id"] == "do-gpu-h100-1x-8x")
    assert h100["gpu_count"] == 1
    assert h100["total_vram_gb"] == 80


def test_qwen3_235b_does_not_fit_smallest_digitalocean_gpu_plan() -> None:
    plans = c10_common.load_digitalocean_gpu_plans(REPO_ROOT)
    baseline = c10_common.smallest_digitalocean_gpu_plan(plans)
    assert baseline is not None
    hardware = {
        "system_ram_gb": baseline["ram_gb"],
        "usable_model_ram_gb": round((baseline["ram_gb"] or 0) * 0.6, 2),
        "minimum_free_disk_gb": baseline["disk_gb"],
        "total_vram_gb": baseline["total_vram_gb"],
        "cuda_available": True,
    }
    lane = {"gpu_lane": True}
    page = json.loads((REPO_ROOT / "profiles/qwen3.json").read_text(encoding="utf-8"))
    target = next(size for size in page["sizes"] if size["ollama_ref"] == "qwen3:235b")
    fit = c10_common.evaluate_lane_fit(target, lane, hardware)
    assert fit.fit_status == "no_fit"
    assert fit.fits is False


def test_aws_lightsail_gpu_unknown_vram_is_not_confirmed_fit() -> None:
    plans = c10_common.load_aws_lightsail_gpu_plans(REPO_ROOT)
    baseline = c10_common.smallest_aws_lightsail_gpu_plan(plans)
    assert baseline is not None
    hardware = {
        "system_ram_gb": baseline["ram_gb"],
        "usable_model_ram_gb": round((baseline["ram_gb"] or 0) * 0.6, 2),
        "minimum_free_disk_gb": baseline["disk_gb"],
        "total_vram_gb": None,
        "cuda_available": None,
    }
    lane = {"gpu_lane": True}
    page = json.loads((REPO_ROOT / "profiles/qwen3.json").read_text(encoding="utf-8"))
    target = next(size for size in page["sizes"] if size["ollama_ref"] == "qwen3:0.6b")
    fit = c10_common.evaluate_lane_fit(target, lane, hardware)
    assert fit.fit_status == "unknown"
    assert fit.fits is False


def test_selector_never_chooses_unknown_fit() -> None:
    env = os.environ.copy()
    env["EIGHTBALL_REPO_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "install/shared/c10-select-model.py"),
            "qwen3",
            "cloud/aws-lightsail/gpu",
            "profiles/provider-assumptions/cloud-aws-lightsail-gpu.json",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=REPO_ROOT,
    )
    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["selection_status"] == "unverified"
    assert payload["selected_ollama_ref"] is None


def test_selector_chooses_confirmed_fit_on_cpu_lane() -> None:
    env = os.environ.copy()
    env["EIGHTBALL_REPO_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "install/shared/c10-select-model.py"),
            "gemma",
            "ubuntu/cpu",
            "profiles/provider-assumptions/ubuntu-cpu.json",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=REPO_ROOT,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["selection_status"] == "selected"
    assert payload["selected_ollama_ref"]


def test_aws_provisional_csv_is_registered() -> None:
    from eight_ball.agents_csv.registry import source_specs

    paths = {spec.path for spec in source_specs()}
    assert "AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv" in paths


def test_trial_install_raw_profiles_base_construction() -> None:
    script = (REPO_ROOT / "trial-install.sh").read_text(encoding="utf-8")
    assert "EIGHTBALL_PROFILES_BASE" in script
    assert "RAW_BASE" in script


def test_trial_install_local_checkout(tmp_path: Path) -> None:
    result = subprocess.run(["bash", "-n", str(REPO_ROOT / "trial-install.sh")], check=False)
    assert result.returncode == 0


def test_trial_install_isolated_copy(tmp_path: Path) -> None:
    copy_root = tmp_path / "copy"
    shutil.copytree(REPO_ROOT / "install", copy_root / "install")
    shutil.copytree(REPO_ROOT / "profiles", copy_root / "profiles")
    shutil.copy(REPO_ROOT / "trial-install.sh", copy_root / "trial-install.sh")
    env = os.environ.copy()
    env["EIGHTBALL_REPO_ROOT"] = str(copy_root)
    result = subprocess.run(
        ["python3", str(copy_root / "install/shared/c10-select-model.py"), "gemma", "ubuntu/cpu", "profiles/provider-assumptions/ubuntu-cpu.json"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=copy_root,
    )
    assert result.returncode == 0, result.stderr


def test_missing_profile_errors_clearly() -> None:
    env = os.environ.copy()
    env["EIGHTBALL_REPO_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "install/shared/c10-select-model.py"),
            "definitely-not-a-real-model-slug-xyz",
            "ubuntu/cpu",
            "profiles/provider-assumptions/ubuntu-cpu.json",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "Missing profile document" in result.stderr or "Missing profile document" in result.stdout

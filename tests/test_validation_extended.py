from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from eight_ball.generate.deployments import stable_deployment_id
from eight_ball.normalize.catalog import build_catalog
from eight_ball.report.summary import write_reports
from eight_ball.validate.catalog import ValidationError, validate_catalog

FIXTURE_DIR = Path("tests/fixtures/families")


def _sample_catalog():
    return build_catalog(families_dir=FIXTURE_DIR, sample_only=False)


def test_duplicate_publisher_detection():
    catalog = _sample_catalog()
    catalog["publishers"].append(dict(catalog["publishers"][0]))
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("duplicate publisher" in error for error in exc.value.errors)


def test_orphan_model_reference():
    catalog = _sample_catalog()
    catalog["models"][0]["family_id"] = "missing-family"
    with pytest.raises(ValidationError):
        validate_catalog(catalog)


def test_alias_target_validation():
    catalog = _sample_catalog()
    catalog["tags"][0]["alias_target"] = "missing:tag"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("alias_target" in error for error in exc.value.errors)


def test_default_tag_validation():
    catalog = _sample_catalog()
    catalog["models"][0]["default_tag"] = "missing:tag"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("default_tag" in error for error in exc.value.errors)


def test_pull_run_equality_validation():
    catalog = _sample_catalog()
    catalog["tags"][0]["pull_command"] = "ollama pull wrong"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("pull_command" in error for error in exc.value.errors)


def test_provenance_requirements():
    catalog = _sample_catalog()
    catalog["tags"][0]["provenance"] = {}
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("provenance" in error for error in exc.value.errors)


def test_unsupported_quantization():
    catalog = _sample_catalog()
    catalog["tags"][0]["quantization"] = "not-a-real-quant"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("unsupported quantization" in error for error in exc.value.errors)


def test_invalid_capability_value():
    catalog = _sample_catalog()
    catalog["models"][0]["capabilities"]["chat"] = "maybe"
    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog)
    assert any("invalid capability value" in error for error in exc.value.errors)


def test_stable_generated_identifiers():
    first = stable_deployment_id("tag-a", "gpu-entry", "interactive")
    second = stable_deployment_id("tag-a", "gpu-entry", "interactive")
    assert first == second


def test_reporting_includes_deployment_count(tmp_path, monkeypatch):
    from eight_ball.paths import NORMALIZED_DIR

    generated = tmp_path / "generated"
    reports = tmp_path / "reports"
    generated.mkdir()
    deployments = [{"id": "abc", "tag_id": "t1", "hardware_profile_id": "cpu-small", "runtime_policy_id": "interactive", "assessment": "unknown", "reason_codes": [], "explanation": "x"}]
    (generated / "deployment_recommendations.json").write_text(json.dumps(deployments), encoding="utf-8")
    monkeypatch.setattr("eight_ball.report.summary.GENERATED_DIR", generated)
    monkeypatch.setattr("eight_ball.report.summary.REPORTS_DIR", reports)
    monkeypatch.setattr("eight_ball.report.summary.NORMALIZED_DIR", NORMALIZED_DIR)

    path = write_reports(generation_summary={"deployment_combinations": 1})
    text = path.read_text(encoding="utf-8")
    assert "Deployment combinations: 1" in text


def test_generated_recommendation_validation(tmp_path, monkeypatch):
    from eight_ball.validate.catalog import validate_catalog

    generated = tmp_path / "generated"
    generated.mkdir()
    catalog = _sample_catalog()
    tag_id = catalog["tags"][0]["id"]
    deployments = [
        {
            "id": "dup",
            "tag_id": tag_id,
            "hardware_profile_id": "cpu-small",
            "runtime_policy_id": "interactive",
            "assessment": "unknown",
            "reason_codes": [],
            "explanation": "ok",
        },
        {
            "id": "dup",
            "tag_id": "missing-tag",
            "hardware_profile_id": "missing-profile",
            "runtime_policy_id": "interactive",
            "assessment": "unknown",
            "reason_codes": [],
            "explanation": "bad",
        },
    ]
    (generated / "deployment_recommendations.json").write_text(
        json.dumps(deployments), encoding="utf-8"
    )
    monkeypatch.setattr("eight_ball.validate.catalog.GENERATED_DIR", generated)

    with pytest.raises(ValidationError) as exc:
        validate_catalog(catalog, include_artifacts=True, generated_dir=generated)
    errors = exc.value.errors
    assert any("duplicate deployment recommendation" in error for error in errors)
    assert any("references missing tag" in error for error in errors)
    assert any("references missing hardware profile" in error for error in errors)


def test_hardware_profile_validation(monkeypatch):
    from eight_ball import config as config_module

    def bad_profiles():
        return {
            "profiles": [
                {
                    "id": "broken-profile",
                    "display_name": "Broken",
                    "system_ram_gb": -1,
                    "vram_gb": 0,
                    "cpu_only": True,
                    "notes": "invalid",
                }
            ]
        }

    monkeypatch.setattr(config_module, "hardware_profiles_config", bad_profiles)
    monkeypatch.setattr(
        "eight_ball.validate.catalog.hardware_profiles_config",
        bad_profiles,
    )
    monkeypatch.setattr(
        "eight_ball.validate.catalog._known_hardware_profile_ids",
        lambda: {"broken-profile"},
    )

    with pytest.raises(ValidationError) as exc:
        validate_catalog(_sample_catalog())
    assert any("hardware_profile" in error for error in exc.value.errors)


def test_wrapper_runs_without_pip_install():
    result = subprocess.run(
        ["bash", "scripts/validate-catalog.sh", "--fixture", "--offline"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert "pip install" not in (result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr


def test_legacy_normalization_is_deterministic():
    first = build_catalog(families_dir=FIXTURE_DIR, sample_only=False)
    second = build_catalog(families_dir=FIXTURE_DIR, sample_only=False)
    assert first == second

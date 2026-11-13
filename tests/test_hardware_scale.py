from __future__ import annotations

import json

from eight_ball.config import load_yaml
from eight_ball.manager.consult import consult
from eight_ball.paths import CONFIG_DIR, NORMALIZED_DIR, REPO_ROOT
from eight_ball.scale import legacy_level, load_scale, place_by_ram, scale_errors


def _catalog(*tags: dict) -> dict:
    return {"tags": list(tags)}


def _tag(identifier: str, availability: str, size: int | None = 638_000_000) -> dict:
    return {
        "ollama_identifier": identifier,
        "availability": availability,
        "download_size_bytes": size,
        "parameter_count": 1_100_000_000,
        "quantization": "q4_0",
    }


def test_scale_is_zero_through_nine_and_keeps_stage_numbers():
    document = load_scale()
    assert scale_errors(document) == []
    assert [row["level"] for row in document["levels"]] == list(range(10))
    assert document["levels"][0]["display_name"] == "Raspberry Pi class"
    assert document["levels"][9]["display_name"] == "Top of the line"
    assert legacy_level(document, "cloud-only") is None
    assert legacy_level(document, "cpu-small") == 2
    assert legacy_level(document, "multi-gpu") == 8
    deployment = load_yaml(CONFIG_DIR / "deployment_types.yaml")
    assert [row["deployment_type_id"] for row in deployment["deployment_types"]] == [
        "3",
        "4",
        "5",
        "6",
        "7",
    ]
    profiles = load_yaml(CONFIG_DIR / "hardware_profiles.yaml")["profiles"]
    by_id = {row["id"]: row for row in profiles}
    assert by_id["cpu-small"]["scale_level"] == 2
    assert "scale_level" not in by_id["cloud-only"]


def test_ram_placement_uses_measured_bytes():
    document = load_scale()
    low = place_by_ram(document, 1_000_000_000)
    assert low["level"] == 0
    assert low["evidence"] == "measured"
    desktop = place_by_ram(document, 16_000_000_000)
    assert desktop["level"] == 4
    unknown = place_by_ram(document, None)
    assert unknown["level"] is None
    assert unknown["evidence"] == "unknown"


def test_jets_are_official_cloud_tags_and_gaps_stay_gaps():
    catalog = _catalog(
        _tag("tinyllama:1.1b", "local"),
        _tag("llama3.2:1b", "local", 1_300_000_000),
        _tag("someone/llama:cloud", "cloud_only", None),
        _tag("llama3.2:cloud", "cloud_only", None),
    )
    offer = consult(
        catalog,
        ram_bytes=16_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed=set(),
    )
    by_id = {row["id"]: row for row in offer["options"]}
    assert by_id["llama"]["offered"] is True
    assert by_id["llama"]["tag"] == "llama3.2:cloud"
    assert by_id["llama"]["local_download"] is False
    assert by_id["llama"]["runtime"] == "ollama-cloud"
    assert by_id["grok"]["offered"] is False
    assert offer["consultation"]["runner"] == "local"
    assert offer["install_performed"] is False


def test_level_zero_canary_miss_offers_unconfirmed_openclaw_path():
    catalog = _catalog(_tag("tinyllama:1.1b", "local"))
    offer = consult(
        catalog,
        ram_bytes=1_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
    )
    assert offer["level"] == 0
    assert offer["canary"]["fits"] is False
    assert offer["canary"]["ran"] is False
    assert offer["consultation"]["runner"] == "openclaw"
    assert offer["consultation"]["status"] == "awaiting_jonathan_confirmation"
    assert offer["consultation"]["uses"] == "ollama-cloud"
    assert offer["consultation"]["invoked"] is False
    assert offer["consultation"]["implemented"] is False


def test_slow_level_one_canary_is_measured_and_flags_openclaw():
    catalog = _catalog(_tag("tinyllama:1.1b", "local"))
    offer = consult(
        catalog,
        ram_bytes=5_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
        measurement={"eval_count": 1, "elapsed_seconds": 10},
    )
    assert offer["level"] == 1
    assert offer["canary"]["ran"] is True
    assert offer["canary"]["evidence"] == "measured"
    assert offer["canary"]["tokens_per_second"] == 0.1
    assert offer["consultation"]["runner"] == "openclaw"
    assert offer["consultation"]["invoked"] is False


def test_missing_eval_count_does_not_invent_speed():
    catalog = _catalog(_tag("tinyllama:1.1b", "local"))
    offer = consult(
        catalog,
        ram_bytes=16_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
        measurement={"done": True},
    )
    assert offer["canary"]["tokens_per_second"] is None
    assert offer["canary"]["ran"] is False
    assert "unmeasured" in offer["canary"]["reason"]
    assert offer["level"] == 4


def test_catalog_snapshot_has_no_official_llama_or_grok_cloud_tag():
    tags = json.loads((NORMALIZED_DIR / "tags.json").read_text(encoding="utf-8"))
    offer = consult(
        {"tags": tags},
        ram_bytes=16_000_000_000,
        disk_free_bytes=80_000_000_000,
        installed=set(),
    )
    by_id = {row["id"]: row for row in offer["options"]}
    assert by_id["llama"]["offered"] is False
    assert by_id["grok"]["offered"] is False
    assert by_id["llama"]["tag"] is None
    assert "no official Llama-family or Grok-family" in by_id["llama"]["reason"]


def test_consultation_script_is_letter_suffixed():
    script = (REPO_ROOT / "install/shared/8.4b-consult.sh").read_text(encoding="utf-8")
    assert "8.4b" in script
    assert "exec python3 -m eight_ball.manager consult" in script
    assert '"$@"' in script
    assert "/root" in script
    text = (REPO_ROOT / "config/deployment_types.yaml").read_text(encoding="utf-8")
    assert 'deployment_type_id: "3"' in text
    assert 'deployment_type_id: "8"' not in text

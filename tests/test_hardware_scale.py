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


def test_larger_level_drops_canary_and_jets_is_grok_cloud():
    catalog = _catalog(
        _tag("tinyllama:1.1b", "local"),
        _tag("llama3.2:3b", "local", 2_000_000_000),
        _tag("someone/grok:cloud", "cloud_only", None),
        _tag("grok:cloud", "cloud_only", None),
    )
    offer = consult(
        catalog,
        ram_bytes=16_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed=set(),
    )
    by_id = {row["id"]: row for row in offer["options"]}
    assert offer["level"] == 4
    assert offer["canary"]["dropped"] is True
    assert "canary" not in by_id
    assert by_id["llama"]["tag"] == "llama3.2:3b"
    assert by_id["llama"]["local_download"] is True
    assert by_id["jets"]["offered"] is True
    assert by_id["jets"]["tag"] == "grok:cloud"
    assert by_id["jets"]["local_download"] is False
    assert offer["consultation"]["runner"] == "local"
    assert offer["install_performed"] is False


def test_level_zero_canary_too_large_uses_openclaw_when_capable():
    catalog = _catalog(_tag("tinyllama:1.1b", "local"))
    offer = consult(
        catalog,
        ram_bytes=1_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
        openclaw_capable=True,
    )
    assert offer["level"] == 0
    assert offer["canary"]["fits"] is False
    assert offer["canary"]["ran"] is False
    assert offer["consultation"]["runner"] == "openclaw"
    assert offer["consultation"]["status"] == "openclaw-capable"
    assert offer["consultation"]["invoked"] is False
    assert offer["consultation"]["implemented"] is False
    unknown = consult(
        catalog,
        ram_bytes=1_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
    )
    assert unknown["consultation"]["status"] == "openclaw-capability-unknown"
    assert unknown["consultation"]["invoked"] is False


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
    assert offer["consultation"]["runner"] == "local"


def test_missing_eval_count_does_not_invent_speed():
    catalog = _catalog(_tag("tinyllama:1.1b", "local"))
    offer = consult(
        catalog,
        ram_bytes=5_000_000_000,
        disk_free_bytes=20_000_000_000,
        installed={"tinyllama:1.1b"},
        measurement={"done": True},
    )
    assert offer["canary"]["tokens_per_second"] is None
    assert offer["canary"]["ran"] is False
    assert "unmeasured" in offer["canary"]["reason"]
    assert offer["level"] == 1
    assert offer["consultation"]["runner"] == "local"


def test_catalog_snapshot_recommends_local_llama_and_records_grok_gap():
    tags = json.loads((NORMALIZED_DIR / "tags.json").read_text(encoding="utf-8"))
    offer = consult(
        {"tags": tags},
        ram_bytes=16_000_000_000,
        disk_free_bytes=80_000_000_000,
        installed=set(),
        focus="code",
    )
    by_id = {row["id"]: row for row in offer["options"]}
    assert offer["canary"]["dropped"] is True
    assert by_id["llama"]["offered"] is True
    assert by_id["llama"]["tag"] == "llama3.2:3b"
    assert by_id["jets"]["offered"] is False
    assert by_id["jets"]["tag"] is None
    assert "no" in by_id["jets"]["reason"] and "Grok" in by_id["jets"]["reason"]
    assert by_id["qwen"]["tentative"] is True
    assert by_id["qwen"]["tag"] == "qwen2.5-coder:7b"
    assert by_id["qwen"]["status"] == "tentative"


def test_consultation_script_is_letter_suffixed():
    script = (REPO_ROOT / "install/shared/8.4b-consult.sh").read_text(encoding="utf-8")
    assert "8.4b" in script
    assert "exec python3 -m eight_ball.manager consult" in script
    assert '"$@"' in script
    assert "/root" in script
    text = (REPO_ROOT / "config/deployment_types.yaml").read_text(encoding="utf-8")
    assert 'deployment_type_id: "3"' in text
    assert 'deployment_type_id: "8"' not in text

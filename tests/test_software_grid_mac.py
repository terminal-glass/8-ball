"""Checks for the macOS column of the shared per-OS software grid."""
from __future__ import annotations

from eight_ball.config import load_yaml
from eight_ball.paths import CONFIG_DIR
from eight_ball.scale import load_scale

MAC_GRID = CONFIG_DIR / "software_grid" / "mac.yaml"
REQUIRED_KEYS = {
    "level",
    "hardware_profile_ref",
    "ui",
    "chat_frontend",
    "consultation",
    "local_models",
    "cloud_option",
    "scheduler",
    "services",
    "docker",
    "open_webui",
    "notes",
    "measured",
    "stage3_variant",
}
OPTIONAL_KEYS = {"dropped"}


def _levels() -> list[dict]:
    return load_yaml(MAC_GRID)["levels"]


def test_mac_grid_has_levels_zero_through_nine_with_shared_keys():
    levels = _levels()
    assert [row["level"] for row in levels] == list(range(10))
    for row in levels:
        assert REQUIRED_KEYS <= set(row), row["level"]
        assert set(row) <= REQUIRED_KEYS | OPTIONAL_KEYS, row["level"]
        assert row["scheduler"] == "launchd"
        assert row["hardware_profile_ref"] == f"config/hardware_scale.yaml#level-{row['level']}"


def test_mac_grid_is_never_marked_measured():
    assert all(row["measured"] is False for row in _levels())


def test_mac_grid_models_follow_the_scale():
    scale = {row["level"]: row for row in load_scale()["levels"]}
    canary = load_scale()["canary"]["tag"]
    for row in _levels()[1:]:
        level = scale[row["level"]]
        expected = canary if level["local_model"] == "canary" else level["llama_tag"]
        assert row["local_models"]["primary"] == expected, row["level"]
        assert row["cloud_option"]["id"] == "jet-llama"
        assert row["cloud_option"]["grok"] is False


def test_mac_grid_uses_open_webui_from_level_two():
    for row in _levels()[2:]:
        assert row["open_webui"]["enabled"] is True, row["level"]
        assert row["docker"]["runtime"] == "colima", row["level"]


def test_mac_grid_has_no_root_homebrew_or_root_paths():
    text = MAC_GRID.read_text(encoding="utf-8")
    assert "sudo brew" not in text
    assert "/root/" not in text
    assert "cron" not in text.replace("No cron", "")


STAGE3_BY_LEVEL = {0: "3-ram1", 1: "3-ram1", 2: "3-ram2", 3: "3-ram2"}


def test_mac_grid_stage3_variant_is_required_and_mapped():
    for row in _levels():
        assert row["stage3_variant"] in {"3", "3-ram1", "3-ram2"}, row["level"]
        assert row["stage3_variant"] == STAGE3_BY_LEVEL.get(row["level"], "3"), row["level"]
        if row["stage3_variant"] == "3-ram1" and row["level"] > 0:
            assert row["open_webui"]["enabled"] is False
            assert row["docker"]["runtime"] == "none"


def test_mac_grid_ram2_levels_have_a_user_free_ram_setting():
    for row in _levels():
        if row["stage3_variant"] != "3-ram2":
            continue
        setting = row["open_webui"]["free_ram_setting"]
        assert "never root" in setting["run_as"]
        assert "colima stop" in setting["turn_off"]
        assert "colima start" in setting["turn_on"]

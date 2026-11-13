"""Checks for the macOS column of the shared per-OS software grid."""
from __future__ import annotations

import re

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
OPTIONAL_KEYS = {"dropped", "stage3_options"}
VARIANTS = {"3", "3-ram1", "3-ram2"}
STAGE3_BY_LEVEL = {0: "3-ram1", 1: "3-ram1", 2: "3-ram2", 3: "3-ram2"}
CHAT_FRONTENDS = {"openclaw-control-ui", "open-webui", "both", "none"}


def _doc() -> dict:
    return load_yaml(MAC_GRID)


def _levels() -> list[dict]:
    return _doc()["levels"]


def _owui_installed(row: dict) -> bool:
    value = row["open_webui"]
    return value if isinstance(value, bool) else value["installed"]


def test_mac_grid_header_matches_the_shared_schema():
    doc = _doc()
    assert doc["schema"] == "terminal-glass.8-ball.software-grid/1"
    assert doc["os"] == "mac"
    assert doc["scale_ref"] == "config/hardware_scale.yaml"
    assert set(doc["stage3_variants"]) >= VARIANTS
    for name in VARIANTS:
        assert doc["stage3_variants"][name]["mac_script"] == f"{name}.sh"


def test_mac_grid_has_levels_zero_through_nine_with_shared_keys():
    levels = _levels()
    assert [row["level"] for row in levels] == list(range(10))
    for row in levels:
        assert REQUIRED_KEYS <= set(row), row["level"]
        assert set(row) <= REQUIRED_KEYS | OPTIONAL_KEYS, row["level"]
        assert row["hardware_profile_ref"] == f"config/hardware_scale.yaml#level-{row['level']}"
        assert row["chat_frontend"] in CHAT_FRONTENDS
        assert row["scheduler"]["engine"] == "launchd"
        assert isinstance(row["docker"], bool)
        assert isinstance(_owui_installed(row), bool)
        assert isinstance(row.get("dropped", []), list)
    assert levels[9].get("dropped", []) == []


def test_mac_grid_is_never_marked_measured():
    assert all(row["measured"] is False for row in _levels())


def test_mac_grid_models_follow_the_scale():
    document = load_scale()
    scale = {row["level"]: row for row in document["levels"]}
    for row in _levels()[1:]:
        level = scale[row["level"]]
        models = row["local_models"]
        if level["local_model"] == "canary":
            assert models["canary"] == document["canary"]["tag"], row["level"]
        else:
            assert models["llama"] == level["llama_tag"], row["level"]
        assert row["cloud_option"]["grok"] is False
        assert row["cloud_option"]["primary"].startswith("jet-llama")


def test_mac_grid_stage3_variant_and_options():
    for row in _levels():
        assert row["stage3_variant"] in VARIANTS, row["level"]
        assert row["stage3_variant"] == STAGE3_BY_LEVEL.get(row["level"], "3"), row["level"]
        options = row["stage3_options"]
        assert options[0] == row["stage3_variant"], row["level"]
        assert set(options) <= VARIANTS
        if row["stage3_variant"] == "3-ram1":
            assert _owui_installed(row) is False
            assert row["docker"] is False
        else:
            assert _owui_installed(row) is True
            assert row["docker"] is True


def test_mac_grid_ram2_free_ram_setting_runs_as_the_user():
    setting = _doc()["stage3_variants"]["3-ram2"]["free_ram_setting"]
    assert "never root" in setting["elevation"]
    assert any("colima stop" in step for step in setting["when_on"])
    assert any("colima start" in step for step in setting["when_off"])


def test_mac_grid_nextcloud_only_allowed_at_levels_seven_to_nine():
    for row in _levels():
        nextcloud = row["services"]["nextcloud"]
        assert nextcloud["allowed"] is (row["level"] >= 7), row["level"]
        assert nextcloud["installed"] is False


def test_mac_grid_wekan_is_the_core_task_board():
    text = MAC_GRID.read_text(encoding="utf-8").lower()
    assert not re.search(r"any\.?do", text)
    for row in _levels():
        wekan = row["services"]["wekan"]
        assert wekan["installed"] is True, row["level"]
        assert "core task board" in wekan["role"], row["level"]


def test_mac_grid_chats_stay_off_tailscale_and_public():
    doc = _doc()
    assert doc["defaults"]["chat_exposure"] == "lan-only"
    for row in _levels():
        assert "never the default chat exposure" in row["services"]["tailscale"]


def test_mac_grid_has_no_root_homebrew_private_names_or_root_paths():
    text = MAC_GRID.read_text(encoding="utf-8")
    assert "sudo brew" not in text
    assert "/root/" not in text
    assert "ycgpt" not in text
    assert "/workspace" not in text
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text.replace("127.0.0.1", ""))


def test_mac_level_zero_mirrors_the_linux_consultation_stack():
    row = _levels()[0]
    assert row["consultation"]["runner"] == "openclaw"
    assert row["consultation"]["model"].startswith("jet-llama")
    assert "before OpenClaw starts" in row["consultation"]["rule"]
    assert row["local_models"]["canary"] == load_scale()["canary"]["tag"]
    assert row["local_models"]["llama"] is None
    assert row["cloud_option"]["primary"] == "jet-llama"
    assert row["docker"] is False
    assert _owui_installed(row) is False
    assert "linux.yaml level 0" in row["notes"]["mirrors"]
    assert "No Apple Silicon Mac lands on level 0" in row["notes"]["macs"]

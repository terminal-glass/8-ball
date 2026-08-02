import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REQUIRED_IDS = {
    "personal-chat",
    "documents-rag",
    "coding-assistant",
    "small-business",
    "multi-user-office",
    "vision-documents",
    "agents-automation",
    "heavy-ai-research",
}
FORBIDDEN_KEYS = {
    "price",
    "pricing",
    "monthly_price",
    "hourly_price",
    "provider_plan",
    "provider_plan_id",
    "plan_id",
    "installer",
    "passport",
    "checkout",
    "ordering",
    "fulfillment",
}


def load_profiles():
    return [json.loads(path.read_text()) for path in sorted(DATA_DIR.glob("*.json")) if path.name != "workloads.json"]


def walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key).lower()
            yield from walk_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def test_all_eight_required_workload_profiles_exist():
    assert {path.stem for path in DATA_DIR.glob("*.json") if path.name != "workloads.json"} == REQUIRED_IDS


def test_all_json_parses():
    for path in DATA_DIR.glob("*.json"):
        json.loads(path.read_text())


def test_unique_workload_ids():
    ids = [profile["workload_id"] for profile in load_profiles()]
    assert len(ids) == len(set(ids))


def test_resource_ordering():
    for profile in load_profiles():
        resources = profile["resources"]
        assert resources["minimum_ram_gb"] <= resources["recommended_ram_gb"]
        assert resources["minimum_vcpu"] <= resources["recommended_vcpu"]


def test_user_range_ordering():
    for profile in load_profiles():
        users = profile["expected_users"]
        assert users["minimum"] <= users["typical"] <= users["maximum"]


def test_concurrency_ordering():
    for profile in load_profiles():
        concurrency = profile["expected_concurrency"]
        assert concurrency["typical"] <= concurrency["peak"]


def test_required_and_optional_capabilities_do_not_overlap():
    for profile in load_profiles():
        assert not (set(profile["required_capabilities"]) & set(profile["optional_capabilities"]))


def test_index_completeness():
    index = json.loads((DATA_DIR / "workloads.json").read_text())
    indexed_ids = {entry["workload_id"] for entry in index["workloads"]}
    profile_ids = {profile["workload_id"] for profile in load_profiles()}
    assert indexed_ids == profile_ids == REQUIRED_IDS
    for entry in index["workloads"]:
        assert (DATA_DIR / entry["path"]).exists()


def test_no_exact_ollama_model_tags_are_selected():
    for profile in load_profiles():
        guidance = profile["model_guidance"]
        assert "model" not in profile or "exact" not in profile.get("model", "")
        assert all(":" not in model_class for model_class in guidance["recommended_model_classes"])
        assert ":" not in guidance["maximum_model_class"]


def test_exact_model_selection_is_deferred_to_p5():
    for profile in load_profiles():
        assert profile["model_guidance"]["exact_model_selection_deferred_to"] == "P5-Compatibility-Estimator"


def test_no_pricing_fields_exist():
    for profile in load_profiles():
        keys = set(walk_keys(profile))
        assert not (keys & {"price", "pricing", "monthly_price", "hourly_price"})


def test_no_provider_plan_identifiers_exist():
    for profile in load_profiles():
        keys = set(walk_keys(profile))
        assert not (keys & {"provider_plan", "provider_plan_id", "plan_id"})


def test_no_installer_or_passport_logic_exists():
    for profile in load_profiles():
        serialized = json.dumps(profile).lower()
        assert "installer" not in serialized
        assert "passport" not in serialized
        assert "8.sh" not in serialized
        assert "checkout" not in serialized
        assert "ordering" not in serialized
        assert "fulfillment" not in serialized

import json

from eightball_console import fit, nerds, producer, profile
from eightball_console.catalog import Catalog

from conftest import REPO, make_profile

CAT = Catalog(REPO, "x")


def host(ram=None, vram=None, disk=None):
    return {"ram_gb": ram, "vram_gb": vram, "disk_free_gb": disk}


def test_cloud_is_blue():
    r = fit.evaluate("gpt-oss:20b-cloud", CAT.size_for_ref("gpt-oss:20b-cloud"), host(1, None, 1), 1)
    assert r["state"] == "cloud" and r["color"] == "blue"


def test_small_model_fits_big_model_rejected():
    small = CAT.size_for_ref("all-minilm:22m")
    assert fit.evaluate("all-minilm:22m", small, host(31, None, 100), 100)["state"] == "fits"
    big = CAT.size_for_ref("gpt-oss:120b")
    assert big is not None
    assert fit.evaluate("gpt-oss:120b", big, host(8, None, 100), 100)["state"] == "rejected"


def test_unknowns_never_count_as_enough():
    small = CAT.size_for_ref("all-minilm:22m")
    assert fit.evaluate("all-minilm:22m", small, host(None, None, None), None)["state"] == "unknown"
    assert fit.evaluate("all-minilm:22m", None, host(31, None, 100), 100)["state"] == "unknown"


def test_disk_too_small_is_red():
    small = CAT.size_for_ref("qwen3:8b")
    assert fit.evaluate("qwen3:8b", small, host(64, 24, 0.5), 0.5)["state"] == "rejected"


def test_every_result_is_marked_estimated():
    for ref in ("qwen3:4b", "all-minilm:22m"):
        assert fit.evaluate(ref, CAT.size_for_ref(ref), host(16, None, 50), 50)["estimated"] is True


def test_menu_resolves_50_families_to_exact_tags(tmp_path):
    prof = json.loads(make_profile(tmp_path).read_text())
    res = nerds.resolve(CAT, prof, {"qwen3:4b"}, 200)
    assert len(res["families"]) == 50
    for f in res["families"]:
        for v in f["variants"]:
            assert ":" in v["ref"], v["ref"]
    q = next(f for f in res["families"] if f["family_slug"] == "qwen3")
    assert "qwen3:4b" in q["installed_refs"]
    inst = next(v for v in q["variants"] if v["ref"] == "qwen3:4b")
    assert inst["installed"] is True and inst["fit"]["state"] in fit.LABELS  # installed is separate from fit
    assert res["tier"]["p_identity"] is None and res["tier"]["m_tier"] is None


def test_no_profile_means_unknown_not_fits():
    res = nerds.resolve(CAT, None, set(), 200)
    states = {v["fit"]["state"] for f in res["families"] for v in f["variants"]}
    assert states <= {"unknown", "cloud"}


def test_profile_states(tmp_path):
    p = tmp_path / "p.json"
    assert profile.load(p)["status"] == "missing"
    p.write_text("{nope")
    assert profile.load(p)["status"] == "corrupt"
    p.write_text(json.dumps({"schema_version": "other"}))
    assert profile.load(p)["status"] == "invalid"
    good = json.loads(make_profile(tmp_path).read_text())
    assert profile.load(tmp_path / "profile.v1.json")["status"] == "valid"
    p.write_text(json.dumps({**good, "state": "partial"}))
    assert profile.load(p)["status"] == "incomplete"
    p.write_text(json.dumps({**good, "platform": {**good["platform"], "authorized": False}}))
    assert profile.load(p)["status"] == "unauthorized"
    p.write_text(json.dumps({**good, "captured_at": "2020-01-01T00:00:00Z"}))
    assert profile.load(p, 30)["status"] == "stale"


def test_build_classification_keeps_p_and_m_unknown(tmp_path):
    prof = json.loads(make_profile(tmp_path, ram_gb=31).read_text())
    c = prof["classification"]
    assert c["p_identity"]["value"] is None and c["p_identity"]["status"] == "unknown"
    assert c["m_tier"]["value"] is None and c["m_tier"]["status"] == "unclassified"
    assert c["catalog_deployment_type_id"] in {"3", "4", "5", "6", "7"}
    assert prof["lane"]["lane_path"] == "ubuntu/cpu"


def test_gpu_without_vram_is_recorded_as_unknown(tmp_path, monkeypatch):
    unknowns = []
    monkeypatch.setattr(producer, "_run", lambda argv, timeout=10: (9, "", "NVIDIA-SMI has failed: driver/library version mismatch"))
    monkeypatch.setattr(producer.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(producer, "_pci_display", lambda: [{"vendor_id": "0x10de", "class": "0x030000", "slot": "0000:01:00.0"}])
    g = producer._gpu(unknowns)
    assert g["detected"] is True
    assert any(u["field"] == "gpu.vram_mb" for u in unknowns)


def test_write_atomic_and_schema(tmp_path):
    import jsonschema
    prof = json.loads(make_profile(tmp_path).read_text())
    schema = json.loads((REPO / "app" / "eightball_console" / "schemas" / "host-profile.v1.schema.json").read_text())
    jsonschema.validate(prof, schema)
    scan = producer.scan(models_dir=str(tmp_path), ollama_url=None)
    sschema = json.loads((REPO / "app" / "eightball_console" / "schemas" / "host-scan.v1.schema.json").read_text())
    jsonschema.validate(scan, sschema)

from __future__ import annotations

import json
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from eight_ball.config import load_json, write_json
from eight_ball.manager.argv import ArgvRejected, ollama_argv
from eight_ball.manager.catalog_view import browse
from eight_ball.manager.lifecycle import list_state, pull_model, remove_model, use_model
from eight_ball.manager.ollama_http import OllamaClient
from eight_ball.manager.refresh import adopt_snapshot, current_pointer, last_known_good
from eight_ball.manager.release import build_manifest, verify_manifest
from eight_ball.manager.runner import StageInterrupted, run_stages
from eight_ball.manager.secrets import write_private_file
from eight_ball.manager.suitability import assess_suitability
from eight_ball.paths import REPO_ROOT


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._send({"models": [{"name": name} for name in sorted(self.server.installed)]})
            return
        if self.path == "/api/ps":
            self._send({"models": [{"name": name} for name in sorted(self.server.running)]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/pull":
            name = body["name"]
            self.server.pulls.append(name)
            payload = b'{"status":"pulling","completed":1,"total":2}\n{"status":"success"}\n'
            self._bytes(payload)
            self.server.installed.add(name)
            return
        if self.path == "/api/chat":
            self.server.chats.append(body["model"])
            self._send({"message": {"role": "assistant", "content": "ready"}})
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        name = body["name"]
        self.server.deleted.append(name)
        self.server.installed.discard(name)
        self.server.running.discard(name)
        self._send({"status": "success"})

    def _send(self, payload: dict) -> None:
        self._bytes(json.dumps(payload).encode())

    def _bytes(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.installed = set()
    server.running = set()
    server.pulls = []
    server.chats = []
    server.deleted = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield server, OllamaClient(base, timeout=5)
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _tag(identifier: str, model_id: str, *, availability: str, size: int | None, params: int | None) -> dict:
    return {
        "id": identifier.replace(":", "__"),
        "ollama_identifier": identifier,
        "model_id": model_id,
        "tag": identifier.split(":", 1)[1],
        "parameter_count": params,
        "parameter_unit": None,
        "quantization": "q4_0" if params is not None else None,
        "architecture": None,
        "context_window_tokens": None,
        "download_size_bytes": size,
        "download_size_text": None,
        "installed_storage_bytes_estimated": None,
        "availability": availability,
        "capabilities": {"chat": "true"},
        "pull_command": f"ollama pull {identifier}",
        "run_command": f"ollama run {identifier}",
        "alias_target": None,
        "source_url": "https://ollama.com/library/tiny",
        "retrieved_at": "2026-08-01T00:00:00Z",
        "provenance": {
            "download_size_bytes": {
                "value": size,
                "confidence": "observed" if size is not None else "unknown",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
            },
            "parameter_count": {
                "value": params,
                "confidence": "observed" if params is not None else "unknown",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
            },
        },
    }


def _catalog() -> dict:
    return {
        "publishers": [
            {
                "id": "ollama-library",
                "display_name": "Ollama Library",
                "aliases": [],
                "official_url": "https://ollama.com/library",
            }
        ],
        "families": [
            {
                "id": "tiny",
                "publisher_id": "ollama-library",
                "name": "Tiny",
                "aliases": [],
                "description": "Tiny",
                "primary_capabilities": {"chat": "true"},
                "ollama_url": "https://ollama.com/library/tiny",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
            }
        ],
        "models": [
            {
                "id": "tiny-local",
                "ollama_name": "tiny-local",
                "display_name": "Tiny Local",
                "publisher_id": "ollama-library",
                "family_id": "tiny",
                "description": "Local",
                "availability": "local",
                "capabilities": {"chat": "true"},
                "default_tag": "tiny:latest",
                "source_url": "https://ollama.com/library/tiny",
                "retrieved_at": "2026-08-01T00:00:00Z",
                "validation_status": "valid",
            }
        ],
        "tags": [
            _tag("tiny:latest", "tiny-local", availability="local", size=5_000_000_000, params=8_000_000_000),
            _tag("tiny:small", "tiny-local", availability="local", size=100_000_000, params=1_000_000_000),
            _tag("tiny:cloud", "tiny-local", availability="cloud_only", size=None, params=None),
        ],
        "catalog_meta": {"catalog_version": "2026.08.01", "candidate": False},
    }


def _write_catalog(directory: Path, catalog: dict | None = None) -> None:
    catalog = catalog or _catalog()
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("publishers", "families", "models", "tags"):
        write_json(directory / f"{name}.json", catalog[name])
    write_json(directory / "catalog-meta.json", catalog["catalog_meta"])


def _metadata() -> dict[str, str]:
    return {
        "source_repository": "terminal-glass/8-ball",
        "source_ref": "refs/heads/main",
        "source_sha": "1" * 40,
        "schema_version": "normalized-entities",
        "catalog_version": "2026.08.01",
    }


def test_release_manifest_matches_source_and_rejects_tampering():
    manifest = build_manifest()
    committed = load_json(REPO_ROOT / "install/releases/v0.8.0/component-release-manifest.json")
    assert committed == manifest
    assert verify_manifest(manifest) == []
    assert manifest["catalog_version"] == "2026.08.01"
    assert manifest["catalog_version_independent"] is True
    assert manifest["auto_install_on_catalog_refresh"] is False
    assert manifest["default_execution_order"] == [
        "trial-install.sh",
        "8.1.sh",
        "8.2.sh",
        "8.3.sh",
    ]
    by_id = {row["id"]: row for row in manifest["components"]}
    assert by_id["model-manager"]["letter_suffix"] == "a"
    assert by_id["model-manager"]["not_in_default_chain"] is True
    assert by_id["ubuntu-trial-chain"]["execution_order"][0].endswith("trial-install.sh")
    consumers = {row["consumer"] for row in manifest["entry_points"]}
    assert "funtech64/ycgpt-lightsail-installer#177" in consumers
    assert "funtech64/ycgpt-lightsail-installer#178" in consumers
    assert "funtech64/ycgpt-lightsail-installer#179" in consumers
    assert "funtech64/ycgpt-lightsail-installer#180" in consumers
    assert all(row["hardware_execution"] == "untested" for row in manifest["entry_points"])

    tampered = json.loads(json.dumps(manifest))
    tampered["components"][0]["artifacts"][0]["sha256"] = "0" * 64
    failures = verify_manifest(tampered)
    assert any("sha256 mismatch" in failure for failure in failures)

    unsigned = json.loads(json.dumps(manifest))
    unsigned["components"][0]["signature"]["value"] = "abcd"
    assert any("unsigned component carries a signature" in failure for failure in verify_manifest(unsigned))


def test_signed_component_rejects_a_bad_signature():
    manifest = build_manifest()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    component = manifest["components"][0]
    component["signature"] = {
        "status": "signed",
        "algorithm": "ed25519",
        "public_key_id": "test-key",
        "value": private.sign(component["sha256"].encode()).hex(),
    }
    assert verify_manifest(manifest, public_keys={"test-key": public}) == []
    component["signature"]["value"] = "00" * 64
    failures = verify_manifest(manifest, public_keys={"test-key": public})
    assert any("signature verification failed" in failure for failure in failures)
    component["signature"]["public_key_id"] = "missing"
    failures = verify_manifest(manifest, public_keys={"test-key": public})
    assert any("unknown signing key" in failure for failure in failures)


def test_download_size_is_not_runtime_memory():
    tag = _tag("tiny:latest", "tiny-local", availability="local", size=50_000_000_000, params=1_000_000_000)
    hardware = {"ram_bytes": 8_000_000_000, "vram_bytes": None}
    result = assess_suitability(tag, hardware)
    assert result["classification"] == "estimated_fit"
    assert result["evidence_level"] == "estimated"
    assert result["download_size_used_as_memory"] is False
    assert result["download_size_bytes"] == 50_000_000_000
    assert result["estimated_runtime_memory_bytes"] < hardware["ram_bytes"]
    unknown = assess_suitability(
        _tag("tiny:latest", "tiny-local", availability="local", size=1, params=None),
        hardware,
    )
    assert unknown["classification"] == "unknown"
    assert "not used as RAM or VRAM" in unknown["reason"]


def test_browse_hides_cloud_only_downloads():
    rows = browse(_catalog(), local_downloads_only=True, hardware={"ram_bytes": 8_000_000_000})
    tags = [row["exact_tag"] for row in rows]
    assert "tiny:cloud" not in tags
    assert "tiny:latest" in tags
    cloud = next(row for row in browse(_catalog(), availability="cloud_only") if row["exact_tag"] == "tiny:cloud")
    assert cloud["actions"] == []
    assert cloud["suitability"] == "not_local"


def test_argv_keeps_catalog_text_out_of_a_shell():
    catalog = _catalog()
    assert ollama_argv("pull", catalog, "tiny:small") == ["ollama", "pull", "tiny:small"]
    assert ollama_argv("list", catalog) == ["ollama", "list"]
    with pytest.raises(ArgvRejected):
        ollama_argv("pull", catalog, "tiny:cloud")
    with pytest.raises(ArgvRejected):
        ollama_argv("pull", catalog, "tiny:latest;rm -rf /")


def test_pull_use_list_and_protected_remove(ollama):
    server, client = ollama
    catalog = _catalog()
    hardware = {"ram_bytes": 32_000_000_000, "vram_bytes": None}
    refused = pull_model(
        catalog,
        client,
        "tiny:cloud",
        free_bytes=10**12,
        hardware=hardware,
    )
    assert refused["ok"] is False
    assert server.pulls == []

    too_big = pull_model(
        catalog,
        client,
        "tiny:latest",
        free_bytes=200_000_000,
        hardware=hardware,
        policy={},
    )
    assert too_big["pulled"] is False
    assert too_big["substituted"] is False
    assert too_big["fallbacks"] == ["tiny:small"]
    assert server.pulls == []

    substituted = pull_model(
        catalog,
        client,
        "tiny:latest",
        free_bytes=200_000_000,
        hardware=hardware,
        policy={"allow_unattended_fallback": True},
    )
    assert substituted["substituted"] is True
    assert substituted["fallback_tag"] == "tiny:small"
    assert server.pulls == ["tiny:small"]

    progress: list[dict] = []
    again = pull_model(
        catalog,
        client,
        "tiny:small",
        free_bytes=10**12,
        hardware=hardware,
        on_progress=progress.append,
    )
    assert again["status"] == "skipped"
    assert server.pulls == ["tiny:small"]

    missing = use_model(catalog, client, "tiny:latest", "hello")
    assert missing["ok"] is False
    assert server.chats == []

    cancelled = pull_model(
        catalog,
        client,
        "tiny:latest",
        free_bytes=10**12,
        hardware=hardware,
        on_progress=lambda _event: False,
    )
    assert cancelled["status"] == "cancelled"
    assert cancelled["pulled"] is False

    used = use_model(catalog, client, "tiny:small", "hello")
    assert used["ok"] is True
    assert used["enrolled_network"] is False
    assert used["tools_granted"] is False
    assert server.chats == ["tiny:small"]
    assert "tiny:small" in list_state(client)["installed"]

    server.running.add("tiny:small")
    assignments = [{"agent": "local", "tag": "tiny:small"}]
    protected = remove_model(catalog, client, "tiny:small", assignments)
    assert protected["removed"] is False
    assert server.deleted == []
    stopped = remove_model(catalog, client, "tiny:small", assignments, decision="stop")
    assert stopped["removed"] is False
    reassigned = remove_model(
        catalog,
        client,
        "tiny:small",
        assignments,
        decision="reassign",
        reassign_to="tiny:latest",
    )
    assert reassigned["removed"] is False
    assert assignments == [{"agent": "local", "tag": "tiny:latest"}]
    removed = remove_model(catalog, client, "tiny:small", assignments, decision="remove")
    assert removed["removed"] is True
    assert removed["exact_tag"] == "tiny:small"
    assert "tiny:small" not in list_state(client)["installed"]


def test_failed_refresh_keeps_last_known_good(tmp_path: Path):
    candidate = tmp_path / "candidate"
    store = tmp_path / "store"
    _write_catalog(candidate)
    first = adopt_snapshot(candidate, store, _metadata())
    assert first["ok"] is True
    assert first["receipt"]["install_performed"] is False
    assert first["receipt"]["models_switched"] is False
    good = current_pointer(store)
    assert last_known_good(store) == good

    broken = tmp_path / "broken"
    _write_catalog(broken)
    tags = load_json(broken / "tags.json")
    tags[0]["pull_command"] = "ollama pull not-the-tag"
    write_json(broken / "tags.json", tags)
    second = adopt_snapshot(broken, store, _metadata())
    assert second["ok"] is False
    assert second["current_unchanged"] is True
    assert current_pointer(store) == good
    assert last_known_good(store) == good
    assert second["receipt"]["install_performed"] is False

    rejected = adopt_snapshot(candidate, store, {})
    assert rejected["ok"] is False
    assert current_pointer(store) == good

    payload = tmp_path / "payload"
    _write_catalog(payload)
    (payload / "weights.gguf").write_bytes(b"not-a-weight")
    blocked = adopt_snapshot(payload, store, _metadata())
    assert blocked["ok"] is False
    assert current_pointer(store) == good


def test_stage_rerun_is_idempotent_and_reports_recovery(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    state = home / ".config" / "8-ball" / "stages.json"
    calls: list[str] = []

    def stages():
        return [
            {"id": "detect", "recovery": "Rerun hardware detection.", "run": lambda: calls.append("detect")},
            {"id": "catalog", "recovery": "Keep the last-known-good catalog and retry.", "run": lambda: calls.append("catalog")},
        ]

    first = run_stages(stages(), state_path=state, home=home, healthcheck=lambda _stage: True)
    assert first["ok"] is True
    second = run_stages(stages(), state_path=state, home=home, healthcheck=lambda _stage: True)
    assert second["ok"] is True
    assert calls == ["detect", "catalog"]
    assert second["state"]["stages"]["detect"]["status"] == "skipped"
    mode = stat.S_IMODE(state.stat().st_mode)
    assert mode == 0o600

    def fail() -> None:
        raise RuntimeError("disk full")

    failed = run_stages(
        [{"id": "pull", "recovery": "Free disk and rerun the pull.", "run": fail}],
        state_path=state,
        home=home,
        healthcheck=lambda _stage: True,
    )
    assert failed["ok"] is False
    assert failed["failed_stage"] == "pull"
    assert failed["recovery"] == "Free disk and rerun the pull."
    assert failed["state"]["stages"]["pull"]["status"] == "failure"

    def interrupt() -> None:
        raise StageInterrupted()

    interrupted = run_stages(
        [{"id": "fetch", "recovery": "Rerun the interrupted fetch.", "run": interrupt}],
        state_path=state,
        home=home,
        healthcheck=lambda _stage: True,
    )
    assert interrupted["state"]["stages"]["fetch"]["status"] == "interrupted"
    assert interrupted["recovery"] == "Rerun the interrupted fetch."


def test_private_files_stay_out_of_root(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    target = write_private_file(home / ".config" / "8-ball" / "token", b"super-secret-token", home=home)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert target.read_bytes() == b"super-secret-token"
    with pytest.raises(PermissionError):
        write_private_file(Path("/root/.config/8-ball/token"), b"nope", home=Path("/root"))


def test_experimental_script_does_not_interpolate_catalog_text():
    script = (REPO_ROOT / "install/shared/8.4a-model-manager.sh").read_text(encoding="utf-8")
    assert "exec python3 -m eight_ball.manager" in script
    assert '"$@"' in script
    assert "eval " not in script
    assert "ollama pull" not in script
    assert "8.1.sh" in script
    assert "letter suffix" in script.casefold() or 'Letter suffix' in script

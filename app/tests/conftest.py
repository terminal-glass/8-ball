"""Shared fixtures: a fake native-Ollama server and an app wired to it. No network, no real Ollama."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


class FakeOllama:
    def __init__(self) -> None:
        self.models: dict[str, int] = {"qwen3:4b": 2_500_000_000, "gpt-oss:20b-cloud": 384}
        self.running: set[str] = set()
        self.pull_delay = 0.05
        self.pull_steps = 6
        self.fail_list_after_pull = False
        self.calls: list[tuple[str, str]] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def _send(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}")

            def do_GET(self):
                fake.calls.append(("GET", self.path))
                if self.path == "/api/version":
                    return self._send(200, {"version": "0.0.0-fake"})
                if self.path == "/api/tags":
                    return self._send(200, {"models": [{"name": n, "model": n, "size": s, "modified_at": "2026-10-01T00:00:00Z",
                                                        "digest": "abc123"} for n, s in fake.models.items()]})
                if self.path == "/api/ps":
                    return self._send(200, {"models": [{"name": n, "model": n} for n in fake.running]})
                self._send(404, {"error": "not found"})

            def do_POST(self):
                fake.calls.append(("POST", self.path))
                body = self._body()
                if self.path == "/api/show":
                    return self._send(200, {"details": {"family": "x"}, "capabilities": ["completion"]})
                if self.path == "/api/pull":
                    m = body["model"]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.end_headers()
                    try:
                        self.wfile.write(json.dumps({"status": "pulling manifest"}).encode() + b"\n")
                        total = 46_000_000
                        for i in range(1, fake.pull_steps + 1):
                            time.sleep(fake.pull_delay)
                            self.wfile.write(json.dumps({"status": "pulling abc", "digest": "sha256:abc", "total": total,
                                                         "completed": total * i // fake.pull_steps}).encode() + b"\n")
                            self.wfile.flush()
                        if not fake.fail_list_after_pull:
                            fake.models[m] = total
                        self.wfile.write(json.dumps({"status": "success"}).encode() + b"\n")
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    return None
                self._send(404, {"error": "not found"})

            def do_DELETE(self):
                fake.calls.append(("DELETE", self.path))
                m = self._body()["model"]
                if m not in fake.models:
                    return self._send(404, {"error": "model not found"})
                del fake.models[m]
                self._send(200, {})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.srv.shutdown()


@pytest.fixture
def fake_ollama():
    f = FakeOllama()
    yield f
    f.close()


def make_profile(tmp: Path, ram_gb: float = 31.0, vram_gb: float | None = None, disk_gb: float = 200.0) -> Path:
    from eightball_console import producer
    gpu = {"detected": vram_gb is not None, "devices": [], "probes": [], "pci_display_controllers": []}
    if vram_gb:
        gpu["devices"] = [{"vendor": "nvidia", "name": "Test GPU", "vram_mb": int(vram_gb * 1024)}]
    scan = {
        "schema_version": producer.SCAN_SCHEMA, "scan_id": "test-scan", "captured_at": producer.now_utc(),
        "producer": {"name": "test", "version": "0"}, "host": {"hostname": "testhost"},
        "os": {"family": "linux", "id": "ubuntu", "version_id": "26.04", "pretty_name": "Ubuntu 26.04", "kernel": "6", "arch": "x86_64"},
        "cpu": {"model": "Test CPU", "threads": 8},
        "memory": {"total_mb": int(ram_gb * 1024), "available_mb": None, "swap_mb": 0},
        "disk": [{"role": "models", "path": "/m", "measured_at_path": "/m", "total_mb": 999999, "free_mb": int(disk_gb * 1024)}],
        "gpu": gpu, "virtualization": "none", "cloud_provider": None, "ollama": None, "unknowns": [],
    }
    from eightball_console.catalog import Catalog
    from eightball_console import nerds
    doc = producer.build(scan, Catalog(REPO), nerds.menu())
    p = tmp / "profile.v1.json"
    producer.write_atomic(p, doc)
    return p


@pytest.fixture
def app_env(tmp_path, fake_ollama, monkeypatch):
    from eightball_console import config as cfgmod
    from eightball_console.config import Instance
    from eightball_console.server import create_app
    from fastapi.testclient import TestClient

    cfg = cfgmod.Config()
    cfg.state_dir = tmp_path / "state"
    cfg.profile_path = make_profile(tmp_path)
    cfg.catalog_root = REPO
    cfg.catalog_commit = "testcommit"
    cfg.auth_mode = "trusted-proxy"
    cfg.trusted_proxies = ("testclient", "127.0.0.1")
    cfg.instances = (Instance("local", "This machine", fake_ollama.url),)
    cfg.models_dir = tmp_path
    cfg.offline = "off"
    cfg.console_path = "tty/"
    app = create_app(cfg)
    client = TestClient(app, headers={"X-8Ball-User": "admin", "X-8Ball-Role": "admin"})
    return {"cfg": cfg, "app": app, "client": client, "fake": fake_ollama, "store": app.state.store}


MUT = {"X-8Ball": "1", "Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"}

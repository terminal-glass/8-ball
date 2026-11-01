import json
import time

import pytest

from eightball_console import console, redact
from eightball_console.auth import Users, hash_password, verify_password
from eightball_console.jobs import JobStore

from conftest import MUT


def wait(store, jid, t=20):
    j = store.wait(jid, t)
    assert j["state"] in ("succeeded", "failed", "cancelled", "interrupted"), j
    return j


def test_read_endpoints(app_env):
    c = app_env["client"]
    assert c.get("/api/health").json()["status"] == "ok"
    p = c.get("/api/profile").json()
    assert p["status"] == "valid" and p["fit_policy"] == "fit-policy.v1"
    inst = c.get("/api/instances").json()
    assert inst[0]["reachable"] and inst[0]["version"] == "0.0.0-fake"
    m = c.get("/api/models").json()
    refs = {r["ref"]: r for r in m["installed"]}
    assert refs["gpt-oss:20b-cloud"]["fit"]["state"] == "cloud"
    assert "qwen3:4b" in refs
    n = c.get("/api/nerds").json()
    assert len(n["families"]) == 50
    spec = c.get("/openapi.json").json()
    for path in ("/api/health", "/api/profile", "/api/instances", "/api/models", "/api/nerds", "/api/jobs/pull",
                 "/api/jobs/remove", "/api/jobs/upgrade", "/api/jobs/{job_id}", "/api/jobs/{job_id}/events",
                 "/api/jobs/{job_id}/cancel", "/api/console/{job_id}/token"):
        assert path in spec["paths"], path


def test_security_headers(app_env):
    r = app_env["client"].get("/api/health")
    assert "frame-ancestors 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_pull_list_remove_flow(app_env):
    c, store, fake = app_env["client"], app_env["store"], app_env["fake"]
    r = c.post("/api/jobs/pull", json={"model": "all-minilm:22m", "idempotency_key": "k1"}, headers=MUT)
    assert r.status_code == 202, r.text
    jid = r.json()["job"]["id"]
    # same key + same body -> same job, not a second pull
    r2 = c.post("/api/jobs/pull", json={"model": "all-minilm:22m", "idempotency_key": "k1"}, headers=MUT)
    assert r2.status_code == 200 and r2.json()["job"]["id"] == jid
    # same key + different body -> conflict
    assert c.post("/api/jobs/pull", json={"model": "all-minilm:33m", "idempotency_key": "k1"}, headers=MUT).status_code == 409
    j = wait(store, jid)
    assert j["state"] == "succeeded" and j["result"]["confirmed_by"] == "/api/tags"
    assert "all-minilm:22m" in {r["ref"] for r in c.get("/api/models").json()["installed"]}
    # remove needs the exact tag typed again
    assert c.post("/api/jobs/remove", json={"model": "all-minilm:22m", "confirm": "all-minilm"}, headers=MUT).status_code == 400
    r = c.post("/api/jobs/remove", json={"model": "all-minilm:22m", "confirm": "all-minilm:22m"}, headers=MUT)
    assert r.status_code == 202
    assert wait(store, r.json()["job"]["id"])["state"] == "succeeded"
    assert "all-minilm:22m" not in fake.models and "qwen3:4b" in fake.models


def test_installed_only_after_list_confirms(app_env):
    app_env["fake"].fail_list_after_pull = True
    r = app_env["client"].post("/api/jobs/pull", json={"model": "all-minilm:22m"}, headers=MUT)
    j = wait(app_env["store"], r.json()["job"]["id"])
    assert j["state"] == "failed" and "not in /api/tags" in j["error"]


def test_pull_refusals(app_env):
    c = app_env["client"]
    assert c.post("/api/jobs/pull", json={"model": "made-up:1b"}, headers=MUT).status_code == 400
    assert c.post("/api/jobs/pull", json={"model": "gpt-oss:20b-cloud"}, headers=MUT).status_code == 400
    app_env["cfg"].offline = "on"
    assert c.post("/api/jobs/pull", json={"model": "all-minilm:22m"}, headers=MUT).status_code == 409


def test_remove_refuses_running_model(app_env):
    app_env["fake"].running.add("qwen3:4b")
    r = app_env["client"].post("/api/jobs/remove", json={"model": "qwen3:4b", "confirm": "qwen3:4b"}, headers=MUT)
    j = wait(app_env["store"], r.json()["job"]["id"])
    assert j["state"] == "failed" and "qwen3:4b" in app_env["fake"].models


def test_cancel_pull(app_env):
    fake = app_env["fake"]
    fake.pull_delay, fake.pull_steps = 0.2, 50
    c, store = app_env["client"], app_env["store"]
    jid = c.post("/api/jobs/pull", json={"model": "all-minilm:22m"}, headers=MUT).json()["job"]["id"]
    for _ in range(100):
        if store.get(jid)["state"] == "running":
            break
        time.sleep(0.05)
    time.sleep(0.5)
    assert c.post(f"/api/jobs/{jid}/cancel", json={}, headers=MUT).status_code == 200
    assert wait(store, jid)["state"] == "cancelled"
    assert "all-minilm:22m" not in fake.models


def test_sse_replay_and_disconnect_does_not_cancel(app_env):
    fake = app_env["fake"]
    fake.pull_delay, fake.pull_steps = 0.1, 15
    c, store = app_env["client"], app_env["store"]
    jid = c.post("/api/jobs/pull", json={"model": "all-minilm:22m"}, headers=MUT).json()["job"]["id"]
    # open the stream, read a little, then drop it (a browser tab closing)
    with c.stream("GET", f"/api/jobs/{jid}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("id: 2"):
                break
    j = wait(store, jid)
    assert j["state"] == "succeeded"
    # replay everything after event 3 once the job is over
    body = c.get(f"/api/jobs/{jid}/events", headers={"Last-Event-ID": "3"}).text
    ids = [int(l[4:]) for l in body.splitlines() if l.startswith("id: ")]
    assert ids and ids[0] == 4 and ids == sorted(ids)
    assert "event: end" in body


def test_csrf_and_roles(app_env):
    c = app_env["client"]
    body = {"model": "all-minilm:22m"}
    assert c.post("/api/jobs/pull", json=body).status_code == 403  # no X-8Ball header
    assert c.post("/api/jobs/pull", json=body, headers={**MUT, "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert c.post("/api/jobs/pull", json=body, headers={**MUT, "Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/jobs/pull", content="model=x", headers={**MUT, "Content-Type": "text/plain"}).status_code in (403, 415, 422)
    assert c.post("/api/jobs/pull", json=body, headers={**MUT, "X-8Ball-Role": "viewer"}).status_code == 403
    # no proxy user header -> 401
    from fastapi.testclient import TestClient
    assert TestClient(app_env["app"]).get("/api/profile").status_code == 401


def test_workflow_allowlist_and_diagnostics(app_env):
    c, store = app_env["client"], app_env["store"]
    assert c.post("/api/jobs/upgrade", json={"workflow": "rm -rf /"}, headers=MUT).status_code == 400
    assert "diagnostics" in c.get("/api/workflows").json()
    r = c.post("/api/jobs/upgrade", json={"workflow": "diagnostics", "seconds": 3}, headers=MUT)
    assert r.status_code == 202
    j = wait(store, r.json()["job"]["id"])
    assert j["state"] == "succeeded"


def test_console_token_and_viewer(app_env, capsys):
    c, store, cfg = app_env["client"], app_env["store"], app_env["cfg"]
    jid = c.post("/api/jobs/upgrade", json={"workflow": "diagnostics", "seconds": 3}, headers=MUT).json()["job"]["id"]
    tok = c.get(f"/api/console/{jid}/token").json()
    assert tok["url"].startswith("tty/?arg=")
    wait(store, jid)
    assert console.view(cfg.jobs_dir, cfg.secret_file, [tok["token"]]) == 0
    out = capsys.readouterr().out
    assert "ollama version" in out and "job succeeded" in out
    assert console.view(cfg.jobs_dir, cfg.secret_file, [tok["token"][:-1] + "0"]) == 2
    assert console.view(cfg.jobs_dir, cfg.secret_file, ["a", "b"]) == 2
    secret = cfg.secret_file.read_text().encode()
    assert console.check_token(secret, console.make_token(secret, jid, -5)) is None


def test_restart_marks_running_jobs_interrupted(tmp_path):
    s = JobStore(tmp_path / "jobs")
    s.register("pull", lambda ctx, p: time.sleep(30))
    job, _ = s.submit("pull", {"instance": "local", "model": "x:1"}, "admin")
    time.sleep(0.2)
    s2 = JobStore(tmp_path / "jobs")
    assert s2.get(job["id"])["state"] == "interrupted"


def test_redaction():
    s = "Authorization: Bearer abc.def password=hunter2 https://u:p@host/x ghp_" + "a" * 36
    r = redact.redact(s)
    assert "hunter2" not in r and "abc.def" not in r and "u:p@" not in r and "ghp_" + "a" * 36 not in r


def test_users_file(tmp_path):
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h) and not verify_password("nope", h)
    u = Users(tmp_path / "users.json")
    u.add("admin", "admin", "pw-1")
    assert (tmp_path / "users.json").stat().st_mode & 0o777 == 0o600
    assert u.check("admin", "pw-1").role == "admin" and u.check("admin", "x") is None
    assert "pw-1" not in (tmp_path / "users.json").read_text()

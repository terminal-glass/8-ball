from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from eight_ball.evidence.capabilities import agent_ready, evidence_errors
from eight_ball.osamp.adapter import invoke_adapter
from eight_ball.osamp.covenant import Covenant
from eight_ball.osamp.gate import decide
from eight_ball.osamp.store import HoldStore

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> HoldStore:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    return HoldStore(home / ".config" / "8-ball" / "osamp-hold.json", home)


def _request(**overrides: object) -> dict:
    base = {
        "identity": "worker-1",
        "contract": "Peer",
        "accepted": True,
        "delivered": True,
        "nonce": "n-1",
        "expires_at": "2026-12-01T00:00:00Z",
        "budget_remaining": 1,
        "scope": ["infer"],
        "requested_scope": "infer",
        "action": "infer",
    }
    base.update(overrides)
    return base


def test_unauthorized_replay_and_expiry_do_not_invoke(tmp_path: Path):
    calls: list[str] = []

    def invoke(request: dict) -> None:
        calls.append(request["nonce"])

    store = _store(tmp_path)
    missing = decide(_request(identity="", nonce="missing"), store, now=NOW, invoke=invoke)
    assert missing["decision"] == "refuse"
    assert missing["invoke_model"] is False

    no_contract = decide(_request(contract=None, nonce="noc"), store, now=NOW, invoke=invoke)
    assert no_contract["reason"] == "No contract means no relay."
    assert calls == []

    fitting = decide(
        _request(contract=None, nonce="fit", ram_bytes=64_000_000_000, hardware_fit="recommended"),
        store,
        now=NOW,
        invoke=invoke,
    )
    assert fitting["decision"] == "refuse"
    assert calls == []

    first = decide(_request(nonce="once"), store, now=NOW, invoke=invoke)
    assert first["decision"] == "allow"
    assert calls == ["once"]
    replay = decide(_request(nonce="once"), store, now=NOW, invoke=invoke)
    assert replay["reason"] == "Replayed nonce."
    assert calls == ["once"]

    expired = decide(
        _request(nonce="old", expires_at="2020-01-01T00:00:00Z"),
        store,
        now=NOW,
        invoke=invoke,
    )
    assert expired["reason"] == "The work is expired."
    assert calls == ["once"]


def test_delivery_is_not_acceptance_and_hold_survives_restart(tmp_path: Path):
    calls: list[str] = []
    store = _store(tmp_path)
    held = decide(
        _request(accepted=False, delivered=True, nonce="held-1"),
        store,
        now=NOW,
        invoke=lambda _request: calls.append("x"),
    )
    assert held["decision"] == "hold"
    assert held["delivery_is_acceptance"] is False
    assert calls == []
    assert store.held

    restarted = HoldStore(store.path, store.home)
    assert restarted.held[0]["nonce"] == "held-1"
    assert restarted.commitments == []

    accepted = decide(_request(nonce="kept", contract="Work", work_kind="Project"), store, now=NOW)
    assert accepted["decision"] == "allow"
    restarted = HoldStore(store.path, store.home)
    assert any(row["nonce"] == "kept" for row in restarted.commitments)

    noisy = _store(tmp_path / "noise")
    decide(
        _request(accepted=False, nonce="noise", expires_at="2020-01-01T00:00:00Z"),
        noisy,
        now=datetime(2019, 1, 1, tzinfo=timezone.utc),
    )
    later = HoldStore(noisy.path, noisy.home)
    later.drop_expired(NOW)
    assert later.held == []


def test_revocation_budget_scope_and_planned_adapters(tmp_path: Path):
    calls: list[str] = []
    store = _store(tmp_path)
    revoked = decide(_request(revoked=True, nonce="rev"), store, now=NOW, invoke=lambda _r: calls.append("r"))
    assert revoked["decision"] == "refuse"
    assert calls == []
    poor = decide(_request(budget_remaining=0, nonce="poor"), store, now=NOW, invoke=lambda _r: calls.append("b"))
    assert poor["reason"] == "The budget is exhausted."
    wide = decide(
        _request(requested_scope="admin", nonce="wide"),
        store,
        now=NOW,
        invoke=lambda _r: calls.append("s"),
    )
    assert wide["decision"] == "refuse"
    table = decide(_request(contract="Table", nonce="table"), store, now=NOW, invoke=lambda _r: calls.append("t"))
    assert "bounded role" in table["reason"]
    bridge = decide(
        _request(contract="Bridge Acceptance", nonce="bridge"),
        store,
        now=NOW,
        invoke=lambda _r: calls.append("bridge"),
    )
    assert bridge["decision"] == "refuse"
    cast = decide(_request(action="broadcast", nonce="cast"), store, now=NOW, invoke=lambda _r: calls.append("cast"))
    assert cast["decision"] == "refuse"
    review = decide(_request(human_review=True, nonce="person"), store, now=NOW, invoke=lambda _r: calls.append("h"))
    assert review["decision"] == "human_review"
    assert calls == []

    allowed = decide(_request(nonce="local"), store, now=NOW, invoke=lambda _r: calls.append("local"))
    assert allowed["invoke_model"] is True
    adapter_calls: list[str] = []
    for name in ("openclaw", "hermes"):
        result = invoke_adapter(
            name,
            _request(),
            allowed,
            invoke=lambda _request, bucket=adapter_calls: bucket.append("called"),
        )
        assert result["invoked"] is False
        assert result["status"] == "planned"
    assert adapter_calls == []


def test_covenant_markers_and_rewind():
    covenant = Covenant()
    playing = covenant.command("PLAY")
    assert playing["state"] == "playing"
    assert playing["marker"] == "%%"
    assert covenant.hold()["marker"] == "!!"
    assert covenant.command("TIMEOUT")["marker"] == "!*"
    assert covenant.external_service()["marker"] == "~ ~"
    rewind = covenant.command("REWIND")
    assert rewind["review_required"] is True
    assert rewind["undo_promised"] is False
    assert rewind["external_effects_undone"] is False
    pending = covenant.command("STOP", peer="peer-a", peer_reachable=False)
    assert pending["state"] == "stop_pending"
    assert pending["stop_pending_peers"] == ["peer-a"]
    acknowledged = covenant.acknowledge_stop("peer-a")
    assert acknowledged["state"] == "stopped"
    assert acknowledged["stop_pending_peers"] == []


def test_source_claim_is_not_a_measured_test():
    claim = {
        "ollama_identifier": "tiny:latest",
        "capability_id": "tool_use",
        "kind": "source_claim",
        "value": "true",
        "source_url": "https://example.test/model",
        "method": None,
        "runtime_version": None,
        "hardware": None,
        "limitations": None,
        "status": "untested",
    }
    measured = {
        **claim,
        "kind": "measured_test",
        "method": "fixed tool-call fixture",
        "runtime_version": "test-runtime",
        "hardware": "fixture",
        "limitations": "one fixture prompt",
        "status": "tested",
    }
    assert evidence_errors({"schema": "terminal-glass.8-ball.capability-evidence/1", "catalog_version": "2026.08.01", "note": "fixture", "records": [claim, measured]}) == []
    assert agent_ready([claim], display_name="Giant Agent 700B", parameter_count=700_000_000_000)["agent_ready"] is False
    ready = agent_ready([measured], display_name="Giant Agent 700B", parameter_count=700_000_000_000)
    assert ready["agent_ready"] is True
    assert ready["evidence_kind"] == "measured_test"
    incomplete = {**measured, "method": None}
    assert any("method" in error for error in evidence_errors({"schema": "terminal-glass.8-ball.capability-evidence/1", "catalog_version": "2026.08.01", "note": "fixture", "records": [incomplete]}))

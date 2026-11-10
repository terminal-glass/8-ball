from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from eight_ball.osamp.store import HoldStore, parse_time

STANDING_CONTRACTS = ("Peer", "Tribe", "Clan", "Table", "Work")
WORK_KINDS = ("Project", "Corridor")
REFUSED_ACTIONS = {
    "broadcast",
    "cross_clan_disclosure",
    "nextcloud_sync",
    "git_replication",
}


def decide(
    request: dict[str, Any],
    store: HoldStore,
    *,
    now: datetime,
    invoke: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Decide locally before any model call.

    This is an 8-BALL check aligned to named OSAMP rules. It is not an OSAMP
    wire message and it does not rename the protocol.
    """
    store.drop_expired(now)
    result = _evaluate(request, store, now)
    if result["decision"] == "allow" and request.get("action") == "infer":
        if invoke is not None:
            invoke(request)
        result["invoke_model"] = True
    else:
        result["invoke_model"] = False
    if result["decision"] in {"allow", "hold", "refuse"}:
        nonce = request.get("nonce")
        if isinstance(nonce, str) and nonce and result["reason"] != "Replayed nonce.":
            store.remember_nonce(nonce)
    store.save()
    result["delivery_is_acceptance"] = False
    return result


def _evaluate(request: dict[str, Any], store: HoldStore, now: datetime) -> dict[str, Any]:
    identity = request.get("identity")
    if not identity:
        return _decision("refuse", "Identity is missing.")
    contract = request.get("contract")
    if not contract:
        return _decision("refuse", "No contract means no relay.")
    if contract == "Bridge Acceptance":
        return _decision("refuse", "Bridge Acceptance is not a standing contract.")
    if contract not in STANDING_CONTRACTS:
        return _decision("refuse", "The contract is not one of Peer, Tribe, Clan, Table, or Work.")
    if request.get("trust_transitive") or request.get("trusted_via"):
        return _decision("refuse", "Trust is not transitive.")
    if request.get("revoked"):
        return _decision("refuse", "The contract is revoked.")
    nonce = request.get("nonce")
    if nonce and nonce in store.seen_nonces:
        return _decision("refuse", "Replayed nonce.")
    expires_at = request.get("expires_at")
    if expires_at and parse_time(expires_at) <= now:
        return _decision("refuse", "The work is expired.")
    budget = request.get("budget_remaining")
    if budget is not None and budget <= 0:
        return _decision("refuse", "The budget is exhausted.")
    action = request.get("action")
    if action in REFUSED_ACTIONS:
        return _decision("refuse", f"{action} is refused.")
    if request.get("already_known") or request.get("no_action") or request.get("irrelevant"):
        return _decision("refuse", "The message does not need a model call.")
    if contract == "Work" and request.get("work_kind") not in WORK_KINDS:
        return _decision("refuse", "Work must name Project or Corridor.")
    scope = list(request.get("scope") or [])
    requested = request.get("requested_scope")
    if requested and requested not in scope:
        return _decision("refuse", "The requested scope is outside the contract.")
    if contract == "Table" and not request.get("accepted_roles"):
        return _decision("refuse", "A Table requires an explicit bounded role.")
    if request.get("human_review"):
        return _decision("human_review", "A person needs to review this before a model call.")
    if request.get("delivered") and not request.get("accepted"):
        store.held.append(
            {
                "nonce": nonce,
                "identity": identity,
                "contract": contract,
                "expires_at": expires_at,
                "accepted": False,
            }
        )
        return _decision("hold", "Delivery is not acceptance. The work is held.")
    if request.get("accepted"):
        store.commitments.append(
            {
                "nonce": nonce,
                "identity": identity,
                "contract": contract,
                "scope": scope,
                "accepted": True,
            }
        )
        return _decision("allow", "The accepted contract allows this action.")
    return _decision("refuse", "The work was not accepted.")


def _decision(kind: str, reason: str) -> dict[str, Any]:
    return {
        "decision": kind,
        "reason": reason,
        "contract_accepted": kind == "allow",
    }

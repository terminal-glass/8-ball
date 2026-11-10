from __future__ import annotations

from collections.abc import Callable
from typing import Any

PLANNED_ADAPTERS = {
    "openclaw": {"status": "planned", "tested": False},
    "hermes": {"status": "planned", "tested": False},
}


def invoke_adapter(
    adapter_id: str,
    request: dict[str, Any],
    decision: dict[str, Any],
    *,
    invoke: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Optional adapter boundary. Planned adapters are not called."""
    if decision.get("decision") != "allow" or not decision.get("invoke_model"):
        return {
            "adapter_id": adapter_id,
            "invoked": False,
            "status": "refused",
            "reason": decision.get("reason"),
        }
    spec = PLANNED_ADAPTERS.get(adapter_id)
    if spec is None or spec["status"] != "tested":
        return {
            "adapter_id": adapter_id,
            "invoked": False,
            "status": "planned",
            "tested": False,
            "reason": "No tested adapter is registered. OpenClaw and Hermes stay planned.",
        }
    if invoke is not None:
        invoke(request)
    return {"adapter_id": adapter_id, "invoked": True, "status": "tested", "tested": True}

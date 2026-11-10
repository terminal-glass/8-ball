from __future__ import annotations

from typing import Any

COMMANDS = ("PLAY", "PAUSE", "STOP", "REWIND", "REVIEW", "FAST-FORWARD", "TIMEOUT")


class Covenant:
    """Local self-governance controls.

    Rewind asks for review. It does not promise that an external effect can be undone.
    """

    def __init__(self) -> None:
        self.state = "stopped"
        self.marker: str | None = None
        self.undo_promised = False
        self.review_required = False
        self.stop_pending_peers: list[str] = []

    def command(
        self,
        name: str,
        *,
        peer: str | None = None,
        peer_reachable: bool = True,
    ) -> dict[str, Any]:
        command = name.strip().upper()
        if command not in COMMANDS:
            raise ValueError(f"Unknown covenant command {name}")
        if command == "PLAY":
            self.state = "playing"
            self.marker = "%%"
        elif command == "PAUSE":
            self.state = "paused"
            self.marker = "%%"
        elif command == "STOP":
            if peer and not peer_reachable:
                self.state = "stop_pending"
                if peer not in self.stop_pending_peers:
                    self.stop_pending_peers.append(peer)
            else:
                self.state = "stopped"
                self.marker = None
                if peer and peer in self.stop_pending_peers:
                    self.stop_pending_peers.remove(peer)
        elif command == "REWIND":
            self.review_required = True
            self.undo_promised = False
            self.state = "review"
        elif command == "REVIEW":
            self.review_required = True
            self.state = "review"
        elif command == "FAST-FORWARD":
            if self.state == "playing":
                self.marker = "%%"
            else:
                self.review_required = True
        elif command == "TIMEOUT":
            self.state = "timeout"
            self.marker = "!*"
        return self.snapshot()

    def acknowledge_stop(self, peer: str) -> dict[str, Any]:
        if peer in self.stop_pending_peers:
            self.stop_pending_peers.remove(peer)
        if not self.stop_pending_peers and self.state == "stop_pending":
            self.state = "stopped"
        return self.snapshot()

    def hold(self) -> dict[str, Any]:
        self.state = "held"
        self.marker = "!!"
        return self.snapshot()

    def external_service(self) -> dict[str, Any]:
        self.marker = "~ ~"
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "marker": self.marker,
            "undo_promised": self.undo_promised,
            "review_required": self.review_required,
            "stop_pending_peers": list(self.stop_pending_peers),
            "external_effects_undone": False,
        }

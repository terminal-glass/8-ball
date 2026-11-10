from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TAG_FIELDS = ("name", "model")


class OllamaError(Exception):
    """The local Ollama HTTP API returned an error."""


class PullCancelled(OllamaError):
    """The caller stopped a pull before it finished."""


class OllamaClient:
    """Talk to a local Ollama daemon over HTTP. Catalog text stays in JSON bodies."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", *, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._json("GET", "/api/tags")
        return list(payload.get("models") or [])

    def running(self) -> list[dict[str, Any]]:
        payload = self._json("GET", "/api/ps")
        return list(payload.get("models") or [])

    def has_model(self, tag: str) -> bool:
        return tag in _names(self.list_models())

    def is_running(self, tag: str) -> bool:
        return tag in _names(self.running())

    def pull(
        self,
        tag: str,
        *,
        on_progress: Callable[[dict[str, Any]], bool | None] | None = None,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        body = json.dumps({"name": tag, "stream": True}).encode()
        request = Request(
            self.base_url + "/api/pull",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    events.append(event)
                    if event.get("error"):
                        raise OllamaError(str(event["error"]))
                    if on_progress is not None and on_progress(event) is False:
                        raise PullCancelled("pull cancelled")
        except HTTPError as exc:
            raise OllamaError(f"Ollama pull failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise OllamaError(f"Ollama pull failed: {exc.reason}") from exc
        return events

    def chat(self, tag: str, prompt: str) -> str:
        payload = self._json(
            "POST",
            "/api/chat",
            {"model": tag, "messages": [{"role": "user", "content": prompt}], "stream": False},
        )
        message = payload.get("message") or {}
        return str(message.get("content") or "")

    def delete(self, tag: str) -> None:
        self._json("DELETE", "/api/delete", {"name": tag})

    def _json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise OllamaError(f"Ollama {method} {path} failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise OllamaError(f"Ollama {method} {path} failed: {exc.reason}") from exc
        if not raw:
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("error"):
            raise OllamaError(str(parsed["error"]))
        return parsed if isinstance(parsed, dict) else {"value": parsed}


def _names(models: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for model in models:
        for field in TAG_FIELDS:
            value = model.get(field)
            if isinstance(value, str) and value:
                found.add(value)
    return found

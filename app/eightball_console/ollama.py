"""Native Ollama REST client (only /api/version, /api/tags, /api/show, /api/pull, /api/delete, /api/ps)."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from .config import Instance


class OllamaError(RuntimeError):
    pass


class Ollama:
    def __init__(self, inst: Instance, timeout: float = 10.0) -> None:
        self.inst = inst
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return self.inst.base_url + path

    def _json(self, method: str, path: str, body: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
        try:
            r = httpx.request(method, self._url(path), json=body, timeout=timeout or self.timeout)
        except httpx.HTTPError as exc:
            raise OllamaError(f"{self.inst.id}: cannot reach Ollama ({exc.__class__.__name__})") from exc
        if r.status_code >= 400:
            try:
                msg = r.json().get("error") or r.text
            except ValueError:
                msg = r.text
            raise OllamaError(f"{path} -> HTTP {r.status_code}: {str(msg)[:300]}")
        return r.json() if r.content else {}

    def version(self) -> str | None:
        return self._json("GET", "/api/version", timeout=3).get("version")

    def tags(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/tags").get("models", [])

    def ps(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/ps").get("models", [])

    def show(self, model: str) -> dict[str, Any]:
        return self._json("POST", "/api/show", {"model": model})

    def delete(self, model: str) -> None:
        self._json("DELETE", "/api/delete", {"model": model}, timeout=60)

    def pull_stream(self, model: str, client: httpx.Client) -> Iterator[dict[str, Any]]:
        with client.stream("POST", self._url("/api/pull"), json={"model": model, "stream": True},
                           timeout=httpx.Timeout(30.0, read=600.0)) as r:
            if r.status_code >= 400:
                r.read()
                raise OllamaError(f"/api/pull -> HTTP {r.status_code}: {r.text[:300]}")
            for line in r.iter_lines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("error"):
                    raise OllamaError(str(ev["error"])[:300])
                yield ev


def names(models: list[dict[str, Any]]) -> set[str]:
    out = set()
    for m in models:
        n = m.get("name") or m.get("model")
        if n:
            out.add(n if ":" in n else n + ":latest")
    return out

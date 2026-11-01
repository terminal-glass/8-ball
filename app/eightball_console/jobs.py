"""Durable job runner: one directory per job (job.json + events.jsonl + console.log).

Jobs run in background worker threads owned by the service process, not by a browser connection,
so closing a tab or losing the event stream never cancels a job. Only an explicit cancel does.
On restart, jobs that were running are marked "interrupted" (they are not silently resumed).
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .producer import now_utc
from .redact import redact

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
KINDS = {"pull", "remove", "upgrade"}


class Cancelled(Exception):
    pass


class JobContext:
    def __init__(self, store: "JobStore", job_id: str) -> None:
        self.store = store
        self.id = job_id
        self.cancel_event = threading.Event()
        self.on_cancel: list[Callable[[], None]] = []

    def log(self, msg: str) -> None:
        self.store.event(self.id, "log", msg=msg)

    def progress(self, **data: Any) -> None:
        self.store.event(self.id, "progress", data=data)
        self.store.update(self.id, progress={k: v for k, v in data.items() if not k.startswith("_")})

    def check(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled()


class JobStore:
    def __init__(self, root: Path, max_parallel: int = 1) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o750)
        self._lock = threading.RLock()
        self._seq: dict[str, int] = {}
        self._ctx: dict[str, JobContext] = {}
        self._runners: dict[str, Callable[[JobContext, dict[str, Any]], dict[str, Any] | None]] = {}
        self._q: "queue.Queue[str]" = queue.Queue()
        self._idem_file = self.root / "idempotency.json"
        self._recover()
        for i in range(max(1, max_parallel)):
            threading.Thread(target=self._worker, name=f"8ball-job-{i}", daemon=True).start()

    # ------------------------------------------------------------ persistence
    def _dir(self, job_id: str) -> Path:
        if not job_id or not all(c in "0123456789abcdef-" for c in job_id):
            raise KeyError(job_id)
        return self.root / job_id

    def _write_job(self, job: dict[str, Any]) -> None:
        d = self._dir(job["id"])
        tmp = d / ".job.json.tmp"
        tmp.write_text(json.dumps(job, indent=1))
        os.replace(tmp, d / "job.json")

    def get(self, job_id: str) -> dict[str, Any] | None:
        try:
            p = self._dir(job_id) / "job.json"
        except KeyError:
            return None
        if not p.is_file():
            return None
        with self._lock:
            return json.loads(p.read_text())

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        jobs = []
        for d in self.root.iterdir():
            if (d / "job.json").is_file():
                try:
                    jobs.append(json.loads((d / "job.json").read_text()))
                except ValueError:
                    continue
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        return jobs[:limit]

    def update(self, job_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            job = self.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job.update(fields)
            job["updated_at"] = now_utc()
            self._write_job(job)
            return job

    def event(self, job_id: str, etype: str, msg: str | None = None, data: dict[str, Any] | None = None) -> int:
        with self._lock:
            seq = self._seq.get(job_id, 0) + 1
            self._seq[job_id] = seq
            ev: dict[str, Any] = {"seq": seq, "ts": now_utc(), "type": etype}
            if msg is not None:
                ev["msg"] = redact(msg)
            if data is not None:
                ev["data"] = json.loads(redact(json.dumps(data)))
            d = self._dir(job_id)
            with (d / "events.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev) + "\n")
            line = None
            if etype == "log":
                line = ev["msg"]
            elif etype == "state":
                line = f"== {ev['data'].get('state')}" + (f": {ev['data'].get('detail')}" if ev["data"].get("detail") else "")
            elif etype == "progress" and data and data.get("status") and not data.get("_quiet"):
                pct = data.get("percent")
                line = f"{data['status']}" + (f" {pct:.1f}%" if isinstance(pct, (int, float)) else "")
            if line is not None:
                with (d / "console.log").open("a", encoding="utf-8") as fh:
                    fh.write(f"[{ev['ts'][11:19]}Z] {line}\n")
            return seq

    def events_since(self, job_id: str, after: int = 0) -> list[dict[str, Any]]:
        p = self._dir(job_id) / "events.jsonl"
        if not p.is_file():
            return []
        out = []
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev["seq"] > after:
                    out.append(ev)
        return out

    def console_log(self, job_id: str) -> Path:
        return self._dir(job_id) / "console.log"

    def _recover(self) -> None:
        for d in self.root.iterdir() if self.root.is_dir() else []:
            p = d / "job.json"
            if not p.is_file():
                continue
            try:
                job = json.loads(p.read_text())
            except ValueError:
                continue
            ev = d / "events.jsonl"
            self._seq[job["id"]] = sum(1 for _ in ev.open()) if ev.is_file() else 0
            if job.get("state") in ("queued", "running"):
                job.update(state="interrupted", finished_at=now_utc(),
                           error="the console service restarted while this job was " + job["state"])
                self._write_job(job)
                self.event(job["id"], "state", data={"state": "interrupted", "detail": job["error"]})

    # ------------------------------------------------------------ submission
    def register(self, kind: str, fn: Callable[[JobContext, dict[str, Any]], dict[str, Any] | None]) -> None:
        self._runners[kind] = fn

    def _idem(self) -> dict[str, Any]:
        try:
            return json.loads(self._idem_file.read_text())
        except (OSError, ValueError):
            return {}

    def submit(self, kind: str, params: dict[str, Any], owner: str, idempotency_key: str | None = None) -> tuple[dict[str, Any], bool]:
        """Returns (job, created). Same key + same params returns the earlier job; different params -> ValueError."""
        if kind not in KINDS or kind not in self._runners:
            raise ValueError(f"unknown job kind {kind}")
        with self._lock:
            if idempotency_key:
                if len(idempotency_key) > 128 or not idempotency_key.isprintable():
                    raise ValueError("bad idempotency key")
                idem = self._idem()
                k = f"{owner}\x1f{idempotency_key}"
                if k in idem:
                    prev = self.get(idem[k]["job_id"])
                    if prev is not None:
                        if idem[k]["kind"] != kind or idem[k]["params"] != params:
                            raise ValueError("idempotency key was already used for a different request")
                        return prev, False
            # one active job per (kind-group, instance, target)
            for j in self.list(200):
                if j["state"] in ("queued", "running") and j["params"] == params and j["kind"] == kind:
                    return j, False
            job_id = str(uuid.uuid4())
            self._dir(job_id).mkdir(mode=0o750)
            job = {"id": job_id, "kind": kind, "params": params, "owner": owner, "state": "queued",
                   "created_at": now_utc(), "updated_at": now_utc(), "started_at": None, "finished_at": None,
                   "progress": None, "result": None, "error": None, "idempotency_key": idempotency_key}
            self._write_job(job)
            self._seq[job_id] = 0
            self._ctx[job_id] = JobContext(self, job_id)
            self.event(job_id, "state", data={"state": "queued"})
            if idempotency_key:
                idem = self._idem()
                idem[f"{owner}\x1f{idempotency_key}"] = {"job_id": job_id, "kind": kind, "params": params}
                tmp = self._idem_file.with_suffix(".tmp")
                tmp.write_text(json.dumps(idem))
                os.replace(tmp, self._idem_file)
            self._q.put(job_id)
            return job, True

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job["state"] in TERMINAL:
                return job
            ctx = self._ctx.get(job_id)
            if job["state"] == "queued":
                self._finish(job_id, "cancelled", detail="cancelled before it started")
            elif ctx:
                self.event(job_id, "log", msg="cancel requested")
                ctx.cancel_event.set()
                for cb in list(ctx.on_cancel):
                    try:
                        cb()
                    except Exception:  # noqa: BLE001
                        pass
            return self.get(job_id) or job

    def _finish(self, job_id: str, state: str, detail: str | None = None, result: Any = None) -> None:
        self.update(job_id, state=state, finished_at=now_utc(), error=detail if state != "succeeded" else None,
                    result=result)
        self.event(job_id, "state", data={"state": state, **({"detail": detail} if detail else {})})

    def _worker(self) -> None:
        while True:
            job_id = self._q.get()
            job = self.get(job_id)
            if job is None or job["state"] != "queued":
                continue
            ctx = self._ctx.setdefault(job_id, JobContext(self, job_id))
            self.update(job_id, state="running", started_at=now_utc())
            self.event(job_id, "state", data={"state": "running"})
            try:
                result = self._runners[job["kind"]](ctx, job["params"])
                if ctx.cancel_event.is_set():
                    raise Cancelled()
                self._finish(job_id, "succeeded", detail=(result or {}).get("detail"), result=result)
            except Cancelled:
                self._finish(job_id, "cancelled", detail="cancelled by request")
            except Exception as exc:  # noqa: BLE001
                self._finish(job_id, "failed", detail=redact(str(exc))[:500] or exc.__class__.__name__)
            finally:
                self._ctx.pop(job_id, None)

    def wait(self, job_id: str, timeout: float = 30.0) -> dict[str, Any]:
        end = time.time() + timeout
        while time.time() < end:
            j = self.get(job_id)
            if j and j["state"] in TERMINAL:
                return j
            time.sleep(0.05)
        return self.get(job_id) or {}

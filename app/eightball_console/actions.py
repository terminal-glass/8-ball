"""Job implementations: pull, remove and allowlisted upgrade workflows."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from . import fit
from .catalog import Catalog
from .config import Config
from .jobs import Cancelled, JobContext
from .ollama import Ollama, OllamaError, names


def norm(ref: str) -> str:
    return ref if ":" in ref else ref + ":latest"


def disk_free_gb(path: Path) -> float | None:
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return round(shutil.disk_usage(p).free / 1024**3, 2)
    except OSError:
        return None


# ------------------------------------------------------------------ built-in workflows
BUILTIN_WORKFLOWS: dict[str, dict[str, Any]] = {
    "diagnostics": {
        "label": "Diagnostics",
        "description": "Read-only: Ollama version, installed and running models and free disk, then watch running models for 45 seconds.",
        "params": {},
    },
    "model-refresh": {
        "label": "Refresh an installed model",
        "description": "Re-pull an installed catalog model to pick up a newer build of the same exact tag.",
        "params": {"model": "installed catalog tag"},
    },
}


def load_workflows(cfg: Config) -> dict[str, dict[str, Any]]:
    """Built-ins plus optional admin-defined command workflows (fixed argv, no user input)."""
    wf = {k: {**v, "type": "builtin"} for k, v in BUILTIN_WORKFLOWS.items()}
    if cfg.workflows_file and cfg.workflows_file.is_file():
        data = json.loads(cfg.workflows_file.read_text())
        for wid, spec in (data.get("workflows") or {}).items():
            argv = spec.get("argv")
            if (not wid.replace("-", "").isalnum() or wid in wf or not isinstance(argv, list)
                    or not argv or not all(isinstance(a, str) for a in argv) or not Path(argv[0]).is_absolute()):
                continue
            wf[wid] = {"label": spec.get("label", wid), "description": spec.get("description", ""),
                       "params": {}, "type": "command", "argv": argv,
                       "timeout": int(spec.get("timeout", 600))}
    return wf


class Actions:
    def __init__(self, cfg: Config, catalog: Catalog, clients: dict[str, Ollama]) -> None:
        self.cfg = cfg
        self.catalog = catalog
        self.clients = clients

    # --------------------------------------------------------------- pull
    def pull(self, ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
        cli = self.clients[params["instance"]]
        ref = params["model"]
        size = self.catalog.size_for_ref(ref)
        if size is None:
            raise RuntimeError(f"{ref} is not an exact tag in the catalog")
        req = fit.requirements(size)
        free = disk_free_gb(self.cfg.models_dir)
        if free is not None and req["min_disk_free_gb"] is not None and free < req["min_disk_free_gb"]:
            raise RuntimeError(f"not enough free disk: {free} GB < {req['min_disk_free_gb']} GB")
        ctx.log(f"pull {ref} on {cli.inst.label} (download about {_gb(size.get('download_size_bytes'))})")
        before = names(cli.tags())
        ctx.log("already installed; pulling again checks for a newer build" if norm(ref) in before else "not installed yet")
        last_emit = 0.0
        last_status = None
        with httpx.Client() as client:
            ctx.on_cancel.append(client.close)
            try:
                for ev in cli.pull_stream(ref, client):
                    ctx.check()
                    status = str(ev.get("status", ""))
                    total, done = ev.get("total"), ev.get("completed")
                    pct = (100.0 * done / total) if total and done is not None else None
                    now = time.monotonic()
                    if status != last_status or now - last_emit > 0.5:
                        ctx.progress(status=status[:120], total=total, completed=done, percent=pct,
                                     digest=(ev.get("digest") or "")[:19] or None,
                                     _quiet=(status == last_status))
                        last_emit, last_status = now, status
                    if status == "success":
                        break
                else:
                    ctx.check()
                    raise RuntimeError("pull stream ended without success")
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001  (closing the client on cancel surfaces here)
                ctx.check()
                raise RuntimeError(f"pull failed: {exc}") from exc
        ctx.log("Ollama reported success; refreshing the model list to confirm")
        after = names(cli.tags())
        if norm(ref) not in after:
            raise RuntimeError("Ollama reported success but the model is not in /api/tags")
        ctx.log(f"confirmed installed: {norm(ref)}")
        return {"detail": f"installed {norm(ref)}", "model": norm(ref), "confirmed_by": "/api/tags"}

    # --------------------------------------------------------------- remove
    def remove(self, ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
        cli = self.clients[params["instance"]]
        ref = norm(params["model"])
        if ref not in names(cli.tags()):
            raise RuntimeError(f"{ref} is not installed")
        running = names(cli.ps())
        if ref in running:
            raise RuntimeError(f"{ref} is loaded right now (in /api/ps); try again when it is idle")
        ctx.check()
        ctx.log(f"remove {ref} from {cli.inst.label}")
        cli.delete(ref)
        if ref in names(cli.tags()):
            raise RuntimeError("delete returned OK but the model is still listed")
        ctx.log(f"confirmed removed: {ref}")
        return {"detail": f"removed {ref}", "model": ref, "confirmed_by": "/api/tags"}

    # --------------------------------------------------------------- upgrade workflows
    def upgrade(self, ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
        wf = load_workflows(self.cfg).get(params["workflow"])
        if wf is None:
            raise RuntimeError("workflow not allowed")
        if params["workflow"] == "diagnostics":
            return self._diagnostics(ctx, params)
        if params["workflow"] == "model-refresh":
            res = self.pull(ctx, {"instance": params["instance"], "model": params["model"]})
            return {**res, "detail": f"refreshed {res['model']}"}
        return self._command(ctx, wf)

    def _diagnostics(self, ctx: JobContext, params: dict[str, Any]) -> dict[str, Any]:
        cli = self.clients[params["instance"]]
        ctx.log(f"instance: {cli.inst.label}")
        try:
            ctx.log(f"ollama version: {cli.version()}")
            tags = cli.tags()
            local = [m for m in tags if not fit.is_cloud_ref(m.get("name", ""))]
            ctx.log(f"installed models: {len(tags)} ({len(local)} local, {len(tags) - len(local)} cloud)")
        except OllamaError as exc:
            raise RuntimeError(str(exc)) from exc
        ctx.log(f"free disk for models: {disk_free_gb(self.cfg.models_dir)} GB")
        seconds = int(params.get("seconds") or 45)
        for i in range(0, seconds, 3):
            ctx.check()
            try:
                running = sorted(names(cli.ps()))
            except OllamaError as exc:
                running = [f"error: {exc}"]
            ctx.progress(status="watching running models", percent=100.0 * i / seconds, _quiet=True)
            ctx.log(f"t+{i:02d}s running: {', '.join(running) or 'none'}")
            for _ in range(30):
                ctx.check()
                time.sleep(0.1)
        return {"detail": "diagnostics complete"}

    def _command(self, ctx: JobContext, wf: dict[str, Any]) -> dict[str, Any]:
        ctx.log("run: " + " ".join(wf["argv"]))
        proc = subprocess.Popen(wf["argv"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                text=True, close_fds=True)
        ctx.on_cancel.append(proc.terminate)
        start = time.monotonic()
        assert proc.stdout is not None
        for line in proc.stdout:
            ctx.log(line.rstrip("\n")[:2000])
            if time.monotonic() - start > wf["timeout"]:
                proc.kill()
                raise RuntimeError("workflow timed out")
        rc = proc.wait()
        if ctx.cancel_event.is_set():
            raise Cancelled()
        if rc != 0:
            raise RuntimeError(f"workflow exited with {rc}")
        return {"detail": "workflow complete", "exit_code": rc}


def _gb(n: Any) -> str:
    return f"{n / 1e9:.2f} GB" if isinstance(n, (int, float)) and n else "unknown size"

"""FastAPI service. Default listener: 127.0.0.1:8788 (loopback only)."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, fit, nerds, profile as profile_mod
from .actions import Actions, disk_free_gb, load_workflows, norm
from .auth import Authenticator, User, guard_mutation
from .catalog import Catalog
from .config import Config
from .console import ensure_secret, make_token
from .jobs import TERMINAL, JobStore
from .ollama import Ollama, OllamaError, names

STATIC = Path(__file__).parent / "static"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; object-src 'none'")


class Online:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._at = 0.0
        self._val = False

    def __call__(self) -> bool:
        if self.cfg.offline == "on":
            return False
        if self.cfg.offline == "off":
            return True
        if time.time() - self._at > 60:
            try:
                httpx.get(self.cfg.registry_probe_url, timeout=3)
                self._val = True
            except httpx.HTTPError:
                self._val = False
            self._at = time.time()
        return self._val


def create_app(cfg: Config) -> FastAPI:
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    catalog = Catalog(cfg.catalog_root, cfg.catalog_commit)
    clients = {i.id: Ollama(i) for i in cfg.instances}
    store = JobStore(cfg.jobs_dir, cfg.max_parallel_jobs)
    acts = Actions(cfg, catalog, clients)
    store.register("pull", acts.pull)
    store.register("remove", acts.remove)
    store.register("upgrade", acts.upgrade)
    secret = ensure_secret(cfg.secret_file)
    auth = Authenticator(cfg)
    online = Online(cfg)

    app = FastAPI(title="8-Ball Console", version=__version__, docs_url=None, redoc_url=None,
                  openapi_url="/openapi.json")
    app.state.store = store
    app.state.cfg = cfg

    @app.middleware("http")
    async def headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def current_user(request: Request) -> User:
        return auth.user(request)

    def client_for(instance: str) -> Ollama:
        if instance not in clients:
            raise HTTPException(404, "unknown instance")
        return clients[instance]

    def load_profile() -> dict[str, Any]:
        return profile_mod.load(cfg.profile_path, cfg.profile_max_age_days)

    def usable_profile() -> dict[str, Any] | None:
        res = load_profile()
        return res["profile"] if res["status"] in ("valid", "stale") else None

    # ------------------------------------------------------------- read endpoints
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/profile")
    def get_profile(user: User = Depends(current_user)) -> dict[str, Any]:
        res = load_profile()
        p = res["profile"]
        return {"status": res["status"], "problems": res["problems"], "age_days": res.get("age_days"),
                "profile": p, "legend": fit.LABELS, "fit_policy": fit.POLICY_ID,
                "live": {"model_disk_free_gb": disk_free_gb(cfg.models_dir)}}

    @app.get("/api/instances")
    def instances(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        out = []
        for inst in cfg.instances:
            try:
                v, ok, err = clients[inst.id].version(), True, None
            except OllamaError as exc:
                v, ok, err = None, False, str(exc)
            out.append({"id": inst.id, "label": inst.label, "reachable": ok, "version": v, "error": err})
        return out

    @app.get("/api/models")
    def models(instance: str = Query("local"), user: User = Depends(current_user)) -> dict[str, Any]:
        cli = client_for(instance)
        try:
            tags, running = cli.tags(), cli.ps()
        except OllamaError as exc:
            raise HTTPException(502, str(exc)) from exc
        prof = usable_profile()
        host = fit.host_capacity(prof)
        free = disk_free_gb(cfg.models_dir)
        run_names = names(running)
        rows = []
        for m in tags:
            ref = norm(m.get("name") or m.get("model") or "")
            size = catalog.size_for_ref(ref)
            f = fit.evaluate(ref, size, host, free) if (prof or fit.is_cloud_ref(ref)) else \
                {**fit.evaluate(ref, None, host), "reasons": ["no valid host profile"]}
            rows.append({"ref": ref, "size_bytes": m.get("size"), "modified_at": m.get("modified_at"),
                         "digest": (m.get("digest") or "")[:12], "details": m.get("details"),
                         "cloud": fit.is_cloud_ref(ref) or bool(m.get("remote_host")), "in_catalog": size is not None,
                         "running": ref in run_names, "fit": f})
        rows.sort(key=lambda r: (r["cloud"], r["ref"]))
        return {"instance": instance, "installed": rows, "running": sorted(run_names),
                "online": online(), "model_disk_free_gb": free}

    @app.get("/api/models/show")
    def show(model: str, instance: str = Query("local"), user: User = Depends(current_user)) -> dict[str, Any]:
        cli = client_for(instance)
        if norm(model) not in names(cli.tags()):
            raise HTTPException(404, "model not installed")
        try:
            d = cli.show(norm(model))
        except OllamaError as exc:
            raise HTTPException(502, str(exc)) from exc
        return {k: d.get(k) for k in ("details", "capabilities", "modified_at", "parameters", "model_info")
                if k in d} | {"model": norm(model)}

    @app.get("/api/nerds")
    def get_nerds(instance: str = Query("local"), user: User = Depends(current_user)) -> dict[str, Any]:
        cli = client_for(instance)
        try:
            installed = names(cli.tags())
            reach = True
        except OllamaError:
            installed, reach = set(), False
        res = nerds.resolve(catalog, usable_profile(), installed, disk_free_gb(cfg.models_dir))
        res["profile_status"] = load_profile()["status"]
        res["online"] = online()
        res["instance_reachable"] = reach
        return res

    @app.get("/api/workflows")
    def workflows(user: User = Depends(current_user)) -> dict[str, Any]:
        return {k: {kk: vv for kk, vv in v.items() if kk != "argv"} for k, v in load_workflows(cfg).items()}

    @app.get("/api/jobs")
    def list_jobs(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        return store.list(50)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        j = store.get(job_id)
        if j is None:
            raise HTTPException(404, "job not found")
        return j

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str, request: Request, after: int = Query(0, ge=0),
                         last_event_id: str | None = Header(None), user: User = Depends(current_user)):
        if store.get(job_id) is None:
            raise HTTPException(404, "job not found")
        start = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

        async def gen():
            seq = start
            idle = 0.0
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    return  # the job keeps running; only the stream ends
                evs = store.events_since(job_id, seq)
                for ev in evs:
                    seq = ev["seq"]
                    yield f"id: {seq}\nevent: {ev['type']}\ndata: {json.dumps(ev)}\n\n"
                job = store.get(job_id) or {}
                if job.get("state") in TERMINAL and not store.events_since(job_id, seq):
                    yield f"event: end\ndata: {json.dumps({'state': job.get('state')})}\n\n"
                    return
                await asyncio.sleep(0.4)
                idle += 0.4
                if idle >= 15:
                    idle = 0
                    yield ": keepalive\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})

    @app.get("/api/console/{job_id}/token")
    def console_token(job_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        if store.get(job_id) is None:
            raise HTTPException(404, "job not found")
        if not cfg.console_path:
            raise HTTPException(404, "terminal view is not enabled")
        tok = make_token(secret, job_id, cfg.console_token_ttl)
        return {"token": tok, "expires_in": cfg.console_token_ttl, "url": f"{cfg.console_path}?arg={tok}"}

    # ------------------------------------------------------------- mutations
    def mutation(request: Request, user: User = Depends(current_user)) -> User:
        guard_mutation(request, user)
        return user

    def idem(body: dict[str, Any], header: str | None) -> str | None:
        k = header or body.get("idempotency_key")
        return str(k) if k else None

    def submitted(job: dict[str, Any], created: bool) -> JSONResponse:
        return JSONResponse({"job": job, "created": created}, status_code=202 if created else 200)

    @app.post("/api/jobs/pull")
    def pull(body: dict[str, Any] = Body(...), idempotency_key: str | None = Header(None),
             user: User = Depends(mutation)) -> JSONResponse:
        instance = str(body.get("instance") or "local")
        client_for(instance)
        ref = norm(str(body.get("model") or ""))
        if not catalog.known_ref(ref):
            raise HTTPException(400, "pick an exact tag from the catalog")
        if fit.is_cloud_ref(ref):
            raise HTTPException(400, "cloud models are not pulled from this console")
        if not online():
            raise HTTPException(409, "offline: pulls are disabled")
        try:
            job, created = store.submit("pull", {"instance": instance, "model": ref}, user.name, idem(body, idempotency_key))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return submitted(job, created)

    @app.post("/api/jobs/remove")
    def remove(body: dict[str, Any] = Body(...), idempotency_key: str | None = Header(None),
               user: User = Depends(mutation)) -> JSONResponse:
        instance = str(body.get("instance") or "local")
        cli = client_for(instance)
        ref = norm(str(body.get("model") or ""))
        if norm(str(body.get("confirm") or "")) != ref:
            raise HTTPException(400, "type the exact model tag to confirm removal")
        try:
            if ref not in names(cli.tags()):
                raise HTTPException(404, "model not installed")
        except OllamaError as exc:
            raise HTTPException(502, str(exc)) from exc
        try:
            job, created = store.submit("remove", {"instance": instance, "model": ref}, user.name, idem(body, idempotency_key))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return submitted(job, created)

    @app.post("/api/jobs/upgrade")
    def upgrade(body: dict[str, Any] = Body(...), idempotency_key: str | None = Header(None),
                user: User = Depends(mutation)) -> JSONResponse:
        instance = str(body.get("instance") or "local")
        cli = client_for(instance)
        wid = str(body.get("workflow") or "")
        wfs = load_workflows(cfg)
        if wid not in wfs:
            raise HTTPException(400, "workflow is not on the allowlist")
        params: dict[str, Any] = {"instance": instance, "workflow": wid}
        if wid == "model-refresh":
            ref = norm(str(body.get("model") or ""))
            if not catalog.known_ref(ref) or fit.is_cloud_ref(ref) or ref not in names(cli.tags()):
                raise HTTPException(400, "pick an installed local catalog model")
            if not online():
                raise HTTPException(409, "offline: refresh is disabled")
            params["model"] = ref
        elif wid == "diagnostics" and body.get("seconds") is not None:
            s = body.get("seconds")
            if not isinstance(s, int) or not 3 <= s <= 600:
                raise HTTPException(400, "seconds must be 3..600")
            params["seconds"] = s
        try:
            job, created = store.submit("upgrade", params, user.name, idem(body, idempotency_key))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return submitted(job, created)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str, user: User = Depends(mutation)) -> dict[str, Any]:
        j = store.get(job_id)
        if j is None:
            raise HTTPException(404, "job not found")
        return store.cancel(job_id)

    @app.get("/api/whoami")
    def whoami(user: User = Depends(current_user)) -> dict[str, Any]:
        return {"name": user.name, "role": user.role, "auth_mode": cfg.auth_mode,
                "catalog_commit": catalog.commit, "version": __version__, "offline_mode": cfg.offline,
                "online": online(), "console_enabled": bool(cfg.console_path),
                "instances": [{"id": i.id, "label": i.label} for i in cfg.instances]}

    # ------------------------------------------------------------- static UI
    @app.get("/", include_in_schema=False)
    def index(user: User = Depends(current_user)) -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app

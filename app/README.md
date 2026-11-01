# 🎱 8-Ball console (`/app`)

A small, self-hosted web console for one machine running [Ollama](https://ollama.com):

- **Profile**: what this machine has (RAM, GPU VRAM, free disk, OS, lane), with unknowns kept unknown.
- **Ollama**: installed models, live pull progress, safe removal (type the exact tag to confirm).
- **Happy Nerds**: the 50 featured model families from `nerds-menu.v1.json`, resolved to exact catalog
  tags and labelled for this machine.
- **Console**: durable job logs that survive a closed tab or a dropped connection, with reconnect and
  cancel; optional read-only terminal view through ttyd/xterm.js.
- **Settings**: instances, auth mode, catalog commit, offline state, theme.

It is downloadable on its own and is not tied to any one installer. It talks only to the native Ollama
REST API (`/api/version`, `/api/tags`, `/api/ps`, `/api/show`, `/api/pull`, `/api/delete`).

## Fit labels (fit-policy.v1)

| Label | Meaning |
|---|---|
| 🟢 **Fits** | meets the catalog's recommended RAM (or VRAM) estimate and the disk estimate |
| 🟠 **Constrained** | meets the minimum but not the recommended estimate, or disk headroom is low |
| 🔴 **Rejected** | below the minimum RAM/VRAM estimate or the minimum free disk |
| ⚪ **Unknown** | a catalog estimate or a host fact is missing; never treated as enough |
| 🔵 **Cloud** | runs on Ollama's cloud; nothing is downloaded |

Every label is an estimate from catalog metadata and always has a text label, not just a colour.
**Installed** is a separate badge: a model is shown as installed only after Ollama reports success
*and* a fresh `/api/tags` lists it.

P# identities and M1–M6 tiers are not defined in the catalog, so the console shows them as
*unknown* / *unclassified*. The catalog's deployment type (3–7) is shown separately and is not a P#
or M tier.

## Stages

| Stage role | Command | Output |
|---|---|---|
| hardware scan (role of `8.sh`) | `python -m eightball_console scan --out scan.json` | `8ball.host-scan.v1` (raw facts) |
| profile build (role of `8-1.sh`) | `python -m eightball_console build --scan scan.json --out /var/lib/8ball/profile.v1.json` | `8ball.host-profile.v1` |
| gate (before the console runs) | `python -m eightball_console check` | exit 0 when the profile is valid |
| console | `python -m eightball_console serve` | loopback HTTP on 127.0.0.1:8788 |

Schemas: `eightball_console/schemas/host-scan.v1.schema.json` and `host-profile.v1.schema.json`.
The build uses this repository's catalog (`profiles/*/sizes/*.json`) and its lane resolver
(`install/shared/c10-hardware-resolve.py`). The console never runs a hidden scan: if the profile is
missing, stale, corrupt or unsupported it says so and every fit shows as Unknown.

## API

`GET /api/health`, `/api/profile`, `/api/instances`, `/api/models`, `/api/nerds`, `/api/workflows`,
`/api/jobs`, `/api/jobs/{id}`, `/api/jobs/{id}/events` (server-sent events; resume with
`Last-Event-ID` or `?after=N`), `/api/console/{id}/token`, `/openapi.json`;
`POST /api/jobs/pull`, `/api/jobs/remove`, `/api/jobs/upgrade`, `/api/jobs/{id}/cancel`.

- Jobs are stored on disk (`job.json`, `events.jsonl`, `console.log`) and run in the service, not in
  the browser. Closing the page never cancels a job; only `cancel` does. A service restart marks
  running jobs `interrupted` (they are not silently resumed).
- `idempotency_key` (body or `Idempotency-Key` header): the same key and body return the same job;
  the same key with a different body is a 409.
- Pulls accept only exact catalog tags, refuse cloud tags, check free disk, and are disabled offline.
- Removal needs `confirm` equal to the exact tag and refuses a model that is loaded right now.
- "Upgrade" runs allowlisted workflows only: `diagnostics` (read-only), `model-refresh` (re-pull an
  installed catalog tag) and optional admin-defined fixed commands from a root-owned file. No user
  input ever reaches a command line. The console never upgrades or restarts Ollama.
- Logs and events are redacted (authorization headers, bearer tokens, passwords, URL credentials).

## Security model

- Listens on **127.0.0.1** only. Publish it through a same-host reverse proxy with TLS.
- Auth: `basic` (own users file, scrypt) or `trusted-proxy` (the proxy authenticates and sets
  `X-8Ball-User`/`X-8Ball-Role`, accepted only from loopback).
- Every change needs the admin role, a JSON body, the header `X-8Ball: 1`, and a same-origin request.
- Strict CSP, `frame-ancestors 'self'`, `no-store` on the API.
- The terminal view is read-only: ttyd runs without `-W` and starts only the log viewer, which needs a
  5-minute HMAC token bound to one job.
- The console never changes Ollama's own listener or settings and never exposes port 11434.

See [INSTALL.md](INSTALL.md) for setup and [LICENSES.md](LICENSES.md) for third-party licenses.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements.txt pytest jsonschema
python -m pytest -q          # uses a fake Ollama server; never pulls real models
EIGHTBALL_CATALOG_ROOT=.. EIGHTBALL_AUTH_MODE=trusted-proxy python -m eightball_console serve
```

Model weights are never stored in this repository.

## Not done yet

macOS and Windows hosts; cloud-model actions (shown, never pulled); an interactive admin terminal
(intentionally absent); resuming interrupted jobs; P# / M-tier mapping (undefined in the catalog).

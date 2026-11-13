# Per-OS software grid

One file per operating system, one entry per hardware level 0–9. Each OS
column has its own owner, so the three files can be edited in parallel
without merge conflicts.

| File | OS | Owner |
| --- | --- | --- |
| `linux.yaml` | Linux | Leonardo |
| `mac.yaml` | macOS | Monet |
| `windows.yaml` | Windows | Raphael |

Levels come from [`config/hardware_scale.yaml`](../hardware_scale.yaml)
(0/1 = Raspberry Pi class, 9 = top of the line; one uniform scale for every
OS). Installer **stage numbers are a different sequence** and are never
renumbered here. The software assigned to a level is different on each OS,
which is why there are three files rather than one table.

Frontend rule from the owner: **Mac and Windows use Open WebUI.** Linux small
levels do not; they use OpenClaw's built-in browser chat (Control UI) as a
GridStack tile, with no Docker. Linux has no Open WebUI on levels 0-2.

**Each OS sets its own cutoffs.** The level scale is shared, but the level at
which a component appears or is dropped (Open WebUI, Docker, a model tag)
can differ between `linux.yaml`, `mac.yaml` and `windows.yaml`.

Owner decisions that apply to every file:

- Chats are **LAN-only by default**. Remote access goes through Tailscale and
  must still get the proper app and chat interfaces (not a reduced view).
  Record it under `services` and `notes`.
- **WeKan stays in the core stack.** It is never replaced by Any.do, which is
  an outside service. Any.do may be offered as an extra connector only.
- Nextcloud is installed only at levels 7-9.
- 2 GB machines are supported.

## File header

```yaml
schema: terminal-glass.8-ball.software-grid/1
os: linux | mac | windows
owner: <bot name>
status: draft
scale_ref: config/hardware_scale.yaml
levels: [ ... ten entries, level 0 through 9 ... ]
```

Optional top-level blocks:

- `stage3_variants`: a map keyed `'3'`, `'3-ram1'`, `'3-ram2'` describing
  each script on this OS (`script` or `linux_script` / `windows_script`,
  `does`) and, under `'3-ram2'`, the free-RAM toggle (`free_ram_setting`
  with `name`, `where`, `when_on`, `when_off`) and the shared database.
- `defaults`, `supported_clients`, `benchmarks_ref`, and similar.

Consumers must ignore top-level keys they do not know.

## Per-level keys

Every entry in `levels` has these **13 required keys**, plus the new required
`stage3_variant` and the optional `dropped` / `stage3_options`.

| Key | Required | Type | Meaning |
| --- | --- | --- | --- |
| `level` | yes | int 0–9 | Level on the hardware scale. |
| `hardware_profile_ref` | yes | string | Always `config/hardware_scale.yaml#level-N`. |
| `ui` | yes | string | What the user sees first (for example the GridStack workspace with a chat tile). |
| `chat_frontend` | yes | string | `openclaw-control-ui`, `open-webui`, `both`, or `none`. |
| `stage3_variant` | yes (new) | string, quoted | Default installer stage 3 variant at this level: `'3'`, `'3-ram1'` or `'3-ram2'` (see below). |
| `consultation` | yes | string or map | Who gives the 8-BALL install consultation at this level (canary, local Llama, OpenClaw, or jets) and the fallback. |
| `local_models` | yes | map or `[]` | Exact Ollama tags: `canary`, `llama`, `qwen` (code/agentic focus, tentative), plus any tuning (`num_ctx`, Ollama env). |
| `cloud_option` | yes | string or map | The hosted option. Level 0 (and Linux level 1): Muse Spark (e.g. `meta/muse-spark-1.3`) through the `@openclaw/meta-provider` plugin, with the customer's own Meta API key (owner decision; Llama is too big for that tier). Higher levels: `jet-llama`, a hosted Llama on Meta's service with the same customer key (endpoint and model id are still TODO in `hardware_scale.yaml`). The key lives only in the installing user's home, file 600 in a 700 folder. |
| `scheduler` | yes | map | Scheduler engine and how it is verified. **Linux: cron. Mac: launchd. Windows: Task Scheduler.** |
| `services` | yes | map | Services and apps installed at this level, and how (native, Docker, snap). |
| `docker` | yes | bool | Whether Docker is installed by default at this level. |
| `open_webui` | yes | bool or map | Whether Open WebUI is installed. A map must carry `installed: <bool>` and may add method, bind, and settings. |
| `notes` | yes | string or map | Free-form notes, reasons, open questions. |
| `measured` | yes | `false`, `null`, or string | `false` (or `null`) when nothing at this level was measured. Otherwise a repo-relative link to the benchmark results that back the entry. |
| `dropped` | optional | list of strings | What this level **removes compared with the level above** (level N vs level N+1). Omit or `[]` at level 9. |
| `stage3_options` | optional | list of strings | Every stage 3 variant the installer offers at this level, default first. |

Count check: the 13 required keys are `level`, `hardware_profile_ref`, `ui`,
`chat_frontend`, `consultation`, `local_models`, `cloud_option`, `scheduler`,
`services`, `docker`, `open_webui`, `notes`, `measured`. `stage3_variant` is
the new required key that `mac.yaml` and `windows.yaml` will add as well.

## Stage 3 variants

Stage 3 is the chat-frontend stage. The variant scripts sit next to the
existing `3.sh`; no stage is renumbered.

| Value | Script | What it installs |
| --- | --- | --- |
| `'3'` | `3.sh` | The standard Open WebUI stage. |
| `'3-ram1'` | `3-ram1.sh` | Low-RAM install. Runs the lightweight OpenClaw chat only and bypasses Open WebUI. No Docker. |
| `'3-ram2'` | `3-ram2.sh` | OpenClaw chat and Open WebUI side by side on the same shared database, plus a user setting that turns off Docker and Open WebUI to free RAM. |

Low levels, including level 0, use `'3-ram1'`. Mac and Windows scripts may
use their platform's extension (`3-ram1.ps1`) for the same variant.

Quote the values in YAML (`'3'`), so `3` is never read as a number.

## Rules for every file

- Draft only until the owner signs off. No merges without review.
- Model tags must be exact Ollama tags that exist in the catalog.
- Numbers are labeled: measured (with a link in `measured`) or not.
- Public repository: no hostnames, IPs, VM ids, usernames, private repo
  names, internal paths, or credentials in any grid file.

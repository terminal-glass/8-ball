# 8-BALL Data-Science Planning Briefs

This directory contains **Cursor/agent planning briefs** for the 8-BALL environment
artifact and sizing-governance workstream.

It is for planning, sequencing, and governance only. It is **not** the runtime
artifact scaffold.

## Repository boundary

`terminal-glass/8-ball` is **metadata/catalog only**.

| Location | Role |
| --- | --- |
| `AGENTS/data-science/` | Agent briefs, sequencing, and governance (this folder) |
| `profiles/` | Repo-side artifact scaffold that future `8.2`/`8.3` work will consume |
| `data/normalized/` | Canonical Ollama catalog records |
| `P1`–`P4` datasets | Static estimator, provider, catalog export, and workload metadata |

Do **not** edit installer scripts (`0.sh`, `8.1.sh`, `8.2.sh`, `8.3.sh`, etc.) in
this repository. Runtime loader behavior is implemented in a separate installer
repository. This repo documents the contract and generates catalog-derived exports.

Do **not** invent disk, RAM, CPU, or GPU sizing thresholds. Do **not** invent
Docker image names, RecordsCore keys, or S3 keys.

## Brief sequence

Read these files in order before implementing environment-artifact work:

1. [`CursorFileC1-environment-artifacts.md`](CursorFileC1-environment-artifacts.md)
   — **C1:** environment artifact loader and profile contract
2. [`CursorFileC2-environment-artifact-sequencing.md`](CursorFileC2-environment-artifact-sequencing.md)
   — **C2:** steps 1–3 (family, model, deployment type)
3. [`CursorFileC3-environment-gates-testing-plan.md`](CursorFileC3-environment-gates-testing-plan.md)
   — **C3:** planned steps 4–7 (hard disk, RAM, CPU, GPU/VRAM)

## C1 — Environment artifact loader / profile contract

Defines:

- runtime paths (`/opt/philosopher/profiles`, `/opt/philosopher/instance.env`)
- profile directory precedence and load order for future `8.2`
- shell-safe `.env` artifact names (`00-instance.env` … `90-result.env`)
- minimum variable names

In **this repository**, C1 is implemented as metadata-only documentation under
[`profiles/`](../../profiles/README.md). Installer scripts that write or load
runtime artifacts belong outside this repo.

## C2 — Steps 1–3: family, model, deployment type

Defines catalog-derived identity artifacts under:

```text
profiles/01-families/
profiles/02-models/
profiles/03-deployment-types/
profiles/generated/
```

C2 work happens in `terminal-glass/8-ball`: generate family/model metadata and
deployment-type definitions from the approved normalized catalog. C2 must not
assign disk/RAM/CPU/GPU gates.

## C3 — Planned steps 4–7: hard disk, RAM, CPU, GPU/VRAM

Defines sizing gate artifacts under:

```text
profiles/04-hard-disk/
profiles/05-ram/
profiles/06-cpu/
profiles/07-gpu/
profiles/generated/
```

C3 is planning and recovered-history reconciliation first. Do not implement C3
gates until prior NoCloudGPT sizing history is recovered or explicitly marked
unresolved.

## `profiles/01-*` through `profiles/07-*`

The numbered `profiles/` directories are the **artifact scaffold**, not AGENTS
instructions. They hold generated metadata exports and human-readable notes that
installers and website selectors consume later.

Agents should read the briefs here for *what to build and why*, then write
outputs under `profiles/` and `profiles/generated/`.

## Related governance

- [`../cursorFileA0.md`](../cursorFileA0.md) — repository constitution
- [`../../AGENTS.md`](../../AGENTS.md) — agent rules and prohibited actions
- [`../../profiles/README.md`](../../profiles/README.md) — C1 scaffold documentation

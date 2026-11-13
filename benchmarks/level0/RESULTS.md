# Level-0 results (2026-11-13)

All numbers below were measured. Nothing here was run on real Raspberry Pi
hardware. Three kinds of machine:

1. **box-emulated**: a cgroup v2 slice on a shared x86 server (CPU model
   reported as "Intel(R) Xeon(R) Processor", AVX-512/AMX). 4 pinned cores,
   optionally `cpu.max` 50 %, `memory.max` 2 GiB or 1 GiB, no swap. The
   server was shared and busy (load average 7-25 during runs), and its CPU is
   far faster than a Pi's, so these are an upper bound on speed. The RAM caps
   are the faithful part.
2. **real VM, 2 vCPU / 2 GB x86 (not ARM Pi)**: Ubuntu 24.04.5, Intel Xeon
   E5-2420 @ 1.90 GHz (AVX, no AVX2), 1967 MiB RAM, no swap. Ollama 0.40.16 via
   the official installer (systemd service). Closest to Pi-class speed of the
   machines tested, but x86.
3. **arm64 emulated 2 GB VM**: pending (same scripts, `LABEL=vm-arm64-2g`).

Fixed prompt (consultation style), temperature 0, seed 42, 128 output tokens,
`num_ctx` 4096 (tinyllama is clamped to 2048 by Ollama), 3 runs per model,
run 1 cold. Warm-run TTFT is low because Ollama reuses the cached prompt;
the cold TTFT is the number that matters for a consultation.

See [RESULTS-TABLE.md](RESULTS-TABLE.md) for the generated table and
`results/<label>/` for raw JSON lines.

## Models

| Machine | Model | Loads | Peak RSS | Cold load | Cold TTFT | Eval tok/s (3 runs) |
| --- | --- | --- | --- | --- | --- | --- |
| box-emulated 4c / 2 GiB | tinyllama:1.1b | 3/3 | 699 MB | 1.0 s | 1.5 s | 65.9-71.7 |
| box-emulated 4c / 2 GiB | llama3.2:1b | 3/3 | 1911 MB | 3.9 s | 4.1 s | 36.8-42.4 |
| box-emulated 4c at 50 % / 2 GiB | tinyllama:1.1b | 3/3 | 704 MB | 7.4 s | 8.2 s | 28.2-29.1 |
| box-emulated 4c at 50 % / 2 GiB | llama3.2:1b | 3/3 | 1911 MB | 2.4 s | 2.8 s | 16.2-16.9 |
| box-emulated 4c / 1 GiB | tinyllama:1.1b | 3/3 | 699 MB | 0.8 s | 1.1 s | 65.8-71.7 |
| box-emulated 4c / 1 GiB | llama3.2:1b | **0/3, OOM-killed 3x** | - | - | - | - |
| real VM 2 vCPU / 2 GB x86 | tinyllama:1.1b | 3/3 | 692 MB | 9.7 s | 17.4 s | 6.5-6.8 |
| real VM 2 vCPU / 2 GB x86 | llama3.2:1b | 3/3 | 1480 MB | 17.5 s | 23.6 s | 5.8-5.9 |
| arm64 emulated 2 GB VM | both | pending | | | | |

Earlier VM attempt (`results/vm-x86-2c-2g/bench-attempt1.jsonl`): when the
tinyllama runner had not fully exited before llama3.2:1b loaded, the kernel
OOM-killed llama3.2:1b on the 2 GB VM. The bench now waits until no runner is
left before each cold run. Ollama's own memory check did not prevent it.

## Cron under model load

Every-minute crontab probe for 10 minutes while the model generated
512-token answers back to back. Debian/Ubuntu cron, cron daemon in the same
CPU/RAM slice on the box.

| Machine | Load | Fired | Missed | Late > 5 s | Lateness after the minute |
| --- | --- | --- | --- | --- | --- |
| box-emulated 4c at 50 % / 2 GiB | tinyllama:1.1b | 10/10 | 0 | 0 | 1.12-1.37 s |
| box-emulated 4c at 50 % / 2 GiB | llama3.2:1b | 10/10 | 0 | 0 | 1.03-2.01 s |
| real VM 2 vCPU / 2 GB x86 | tinyllama:1.1b | 10/10 | 0 | 0 | 1.57-2.04 s |
| real VM 2 vCPU / 2 GB x86 | llama3.2:1b | 10/10 | 0 | 0 | 1.13-2.00 s |
| real VM 2 vCPU / 2 GB x86 | OpenClaw gateway only, no Ollama (5 min) | 5/5 | 0 | 0 | 1.53-1.61 s |
| arm64 emulated 2 GB VM | all | pending | | | |

## OpenClaw on the 2 GB VM, cloud model only, no Ollama

OpenClaw 2026.11.3 on Node 24, gateway bound to loopback, the only model the
hosted Meta provider (`meta/muse-spark-1.3`, plugin `@openclaw/meta-provider`),
Ollama stopped. No API key was available or used.

- Install: works, but `npm install -g openclaw` needs several hundred MB; with
  a model still loaded the 2 GB VM thrashed until the model was unloaded.
- Gateway start to "ready": about 48 s.
- Gateway RSS: about 1.13 GB observed while idle (single `ps` sample; the
  scripted idle/peak capture is being re-run, see `openclaw.json` when present).
- Consultation turn: fails fast with `No API key found for provider "meta"`
  (ProviderAuthError). The credential it needs is a **Meta Model API key**
  (`MODEL_API_KEY`, or `openclaw models auth paste-api-key --provider meta`).
- Cron next to the gateway: 5/5 fired, none late.
- OpenClaw consultation through the local canary (`ollama/tinyllama:1.1b`):
  first attempt timed out because the agent call started before the gateway
  was ready; re-run pending.

## What this means for level 0

- The canary `tinyllama:1.1b` loads at 1 GiB and 2 GiB and needs about
  0.7 GB. On the 2 vCPU x86 VM it ran at about 6.6 tok/s, above the scale's
  2 tok/s slow gate, but a cold consultation answer took about 37 s.
- `llama3.2:1b` needs about 1.5-1.9 GB. It fails at 1 GiB and fits a 2 GB
  machine only when nothing else large is running. It is not assigned to
  level 0.
- The OpenClaw gateway alone uses about 1.1 GB on 2 GB. OpenClaw plus the
  canary is roughly 1.8 GB, so a 2 GB level-0 machine needs swap or zram and
  should load the canary only for the probe.
- Cron never missed a minute under any load tested.

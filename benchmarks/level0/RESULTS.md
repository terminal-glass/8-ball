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
3. **arm64 emulated 2 GB VM**: Ubuntu 24.04.5, aarch64, CPU model Cortex-A57,
   4 CPU, 1952 MiB RAM, no swap during the model bench (`LABEL=vm-arm64-2g`).
   Same scripts as the x86 VM. This is still not real Raspberry Pi hardware;
   qemu-style emulation can be much slower than a real Pi, so treat these
   numbers as what this emulated VM did, not as Pi performance.

Fixed prompt (consultation style), temperature 0, seed 42, 128 output tokens,
`num_ctx` 4096 (tinyllama is clamped to 2048 by Ollama). Box-emulated and
x86 VM runs used 3 runs per model; the arm64 VM used 2 (`RUNS=2`). Run 1
is cold. Warm-run TTFT is low because Ollama reuses the cached prompt;
the cold TTFT is the number that matters for a consultation. On the arm64
VM the cold run of both models timed out at 900 s before the first token,
so there is no cold TTFT for that column.

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
| arm64 emulated 2 GB VM | tinyllama:1.1b | **1/2; cold timed out at 900 s** | 686 MB | (loaded, no first token) | (none; warm TTFT 559.3 s) | 0.06 (warm only) |
| arm64 emulated 2 GB VM | llama3.2:1b | **1/2; cold timed out at 900 s** | 1472 MB | (loaded, no first token) | (none; warm TTFT 451.23 s) | 0.05 (warm only) |

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
| arm64 emulated 2 GB VM | tinyllama:1.1b | 3/10 | **7** | **2** | 2.286-40.927 s |
| arm64 emulated 2 GB VM | llama3.2:1b | 10/10 | 0 | 0 | 1.947-3.026 s |
| arm64 emulated 2 GB VM | OpenClaw gateway only, no Ollama (5 min, no swap) | 5/5 | 0 | 0 | 2.251-3.385 s |
| arm64 emulated 2 GB VM | OpenClaw gateway only, no Ollama (5 min, 2 GB swapfile) | 5/5 | 0 | 0 | 1.964-2.533 s |

## OpenClaw on the 2 GB VM, cloud model only, no Ollama

OpenClaw 2026.11.3 on Node 24, gateway bound to loopback, the only model the
hosted Meta provider (`meta/muse-spark-1.3`, plugin `@openclaw/meta-provider`),
Ollama stopped. No API key was available or used.

- Install: works, but `npm install -g openclaw` needs several hundred MB; with
  a model still loaded the 2 GB VM thrashed until the model was unloaded.
  The script now stops Ollama before installing.
- Gateway start to "ready": 48 s and 108 s on two starts.
- Gateway RAM (sum of OpenClaw processes): **1224 MB idle, 1603 MB peak**.
  MemAvailable fell from 1533 MB to **464 MB** with the gateway idle.
- Consultation turn with no key: fails in 15 s with
  `No API key found for provider "meta"` (ProviderAuthError). The credential
  it needs is a **Meta Model API key** (`MODEL_API_KEY`, or
  `openclaw models auth paste-api-key --provider meta`). No key was used.
- Cron next to the gateway, no Ollama: 5/5 fired twice, none late
  (1.36-1.61 s after the minute).
- OpenClaw consultation through the local canary (`ollama/tinyllama:1.1b`,
  Ollama running again): **refused by OpenClaw**, "Model context window too
  small (2048 tokens). Minimum is 4000." tinyllama's trained context is 2048
  (Ollama clamps it), so OpenClaw cannot use the canary as its model at all.
  System memory in use peaked at 1922 of 1967 MB during that attempt; no OOM
  kill.

Raw: `results/vm-x86-2c-2g/openclaw.json`.

## OpenClaw on the arm64 emulated 2 GB VM, cloud model only, no Ollama

OpenClaw 2026.11.3 on Node 24, same hosted Meta provider and no API key as
the x86 run. Two passes: first with a 2 GB swapfile
(`results/vm-arm64-2g-swap/openclaw.json`, includes the Node/OpenClaw
install), then swap off and a second pass on the already-installed stack
(`results/vm-arm64-2g/openclaw.json`). Ollama was stopped. Neither pass
recorded a gateway ready time (`gateway_ready_s` is null). The consult
exit was 1 in both cases with an empty `consult_error`; the consult log
said the gateway agent call connection closed and "Couldn't connect to
OpenClaw." RSS is much lower than the x86 figures, which fits a gateway
that never became ready rather than a like-for-like RAM comparison.

| Pass | Gateway ready | RSS idle | RSS peak | MemAvailable before / with gateway | Consult | Cron (5 min) |
| --- | --- | --- | --- | --- | --- | --- |
| 2 GB swapfile | never | 470.0 MB | 551.2 MB | 1701 / 1285 MB | exit 1 in 179.3 s, empty error | 5/5, 0 missed, 0 late (1.964-2.533 s) |
| no swap | never | 451.4 MB | 469.2 MB | 1658 / 1259 MB | exit 1 in 209.3 s, empty error | 5/5, 0 missed, 0 late (2.251-3.385 s) |

No local-canary consult (`LOCAL_MODEL`) was recorded in these arm64
result files.

## What this means for level 0

- The canary `tinyllama:1.1b` loads at 1 GiB and 2 GiB and needs about
  0.7 GB. On the 2 vCPU x86 VM it ran at about 6.6 tok/s, above the scale's
  2 tok/s slow gate, but a cold consultation answer took about 37 s.
- On the arm64 emulated 2 GB VM the canary also loaded (peak RSS 686 MB,
  no OOM) but was far slower: the cold run timed out at 900 s with no
  first token, and the one successful warm run was **0.06 tok/s** with
  TTFT 559.3 s and a 2765 s wall for 128 tokens. `llama3.2:1b` was the
  same pattern (peak RSS 1472 MB, cold timeout at 900 s, warm 0.05 tok/s,
  TTFT 451.23 s, wall 2873 s). Both are well under the 2 tok/s slow gate
  *on this emulated VM*; that is not a measurement of a real Pi.
- `llama3.2:1b` needs about 1.5-1.9 GB. It fails at 1 GiB and fits a 2 GB
  machine only when nothing else large is running. It is not assigned to
  level 0.
- The OpenClaw gateway alone uses 1.2-1.6 GB on a 2 GB machine and leaves
  about 0.46 GB available (x86 VM, where the gateway did become ready).
  OpenClaw plus the canary (0.7 GB) does not fit without swap or zram, so
  on a 2 GB level-0 machine the canary should run only as the 8-BALL probe,
  before or instead of OpenClaw, never alongside it. On the arm64 emulated
  VM the gateway never became ready, with or without a 2 GB swapfile, so
  those RAM figures are not a completed-gateway comparison.
- OpenClaw cannot consult on the canary (its 4000-token context minimum is
  above tinyllama's 2048). At level 0 OpenClaw consults on the hosted model,
  which needs the customer's Meta key.
- Cron never missed a minute on the box-emulated and x86 VM runs. On the
  arm64 emulated VM it missed 7 of 10 minutes under `tinyllama:1.1b` (2
  late by more than 5 s, lateness up to 40.927 s, and the load generator
  recorded 0 completed generations). Under `llama3.2:1b` and next to the
  OpenClaw gateway it fired 10/10 and 5/5 with none late.

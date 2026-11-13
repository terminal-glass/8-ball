# Hardware profile sets found

Checked on 2026-11-13. The new source of truth is `config/hardware_scale.yaml`, levels 0 through 9. Installer stage numbers were not changed. Private installer trees were not copied into this repository and were not edited.

## terminal-glass/8-ball

| Set | Count | Path | What it is |
| --- | --- | --- | --- |
| Named hardware profiles | 8 | `config/hardware_profiles.yaml` | cpu-small, desktop-standard, server-high-mem, gpu-entry, gpu-midrange, gpu-high-mem, multi-gpu, and cloud-only. cloud-only is hosted access, not a machine class. Each machine class now records `scale_level`. |
| C6 assumed profiles | 17 | `data/normalized/hardware-assumed-profiles.json` | CUDA, Mac, and Windows size buckets used for capability records. They stay as evidence rows. They are not a second customer scale. |
| Deployment types | 5 | `config/deployment_types.yaml` | IDs 3, 4, 5, 6, and 7. These are install gates, not hardware classes. |
| Per-model lane tree | many | `profiles/` | Model and platform lanes. Not a 0-9 machine scale. |

## funtech64/ycgpt-lightsail-installer

These paths are on draft pull-request heads, not on installer main. Main has no 1.10.1, 1.11.1, 1.12.1, or 1.13.1 directory.

| Set | Count | Path | Ref |
| --- | --- | --- | --- |
| Linux 8-Ball tiers | 6 | `1.10.1-LINUX-BETA-glass/payload/usr/lib/ycgpt/catalog/eightball-catalog.json` | PR #179, tiers M1–M6, empty placeholder, `verified: false` |
| Mac memory tiers | 6 | `1.11.1-MAC-BETA-glass/src/lib/eightball.zsh` | PR #178, function `tg_eightball_tier`, M1 below 8 GiB through M6 at 48 GiB and above |
| Windows tiers | 6 | `1.12.1-WIN-BETA-glass/scripts/lib/TgEightBall.ps1` | PR #180, `$script:TgTiers = M1..M6` |
| Lightsail 1.13.1 | none found | `1.13.1-LIGHTSAIL-BETA-glass/` | PR #177 has no hardware-class database |
| 9-Ball 1.0.38–1.0.40 | none found | `1.0.38-LINUX-9BALL-BETA/`, `1.0.39-MAC-9BALL-BETA/`, `1.0.40-WIN-9BALL-BETA/` | PR #183. Preflight and pins only. Not a hardware-class scale. |

No 9-level hardware set was found. The 8-name set is `config/hardware_profiles.yaml`. The other customer scale is the 6-step M1–M6 list in the Mac and Windows drafts, repeated as empty M1–M6 keys in the Linux placeholder catalog.

## Jets model

Jonathan corrected the jets model: it is Grok, as an official Ollama cloud tag, not a separate product and not the whole cloud catalog.

Catalog 2026.08.01 has no Grok family. A live Ollama cloud listing on 2026-11-13 (`https://ollama.com/search?c=cloud` and `https://ollama.com/search?q=grok`) shows no official Grok library model. Community forks are not offered. The consultation records that gap and does not invent a tag.

## Recommendations by level

Levels 0 and 1 use `tinyllama:1.1b` as the canary when measured memory and disk can hold it. From level 2 upward the canary is dropped. The database recommends a local Llama tag: `llama3.2:1b` at levels 2–3, `llama3.2:3b` at levels 4–5, and `llama3:8b` at levels 6–9. Those tags are in catalog 2026.08.01.

A code or agentic focus adds Qwen. Jonathan wrote `qwen(?)`, so the recommendation is marked tentative: `qwen2.5-coder:1.5b` at levels 0–3 and `qwen2.5-coder:7b` at levels 4–9, both present as local tags.

## OpenClaw on the lowest levels

When the placed level is 0 or 1 and the canary is too large to run locally, OpenClaw gives the consultation if OpenClaw is capable on that machine. If capability was not measured, the record says so. The OpenClaw adapter remains planned and is not called. A slow canary that does fit stays a local measurement and does not hand the consultation to OpenClaw.

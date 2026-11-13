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

## Jets line

In this repository, 8-BALL JETS already means optional Ollama cloud use after sign-in (`install/ubuntu/8.2.sh` helper `8balljets`). Jonathan confirmed the jets line is Ollama's cloud model tags, not a separate product.

Catalog 2026.08.01 has no official Llama-family cloud tag and no Grok-family tag at all. A live Ollama cloud listing on 2026-11-13 (`https://ollama.com/search?c=cloud`) shows official cloud models such as deepseek-v4, glm-5, gemma4, kimi, minimax, mistral-large, nemotron, and qwen-class names. It does not show an official Llama cloud model or an official Grok cloud model. Community forks that mention those names are not offered.

## OpenClaw on level 0 or 1

When the placed level is 0 or 1 and the canary does not fit or measures below 2 tokens per second, the consultation record sets `runner` to `openclaw` and `status` to `awaiting_jonathan_confirmation`. OpenClaw is not called. The OpenClaw adapter remains planned.

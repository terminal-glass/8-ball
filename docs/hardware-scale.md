<!-- Generated from config/hardware_scale.yaml by eight_ball.scale. Do not edit by hand. -->

# Hardware scale 0-9

This is the machine scale installers consult. Decimal SI bytes.
Level 0 is Raspberry Pi class. Level 9 is top of the line.
Installer stage numbers are not these levels.
cloud-only is hosted access, not a row in this table.

| Level | Name | RAM from | RAM below | Legacy names |
| --- | --- | --- | --- | --- |
| 0 | Raspberry Pi class | 0 | 4000000000 | none |
| 1 | Small board or low-memory PC | 4000000000 | 8000000000 | none |
| 2 | Small computer | 8000000000 | 12000000000 | cpu-small |
| 3 | Everyday laptop | 12000000000 | 16000000000 | none |
| 4 | Standard desktop | 16000000000 | 24000000000 | desktop-standard, gpu-entry |
| 5 | Large desktop | 24000000000 | 32000000000 | none |
| 6 | Midrange workstation | 32000000000 | 64000000000 | gpu-midrange |
| 7 | High-memory workstation | 64000000000 | 128000000000 | server-high-mem, gpu-high-mem |
| 8 | Multi-GPU workstation | 128000000000 | 256000000000 | multi-gpu |
| 9 | Top of the line | 256000000000 | none | none |

Canary tag: `tinyllama:1.1b`.

The jets model is Grok, offered only as an official Ollama cloud tag. Catalog 2026.08.01 and the 2026-11-13 Ollama cloud listing have no such tag. Levels 0 and 1 use the canary when it fits. If the canary is too large and OpenClaw is capable, OpenClaw gives the consultation. That adapter is planned and is not called. From level 2 upward the canary is dropped and a local Llama tag is recommended. A code or agentic focus adds a tentative Qwen recommendation.

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

The jets line means Ollama cloud models, the tags Ollama marks cloud. It is not a separate product. The two built-in choices are a Llama-family cloud tag and a Grok-family cloud tag when the catalog has them. On level 0 or 1, when the canary is too small or too slow, OpenClaw may run the consultation with an Ollama cloud model. That path is recorded for Jonathan to confirm. The OpenClaw adapter is not called.

# 8-BALL Windows trial installer — CUDA (`windows/cuda`)

Native Windows installer for hosts with verified NVIDIA CUDA evidence via
`nvidia-smi`. This lane does **not** install drivers, CUDA SDKs, or modify GPU
software.

## Requirements

- Windows 10 22H2 or newer (or Windows 11)
- PowerShell 5.1+ or PowerShell 7+
- Normal user privileges — **do not run elevated as Administrator**
- Native Windows — **WSL is not supported** (use `install/ubuntu/cuda` instead)
- Working `nvidia-smi` with Ollama-supported or unknown (not proven unsupported)
  NVIDIA software per C10.1 policy
- Ollama for Windows installed manually from the official installer

## Before you run

1. Install Ollama:
   [https://docs.ollama.com/windows](https://docs.ollama.com/windows)
2. Confirm NVIDIA drivers and `nvidia-smi` work in a normal user shell.
3. If this lane stops with a CUDA eligibility message, use `install/windows/cpu`
   instead — 8-BALL will not install drivers for you.

GPU documentation:
[https://docs.ollama.com/gpu](https://docs.ollama.com/gpu)
General FAQ: [https://docs.ollama.com/faq](https://docs.ollama.com/faq)

## Run the trial

```powershell
cd install\windows\cuda
.\trial-install.ps1
```

Optional flags:

- `-Model <tag>` — test only that Ollama tag (no silent fallback)
- `-NoMotd` — skip the completion card step
- `-Help`

## CUDA eligibility

- Requires successful `nvidia-smi` evidence — **not** `AdapterRAM` or Device
  Manager display names
- If NVIDIA software is proven unsupported by the C10.1 policy, the installer
  stops and directs you to `windows/cpu`
- No driver installation, CUDA toolkit install, or registry/service changes

## State, logs, and results

Default state root: `%LOCALAPPDATA%\8-BALL`

- `runtime-observation.json` — Windows host facts (RAM, disk, CPU)
- `cuda-runtime-observation.json` — `nvidia-smi` CUDA observation
- `8ball-result.json` / `8ball-result.txt` — trial outcome
- `bin\8ball-status.ps1` — status helper (not added to PATH)

## API and trial behavior

- Loopback endpoint only: `http://127.0.0.1:11434`
- Happy Nerds ladder is a local pull-and-inference **test order**, not a fit promise
- Failed newly pulled candidates may be removed; pre-existing models are kept

## Jets

Jets are opt-in via separate `ollama signin`. This installer does not activate them.

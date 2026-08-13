# 8-BALL Windows trial installer — CPU (`windows/cpu`)

Native Windows installer for CPU-only local inference. This lane never installs
NVIDIA drivers, CUDA SDKs, or GPU tooling.

## Requirements

- Windows 10 22H2 or newer (or Windows 11)
- PowerShell 5.1+ or PowerShell 7+
- Normal user privileges — **do not run elevated as Administrator**
- Native Windows — **WSL is not supported** (use `install/ubuntu/cpu` instead)
- Ollama for Windows installed manually from the official installer

## Before you run

1. Install Ollama using the official Windows app:
   [https://docs.ollama.com/windows](https://docs.ollama.com/windows)
2. Run `OllamaSetup.exe`, launch Ollama once, and confirm the tray app is running.
3. Confirm `ollama` is available: `ollama --version`

GPU notes (reference only; this lane stays CPU-only):
[https://docs.ollama.com/gpu](https://docs.ollama.com/gpu)
General FAQ: [https://docs.ollama.com/faq](https://docs.ollama.com/faq)

## Run the trial

```powershell
cd install\windows\cpu
.\trial-install.ps1
```

Optional flags:

- `-Model <tag>` — test only that Ollama tag (no silent fallback)
- `-NoMotd` — skip the completion card step
- `-Help`

## State, logs, and results

Default state root:

```text
%LOCALAPPDATA%\8-BALL
```

Override only with an absolute, user-writable path:

```powershell
$env:EIGHTBALL_ROOT = 'D:\Users\you\8-BALL'
```

Files written under the state root:

- `8ball-trial.log` — installer log
- `runtime-observation.json` — measured RAM, install-volume free space, CPU threads
- `8ball-result.json` / `8ball-result.txt` — selected model and test outcome
- `bin\8ball-status.ps1` — user-local status helper (not added to PATH)

## API and trial behavior

- Default endpoint: `http://127.0.0.1:11434` (loopback only)
- `8.2.ps1` runs the Happy Nerds ladder using observed RAM and install-disk
  space as a **test order**, not a model-fit guarantee
- Each candidate is pulled and verified with a small local `/api/generate` test
- Only a newly pulled model that fails its test may be removed

## Jets

Jets (cloud models) are **opt-in**. This installer does not run `ollama signin`,
store tokens, or pull cloud models. Sign in separately if you want Jets.

# 8-BALL macOS trial installer — Apple Silicon (`mac/apple-silicon`)

Native macOS installer for Apple Silicon Macs (`arm64`). This lane uses Metal
acceleration through the Ollama macOS application when Metal is supported.

## Requirements

- macOS Sonoma 14 or newer
- Apple Silicon (`arm64`) Mac
- Normal user privileges — **do not run with `sudo`**
- Ollama for macOS installed manually from the official app distribution

## Before you run

1. Install Ollama using the official macOS app:
   [https://docs.ollama.com/macos](https://docs.ollama.com/macos)
2. Drag Ollama into Applications, launch it once, and approve the CLI link
   prompt if macOS asks.
3. Confirm `ollama` is available in your shell: `ollama --version`

GPU and acceleration notes: [https://docs.ollama.com/gpu](https://docs.ollama.com/gpu)
General FAQ: [https://docs.ollama.com/faq](https://docs.ollama.com/faq)

## Run the trial

```bash
cd install/mac/apple-silicon
./trial-install.sh
```

Optional flags:

- `--model <tag>` — test only that Ollama tag (no silent fallback)
- `--no-motd` — skip the completion card step
- `--help`

## State, logs, and results

Default state root:

```text
~/Library/Application Support/8-BALL
```

Override only with an absolute, user-writable path:

```bash
export EIGHTBALL_ROOT="/absolute/path/you/own"
```

Files written there include:

- `8ball-trial.log` — installer log
- `runtime-observation.json` — observed hardware facts (not catalog fit claims)
- `8ball-result.json` / `8ball-result.txt` — selected model and test outcome
- `bin/8ball-status` — user-level status helper (not added to PATH automatically)

## Network endpoint

The installer talks to Ollama on the default loopback endpoint:

```text
http://127.0.0.1:11434
```

Non-loopback `OLLAMA_API` overrides are rejected in this public trial.

## Trial behavior

`8.2.sh` runs the Happy Nerds ladder using observed RAM and free install-disk
space, then verifies the selected model with a small local `/api/generate` test.
The ladder is a test order, not a guarantee that every model fits.

Apple Silicon uses unified memory. The installer does not report dedicated VRAM
or CUDA readiness.

## Jets (optional)

8-BALL Jets cloud options are **not** activated by this installer. They require a
separate `ollama signin` step if you choose to use them later.

Provider assumption: `profiles/provider-assumptions/mac-apple-silicon.json`

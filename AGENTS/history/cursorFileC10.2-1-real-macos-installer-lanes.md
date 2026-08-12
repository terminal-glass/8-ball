# C10.2-1 — Real macOS Installer Lanes

Work in the real `terminal-glass/8-ball` repository only after C10.1-15 has completed successfully and current `main` contains the merged Windows, macOS capability, and CUDA capability work.

Save this complete handoff first, unchanged:

```text
AGENTS/history/cursorFileC10.2-1-real-macos-installer-lanes.md
```

## Objective

Replace the current Linux-copy placeholders with real, user-level macOS installer payloads for both canonical lanes:

```text
install/mac/apple-silicon/
install/mac/intel/
```

Implement all existing public lane payloads in each lane:

```text
trial-install.sh
8.1.sh
8.2.sh
8.3.sh
assets/first-MOTD.txt
README.md
```

The scripts must be actual macOS shell behavior—not Ubuntu/Debian scripts merely relabeled as Mac.

## Existing defects this pass must remove

The current Mac copies still:

- require root;
- require `/etc/os-release`;
- invoke `apt-get`, `systemctl`, and Linux `/proc`/ `nproc` commands;
- assume `/opt/philosopher` and write system-owned paths;
- try to install the Linux Ollama package;
- use NVIDIA VRAM to pick a Mac deployment tier;
- write a global `/usr/local/bin/8balljets` command.

None of those are valid defaults for a normal macOS 8-BALL customer install.

## macOS facts to preserve

Use the runtime observations and contracts already created by C10.1-12.

```text
arm64  -> mac/apple-silicon only
x86_64 -> mac/intel only
unknown architecture -> clear stop; no lane claim
Apple Silicon -> Metal acceleration through Ollama; unified memory, no dedicated VRAM
Intel Mac -> CPU-only support for this 8-BALL pass
macOS Sonoma 14+ -> supported minimum
```

Do not create a Mac CUDA lane, use `nvidia-smi`, set `OLLAMA_VULKAN`, add ROCm/Vulkan, or represent unified memory as VRAM.

## User-level install contract

This is a desktop/laptop install. It must run as the signed-in user.

- Refuse `sudo`/root execution with a clear instruction to rerun normally.
- Default state root:
  ```text
  ~/Library/Application Support/8-BALL
  ```
  Allow an explicit `EIGHTBALL_ROOT` override only when it is an absolute path owned and writable by the invoking user.
- Use that state root for logs, result JSON/text, and small user commands.
- Do not write to `/opt`, `/usr/local/bin`, `/etc`, or shell startup files.
- Do not modify macOS Login Items, firewall configuration, network bindings, or system-wide launch daemons.
- Do not store credentials, API keys, cloud sign-in state, presigned URLs, or model data in the repository.

Provide a user-level status command at:

```text
$EIGHTBALL_ROOT/bin/8ball-status
```

It should display the selected model, local Ollama endpoint, result path, and the explicit next command for Jets. Do not add a PATH entry automatically.

## Ollama application contract

Use the official macOS distribution model; do not attempt a Linux-style curl-pipe-shell install.

1. `8.1.sh` must verify:
  - `sw_vers` reports macOS 14+;
  - the architecture matches its lane;
  - the user-level install root is writable.
2. It must find the Ollama macOS app in either:
  - `/Applications/Ollama.app`, or
  - `$HOME/Applications/Ollama.app`.
3. If missing, stop with a clear, customer-facing manual action:
   download/mount the official Ollama DMG, drag Ollama to Applications, launch it
   once, and approve the CLI-link prompt if macOS presents one. Print the official
   macOS documentation URL in the message.
4. If the app exists, use `open -a Ollama` (or the discovered app path) only to
   launch the existing user application. Wait for the local API at
   `http://127.0.0.1:11434/api/tags`.
5. Verify `ollama` is available in PATH before calling it. If the app is present
   but the CLI is not, stop with the manual launch/CLI-link instruction; do not
   create a privileged symlink yourself.
6. Never run `ollama serve` as a background daemon in this pass. The Ollama
   macOS app owns the service lifecycle.
7. Keep `OLLAMA_API` loopback-only by default. Reject a non-loopback override
   unless a later dedicated network-security task changes that policy.

## Step responsibilities

### `trial-install.sh`

- Validate normal-user execution, macOS, lane architecture, and local adjacent
  payloads before running anything.
- Execute `8.1.sh`, then `8.2.sh`, then `8.3.sh`.
- Support only:
  `--model <ollama-tag>`, `--no-motd`, `--manifest <path>`, and `--help`.
- Quote and validate argument values; `--model` must accept only a conservative
  Ollama tag character set.
- Log into the user state root. On failure show the last useful log lines without
  exposing a secret.
- Do not fetch missing sibling scripts from GitHub at runtime. A Mac trial bundle
  must contain its full lane payload; fail clearly if it does not.

### `8.1.sh`

- Implement the application contract above.
- Write the normalized runtime observation to the user state root using the
  existing C10.1-12 macOS observer where practical.
- Record hardware facts only: architecture, observed RAM, free install disk,
  CPU threads, Metal status, and the detected lane.
- Do not alter catalog profile files or use the observation to claim a model fit.

### `8.2.sh`

- Replace Linux `/proc`, `nproc`, and NVIDIA detection with macOS-native
  measurements from the C10.1-12 observer or equivalent `sysctl` and `df`
  observations.
- Use the existing Happy Nerds runtime trial ladder:
  ```text
  >= 24 GiB: qwen3:14b -> 8b -> 4b -> 1.7b -> 0.6b
  >= 12 GiB: qwen3:8b  -> 4b -> 1.7b -> 0.6b
  >=  8 GiB: qwen3:4b  -> 1.7b -> 0.6b
  >=  4 GiB: qwen3:1.7b -> 0.6b
  otherwise or unknown: qwen3:0.6b
  ```
- Preserve the existing free-disk guards: 14b 14 GiB, 8b 9 GiB, 4b 6 GiB,
  1.7b 4 GiB, 0.6b 3 GiB.
- Treat the ladder as a test order—not a fit guarantee. Pull only one candidate
  at a time, send a small local `/api/generate` test, and try the next smaller
  candidate on a pull or inference failure.
- Remove only a model that this run newly pulled and that then failed its test;
  never remove a previously installed user model.
- `--model` means explicit operator choice: test only that model and do not
  silently fall back to another.
- Save a result record in the user state root, including selected model,
  observed hardware facts, lane, Metal/CPU mode, test result, and timestamp.
- For Apple Silicon, the result may say `acceleration=metal` only when the
  C10.1-12 observation identifies Apple Silicon and Metal support. For Intel,
  state `acceleration=cpu`. Never say CUDA or report dedicated VRAM.

### `8.3.sh`

- Mac has no Linux MOTD installation equivalent in this product. Do not modify
  `/etc/motd`, `/etc/update-motd.d`, shell profiles, or login hooks.
- Print the concise 8-BALL completion card from the lane asset and write/update
  the user-level `8ball-status` helper.
- Explain Jets truthfully: it is optional, requires a separate `ollama signin`
  action, and is not activated by the local installer. Do not call `ollama signin`
  or pull cloud models automatically.

## README requirements

Replace the generated one-line lane READMEs with customer-useful Mac-specific
instructions that state:

- supported macOS version and architecture behavior;
- manual Ollama app installation/first launch requirement;
- run with normal user privileges, not `sudo`;
- state/log/result locations;
- default loopback endpoint;
- the trial ladder is verified by a local inference test;
- Intel is CPU-only in this phase;
- Jets are opt-in and require separate sign-in.

Use direct official-source links:

- `https://docs.ollama.com/macos`
- `https://docs.ollama.com/gpu`
- `https://docs.ollama.com/faq`

## Tests and validation

Add focused tests that execute safely on Linux CI by mocking commands or using
the non-Darwin fallback. Cover at least:

1. root invocation refuses before writing outside a temporary test root;
2. each lane accepts only its correct architecture;
3. non-macOS produces a clear failure;
4. missing Ollama.app produces the manual-install action without downloading;
5. API readiness waits for loopback and rejects non-loopback endpoint overrides;
6. neither Mac lane invokes `apt-get`, `systemctl`, `/proc`, `nproc`,
   `nvidia-smi`, `ollama serve`, or `sudo`;
7. Apple Silicon result has no dedicated VRAM and never mentions CUDA;
8. Intel result is CPU mode;
9. fallback never removes a pre-existing model;
10. failed newly pulled candidate is removed before the next trial;
11. no test modifies catalog matrix data, provider capability data, or
    `profiles/index.csv`.

Run:

```bash
find install/mac -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest \
  tests/test_profile_platform_tree.py \
  tests/test_c10_profiles.py \
  tests/test_c10_windows_capability.py \
  tests/test_c10_macos_capability.py \
  tests/test_c10_cuda_capability.py \
  -q
bash scripts/validate-catalog.sh
git diff --check
python3 scripts/generate-c10-profiles.py
git diff --exit-code
```

If macOS CI is unavailable, do not claim end-to-end runtime success. Run the
mocked/unit coverage, `bash -n`, and document the exact manual smoke-test
commands for a Sonoma 14+ Apple Silicon Mac and a Sonoma 14+ Intel Mac.

## Commit and report

Use one focused commit:

```text
feat(c10.2): implement real macOS installer lanes
```

Report changed files, test results, generator determinism result, any unavailable
macOS-only checks, manual smoke-test instructions, commit SHA, and PR URL.
Keep the PR draft. Do not merge it and do not begin connectors/Jets work in this task.

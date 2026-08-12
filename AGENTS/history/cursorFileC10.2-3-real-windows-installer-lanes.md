# C10.2-3 — Real Windows Installer Lanes

Work in the real `terminal-glass/8-ball` repository only after C10.2-2 has completed successfully and current `main` contains the merged real macOS installer lanes.

Save this complete handoff first, unchanged:

```text
AGENTS/history/cursorFileC10.2-3-real-windows-installer-lanes.md
```

## Objective

Replace the placeholder or Linux-derived Windows lane payloads with real native PowerShell implementation for the two canonical Windows lanes:

```text
install/windows/cpu/
install/windows/cuda/
```

Each lane must contain its full PowerShell public payload set:

```text
trial-install.ps1
8.1.ps1
8.2.ps1
8.3.ps1
assets/first-MOTD.txt
README.md
```

Do not implement WSL as a Windows lane. The existing C10.1 Windows capability contract classifies WSL separately; it must stop with a clear message directing the user to the Ubuntu lane.

## Scope and hard boundaries

This is a normal, per-user Windows install.

- Default 8-BALL state root:
  ```text
  $env:LOCALAPPDATA\8-BALL
  ```
  Allow `$env:EIGHTBALL_ROOT` only when it is an absolute, user-writable path.
- Do not require Administrator. Refuse elevated execution unless a specific future task requires it.
- Do not write to `C:\Program Files`, `C:\Windows`, system services, machine-wide registry, user profile scripts, firewall rules, or scheduled tasks.
- Do not install or modify NVIDIA drivers, CUDA SDK, ROCm, Vulkan, WSL, Docker, or Open WebUI.
- Do not change the ten-lane matrix, provider-capability records, catalog requirements, or model fit values.
- Do not add connectors, Jets auto-sign-in, cloud-model pulls, API keys, or remote/listening endpoints.

## Official Ollama Windows contract

Use the official Windows application model.

1. Require Windows 10 22H2+ and PowerShell 5.1+ or PowerShell 7+.
2. Find `ollama.exe` through PATH or the normal user installation location:
   ```text
   $env:LOCALAPPDATA\Programs\Ollama\ollama.exe
   ```
3. If Ollama is missing, stop with a customer-readable manual instruction to use
   the official `OllamaSetup.exe` installer. Include:
   ```text
   https://docs.ollama.com/windows
   ```
   Do not download, execute, or silently approve an installer in this pass.
4. Verify local API readiness only at:
   ```text
   http://127.0.0.1:11434/api/tags
   ```
   Reject non-loopback `OLLAMA_API` overrides. Do not start `ollama serve`;
   the Ollama application owns its own background lifecycle.
5. The Windows app may manage its own updates and startup behavior. 8-BALL must
   not change either setting.

## Lane behavior

### `trial-install.ps1`

- Support only `-Model <tag>`, `-Manifest <path>`, `-NoMotd`, and `-Help`.
- Require non-elevated native Windows. Stop on WSL, unknown architecture, or
  mismatched lane architecture/context before changing files.
- Validate model tags conservatively and run adjacent local payloads only; do
  not download missing scripts from GitHub at runtime.
- Log inside the state root and show useful non-secret tail output on failure.

### `8.1.ps1`

- Verify Windows release, architecture, state-root writability, installed Ollama
  CLI, and loopback API readiness.
- Run the existing Windows observation contract/collector where applicable:
  record measured RAM, selected install volume free space, logical CPUs,
  topology, and GPU evidence in a user-level result/observation file.
- CPU lane: always remains a safe local CPU candidate.
- CUDA lane: require successful `nvidia-smi` evidence plus a supported or
  unknown (not proven unsupported) C10.1 NVIDIA policy result. If it is missing,
  fails, or is proven unsupported, stop with a clear CUDA-lane message and
  direct the user to `windows/cpu`; do not install drivers.
- A visible adapter or `Win32_VideoController.AdapterRAM` is never verified
  CUDA/VRAM evidence.

### `8.2.ps1`

- Use observed physical RAM and selected install-volume free space with the
  existing Happy Nerds trial order:
  ```text
  >= 24 GiB: qwen3:14b -> 8b -> 4b -> 1.7b -> 0.6b
  >= 12 GiB: qwen3:8b  -> 4b -> 1.7b -> 0.6b
  >=  8 GiB: qwen3:4b  -> 1.7b -> 0.6b
  >=  4 GiB: qwen3:1.7b -> 0.6b
  otherwise or unknown: qwen3:0.6b
  ```
- Keep the free-disk safeguards: 14b 14 GiB, 8b 9 GiB, 4b 6 GiB, 1.7b 4 GiB,
  and 0.6b 3 GiB.
- The ladder is a pull-and-real-inference test order, never a model-fit promise.
- Pull/test one candidate at a time through the loopback API. Remove only a
  candidate newly pulled by this run if it fails; never remove an existing user
  model.
- `-Model` tests only that requested model and does not silently fall back.
- Save result data: selected model, lane, CPU/CUDA observation facts, disk/RAM,
  test result, timestamp, and explicit `unknown` values where evidence is
  absent. Never place a device VRAM value into catalog model requirements.

### `8.3.ps1`

- Windows has no Linux MOTD behavior. Do not change terminal profiles,
  registry autoruns, startup folders, or console settings.
- Print the concise lane completion card from the asset.
- Write a user-local status command:
  ```text
  $EIGHTBALL_ROOT\bin\8ball-status.ps1
  ```
  It should show the selected model, loopback endpoint, result path, and the
  optional next Jets command. Do not add a PATH entry automatically.
- Jets are explicitly opt-in: say that `ollama signin` is a separate user
  action. Do not sign in, store a token, or pull a cloud model.

## README requirements

Give each lane a customer-useful README describing:

- Windows version and normal-user requirements;
- manual Ollama installation requirement;
- CPU vs. CUDA eligibility and that CUDA drivers are not installed by 8-BALL;
- WSL exclusion;
- state/log/result locations;
- loopback API behavior;
- local trial/fallback semantics; and
- Jets as a separate opt-in.

Link to:

```text
https://docs.ollama.com/windows
https://docs.ollama.com/gpu
https://docs.ollama.com/faq
```

## Tests and validation

Add focused PowerShell tests/fixtures plus platform-neutral validation for:

1. WSL rejects both native Windows lanes;
2. elevated execution rejects before changing state;
3. missing Ollama gives manual-install guidance without downloading;
4. only loopback API is accepted;
5. `windows/cuda` requires working `nvidia-smi` and is never inferred from
   AdapterRAM;
6. failure in CUDA lane points to CPU lane without driver installation;
7. selected install volume is measured or remains unknown;
8. Apple/Linux commands never appear in executable Windows payloads;
9. failed-new-pull versus existing-model preservation works;
10. no profile matrix, catalog fit record, or provider capacity data changes.

Run the strongest available checks:

```bash
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

If PowerShell is available, syntax-check every `.ps1` file and run Windows
unit tests. If Windows execution is unavailable, do not claim end-to-end
testing. Document the exact manual smoke-test commands for a Windows CPU host
and a supported NVIDIA Windows host.

## Commit and report

Use one focused commit:

```text
feat(c10.2): implement real Windows installer lanes
```

Report changed files, checks, PowerShell availability, manual smoke-test
instructions, commit SHA, and PR URL. Keep the PR draft; do not merge it and do
not begin connector/Jets implementation in this task.

# CursorFileC1 — 8-BALL Environment Artifacts

## Purpose

Create a clean environment-artifact process so `8.2` can make intelligent install
decisions without guessing.

The current installer history already has useful deployment work:
`/opt/philosopher/instance.env`, network detection, swap checks, Linux package
setup, Passport/RecordsCore flow, and prior bare-metal/cloud thinking. What is
missing is a stable profile contract that `8.2`, `8.3`, Mac importers, Windows
importers, and the website selector can all understand.

This file defines the next safe step: create a `profiles/` scaffold in
`terminal-glass/8-ball` and document how a separate installer will load
environment artifacts at runtime.

## Design rule

Do not make `8.2` guess all model/instance sizing.

`8.2` may measure hardware. It may load known profile facts. It may select from
a sizing manifest once that manifest exists. It must not invent unsupported
RAM, CPU, GPU, disk, provider, or model-family sizing rules.

## Runtime directory

Create this runtime directory during bootstrap (installer repository):

```bash
/opt/philosopher/profiles
```

Keep this legacy file for backward compatibility:

```bash
/opt/philosopher/instance.env
```

This repository contains a source scaffold:

```bash
profiles/
```

The repo-side `profiles/` directory is documentation/templates and catalog-derived
exports only. The live installer writes to `/opt/philosopher/profiles`.

## Profile directory precedence

`8.2` should resolve the profile directory in this order:

1. `--profile-dir <path>` argument, if added to the script
2. `EIGHTBALL_PROFILE_DIR`, if already exported
3. `NCGPT_PROFILE_DIR`, if already exported
4. `PROFILE_DIR` or `EIGHTBALL_PROFILE_DIR` loaded from `/opt/philosopher/instance.env`
5. Default: `/opt/philosopher/profiles`

If none of the profile artifacts exist, `8.2` should fall back to the legacy
behavior of sourcing `/opt/philosopher/instance.env`.

## Artifact files

Use deterministic file names so Mac, Windows, WSL, Linux, AWS Lightsail,
DigitalOcean, and bare-metal adapters can all write the same contract.

| File | Writer | Purpose |
| --- | --- | --- |
| `00-instance.env` | `0.sh` or platform importer | Normalized install root, host, network, and URL facts |
| `10-platform.env` | `8.2` or importer | OS, provider, instance class, architecture, virtualization/container facts |
| `20-hardware.env` | `8.2` or importer | Measured RAM, CPU threads, disk, GPU, VRAM, and hardware notes |
| `30-catalog.env` | Catalog pinning step | Catalog version, projection version, sizing-manifest version, and source paths |
| `40-selection.env` | Website/auth installer or operator | Requested family/model/variant/deployment mode |
| `50-recommendation.env` | `8.2` | Recommended install target, fallback target, and reason codes |
| `90-result.env` | `8.2` | Final result that `8.3` can display |

All files must be shell-safe `KEY="value"` environment files.

## Minimum variables

| Variable | Meaning |
| --- | --- |
| `EIGHTBALL_PROFILE_SCHEMA_VERSION` | Profile artifact schema version. Start with `1` |
| `EIGHTBALL_PROFILE_DIR` | Resolved runtime profile directory |
| `NCGPT_ROOT` | Install root, normally `/opt/philosopher` |
| `INSTANCE_ADDRESS` | Browser-accessible host/IP, legacy-compatible |
| `PRIVATE_IP` | Private bind address, legacy-compatible |
| `HOST_NAME` | Machine hostname |
| `PUBLIC_BASE_DOMAIN` | Public base domain or nip.io fallback |
| `EIGHTBALL_OS_FAMILY` | `linux`, `macos`, `windows`, `wsl`, or `unknown` |
| `EIGHTBALL_PROVIDER` | `bare_metal`, `aws_lightsail`, `digitalocean`, `mac`, `windows`, `unknown`, etc. |
| `EIGHTBALL_INSTANCE_CLASS` | Provider size/shape when known |
| `EIGHTBALL_RAM_MB` | Measured RAM in MB |
| `EIGHTBALL_CPU_THREADS` | Measured CPU threads |
| `EIGHTBALL_DISK_FREE_GB` | Free install disk in GB |
| `EIGHTBALL_GPU_PRESENT` | `yes`, `no`, or `unknown` |
| `EIGHTBALL_GPU_NAME` | GPU name if known |
| `EIGHTBALL_GPU_VRAM_MB` | GPU VRAM in MB if known |
| `EIGHTBALL_CATALOG_VERSION` | Pinned 8-BALL catalog/projection version |
| `EIGHTBALL_SIZING_MANIFEST_VERSION` | Pinned sizing manifest version |
| `EIGHTBALL_SELECTED_FAMILY_ID` | Selected model family ID |
| `EIGHTBALL_SELECTED_MODEL_ID` | Selected canonical model ID |
| `EIGHTBALL_SELECTED_VARIANT_TAG` | Selected Ollama tag/variant |
| `EIGHTBALL_INSTALL_MODE` | `local`, `jet`, `request`, or `unknown` |

## How `0.sh` should behave

`0.sh` should still generate `/opt/philosopher/instance.env` because existing
scripts depend on it.

Add this behavior in the installer repository:

1. Create `/opt/philosopher/profiles`
2. Write `/opt/philosopher/profiles/00-instance.env`
3. Include `EIGHTBALL_PROFILE_DIR="/opt/philosopher/profiles"` in both files
4. Keep legacy variables such as `INSTANCE_ADDRESS`, `PRIVATE_IP`, `HOST_NAME`,
   `CHAT_URL`, and `WIKI_URL`

## How `8.2` should behave

`8.2` should do four jobs:

1. Resolve the profile directory
2. Load existing profile artifacts in deterministic order
3. Measure missing hardware facts and write `20-hardware.env`
4. Use the future sizing manifest to write `50-recommendation.env` and `90-result.env`

Recommended load order:

```bash
/opt/philosopher/instance.env
${EIGHTBALL_PROFILE_DIR}/00-instance.env
${EIGHTBALL_PROFILE_DIR}/10-platform.env
${EIGHTBALL_PROFILE_DIR}/20-hardware.env
${EIGHTBALL_PROFILE_DIR}/30-catalog.env
${EIGHTBALL_PROFILE_DIR}/40-selection.env
```

Later files may override earlier defaults, but `8.2` should log every file it
loads.

## How `8.3` should behave

`8.3` should read `90-result.env` and present the install decision in
customer-readable form. It should not recalculate sizing independently.

## Security rules

Profile artifacts must not contain license keys, install tokens, Passport JWTs,
Stripe secrets, S3 presigned URLs, customer credentials, or database passwords.

## Acceptance criteria

### In `terminal-glass/8-ball` (metadata-only C1)

1. The repo contains `profiles/` with README and example environment profile
2. Numbered scaffold directories exist for the future C2/C3 sequence
3. `profiles/generated/README.md` documents machine-consumed export location
4. No installer scripts are edited in this repository

### In the separate installer repository (runtime C1)

1. `0.sh` creates `/opt/philosopher/profiles`
2. `/opt/philosopher/instance.env` still works for legacy scripts
3. `8.2` resolves and loads a designated profile directory
4. `8.2` writes measured hardware facts to `20-hardware.env`
5. `8.3` reads `90-result.env` instead of recalculating the install result

## Cursor implementation prompt

```text
Work in terminal-glass/8-ball for metadata-only C1.

Create or preserve the profile artifact contract under profiles/.
Do not edit installer scripts in this repository.

Read AGENTS.md and AGENTS/cursorFileA0.md first.

Required changes in this repo:

1. Ensure profiles/README.md documents the runtime contract, precedence, load
   order, and numbered scaffold directories.

2. Ensure profiles/environment.profile.example.env documents shell-safe
   variable names.

3. Ensure profiles/generated/README.md documents future machine-consumed exports.

4. Do not invent model/instance sizing rules.
5. Do not implement C2 or C3 artifacts in this step.

Installer runtime loader behavior (0.sh, 8.2.sh, 8.3.sh) belongs in a separate
installer repository and is out of scope here.

Run:
   - bash scripts/validate-catalog.sh
   - pytest
   - git diff --check

Report:
   - exact files changed
   - profile scaffold confirmed
   - validation results
   - confirmation that no installer scripts were changed
```

# 8-BALL Profile Artifact Contract (C1)

This directory is the **repo-side metadata scaffold** for the 8-BALL environment
profile artifact contract. It documents the future runtime layout that separate
installer work (`0.sh`, `8.2.sh`, `8.3.sh`) will implement.

This repository is **metadata/catalog only**. Files here are documentation and
templates. Live installers write runtime artifacts under `/opt/philosopher/`.

Do not store secrets in profile artifacts. Passport tokens, license keys, Stripe
secrets, S3 presigned URLs, database passwords, and customer credentials belong
in the authenticated installer flow, not in these environment files.

## Runtime locations

Installers use a writable profile directory:

```bash
/opt/philosopher/profiles
```

The legacy file remains supported for backward compatibility:

```bash
/opt/philosopher/instance.env
```

`0.sh` (or a platform importer) is expected to create `/opt/philosopher/profiles`,
write `00-instance.env`, and keep `/opt/philosopher/instance.env` populated with
legacy variables such as `INSTANCE_ADDRESS`, `PRIVATE_IP`, `HOST_NAME`,
`CHAT_URL`, and `WIKI_URL`.

Both files should include:

```bash
EIGHTBALL_PROFILE_DIR="/opt/philosopher/profiles"
```

See `environment.profile.example.env` for the documented variable contract.

## Decision-sequence directories

The numbered folders describe the future installer decision sequence. In this
repository they are **placeholders only** — C2 and C3 populate them later.

| Directory | Step | Purpose | Status in this repo |
| --- | ---: | --- | --- |
| `01-families/` | 1 | Model family identity and eligibility metadata | Scaffold only (C2) |
| `02-models/` | 2 | Canonical model identity, aliases, and variant lists | Scaffold only (C2) |
| `03-deployment-types/` | 3 | Deployment lane definitions (bare metal, providers, Jet, Mac, Windows) | Scaffold only (C2) |
| `04-hard-disk/` | 4 | Hard-disk qualification gates | Scaffold only (C3) |
| `05-ram/` | 5 | RAM qualification gates | Scaffold only (C3) |
| `06-cpu/` | 6 | CPU qualification gates | Scaffold only (C3) |
| `07-gpu/` | 7 | GPU/VRAM qualification gates | Scaffold only (C3) |
| `generated/` | — | Machine-consumed JSON and shell-safe `.env` exports | See `generated/README.md` |

Use `.md` files for human-readable source notes inside the numbered folders.
Use generated `.json` and `.env` files under `generated/` for anything `8.2`,
`8.3`, the website selector, or future Docker routing will consume.

Do not make Bash parse Markdown. Installers should consume generated JSON or
`.env` artifacts.

## Future 8.2 profile directory precedence

When implemented in the installer repository, `8.2.sh` should resolve the
profile directory in this order:

1. `--profile-dir <path>` argument, if implemented
2. `EIGHTBALL_PROFILE_DIR`, if already exported in the environment
3. `NCGPT_PROFILE_DIR`, if already exported in the environment
4. `PROFILE_DIR` or `EIGHTBALL_PROFILE_DIR` loaded from `/opt/philosopher/instance.env`
5. Default: `/opt/philosopher/profiles`

If no profile artifacts exist, `8.2` should fall back to the legacy behavior of
sourcing `/opt/philosopher/instance.env` only.

## Future 8.2 load order

After resolving `EIGHTBALL_PROFILE_DIR`, `8.2` should load existing artifacts
in this order when present. Later files may override earlier defaults; `8.2`
should log every file it loads.

```bash
/opt/philosopher/instance.env
${EIGHTBALL_PROFILE_DIR}/00-instance.env
${EIGHTBALL_PROFILE_DIR}/10-platform.env
${EIGHTBALL_PROFILE_DIR}/20-hardware.env
${EIGHTBALL_PROFILE_DIR}/30-catalog.env
${EIGHTBALL_PROFILE_DIR}/40-selection.env
```

`8.2` does not load `50-recommendation.env` or `90-result.env` as inputs — it
writes them.

## Runtime artifact files

Deterministic file names allow Linux, Mac, Windows, WSL, AWS Lightsail,
DigitalOcean, and bare-metal adapters to write the same contract.

| File | Writer | Purpose |
| --- | --- | --- |
| `00-instance.env` | `0.sh` or platform importer | Normalized install root, host, network, and URL facts |
| `10-platform.env` | `8.2` or importer | OS, provider, instance class, architecture, virtualization/container facts |
| `20-hardware.env` | `8.2` or importer | Measured RAM, CPU threads, disk, GPU, VRAM, and hardware notes |
| `30-catalog.env` | Catalog pinning step | Catalog version, projection version, sizing-manifest version, and source paths |
| `40-selection.env` | Website/auth installer or operator | Requested family, model, variant, and deployment mode |
| `50-recommendation.env` | `8.2` | Recommended install target, fallback target, and reason codes |
| `90-result.env` | `8.2` | Final result that `8.3` displays |

All files must be shell-safe `KEY="value"` environment files.

## Future 8.2 output files

`8.2` is expected to:

1. Resolve the profile directory (precedence above).
2. Load existing input artifacts (load order above).
3. Measure missing hardware facts and write `${EIGHTBALL_PROFILE_DIR}/20-hardware.env`.
4. Use a future sizing manifest to write:
   - `${EIGHTBALL_PROFILE_DIR}/50-recommendation.env`
   - `${EIGHTBALL_PROFILE_DIR}/90-result.env`

`8.3` should prefer `${EIGHTBALL_PROFILE_DIR}/90-result.env`, then fall back to
`/opt/philosopher/8ball-result.txt` for compatibility. `8.3` displays the
install decision; it does not recalculate sizing.

## Design rule

Do not make `8.2` guess model or instance sizing.

`8.2` may measure hardware, load known profile facts, and select from a sizing
manifest once that manifest exists. It must not invent unsupported RAM, CPU, GPU,
disk, provider, or model-family sizing rules.

## Related documentation

- `AGENTS/CursorFileC1-environment-artifacts.md` — full C1 specification
- `AGENTS/CursorFileC2-environment-artifact-sequencing.md` — C2 sequencing brief
- `AGENTS/CursorFileC3-environment-gates-testing-plan.md` — C3 gates plan
- `environment.profile.example.env` — example variable contract
- `generated/README.md` — machine-consumed export location

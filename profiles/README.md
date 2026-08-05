# 8-BALL Profile Artifact Contract (C1)

This directory documents the **runtime** environment profile artifact contract for
separate installer work (`0.sh`, `8.2.sh`, `8.3.sh`). Live installers write
artifacts under `/opt/philosopher/profiles`.

This repository is **metadata/catalog only**. Files here include documentation,
templates, and **repo-root profile exports** derived from canonical C5 generated
pages.

## Repo-root profile exports

Each canonical model has a root folder:

```text
profiles/<model-slug>/
```

C7.1 adds the platform/hardware lane skeleton under every model folder (folders
only; C8 will populate step files):

```text
profiles/<model-slug>/ubuntu/cpu/
profiles/<model-slug>/ubuntu/cuda/
profiles/<model-slug>/mac/apple-silicon/
profiles/<model-slug>/mac/intel/
profiles/<model-slug>/windows/cpu/
profiles/<model-slug>/windows/cuda/
profiles/<model-slug>/cloud/digitalocean/cpu-droplet/
profiles/<model-slug>/cloud/digitalocean/gpu-droplet/
profiles/<model-slug>/cloud/aws-lightsail/cpu/
profiles/<model-slug>/cloud/aws-lightsail/gpu/
```

Create or refresh the lane skeleton with:

```bash
bash scripts/create-profile-platform-tree.sh
```

`8.2` will detect platform/hardware, select the matching profile branch, and run
that branch's steps 3–7 from the populated lane files (C8).

Public, machine-readable profile exports are also generated at the repository root
under `profiles/` from the canonical C5 page tree:

```text
profiles/manifest.json
profiles/index.csv
profiles/families/<family-slug>/profile.json
profiles/models/<model-slug>/model.json
profiles/models/<model-slug>/<3-7>/profile.json
profiles/deployment-classes/<3-7>/profile.json
profiles/provider-assumptions/          # labeled planning assumptions only
```

Regenerate with:

```bash
eight-ball generate-root-profiles
```

Primary source (required):

- `data/generated/pages/install-manifest.json`
- `data/generated/pages/**`

Secondary reference (assumptions only, labeled `provenance_status: assumption`):

- `data/normalized/hardware-assumed-profiles.json` (imported from AGENTS CSV research)

Do not build `profiles/` by crawling unrelated repository files. Do not treat
`CursorFile*.md` agent briefs as profile data.

## Canonical generated pages (C5)

Installer-facing model, family, and deployment metadata pages are generated under:

```text
data/generated/pages/families/
data/generated/pages/deployment-types/<3-7>/
data/generated/pages/models/<model-slug>/<3-7>/
data/generated/pages/install-manifest.json
```

Regenerate with `eight-ball generate`. Validate with `eight-ball validate-pages`.

`8.2` must read `data/generated/pages/install-manifest.json` — see
`docs/install-manifest-contract.md`.

Do not create or reference `data/generated/pages/02-models/`. Deployment type
folders are numbered `3` through `7` per `config/deployment_types.yaml`.

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

## C3 gate scaffolds (future)

Empty placeholders for future sizing-gate work:

| Directory | Step | Purpose |
| --- | ---: | --- |
| `04-hard-disk/` | 4 | Hard-disk qualification gates |
| `05-ram/` | 5 | RAM qualification gates |
| `06-cpu/` | 6 | CPU qualification gates |
| `07-gpu/` | 7 | GPU/VRAM qualification gates |

## Future 8.2 profile directory precedence

When implemented in the installer repository, `8.2.sh` should resolve the
profile directory in this order:

1. `--profile-dir <path>` argument, if implemented
2. `EIGHTBALL_PROFILE_DIR`, if already exported in the environment
3. `NCGPT_PROFILE_DIR`, if already exported in the environment
4. `PROFILE_DIR` or `EIGHTBALL_PROFILE_DIR` loaded from `/opt/philosopher/instance.env`
5. Default: `/opt/philosopher/profiles`

## Future 8.2 load order

After resolving `EIGHTBALL_PROFILE_DIR`, `8.2` should load existing artifacts
in this order when present:

```bash
/opt/philosopher/instance.env
${EIGHTBALL_PROFILE_DIR}/00-instance.env
${EIGHTBALL_PROFILE_DIR}/10-platform.env
${EIGHTBALL_PROFILE_DIR}/20-hardware.env
${EIGHTBALL_PROFILE_DIR}/30-catalog.env
${EIGHTBALL_PROFILE_DIR}/40-selection.env
```

## Runtime artifact files

| File | Writer | Purpose |
| --- | --- | --- |
| `00-instance.env` | `0.sh` or platform importer | Normalized install root, host, network, and URL facts |
| `10-platform.env` | `8.2` or importer | OS, provider, instance class, architecture facts |
| `20-hardware.env` | `8.2` or importer | Measured RAM, CPU, disk, GPU, VRAM |
| `30-catalog.env` | Catalog pinning step | Catalog version and source paths |
| `40-selection.env` | Website/auth installer | Requested family, model, variant, deployment mode |
| `50-recommendation.env` | `8.2` | Recommended install target and reason codes |
| `90-result.env` | `8.2` | Final result that `8.3` displays |

## Design rule

Do not make `8.2` guess model or instance sizing. Use
`data/generated/pages/install-manifest.json` as the machine source of truth.

## Related documentation

- `AGENTS/CursorFileC1-environment-artifacts.md` — full C1 specification
- `AGENTS/cursorFileC5-profile-folder-structure.md` — C5 generated page tree
- `docs/install-manifest-contract.md` — 8.2 manifest lookup contract
- `environment.profile.example.env` — example variable contract

## C10 AGENTS-generated profiles (glass ball)

Regenerate the model/size/profile matrix from AGENTS/ data:

```bash
python3 scripts/generate-profiles-from-agents.py
python3 scripts/validate-profiles-from-agents.py
```

Authoritative inputs: `AGENTS/data-science/P4-Public-Catalog/index/models.json`,
`AGENTS/data-science/P3-Ollama-Metadata-Catalog/indexes/model-selection.json`, and
classified `AGENTS/TG-8Ball-*.csv` hardware research files.


# C10 model profiles namespace

`profiles/` is the canonical **C10 model-selection and install-lane** namespace for
this repository. It is metadata only — no model weights, Ollama blobs, or installer
payloads.

This tree is separate from the **runtime** profile contract installed at
`/opt/philosopher/profiles` (see `docs/profile-runtime/`).

## Layout

Every model has a paired JSON page and lane directory:

```text
profiles/<model-slug>.json
profiles/<model-slug>/
  ubuntu/cpu/
  ubuntu/cuda/
  mac/apple-silicon/
  mac/intel/
  windows/cpu/
  windows/cuda/
  cloud/digitalocean/cpu-droplet/
  cloud/digitalocean/gpu-droplet/
  cloud/aws-lightsail/cpu/
  cloud/aws-lightsail/gpu/
```

Each lane leaf contains:

```text
lane.json
3-cpu.json
4-ram.json
5-hard_disk.json
6-CPU_only.json
7-video_card.json
```

## Allowed profile-root files

| File | Purpose |
| --- | --- |
| `README.md` | This document |
| `c10-index.json` | Installer-facing model/lane index |
| `manifest.json` | C10-only generation manifest (optional) |
| `<model-slug>.json` | One model data page per catalog model |

No other top-level files or directories are permitted under `profiles/`.

Forbidden paths (removed by C10.1-1 cleanup):

- `profiles/families/`, `profiles/models/`, `profiles/deployment-classes/`
- `profiles/provider-assumptions/`, `profiles/index.csv`

## Canonical catalog metadata (not under profiles/)

Family, model, and deployment metadata pages live under the C5 generated tree:

```text
data/generated/pages/families/
data/generated/pages/models/
data/generated/pages/deployment-types/<3-7>/
data/generated/pages/install-manifest.json
```

C10 lane **provider assumptions** live at:

```text
data/generated/provider-assumptions/
```

## Regenerate and validate

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
```

The legacy `eight-ball generate-root-profiles` command has been removed. It previously
recursively cleaned `profiles/` and recreated obsolete compatibility exports. Only the
C10 generator above may write model pages, lane trees, and `profiles/c10-index.json`.

## Public entrypoint

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh | sh -s -- gemma
```

Root `trial-install.sh` detects the platform lane, reads `profiles/<model-slug>.json`,
and selects the largest size with a confirmed lane fit via `install/shared/c10-select-model.py`.

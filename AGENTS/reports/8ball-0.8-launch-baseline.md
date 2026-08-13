# 8-BALL 0.8 Launch Baseline

Date: 2026-08-13

## Current Architecture

```
trial-install.sh (root dispatcher)
  -> detect lane -> install/<lane>/trial-install.sh
       -> 8.1.sh  (Ollama foundation)
       -> 8.2.sh  (hardware -> model selection + inference test)
       -> 8.3.sh  (MOTD + remember helper)

install/trial-install.sh -> install/ubuntu/trial-install.sh (backward compat)
```

Scripts live under `install/ubuntu/` (generic) and per-lane copies under
`install/ubuntu/cpu/`, `install/ubuntu/cuda/`, cloud lanes, etc.

Shared C10 helpers already exist:

- `install/shared/c10-select-model.py` — lane fit selection for `--model-slug`
- `install/shared/c10-model-hook.sh` — bash wrappers for C10 selection

## Profile Data Discovered

Model-first profile tree at `profiles/<model-slug>/<lane>/`:

| Lane path | Install dir | Status |
| --- | --- | --- |
| `ubuntu/cpu` | `install/ubuntu/cpu/` | Complete lane JSON + provider assumption |
| `ubuntu/cuda` | `install/ubuntu/cuda/` | Complete |
| `mac/apple-silicon` | `install/mac/apple-silicon/` | Complete |
| `mac/intel` | `install/mac/intel/` | Complete |
| `windows/cpu` | `install/windows/cpu/` | PowerShell lanes |
| `windows/cuda` | `install/windows/cuda/` | PowerShell lanes |
| `cloud/digitalocean/cpu-droplet` | `install/cloud/digitalocean/cpu-droplet/` | Complete |
| `cloud/digitalocean/gpu-droplet` | `install/cloud/digitalocean/gpu-droplet/` | Complete |
| `cloud/aws-lightsail/cpu` | `install/cloud/aws-lightsail/cpu/` | Complete |
| `cloud/aws-lightsail/gpu` | `install/cloud/aws-lightsail/gpu/` | Complete |

Supporting data:

- `profiles/qwen3.json` — model sizes and ollama refs
- `profiles/qwen3/<lane>/lane.json` — per-lane `size_fit` with `fit_status`
- `profiles/provider-assumptions/*.json` — lane hardware assumptions
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json` — RAM-band pilot candidates (qwen3 ladder)
- `data/generated/pages/install-manifest.json` — deployment-type manifest (types 3–7)
- `profiles/provider-compatibility/ubuntu/lane-runtime-contract-projection.json` — lane taxonomy

## Profile Data Actually Consumable by 8.2.sh Today

| Artifact | Consumable | Notes |
| --- | --- | --- |
| `profiles/qwen3/<lane>/lane.json` | Yes | `size_fit` with `fit_status=fit` gives candidate refs |
| `profiles/qwen3.json` | Yes | Size ordering for largest-first selection |
| `8ball-base-pilot-menu.json` | Yes | RAM-band fallback when lane fit is unverified |
| `install-manifest.json` | Partial | Deployment types 3–7; not lane-aware |
| Provider assumptions | Reference | Static assumed hardware; runtime detection overrides |
| Cloud provider metadata | Optional | DMI/sysfs hints; no hard dependency on IMDS |

**Gap:** `8.2.sh` currently uses only RAM/GPU-VRAM heuristics + manifest `preferred_order`.
C10 hooks exist but only activate with `--model-slug`; default trial path ignores profile tree.

## Gaps

1. **8.1.sh** — No localhost bind enforcement; no listener verification via `ss`
2. **8.2.sh** — RAM ladder/manifest only; profile tree not primary selection path
3. **8.3.sh** — Model status from result file only; no `ollama list` verification; no temp alerts/bulletin; no trial-installed marker
4. **Version contract** — No cross-script version check
5. **Release pinning** — Defaults to mutable `main`; no SHA verification
6. **Permissions** — Alert state files not yet implemented; must avoid 0666
7. **Test harness** — No offline installer validation workflow

## Files to Modify

- `install/shared/` — new version, Ollama localhost, hardware resolve, model test, MOTD helpers
- `install/ubuntu/8.1.sh`, `8.2.sh`, `8.3.sh`, `trial-install.sh`
- `install/ubuntu/cpu/`, `install/ubuntu/cuda/` — thin wrappers to canonical scripts
- `install/trial-install.sh`, `trial-install.sh` — version + release pinning
- `install/releases/v0.8.0/manifest.json` — release integrity manifest
- `scripts/generate-release-manifest.sh`, `scripts/test-installer-harness.sh`
- `docs/proxmox-launch-test-matrix.md`
- `AGENTS/reports/8ball-0.8-launch-hardening-report.md`

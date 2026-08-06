# C10 generation report

Generated: 2026-08-06

Generator: `scripts/generate-c10-profiles.py`  
Validator: `scripts/validate-c10-profiles.py`

## Counts

| Artifact | Count |
| --- | --- |
| Model data pages (`profiles/<model-slug>.json`) | 234 |
| Size records (across all model pages) | 7,271 |
| Install lanes (`install/<lane>/`) | 10 |
| Profile lane leaves (`profiles/<model>/<lane>/`) | 2,340 |
| Stage files per leaf (`lane.json`, `3-cpu` … `7-video_card`) | 14,040 |
| Provider assumption files | 10 |
| C10 index rows | 2,340 |
| Shell scripts checked with `bash -n` | 41 |

## Install lanes

```text
install/ubuntu/cpu/
install/ubuntu/cuda/
install/mac/apple-silicon/
install/mac/intel/
install/windows/cpu/
install/windows/cuda/
install/cloud/digitalocean/cpu-droplet/
install/cloud/digitalocean/gpu-droplet/
install/cloud/aws-lightsail/cpu/
install/cloud/aws-lightsail/gpu/
```

## Provider assumptions

```text
profiles/provider-assumptions/ubuntu-cpu.json
profiles/provider-assumptions/ubuntu-cuda.json
profiles/provider-assumptions/mac-apple-silicon.json
profiles/provider-assumptions/mac-intel.json
profiles/provider-assumptions/windows-cpu.json
profiles/provider-assumptions/windows-cuda.json
profiles/provider-assumptions/cloud-digitalocean-cpu-droplet.json
profiles/provider-assumptions/cloud-digitalocean-gpu-droplet.json
profiles/provider-assumptions/cloud-aws-lightsail-cpu.json
profiles/provider-assumptions/cloud-aws-lightsail-gpu.json
```

## Data gaps

1. `AGENTS/data-science/ollama-mapping/` does not exist. Normalized catalog input used instead.

2. AWS Lightsail GPU VRAM/CUDA/Ollama GPU support remain **unknown** until runtime probe upgrades `AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv` — see `C10.1-1-executable-install-matrix/DATA-GAP.md`.

3. Per-tag RAM/VRAM for non-default tags uses `estimated` values derived from `download_size_bytes` when manifest deployment estimates are absent.

## Conservative fit semantics

- `fit_status`: `fit` | `no_fit` | `unknown`
- `fits: true` only when `fit_status=fit`
- Selector returns `selection_status: unverified` when no confirmed fit exists (never falls back to smallest unknown size)

## Provider-assumption smoke tests

| Model slug | Lane | Result | Status |
| --- | --- | --- | --- |
| `gemma` | `ubuntu/cpu` | `gemma:7b` | PASS — confirmed fit |
| `qwen3` | `ubuntu/cpu` | `qwen3:4b` | PASS — largest confirmed fit |
| `qwen3` | `cloud/aws-lightsail/gpu` | none | PASS — unverified (unknown VRAM/CUDA) |
| `qwen3:235b` | `cloud/digitalocean/gpu-droplet` | n/a | PASS — `no_fit` on smallest DO GPU plan |

## Public entrypoint

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh | sh -s -- gemma4
```

Root `trial-install.sh` detects platform lane, delegates to `install/<lane>/trial-install.sh`, and passes `--model-slug` through to `8.2.sh` via `install/shared/c10-select-model.py`.

## Files created/moved (summary)

**New active prompt**

- `AGENTS/cursorFile.C10.1-1-executable-install-matrix.md`

**Moved to history (`git mv`)**

- `AGENTS/history/cursorFileC7-profile-model-tree.md`
- `AGENTS/history/cursorFileC6.md`
- `AGENTS/history/cursorC9.md`
- `AGENTS/history/cursorC10-glass-ball-execute.md`
- `AGENTS/history/cursorFileC5-profile-folder-structure.md`
- `AGENTS/history/cursorFileC4-helpers-plan.md`
- `AGENTS/history/CursorFileC3-environment-gates-testing-plan.md`
- `AGENTS/history/CursorFileC2-environment-artifact-sequencing.md`
- `AGENTS/history/CursorFileC1-environment-artifacts.md`
- `AGENTS/history/CursorFileC0-8-BALL-CATALOG-DEVELOPMENT-BRIEF.md`
- `AGENTS/history/README.md`

**Generator / validator / installer**

- `scripts/generate-c10-profiles.py`
- `scripts/validate-c10-profiles.py`
- `trial-install.sh` (repository root)
- `install/shared/c10-select-model.py`
- `install/shared/c10-model-hook.sh`
- `install/<lane>/` × 10 (generated installer payloads)
- `profiles/<model-slug>.json` × 234
- `profiles/<model-slug>/<lane>/` × 2,340
- `profiles/provider-assumptions/<lane-id>.json` × 10
- `profiles/c10-index.json`

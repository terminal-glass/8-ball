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

## Provider-assumption smoke tests

| Model slug | Lane | Selected `ollama_ref` | Status |
| --- | --- | --- | --- |
| `qwen3` | `ubuntu/cpu` | `qwen3:8b` | PASS — largest size fitting lane assumptions |
| `gemma` | `ubuntu/cpu` | `gemma:7b` | PASS — promoted size fits lane |

Command:

```bash
python3 install/shared/c10-select-model.py qwen3 ubuntu/cpu profiles/provider-assumptions/ubuntu-cpu.json
python3 install/shared/c10-select-model.py gemma ubuntu/cpu profiles/provider-assumptions/ubuntu-cpu.json
```

## Validation

```bash
python3 scripts/validate-c10-profiles.py
# valid: true
```

## Data gaps

1. `AGENTS/data-science/ollama-mapping/` does not exist. Normalized catalog input used instead:
   - `data/normalized/tags.json`
   - `data/normalized/models.json`
   - `data/normalized/hardware-assumed-profiles.json`
   - `AGENTS/TG-8Ball-*.csv`
   - `AGENTS/data-science/P2-Provider-Datasets/`

2. `cloud/aws-lightsail/gpu` hardware defaults incomplete — see `C10.1-1-executable-install-matrix/DATA-GAP.md`

3. Per-tag RAM/VRAM for non-default tags uses `estimated` values derived from `download_size_bytes` when manifest deployment estimates are absent.

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

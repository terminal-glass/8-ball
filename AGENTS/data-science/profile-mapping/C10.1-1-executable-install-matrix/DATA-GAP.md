# DATA-GAP: AWS Lightsail GPU lane

`cloud/aws-lightsail/gpu` provider assumptions are incomplete.

## Missing source measurements

- No committed AWS Lightsail GPU bundle records in `AGENTS/data-science/P2-Provider-Datasets/`
- `AGENTS/TG-8Ball-GPU-Source-Inventory.csv` lists inventory targets but not full Lightsail GPU plan RAM/VRAM/disk fields

## Current behavior

- Install lane scripts are populated from `install/cloud/aws-lightsail/`
- Provider assumption file `profiles/provider-assumptions/cloud-aws-lightsail-gpu.json` marks `provenance_status: data_gap`
- Profile stage files for this lane retain `null` hardware limits where source data is absent

## Resolution path

Import provider-published Lightsail GPU bundle metadata into P2 provider datasets, then regenerate with `python3 scripts/generate-c10-profiles.py`.

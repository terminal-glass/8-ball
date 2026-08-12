# Provider compatibility projections

Plan-level compatibility matrices live outside the model profile tree.
They join each normalized model size with published provider plan capacity
without multiplying `profiles/index.csv` or adding plan folders under models.

## AWS Lightsail (C10.1-5)

- `aws-lightsail-cpu.csv` — 11 Linux/Unix general-purpose bundles × all C10 sizes
- `aws-lightsail-gpu.csv` — 3 Lightsail for Research GPU plans × all C10 sizes

Source tables:
- `AGENTS/data-science/profile-mapping/aws-lightsail-linux-bundles.csv`
- `AGENTS/data-science/profile-mapping/aws-lightsail-research-gpu-bundles.csv`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`

Regenerate with `python3 scripts/generate-c10-profiles.py`.

## DigitalOcean Droplets (C10.1-9)

- `digitalocean/catalog.json` and `catalog.csv` — 33-plan base-pilot provider snapshot
- `digitalocean/cpu-plan-compatibility.csv` — 24 CPU plans × all C10 sizes
- `digitalocean/gpu-plan-compatibility.csv` — 9 on-demand GPU plans × all C10 sizes

Source tables:
- `AGENTS/data-science/profile-mapping/digitalocean-raw-sizes-2026-08-12.json`
- `AGENTS/data-science/profile-mapping/digitalocean-base-pilot-catalog.json`
- `AGENTS/data-science/profile-mapping/digitalocean-base-pilot-selection.md`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`

Regenerate with `python3 scripts/generate-c10-profiles.py`.

## Ubuntu runtime hosts (C10.1-10)

- `ubuntu/host-capability-categories.json` and `.csv` — 10 runtime host categories
- `ubuntu/runtime-observation-contract.json` — Linux evidence contract
- `ubuntu/lane-runtime-contract-projection.json` — `ubuntu/cpu` and `ubuntu/cuda` projections

Source tables:
- `AGENTS/data-science/profile-mapping/ubuntu-runtime-capability-taxonomy.json`
- `AGENTS/data-science/profile-mapping/ubuntu-runtime-observation-contract.md`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`

Regenerate with `python3 scripts/generate-c10-profiles.py`.

## Windows runtime hosts (C10.1-11)

- `windows/host-capability-categories.json` and `.csv` — runtime host categories
- `windows/runtime-observation-contract.json` — Windows evidence contract
- `windows/lane-runtime-contract-projection.json` — `windows/cpu` and `windows/cuda` projections

Source tables:
- `AGENTS/data-science/profile-mapping/windows/runtime-capability-taxonomy.json`
- `AGENTS/data-science/profile-mapping/windows/runtime-observation-contract.md`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`

Regenerate with `python3 scripts/generate-c10-profiles.py`.

## macOS runtime hosts (C10.1-12)

- `macos/host-capability-categories.json` and `.csv` — runtime host categories
- `macos/runtime-observation-contract.json` — macOS evidence contract
- `macos/lane-runtime-contract-projection.json` — `mac/apple-silicon` and `mac/intel` projections

Source tables:
- `AGENTS/data-science/profile-mapping/macos/runtime-capability-taxonomy.json`
- `AGENTS/data-science/profile-mapping/macos/runtime-observation-contract.md`
- `scripts/macos-observe-host.sh`

Regenerate with `python3 scripts/generate-c10-profiles.py`.

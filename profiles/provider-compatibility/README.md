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

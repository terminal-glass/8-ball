# P1 Estimator — Static Dataset Foundation

This folder is **Step P1** of the YC-GPT installer planning system. It contains **static estimator data only** — no recommendation logic, no installer scripts, and no model payloads.

## Purpose

The estimator will eventually protect customers from poorly planned NoCloudGPT deployments by comparing hardware and workload requirements against published cloud specifications and internal planning templates.

## Contents

| Path | Description |
| --- | --- |
| `data/DO/droplets.json` | DigitalOcean Droplet specifications (provider data) |
| `data/LS/lightsail-linux-ipv4.json` | AWS Lightsail Linux/Unix bundles with public IPv4 (provider data) |
| `data/NC/cpu-only-templates.json` | Internal NoCloudGPT CPU-only hardware planning templates |
| `data/NC/gpu-templates.json` | Internal NoCloudGPT GPU hardware planning templates |
| `data/NC/overhead-reserves.json` | Application stack overhead reserves (excludes model sizes) |
| `data/NC/workload-profiles.json` | Static workload metadata profiles |
| `data/catalog.json` | Dataset index |
| `data/schema.json` | JSON Schema field definitions |

## Data Sources

- **DigitalOcean** and **AWS Lightsail** files contain provider specifications sourced from official pricing and documentation pages.
- **NC/** files are **internal NoCloudGPT planning guidance**, not official cloud-provider plans.
- **Ollama model metadata** remains in the separate `ycgpt-8.sh` repository. Model payloads are **not** downloaded or stored here.

## Future Flow

```text
Provider specifications
+ NoCloudGPT templates
+ Workload profile
+ Ollama metadata catalog
= deployment compatibility estimate
```

Recommendation logic, scoring, and installer generation will be created in later P-steps.

## Validation

Dataset files are JSON arrays (or a catalog object) validated against `data/schema.json`. Run validation from the repository root before consuming these files in downstream steps.

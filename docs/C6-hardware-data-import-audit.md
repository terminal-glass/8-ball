# C6 Hardware Data Import Audit

This audit documents the C6 import gate for the AGENTS `TG-8Ball-*.csv` collection and
recovered P2 provider JSON sources. It was produced by `eight-ball import-agents-csv`.

**8.2 installer wiring remains out of scope.** This layer enriches C5 generated pages and
`install-manifest.json` only.

## Summary

| Category | Imported records | Primary key |
| --- | ---: | --- |
| Provider instance data | 52 | `provider + product_line + provider_plan_id` |
| Provider CPU instances | 42 | same |
| Provider GPU instances | 10 | same |
| Assumed hardware profiles | 17 | `profile_id` |
| Measured hardware hosts | 1 | `host_profile_id` |
| Accelerator classes | 7 | `accelerator_class_id` |
| Deployment types | 5 | `deployment_type_id` (`3`–`7`) |

- True duplicate keys: **0**
- Intentional overlaps preserved: **5**
- Rejected import rows: **0**
- Control/provenance rows imported as hardware: **0**

## File inventory

| File | Classification | Imported | Primary key | Rows read | Rows imported |
| --- | --- | --- | --- | ---: | ---: |
| `AGENTS/TG-8Ball-AWS-Lightsail-Research-GPU-Plans.csv` | provider_instance_data | yes | provider composite | 3 | 3 |
| `AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-NVIDIA.csv` | provider_instance_data | yes | provider composite | 5 | 5 |
| `AGENTS/TG-8Ball-DigitalOcean-GPU-Droplets-AMD.csv` | provider_instance_data | yes | provider composite | 2 | 2 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/lightsail/linux-unix-public-ipv4-bundles.json` | provider_instance_data | yes | provider composite | 13 | 13 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/basic.json` | provider_instance_data | yes | provider composite | 7 | 7 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/cpu-optimized.json` | provider_instance_data | yes | provider composite | 6 | 6 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/general-purpose.json` | provider_instance_data | yes | provider composite | 6 | 6 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/memory-optimized.json` | provider_instance_data | yes | provider composite | 5 | 5 |
| `AGENTS/data-science/P2-Provider-Datasets/providers/digitalocean/storage-optimized.json` | provider_instance_data | yes | provider composite | 5 | 5 |
| `AGENTS/TG-8Ball-Client-Hardware-Assumptions.csv` | assumed_hardware_profiles | yes | `profile_id` | 10 | 10 |
| `AGENTS/TG-8Ball-CUDA-Server-Assumptions.csv` | assumed_hardware_profiles | yes | `profile_id` | 7 | 7 |
| `AGENTS/TG-8Ball-Measured-GPU-Hosts.csv` | measured_hardware_inventory | yes | `host_profile_id` | 1 | 1 |
| `AGENTS/TG-8Ball-Accelerator-Classes.csv` | accelerator_classification | yes | `accelerator_class_id` | 7 | 7 |
| `config/deployment_types.yaml` | accelerator_classification | yes | `deployment_type_id` | 5 | 5 |
| `AGENTS/TG-8Ball-GPU-Source-Inventory.csv` | control_and_provenance | no | control row | 5 | 0 |
| `AGENTS/TG-8Ball-GPU-Recovered-Counts.csv` | control_and_provenance | no | control row | 6 | 0 |
| `AGENTS/TG-8Ball-GPU-Cursor-Checklist.csv` | control_and_provenance | no | control row | 9 | 0 |
| `AGENTS/TG-8Ball-Provider-Recovery-Source-Inventory.csv` | control_and_provenance | no | control row | 15 | 0 |
| `AGENTS/TG-8Ball-Provider-Recovery-Recovered-Counts.csv` | control_and_provenance | no | control row | 11 | 0 |
| `AGENTS/TG-8Ball-Provider-Recovery-Cursor-Checklist.csv` | control_and_provenance | no | control row | 7 | 0 |

Additional non-CSV control/provenance artifacts (not imported):

- `AGENTS/cursorFileC6.md` — C6 specification
- P2 index files (`provider-summary.json`, `providers.json`) — validation references only

## Recovered-count contract checks

Counts are read from the recovered-count CSV files; they are not hardcoded.

| Metric | Imported | Expected (counts CSV) | Status |
| --- | ---: | ---: | --- |
| AWS Lightsail for Research GPU plans | 3 | 3 | pass |
| DigitalOcean NVIDIA GPU rows | 5 | 5 | pass |
| DigitalOcean AMD GPU rows | 2 | 2 | pass |
| Measured local GPU host rows | 1 | 1 | pass |
| Accelerator classes | 7 | 7 | pass |
| CUDA server assumption profiles | 7 | 7 | pass |
| Lightsail CPU bundle records | 13 | 25 | **blocked mismatch** |
| DigitalOcean CPU droplet records | 29 | 31 | **blocked mismatch** |

The Lightsail and DigitalOcean CPU count mismatches reflect the committed P2 JSON snapshot
(13 Lightsail bundles, 29 DigitalOcean droplets). Missing upstream rows were **not**
reconstructed from summary CSVs. The provider recovery inventory and counts files are
preserved; import reports the gap instead of inventing provider specifications.

## Intentional overlaps preserved

Five relationship overlaps were retained (shared deployment type IDs across namespaces with
distinct dedup keys). Examples:

- Multiple hardware profiles and provider instances mapping to deployment type `5`
- Shared deployment type references between assumed profiles and accelerator classes
- Provider and assumption records sharing VRAM bands without merging rows

## Unresolved / unknown fields

The import preserves explicit unknowns instead of inventing values:

- AWS Lightsail for Research GPU plans: `gpu_model`, `gpu_vendor`, `vram_gb_per_gpu` remain null; `accelerator_class_id` is `unknown_gpu`
- Measured host `local-brain1-rtx3060-12gb`: `system_ram_gb` and `cpu_threads` remain unknown; `ollama_inference_verified` is `false`
- Multi-GPU provider options such as `1|8` preserve `gpu_count_options` without collapsing per-device VRAM

## Canonical output files

Committed normalized hardware layer:

- `data/normalized/hardware-provider-instances.json`
- `data/normalized/hardware-assumed-profiles.json`
- `data/normalized/hardware-measured-hosts.json`
- `data/normalized/hardware-accelerator-classes.json`
- `data/normalized/hardware-deployment-types.json`
- `data/normalized/hardware-import-meta.json`

Reproducible machine report (generated, not committed):

- `data/generated/provider-import-report.json`

## C5 enrichment

`eight-ball generate` imports hardware data, then enriches:

- per-deployment `hardware_enrichment` references in model deployment pages and manifest entries
- top-level `hardware_catalog` and `hardware_data_version` in `install-manifest.json`

Lookup contract unchanged:

```text
manifest.models[model_id].deployments[deployment_type_id]
```

## Validation commands

```bash
python3 -m eight_ball import-agents-csv
python3 -m eight_ball validate-agents-csv
python3 -m pytest -q
python3 -m eight_ball generate
python3 -m eight_ball validate-pages
bash scripts/validate-catalog.sh
```

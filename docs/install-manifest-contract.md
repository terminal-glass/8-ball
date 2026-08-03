# 8.2 Install Manifest Contract (C5)

This document defines the **future** machine-readable manifest that `8.2.sh` must
read after C5 page generation. It is documentation only — the manifest file is not
generated until the C5 page generator runs.

## Manifest path

```text
data/generated/pages/install-manifest.json
```

`8.2` must read this manifest. It must **not** scrape Markdown README files or
guess model or deployment identity from loose folder names.

## Lookup contract

The installer resolves a selected model and deployment type with:

```text
manifest.models[model_id].deployments[deployment_type_id]
```

Valid `deployment_type_id` values are exactly: `"3"`, `"4"`, `"5"`, `"6"`, `"7"`.

Deployment type definitions live in `config/deployment_types.yaml`.

## Minimum manifest structure

```json
{
  "schema_version": "c5.install-manifest.v1",
  "generated_at": "2026-08-03T00:00:00Z",
  "deployment_types": {
    "3": {
      "deployment_type_id": "3",
      "display_name": "Deployment Lane",
      "hardware_profile_ids": [],
      "runtime_policy_ids": [],
      "minimum_disk_gb": null,
      "minimum_ram_gb": null,
      "recommended_ram_gb": null,
      "minimum_cpu_threads": null,
      "gpu_required": false,
      "minimum_vram_gb": null,
      "recommended_vram_gb": null
    }
  },
  "models": {
    "<model-id>": {
      "model_id": "<model-id>",
      "model_slug": "<model-slug>",
      "family_id": "<family-id>",
      "family_slug": "<family-slug>",
      "default_tag_id": "<tag-id-or-null>",
      "deployments": {
        "3": {
          "deployment_type_id": "3",
          "selected_tag_id": "<tag-id>",
          "selected_tag": "<ollama-tag-suffix>",
          "ollama_identifier": "model:tag",
          "hardware_profile_id": "desktop-standard",
          "runtime_policy_id": "interactive",
          "assessment": "cpu_only_practical",
          "installed_storage_bytes_estimated": 0,
          "min_system_ram_gb_estimated": 0,
          "recommended_system_ram_gb_estimated": 0,
          "min_vram_gb_estimated": 0,
          "recommended_vram_gb_estimated": 0,
          "pull_command": "ollama pull model:tag",
          "run_command": "ollama run model:tag",
          "helper_path": "data/generated/pages/models/<model-slug>/3/info.json"
        }
      }
    }
  }
}
```

## Required identity fields per deployment entry

Each `manifest.models[model_id].deployments[deployment_type_id]` entry must include:

| Field | Purpose |
| --- | --- |
| `model_id` | Stable normalized model identifier |
| `model_slug` | Filesystem-safe model slug for page paths |
| `family_id` | Parent family identifier |
| `family_slug` | Parent family slug |
| `deployment_type_id` | One of `3`, `4`, `5`, `6`, `7` |
| `selected_tag` / `selected_tag_id` | Chosen Ollama tag for this deployment type |
| `ollama_identifier` | Exact `family:tag` string for pull/run |
| `hardware_profile_id` | Hardware profile used for sizing |
| `assessment` | Deployment assessment label |
| sizing facts | RAM, VRAM, disk estimates as applicable |

## Generated page tree (metadata only)

All page folders are metadata only. No model weights, Ollama blobs, binaries, or
installer payloads belong in generated pages.

```text
data/generated/pages/
  families/<family-slug>/info.json
  deployment-types/<3-7>/info.json
  models/<model-slug>/<3-7>/info.json
  install-manifest.json
```

Example model deployment page:

```text
data/generated/pages/models/qwen3/4/info.json
```

## 8.2 selection flow

1. Detect hardware (RAM, CPU threads, disk, GPU, VRAM).
2. Convert hardware facts into deployment type number `3` through `7`.
3. Resolve requested `model_id` or model alias.
4. Read `data/generated/pages/install-manifest.json`.
5. Select `manifest.models[model_id].deployments[deployment_type_id]`.
6. If unavailable, fall back to the next smaller or suitable deployment type or tag.
7. Pull and run the selected `ollama_identifier`.
8. Log both selected model and deployment type.

## Related documentation

- `AGENTS/cursorFileC5-profile-folder-structure.md` — full C5 generator specification
- `config/deployment_types.yaml` — canonical deployment type IDs `3`–`7`
- `config/hardware_profiles.yaml` — hardware profile definitions

# Canonical profile data contract (C10.3)

This directory is the **data-only**, runtime-facing profile matrix for later
`8.1` / `8.2` / `8.3` resolver work. It does not contain installer scripts.

## Canonical artifacts

| Path | Role |
| --- | --- |
| `manifest.json` | Schema version, generator command, source inventory, counts |
| `lanes.json` | Exactly ten install/profile lanes and OS/acceleration semantics |
| `index.csv` | One row per model-size-lane combination |
| `<model-slug>/model.json` | Model metadata |
| `<model-slug>/sizes.csv` | Size index for the model |
| `<model-slug>/sizes/<size-slug>.json` | Size records (file, never directory) |
| `<model-slug>/<lane>/lane.json` | Lane metadata and per-size fit summary |
| `<model-slug>/<lane>/profile-sizes.csv` | Lane-local size references |
| `<model-slug>/<lane>/3-cpu.json` … `7-gpu-vram.json` | Data-only stage payloads |

## Regenerate

```bash
python3 scripts/generate-profiles-from-agents.py
python3 scripts/validate-profiles-from-agents.py
```

## Legacy compatibility

Non-runtime exports from earlier C5/C10 work are retained under
`profiles/legacy/` with a migration README. They must not be treated as the
canonical profile source.

C5 generated pages remain the catalog page source of truth under
`data/generated/pages/models/<model-slug>/<3-7>/` and
`data/generated/pages/install-manifest.json`.

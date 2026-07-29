# P3 Ollama Metadata Catalog

**Status: RESOLVED.** The earlier import failure (`funtech64/ycgpt-8.sh` not
found) is obsolete: the authoritative Ollama metadata catalog now lives in
**this repository** (`terminal-glass/8-ball`). P3 no longer imports from an
external source; it exports from the canonical catalog here.

## Canonical source

| Item | Location |
| --- | --- |
| Normalized catalog | `data/normalized/` (committed, validated) |
| Legacy observations | `data/families/` (preserved) |
| Candidate refreshes | `data/candidate/` (gitignored until promoted) |
| Validation | `bash scripts/validate-catalog.sh` |

## Exports in this folder

| File | Purpose |
| --- | --- |
| `PROVENANCE.json` | Source commit, catalog version, file checksums, counts |
| `indexes/model-selection.json` | Compact per-hardware-profile local model candidates (estimated RAM/VRAM, exact `ollama pull` commands) |
| `indexes/catalog-summary.json` | Entity counts and export summary |
| `reports/` | Historical import-failure reports (superseded, kept for audit) |

Regenerate with:

```bash
eight-ball export-datasets
```

## Consumption contract for installer-authoring work

Separate installer repositories (for example `terminal-glass/8-ball-installer`)
may fetch these committed files over raw GitHub URLs. This repository provides
metadata only:

- exact Ollama tags with `ollama pull` / `ollama run` commands;
- published download sizes and normalized bytes;
- estimated RAM/VRAM planning values (clearly labeled `estimated`);
- hardware-profile buckets aligned with `config/hardware_profiles.yaml`
  and P1-Estimator overhead reserves.

It does **not** provide installer scripts, `8.sh` generation, model payloads,
or fulfillment logic.

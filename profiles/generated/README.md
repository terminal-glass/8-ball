# Generated profile artifacts

This directory is reserved for **machine-consumed** profile exports produced by
future catalog or installer-generation steps.

## Purpose

Installers (`8.2`, `8.3`), the website model selector, and future Docker routing
should consume files here — not Markdown from the numbered decision folders.

Expected future outputs (C2/C3; not implemented in C1):

| File | Producer | Consumer |
| --- | --- | --- |
| `family-model-index.json` | Catalog export (C2) | `8.2`, website cards |
| `deployment-types.json` | Catalog export (C2) | `8.2`, provider lanes |
| `environment-artifact-index.json` | Catalog export (C2) | Export manifest / provenance |
| `sizing-gates.json` | Recovered sizing rules (C3) | `8.2` gate chain |
| `sizing-gates.env` | Installer export (C3) | `8.2` shell loader |
| `canary-baseline.json` | Recovered baseline (C3) | `8.2` fallback |
| `jet-buckets.json` | Jet routing metadata (C3) | `8.2` Jet lane |
| `provider-instance-buckets.json` | Provider baselines (C3) | `8.2` provider gates |

## Rules

- Files here must be valid JSON or shell-safe `.env` exports.
- Do not hand-edit generated files. Regenerate from catalog or approved sizing
  history.
- Do not invent Docker image names, RecordsCore release keys, S3 keys, or sizing
  thresholds.
- Leave unknown values as `null`, empty strings, or explicit `unknown` — never
  guess.

## C1 status

C1 defines the contract only. This directory is empty until C2/C3 exports are
implemented in a later change.

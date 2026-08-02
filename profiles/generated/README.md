# Generated profile artifacts

This directory is reserved for **machine-consumed** profile exports produced by
future catalog or installer-generation steps.

## Purpose

Installers (`8.2`, `8.3`), the website model selector, and future Docker routing
should consume files here — not Markdown from the numbered decision folders.

Expected outputs (C2 identity; C3 sizing deferred):

| File | Producer | Consumer |
| --- | --- | --- |
| `family-model-index.json` | `eight-ball generate-profiles` (C2) | `8.2`, website cards |
| `deployment-types.json` | `eight-ball generate-profiles` (C2) | `8.2`, provider lanes |
| `environment-artifact-index.json` | `eight-ball generate-profiles` (C2) | Export manifest / provenance |
| `sizing-gates.json` | Recovered sizing rules (C3) | `8.2` gate chain |
| `sizing-gates.env` | Installer export (C3) | `8.2` shell loader |
| `canary-baseline.json` | Recovered baseline (C3) | `8.2` fallback |
| `jet-buckets.json` | Jet routing metadata (C3) | `8.2` Jet lane |
| `provider-instance-buckets.json` | Provider baselines (C3) | `8.2` provider gates |

Regenerate C2 exports with:

```bash
eight-ball generate-profiles
```

## Rules

- Files here must be valid JSON or shell-safe `.env` exports.
- Do not hand-edit generated files. Regenerate from catalog or approved sizing
  history.
- Do not invent Docker image names, RecordsCore release keys, S3 keys, or sizing
  thresholds.
- Leave unknown values as `null`, empty strings, or explicit `unknown` — never
  guess.

## C1/C2 status

C1 defines the loader contract. C2 generates family/model identity artifacts and
deployment-lane metadata from the P4 public catalog projection via
`eight-ball generate-profiles`. C3 sizing gates are not implemented here.

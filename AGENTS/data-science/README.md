# 8-BALL Data-Science Workflow (P1–P7)

This directory contains the **repeatable catalog and data-science workflow**
used when Ollama metadata, provider plans, workload assumptions, or public
catalog exports need to be refreshed.

It is **not** for Cursor agent handoff briefs. Those live directly under
[`../`](../):

- [`../CursorFileC1-environment-artifacts.md`](../CursorFileC1-environment-artifacts.md)
- [`../CursorFileC2-environment-artifact-sequencing.md`](../CursorFileC2-environment-artifact-sequencing.md)
- [`../CursorFileC3-environment-gates-testing-plan.md`](../CursorFileC3-environment-gates-testing-plan.md)

The runtime profile contract is documented under
[`../../profiles/`](../../profiles/README.md). Canonical generated model pages
live under `data/generated/pages/` (see `docs/install-manifest-contract.md`).

## Layout

| Path | Role |
| --- | --- |
| `ollama-mapping/` | Ollama catalog and provider workflow artifacts (P1–P7) |
| `profile-mapping/` | TG-8Ball hardware/profile CSV inputs and C10 generation reports |

## P1–P7 layout (`ollama-mapping/`)

| Folder | Role |
| --- | --- |
| `ollama-mapping/P1-Estimator/` | Static estimator datasets: provider specs, NoCloudGPT templates, overhead reserves |
| `ollama-mapping/P2-Provider-Datasets/` | Provider plan metadata and committed indexes |
| `ollama-mapping/P3-Ollama-Metadata-Catalog/` | Catalog provenance and compact installer-consumable exports |
| `ollama-mapping/P4-Public-Catalog/` | Public catalog publishing outputs |
| `ollama-mapping/P4-Workload-Profiles/` | Static workload assumptions for planning |
| `ollama-mapping/P5-Compatibility-Estimator/` | Reserved for compatibility estimation work |
| `ollama-mapping/P6-Validation-and-Testing/` | Reserved for workflow validation artifacts |
| `ollama-mapping/P7-Installer-Authoring-Preparation/` | Reserved for installer-authoring preparation metadata |

## Profile mapping (`profile-mapping/`)

TG-8Ball CSV/XLSX hardware assumption files and C10 profile-generation reports
live under `profile-mapping/`.

## Repository boundary

`terminal-glass/8-ball` is **metadata/catalog only**.

- Do not edit installer scripts in this repository.
- Do not invent disk, RAM, CPU, or GPU sizing thresholds.
- Do not invent Docker image names, RecordsCore keys, or S3 keys.
- Regenerate committed exports with `eight-ball export-datasets` after catalog
  or dataset changes.

## Related governance

- [`../cursorFileA0.md`](../cursorFileA0.md) — repository constitution
- [`../../AGENTS.md`](../../AGENTS.md) — agent rules and prohibited actions

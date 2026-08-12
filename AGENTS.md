# AGENTS.md

## Repository Purpose

This repository is the public **8-BALL** Ollama model-intelligence and data-science catalog for Terminal.Glass.

It collects, normalizes, validates, and reports on **public model metadata only**. It may estimate hardware compatibility and generate deployment recommendations from observed or configured inputs.

It supports separate future installer-authoring work but must never contain paid
installer packaging, licensing, customer-record, Passport, RecordsCore, or production
deployment infrastructure.

Public **free/trial** installer scripts for end users and fork-friendly developers live
under `install/`. See `install/README.md` for the public/private boundary.

The full project requirements are defined in:

`AGENTS/cursorFileA0.md`

All agents must read that file before making changes.

---

## Repository Layout and Data Classes

Keep these directories distinguishable:

| Path | Role | Commit policy |
| --- | --- | --- |
| `data/families/` | Legacy per-family source observations preserved from prior catalog work | Commit |
| `data/catalog.json*` | Historical aggregate exports from the legacy pipeline | Commit as historical reference only |
| `data/overrides/` | Reviewed manual metadata overrides | Commit when present |
| `data/history/` | Archived canonical normalized catalogs from promote | Commit version archives when promoted |
| `data/raw/` | Ephemeral collection cache | Do not commit |
| `data/snapshots/` | Large fetched pages for repeatable parsing | Do not commit |
| `data/manifests/` | Ephemeral live collection manifests (gitignored) | Do not commit |
| `tests/fixtures/manifests/` | Committed fixture manifests for offline tests | Commit |
| `data/candidate/` | Candidate normalized catalogs from live collection | Do not commit |
| `data/normalized/` | Normalized source-derived entities | Commit |
| `data/generated/` | Reproducible generated recommendations, exports, and indexes | Do not commit |
| `data/generated/pages/` | C5 generated metadata page tree (families, deployment-types, models) | Commit when regenerated |
| `reports/` | Human-readable reports; machine summaries are reproducible | Commit markdown optionally; JSON reports are reproducible |
| `install/` | Public free/trial installer scripts (`trial-install.sh`, `8.1`–`8.3`) | Commit |
| `indexes/` | Generated metadata indexes derived from normalized records | Do not commit |
| `tests/fixtures/` | Offline fixtures for tests | Commit |

**Source versus generated**

- Treat `data/families/` and `data/normalized/` as source-derived data, not generated recommendations.
- Treat `data/generated/` (except `data/generated/pages/`), `indexes/`, `data/candidate/`, and reproducible JSON under `reports/` as generated output.
- Commit `data/generated/pages/` after intentional regeneration; never edit those files by hand.
- Do not treat generated deployment counts or recommendations as manually maintained truth.

---

## Shared Rules for Cursor, Codex, and Other Agents

### Before editing

1. Read this file completely.
2. Read `AGENTS/cursorFileA0.md` completely.
3. Inspect the current repository structure.
4. Inspect existing tests, schemas, reports, and source configuration.
5. Summarize the intended changes before editing.
6. Identify any conflict between the request and the specification.
7. Ask before making a change that expands scope.

Do not begin implementation from only a partial reading of the specification.

---

## Repository Scope

Allowed work includes:

- collecting Ollama model metadata;
- recording exact Ollama model tags;
- recording exact `ollama pull` commands;
- recording exact `ollama run` commands;
- recording published model download sizes;
- normalizing download sizes into bytes;
- recording parameter labels and architecture information;
- recording capabilities;
- distinguishing local, cloud-capable, and cloud-only models;
- preserving source provenance;
- estimating hardware requirements when clearly labeled `estimated`;
- generating deployment recommendations deterministically;
- building metadata indexes;
- generating validation reports;
- building offline tests;
- maintaining catalog version history.

---

## Prohibited Actions

Agents must not:

- run `ollama pull`;
- run `ollama run`;
- install Ollama;
- download model weights;
- download GGUF files;
- download Ollama layers or blobs;
- cache model payloads;
- mirror model binaries;
- package model weights;
- store Ollama model directories;
- generate `8.sh` or other **paid** installer scripts;
- add Passport, Stripe, S3 release bundles, or license fulfillment logic to this repo;
- modify deployment repositories;
- modify Passport or RecordsCore;
- upload artifacts to S3;
- create customer fulfillment logic;
- store credentials, cookies, tokens, or session data;
- invent tags, sizes, commands, capabilities, or classifications.

This repository is metadata-only.

---

## Authoritative Sources

Use source priority in this order:

1. Official Ollama model and tag pages.
2. Official Ollama metadata responses when available.
3. `https://nocloudgpt.com/models` as a curated discovery source.
4. `https://terminal.glass/models` as a curated discovery source.

The curated sites may help discover models, but they are not authoritative for exact Ollama tags or published download sizes.

When official metadata cannot be verified:

- store `null`;
- record the unresolved field;
- preserve the source URL;
- do not estimate or guess observed model facts.

Hardware and deployment outputs may be `estimated` or `derived` when documented and labeled.

---

## Data Quality Rules

Keep these concepts separate:

- parameter count;
- published download size;
- normalized download bytes;
- architecture type;
- quantization;
- context length;
- local availability;
- cloud availability;
- cloud-only status;
- observed versus estimated hardware requirements.

Do not infer download size from parameter count.

Do not flatten mixture-of-experts models into misleading dense parameter counts.

Preserve exact Ollama tag spelling.

Only mark two tags as aliases when official metadata supports that conclusion.

---

## Source Snapshot Rules

Small metadata snapshots are allowed only when needed for repeatable parsing or offline tests.

Allowed:

- sanitized HTML;
- small JSON metadata responses;
- extracted structured metadata;
- compact test fixtures.

Not allowed:

- model binaries;
- blobs;
- layers;
- GGUF files;
- archives containing model payloads;
- Docker images;
- Ollama model storage directories.

Respect the configured snapshot-size limit.

---

## Versioning

Catalog versions are independent from future installer versions.

Use catalog versions in this format:

`YYYY.MM.DD`

For multiple refreshes on one day:

`YYYY.MM.DD.1`

`YYYY.MM.DD.2`

---

## Change Safety

Keep changes narrow and intentional.

Do not silently delete existing catalog records.

When upstream metadata disappears or changes, report it in the change report.

---

## Validation

Before calling work complete, run the relevant validation commands.

At minimum:

```bash
bash scripts/validate-catalog.sh
python3 scripts/validate-install-lanes.py
pytest
```

Development setup is a separate, explicit step:

```bash
python -m pip install -e ".[dev]"
```

Routine wrappers must not reinstall the package automatically.

### Snapshot policy (Phase 2)

- Raw live responses remain in `data/raw/` (gitignored).
- Large fetched pages remain in `data/snapshots/` (gitignored) unless promoted.
- Every live collection writes an ephemeral manifest under `data/manifests/` (gitignored) with source URL, retrieval timestamp, HTTP status, checksum, parser version, and snapshot location.
- Committed fixture manifests live under `tests/fixtures/manifests/` for deterministic offline tests.
- Normalization verifies manifest checksums and uses per-snapshot retrieval timestamps when a manifest is supplied.
- Compact offline fixtures under `tests/fixtures/snapshots/` are committed for deterministic parser tests.
- Candidate normalized output lives under `data/candidate/` and must never overwrite `data/families/` or `data/normalized/`.

### Publisher, capability, and provenance policy (Phase 3)

- `config/publishers.yaml` defines catalog sources (`ollama-library`) separately from model publishers (Meta, Google, Mistral AI, etc.).
- Family `publisher_id` is inferred from slug patterns, page text, and explicit `family_overrides`.
- Capabilities inherit from family badges and refine at model and tag levels from `input_capabilities`.
- Tag provenance records observed, derived, and unknown confidence for download size, parameters, context, quantization, availability, and capabilities.
- Coverage and comparison reports include publisher counts, capability coverage, provenance confidence, and deduplicated review items.

### Generated page tree (C5)

The C5 page generator produces metadata-only folders under `data/generated/pages/`:

```text
data/generated/pages/
  families/<family-slug>/
  deployment-types/<3-7>/
  models/<model-slug>/<3-7>/
  install-manifest.json
```

Rules:

- Use `data/generated/pages/models/`, not `02-models` or `2-models`.
- Deployment type folder names are exactly `3`, `4`, `5`, `6`, `7` (defined in `config/deployment_types.yaml`).
- Generated pages are metadata only — no model weights, Ollama blobs, binaries, or installer payloads.
- `8.2` must read `data/generated/pages/install-manifest.json`, not scrape Markdown or guess from folder names.

See `docs/install-manifest-contract.md` and `AGENTS/cursorFileC5-profile-folder-structure.md`.

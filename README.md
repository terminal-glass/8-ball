# Ollama Model Metadata Catalog

**This repository stores model metadata only. It does not download, cache, mirror, package, or distribute Ollama model payloads.**

This project is the authoritative, versioned metadata catalog for Ollama model families and tags. It supports separate installer-authoring work and does **not** generate installer scripts (`8.sh`) in the initial workflow.

## What this repository contains

- Exact Ollama tags and commands (`ollama pull`, `ollama run`)
- Published download sizes and normalized byte values
- Parameter labels and architecture metadata
- Capabilities and local/cloud availability
- Source provenance and verification timestamps
- Searchable metadata indexes and validation reports

## What this repository does not contain

- Model weights, GGUF files, layers, or blobs
- Cached payloads or mirrored binaries
- Installer scripts or deployment logic
- Customer fulfillment configuration

## Authoritative sources

1. **Official Ollama pages** (`https://ollama.com/library`) — authoritative for tags, commands, sizes, capabilities, and availability.
2. **NoCloudGPT models page** (`https://nocloudgpt.com/models`) — curated discovery only.
3. **Terminal.Glass models page** (`https://terminal.glass/models`) — curated discovery only.

Curated sources help discover families but are not authoritative for exact tags or download sizes.

## Key concepts

| Concept | Description |
| --- | --- |
| Parameter label | Human-readable size label from Ollama (e.g. `7b`, `8x7b`) |
| Download size | Published pull size from Ollama; separate from parameter count |
| Local model | Variant with verified local download metadata |
| Cloud model | Variant with cloud availability per official Ollama metadata |
| Catalog version | `YYYY.MM.DD` metadata snapshot version, independent from installer versions |

Download sizes are normalized using **decimal (SI) units**: 1 GB = 1,000,000,000 bytes.

## Repository layout

```
config/          Source URLs and crawl policy
schemas/         JSON schemas for families, variants, and catalog
src/ycgpt_models Python metadata tooling
data/            Catalog outputs, snapshots, and reports
indexes/         Generated metadata indexes
scripts/         Refresh, validate, and index build scripts
tests/           Offline tests and fixtures
```

## Usage

### Refresh the catalog

```bash
bash scripts/refresh-catalog.sh
```

This crawls configured sources, normalizes records, validates output, builds indexes, generates reports, and runs tests. It does **not** call `ollama pull` or `ollama run`.

### Validate without network access

```bash
bash scripts/validate-catalog.sh
```

### Rebuild indexes from existing catalog data

```bash
bash scripts/build-indexes.sh
```

## Catalog versioning

Catalog versions use `YYYY.MM.DD`. Multiple refreshes on the same day use `YYYY.MM.DD.1`, `YYYY.MM.DD.2`, etc.

Installer versions (for future `8.sh` work) remain independent and may change for reasons unrelated to catalog refreshes (Ollama behavior, OpenWebUI, cloud providers, fulfillment requirements).

## Indexes for future installer authoring

Generated indexes (for example `indexes/by-download-size.json`, `indexes/local-models.json`) are metadata-only views intended for separate installer-authoring agents. This repository does not generate installers.

## Agent guidance

See `AGENTS.md` and `AGENTS/cursorFileA0.md` for full requirements and prohibited actions.

# 8-BALL

**8-BALL** is the Terminal.Glass model-intelligence catalog for publicly available Ollama models. This repository stores **metadata only**. It does not download, cache, mirror, package, or distribute model payloads.

8-BALL supports separate installer-authoring work. It does **not** generate customer installer scripts.

## What this repository contains

- Publishers, model families, models, and tags in a normalized JSON catalog
- Exact Ollama tags plus `ollama pull` / `ollama run` commands
- Published download sizes and normalized byte values
- Parameter labels, quantizations, context windows, and availability
- Provenance/confidence metadata (`observed`, `derived`, `estimated`, `manual`, `unknown`)
- Configurable hardware estimates and generated deployment recommendations
- Validation and coverage reports

## What this repository does not contain

- Model weights, GGUF files, layers, or blobs
- Installer scripts, Passport integration, or fulfillment logic
- Live crawling in CI (tests use offline fixtures)

## Authoritative sources

1. [Official Ollama library](https://ollama.com/library)
2. [NoCloudGPT models](https://nocloudgpt.com/models) — discovery only
3. [Terminal.Glass models](https://terminal.glass/models) — discovery only

Curated sources help discover coverage gaps but are not authoritative for exact tags or download sizes.

## Repository layout

```text
config/                 Source URLs, crawl policy, capabilities, hardware profiles
schemas/                JSON schemas for normalized entities
src/eight_ball/         Collection, normalization, validation, estimation, generation
data/families/          Legacy per-family catalog input (preserved)
data/normalized/        Normalized JSON entities
data/generated/         Generated deployment outputs
data/snapshots/         Small sanitized source snapshots
reports/                Human-readable and machine-readable reports
scripts/                Shell wrappers around the CLI
tests/fixtures/         Offline sample fixtures
```

## Install

```bash
pip install -e ".[dev]"
```

## CLI

```bash
eight-ball collect      # Fetch and cache public source snapshots
eight-ball normalize    # Normalize legacy/catalog inputs into data/normalized/
eight-ball validate     # Schema and integrity validation
eight-ball generate     # Generate deployment recommendations and exports
eight-ball report       # Write coverage and validation reports
eight-ball all          # Run the full offline-capable pipeline
```

Useful flags:

- `--sample` — limit to the six representative fixture families
- `--offline` — use cached snapshots only
- `--fixture` — use `tests/fixtures` inputs

Shell wrappers remain available for compatibility:

```bash
bash scripts/validate-catalog.sh
bash scripts/refresh-catalog.sh
bash scripts/build-indexes.sh
```

## Representative sample

The offline sample pipeline covers:

- `tinyllama` — small local model
- `llama3` — multiple parameter sizes
- `codestral` — coding model
- `llava` — vision model
- `nomic-embed-text` — embedding model
- `gemini-3-flash-preview` — cloud model

```bash
eight-ball all --fixture --offline --sample
```

## Provenance and estimates

Observed values come directly from cited public sources. Derived values are calculated from observed inputs. Estimated values, such as RAM/VRAM recommendations, are heuristic and documented in `src/eight_ball/estimate/`. They are not vendor guarantees.

## Agent guidance

See `AGENTS.md` and `AGENTS/cursorFileA0.md` for repository boundaries and prohibited actions.

## Validation

```bash
bash scripts/validate-catalog.sh
pytest -q
```

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
data/families/          Legacy per-family source observations (preserved)
data/overrides/         Reviewed manual metadata overrides
data/normalized/        Normalized source-derived entities (committed)
data/generated/         Reproducible generated output (not committed)
data/generated/pages/   C5 metadata page tree (families/, deployment-types/, models/)
data/snapshots/         Cached sanitized snapshots (not committed)
reports/                Human-readable reports and reproducible JSON summaries
indexes/                Generated metadata indexes (not committed)
scripts/                Shell wrappers around the CLI
tests/fixtures/         Offline sample fixtures
```

## Install

One-time development setup:

```bash
python -m pip install -e ".[dev]"
```

Routine commands use the installed `eight-ball` CLI or `python -m eight_ball` and do not reinstall the package.

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
- `--source ollama --candidate` — rebuild into `data/candidate/` without touching legacy data
- `--from-index` — discover families from the Ollama library index snapshot
- `--resume` — resume live collection from cached snapshots/state

Shell wrappers remain available for compatibility:

```bash
bash scripts/validate-catalog.sh
bash scripts/refresh-catalog.sh            # legacy pipeline (data/families → data/normalized)
bash scripts/plan-candidate-collect.sh     # offline recreate plan
bash scripts/refresh-candidate-sample.sh   # offline six-family candidate rebuild
bash scripts/refresh-candidate-live.sh     # live metadata crawl (metadata pages only)
bash scripts/promote-candidate.sh          # dry-run promote candidate → normalized
bash scripts/build-indexes.sh
```

## Recreate catalog (candidate scaffolding)

Canonical recreate flow keeps legacy observations intact and writes a reviewable candidate first:

```text
plan → collect/normalize candidate → validate/compare → promote (dry-run) → promote --apply --confirm
```

1. **Plan** (offline, no network):

```bash
eight-ball plan --fixture --offline --from-index
# or: bash scripts/plan-candidate-collect.sh
```

`--fixture` is explicit test data. Without it, an offline index plan requires
`data/snapshots/ollama-library-index.html`; it never silently substitutes the
test fixture for a collected index.

2. **Rebuild candidate from fixtures** (safe CI/sample path):

```bash
bash scripts/refresh-candidate-sample.sh
eight-ball compare --sample
```

3. **Full-index recreate later** (metadata pages only; not run in CI):

```bash
# After an index snapshot exists under data/snapshots/:
eight-ball collect --source ollama --candidate --offline --from-index
eight-ball normalize --source ollama --candidate --offline --from-index
eight-ball validate --candidate --source ollama
eight-ball compare
eight-ball promote --dry-run
```

4. **Promote** only after review. Promote validates the candidate, blocks
unresolved review records and unacknowledged removals, archives
`data/normalized/` into `data/history/<version>/`, and swaps the staged catalog
into place with rollback protection. It never modifies `data/families/`:

```bash
eight-ball promote --dry-run
# eight-ball promote --apply --confirm   # explicit canonical replacement
```

If reviewed upstream removals or unresolved review records are intentionally
accepted, acknowledge each gate explicitly:

```bash
eight-ball promote --apply --confirm --allow-removals --allow-review-items
```

This repository still does **not** run `ollama pull`, download weights, or generate installer scripts.

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
# Candidate path (preferred recreate scaffolding):
eight-ball all --source ollama --candidate --fixture --offline --sample
```

## Installer-authoring datasets (P-steps)

The repository also hosts static planning datasets and committed exports that
separate installer repositories (for example `terminal-glass/8-ball-installer`)
consume. These are metadata only; installer scripts are never generated here.

| Folder | Contents |
| --- | --- |
| `AGENTS/data-science/P1-Estimator/` | Provider hardware specs, NoCloudGPT planning templates, overhead reserves, workload profiles |
| `AGENTS/data-science/P2-Provider-Datasets/` | Provider plan metadata plus committed indexes (`indexes/`) |
| `AGENTS/data-science/P3-Ollama-Metadata-Catalog/` | Catalog provenance and compact installer-consumable indexes, including `indexes/model-selection.json` (per-hardware-profile local model candidates with estimated RAM/VRAM) |

Rebuild the committed P2/P3 exports after catalog or dataset changes:

```bash
eight-ball export-datasets
```

## Provenance and estimates

Observed values come directly from cited public sources. Derived values are calculated from observed inputs. Estimated values, such as RAM/VRAM recommendations, are heuristic and documented in `src/eight_ball/estimate/`. They are not vendor guarantees.

## Agent guidance

See `AGENTS.md` and `AGENTS/cursorFileA0.md` for repository boundaries and prohibited actions.

For C5 generated pages and the `8.2` install manifest contract, see
`docs/install-manifest-contract.md` and `config/deployment_types.yaml`.

## Validation

```bash
bash scripts/validate-catalog.sh
pytest -q
```

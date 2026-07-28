# 8-BALL Reconstruction Audit

Generated: 2026-07-28

## 1. What existed before

| Component | Status before reconstruction |
|-----------|----------------------------|
| `AGENTS.md`, `AGENTS/cursorFileA0.md` | Present |
| `config/sources.yaml`, `config/catalog-policy.yaml` | Present |
| `data/families/*.json` (231 families) | Present |
| `data/catalog.json`, `catalog.jsonl`, `catalog.csv` | Present (stale aggregates) |
| `src/`, `schemas/`, `scripts/`, `tests/`, `.github/` | **Missing** |
| `pyproject.toml` | Referenced non-existent `ycgpt_models` package |

## 2. What was missing

- Python package and CLI
- JSON schemas and provenance model
- Normalization pipeline from legacy family JSON
- Hardware estimation and deployment generation
- Offline tests, fixtures, and CI workflow
- Human/machine reports

## 3. Files added or modified

### Added
- `src/eight_ball/` — full pipeline package
- `schemas/*.schema.json`
- `config/capabilities.yaml`, `hardware_profiles.yaml`, `deployment_tiers.yaml`
- `scripts/eight-ball.sh`, `validate-catalog.sh`, `refresh-catalog.sh`, `build-indexes.sh`
- `tests/` and `tests/fixtures/`
- `.github/workflows/ci.yml`
- `.gitignore`
- `data/normalized/`, `data/generated/`, `reports/` outputs

### Modified
- `README.md` — 8-BALL documentation
- `pyproject.toml` — renamed to `eight-ball`, new CLI entry point
- `requirements.txt`
- `config/catalog-policy.yaml` — updated user agent

### Preserved intentionally
- All `data/families/*.json` legacy records (not deleted or overwritten)
- `data/catalog.json`, `catalog.jsonl`, `catalog.csv` (legacy aggregates kept)
- `AGENTS.md`, `AGENTS/cursorFileA0.md`
- Junk files `data/stupid.md`, `data/families/asdf.txt` (left untouched pending approval)

## 4. Data sources used

| Source | Use |
|--------|-----|
| Legacy `data/families/*.json` | Primary normalization input (catalog version `2026.07.16`) |
| `tests/fixtures/` | Offline sample pipeline |
| Official Ollama library | Collector target (not run in CI) |

`funtech64/lightsail-ncgpt` was **not** accessible from this agent and was not used.

## 5. Commands executed

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
eight-ball all --fixture --offline --sample
eight-ball normalize
eight-ball validate
eight-ball generate
eight-ball report
```

## 6. Test and validation results

| Check | Result |
|-------|--------|
| `pytest -q` | 8 passed |
| `ruff check src tests` | passed |
| Sample validation (`--fixture --offline --sample`) | passed |
| Full legacy validation | passed |

## 7. Current counts (full legacy normalization)

| Entity | Count |
|--------|------:|
| Publishers | 1 |
| Families | 231 |
| Models | 231 |
| Tags | 7,246 |

## 8. Deployment combinations

| Scope | Count |
|-------|------:|
| Full catalog | **173,904** (7,246 tags × 8 hardware profiles × 3 runtime policies) |
| Sample fixture | 5,352 (223 tags × 8 × 3) |

## 9. Known unknowns and manual review

- 561 tags missing `parameter_count` in legacy source
- 17 tags with null `download_size_bytes` (mostly cloud models)
- 53 families with multiple `is_default_alias: true` in legacy data
- `ministral-3` exists in stale aggregates but not in `data/families/`
- Legacy `updated_text` fields contain HTML scrape pollution on some families
- Publisher mapping defaults to `ollama-library` for all models
- No live Ollama refresh yet; catalog remains dated `2026.07.16`

## 10. Assumptions needing approval

1. Rename package from `ycgpt-models` to `eight-ball` / `eight_ball`
2. Treat `data/families/` as legacy input; write normalized output to `data/normalized/`
3. Hardware estimation heuristics in `estimate/hardware.py` are starting points, not guarantees
4. Remove junk files `stupid.md` and `asdf.txt`
5. Salvage additional parsers from private `lightsail-ncgpt` when org agent has access

## 11. Recommended next phase

1. Org agent with `lightsail-ncgpt` access: diff and port surviving crawler/parser code
2. Live Ollama collection refresh with snapshot caching
3. Publisher inference and manual override files
4. Rebuild searchable indexes under `indexes/`
5. Archive or regenerate legacy `data/catalog.json*` from normalized output

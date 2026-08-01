# Live Ollama Metadata Crawl Summary

Generated: 2026-08-01T10:44:21Z  
Catalog version: `2026.08.01`  
Source: official Ollama library HTML (metadata pages only)

## Collection

| Metric | Value |
|--------|------:|
| Library index families | 234 |
| Snapshots collected | 469 (index + family + tags pages) |
| Collection duration | ~13 minutes |
| Model weights downloaded | 0 |
| Resume support | enabled (`--resume`) |

## Candidate catalog (normalized)

| Entity | Count |
|--------|------:|
| Publishers | 11 |
| Families | 232 |
| Models | 435 |
| Tags | 7,269 |
| Deployment combinations | 174,456 |

## Parse failures (skipped families)

| Family | Reason |
|--------|--------|
| `kimi-k2.5` | Tags page has no `/library/kimi-k2.5:<tag>` anchor links in static HTML |
| `minimax-m2.5` | Tags page has no `/library/minimax-m2.5:<tag>` anchor links in static HTML |

These families remain in the library index but produced zero parseable tag records.
The candidate catalog skips them and records the failure in `catalog-meta.json`.

## Comparison vs legacy canonical (`data/normalized`)

| Delta | Count |
|-------|------:|
| Shared tags | 7,244 |
| Candidate-only tags | 25 |
| Legacy-only tags | 2 |
| Candidate-only families | 3 (`kimi-k3`, `laguna-s-2.1`, `ministral-3`) |
| Legacy-only families | 2 (`kimi-k2.5`, `minimax-m2.5` — present in legacy, skipped in candidate due to parse failure) |
| Legacy-only models | 204 (model grouping / digest canonicalization differs) |
| Download size mismatches | 11 |
| Parameter mismatches | 175 |

## Validation

- Candidate catalog validation: **pass**
- Canonical legacy catalog: unchanged
- **Promote: blocked** (expected)
  - 226 families / 426 models with unresolved review records
  - 204 model record removals vs legacy grouping (requires `--allow-removals` after review)

## Publisher coverage (candidate)

- Unknown publisher families: 142
- Inferred mappings needing review: 226
- Identified publishers: Meta, Google, Mistral AI, Microsoft, Alibaba/Qwen, DeepSeek, IBM, Nomic, TinyLlama, LLaVA

## Next steps (not performed)

1. Review publisher mappings and family overrides for high-traffic models
2. Reconcile model grouping differences vs legacy (digest canonicalization)
3. Investigate `kimi-k2.5` and `minimax-m2.5` tags-page layout changes upstream
4. `eight-ball promote --dry-run` until eligible, then explicit `--apply --confirm` only after human review
5. Do **not** promote until review gates pass or are explicitly acknowledged

## Artifacts (gitignored)

- `data/snapshots/` — ephemeral HTML snapshots
- `data/raw/` — raw cache + collection state + latest manifest pointer
- `data/manifests/candidate-*.json` — collection manifest
- `data/candidate/` — normalized + generated candidate catalog

Reproduce reports from candidate output:

```bash
eight-ball report --candidate --source ollama
eight-ball compare
eight-ball promote --dry-run
```

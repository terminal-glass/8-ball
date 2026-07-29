# Live Ollama Metadata Crawl Summary

Generated: 2026-07-29T03:08:00Z  
Catalog version: `2026.07.29`  
Source: official Ollama library HTML (metadata pages only)

## Collection

| Metric | Value |
|--------|------:|
| Library index families | 234 |
| Snapshots collected | 469 (index + family + tags pages) |
| Collection duration | ~10 minutes |
| Model weights downloaded | 0 |

## Candidate catalog (normalized)

| Entity | Count |
|--------|------:|
| Publishers | 11 |
| Families | 234 |
| Models | 437 |
| Tags | 7,270 |
| Deployment combinations | 174,480 |

## Comparison vs legacy canonical (`data/normalized`)

| Delta | Count |
|-------|------:|
| Shared tags | 7,246 |
| Candidate-only tags | 24 |
| Legacy-only tags | 0 |
| Candidate-only families | 3 (`kimi-k3`, `laguna-s-2.1`, `ministral-3`) |
| Legacy-only models | 202 (model grouping / digest canonicalization differs) |
| Download size mismatches | 11 |
| Parameter mismatches | 175 |

## Validation

- Candidate catalog validation: **pass** (after adding `nvfp4` quantization)
- Canonical legacy catalog: unchanged
- **Promote: blocked** (expected)
  - 228 families / 428 models with unresolved review records
  - 202 model record removals vs legacy grouping (requires `--allow-removals` after review)

## Publisher coverage (candidate)

- Unknown publisher families: 144
- Inferred mappings needing review: 228
- Identified publishers: Meta, Google, Mistral AI, Microsoft, Alibaba/Qwen, DeepSeek, IBM, Nomic, TinyLlama, LLaVA

## Next steps (not performed)

1. Review publisher mappings and family overrides for high-traffic models
2. Reconcile model grouping differences vs legacy (digest canonicalization)
3. `eight-ball promote --dry-run` until eligible, then explicit `--apply --confirm` only after human review
4. Do **not** promote until review gates pass or are explicitly acknowledged

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

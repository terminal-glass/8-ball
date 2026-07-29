# Candidate Catalog Recreate Plan

Generated: 2026-07-29T01:26:20Z

## Selection

- Mode: `from_index`
- Index families: 234
- Selected families: 234
- Legacy families: 231
- Shared with legacy: 231
- Estimated metadata page fetches: 469
- Index path: `/workspace/tests/fixtures/snapshots/ollama-library-index.html`

## Coverage deltas

- Index-only families (3): `kimi-k3`, `laguna-s-2.1`, `ministral-3`
- Legacy-only families (0): _none_

## Publisher preview (low-noise)

- Unknown publishers: 145
- Inferred mappings needing review: 83

- `alibaba-qwen`: 15
- `deepseek`: 11
- `google`: 13
- `ibm`: 13
- `llava-project`: 3
- `meta`: 9
- `microsoft`: 7
- `mistral-ai`: 15
- `nomic-ai`: 2
- `tinyllama`: 1
- `unknown`: 145

Preview uses slug/override inference only. Description-based text matches require collected family pages.

## Safety

- Downloads model weights: `False`
- Runs `ollama pull`: `False`
- Writes legacy families: `False`
- Candidate output: `data/candidate/normalized`
- Promote required for canonical catalog: `True`

## Recommended next commands

- `eight-ball all --source ollama --candidate --fixture --offline --sample`
- `eight-ball compare --sample`
- `eight-ball promote --dry-run`

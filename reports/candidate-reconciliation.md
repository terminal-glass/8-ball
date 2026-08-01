# Candidate Catalog Reconciliation

- Catalog version: `2026.08.01`
- Generated at: 2026-08-01T12:00:16Z
- Collection ID: `bab19a56868744a5a39e39ae8eecfa4c`

## Authoritative live candidate counts
- Index families (live Ollama library): **232**
- Normalized families: **232**
- Canonical candidate models: **435**
- Tags / deployments: **7269** tags, **174456** deployment combinations

## Alias and digest merges (candidate)
- Merge records: **965**

## Legacy comparison (informational only)
- Legacy tags: 7246
- Candidate tags: 7269
- Shared tags: 7244
- Legacy-only tags: 2
- Candidate-only tags: 25
- Legacy-only model IDs: 204 (202 likely regrouped)

### Legacy-only tag disposition
- `ambiguous_review`: 0
- `live_absent`: 0
- `regrouped`: 0
- `renamed_aliased_digest_merged`: 0
- `source_unparseable`: 2

> Legacy-only model IDs are usually digest regrouping, not live removals. See disposition_counts for per-tag classification.

## True live absences
- Count: **0**

## Source exceptions (unparseable snapshots)
- Count: **2**
- `kimi-k2.5`: static_html_parse_failure
- `minimax-m2.5`: static_html_parse_failure

## Ambiguous human-review queue
- Count: **0**

Artifacts:
- `/workspace/reports/candidate-reconciliation.json`
- `/workspace/reports/candidate-review-queue.json`
- `/workspace/reports/candidate-source-exceptions.json`
- `/workspace/reports/candidate-mapping.json`

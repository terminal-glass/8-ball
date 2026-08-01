# Catalog Refresh Contract

The 2026-08-01 canonical promotion establishes an independent catalog refresh pipeline
for the 8-BALL Ollama metadata catalog. Future refreshes use this pipeline only; they do
not depend on 8-BALL installer work, deployment systems, or other repositories.

## Scope

This contract applies to **metadata-only** catalog operations in `terminal-glass/8-ball`:

- collect public Ollama library pages (no model-weight downloads)
- normalize into `data/candidate/normalized/`
- validate, compare, and reconcile against canonical `data/normalized/`
- promote reviewed candidates with explicit gates

It does **not** cover installer generation, Passport, RecordsCore, licensing, S3, or
production deployment infrastructure.

## Refresh workflow

```text
plan → collect → normalize (candidate) → validate → compare → reconcile → promote
```

1. **Plan** — `eight-ball plan --from-index` (or explicit family selection)
2. **Collect** — `eight-ball collect --source ollama --candidate --from-index`
3. **Normalize** — `eight-ball normalize --source ollama --candidate --from-index`
4. **Validate** — `eight-ball validate --candidate --source ollama`
5. **Compare** — `eight-ball compare`
6. **Reconcile** — `eight-ball reconcile`
7. **Promote** — `eight-ball promote --dry-run`, then `eight-ball promote --apply --confirm`

Legacy observations in `data/families/` are never modified. Promotion archives the
previous canonical catalog to `data/history/<version>/` before replacement.

## Comparison baseline

Future refreshes compare candidate output against the **current canonical**
`data/normalized/` catalog (version `2026.08.01` as of this promotion), not against
July legacy `data/families/` observations alone.

Legacy `data/families/` remains a historical continuity reference only.

## Source-exception handling

Families listed in `config/snapshot-policy.yaml` `known_static_parse_failures` that
cannot be parsed from live snapshots are **source exceptions**:

- they are not treated as live absences or deletions
- on promotion, prior canonical family/model/tag records are retained when present
- retained records are marked `source_exception_retained: true` in canonical output
- parser support or manual verification is required before replacing stale records

Current configured exceptions: `kimi-k2.5`, `minimax-m2.5`.

## Promotion gates

Structural data quality blocks promotion. The following do **not** block promotion:

- unverified or inferred publisher metadata (`review_reasons` enrichment backlog)
- digest-based model regrouping (legacy model ID deltas with all tags still present)
- configured source-exception retention (not counted as removals)

Blocking conditions include schema validation failures and true unexplained canonical
record removals without `--allow-removals`.

## Count contract

Each reconciliation and promotion receipt reports these counts separately:

- source-indexed families
- parseable source families
- source-exception families
- collected snapshots
- normalized candidate families
- candidate canonical models
- tags
- deployment combinations

Do not relabel filtered counts as “index families.”

## Independence

- Catalog versions (`YYYY.MM.DD`) are independent from future installer versions.
- `eight-ball export-datasets` publishes compact P3 indexes from committed canonical data.
- Installer repositories may consume committed metadata files; this repository does not
  generate installer scripts or download model payloads.

## Current canonical baseline

| Field | Value |
| --- | --- |
| Catalog version | `2026.08.01` |
| Collection date | `2026-08-01` |
| Collection manifest | `tests/fixtures/manifests/candidate-2026-08-01.json` |
| Canonical families | 234 |
| Canonical models | 437 |
| Canonical tags | 7,271 |

See `reports/catalog-promotion-receipt.md` for the full 2026-08-01 promotion record.

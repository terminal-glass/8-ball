# Catalog Promotion Receipt — 2026.08.01

Canonical promotion applied from the validated 2026-08-01 Ollama candidate catalog.

## Promotion summary

| Field | Value |
| --- | --- |
| Catalog version | `2026.08.01` |
| Collection date | `2026-08-01` |
| Collection ID | `bab19a56868744a5a39e39ae8eecfa4c` |
| Promoted at | `2026-08-01T14:08:01Z` |
| Previous canonical archive | `data/history/2026.07.16.20260801T140801Z/` |
| Candidate source | `data/candidate/normalized` |
| Collection manifest | `tests/fixtures/manifests/candidate-2026-08-01.json` |

## Canonical counts (after promotion)

| Count | Value |
| --- | ---: |
| Source-indexed families | 234 |
| Parseable source families | 232 |
| Source-exception families | 2 |
| Collected snapshots | 465 |
| Canonical families | 234 |
| Canonical models | 437 |
| Canonical tags | 7,271 |
| Deployment combinations | 174,504 |

Parseable live inventory: 232 families, 435 models, 7,269 tags from the 2026-08-01 collection.
Two source-exception families were retained from the prior canonical catalog (see below).

## Source-exception retention

These families could not be parsed from the 2026-08-01 live snapshots. Prior canonical
records were retained and marked `source_exception_retained: true`. They are stale
continuity records, not live absences and not deletions.

| Family | Retained records |
| --- | --- |
| `kimi-k2.5` | family, model, tag `kimi-k2.5:cloud` |
| `minimax-m2.5` | family, model, tag `minimax-m2.5:cloud` |

Policy: retain prior canonical records until parser support or manual source verification
is available (`config/snapshot-policy.yaml` known_static_parse_failures).

## Publisher enrichment

Publisher unknown/inferred metadata remains a documented non-blocking enrichment backlog.
No publisher values were invented during promotion.

## Legacy preservation

- `data/families/` — unchanged (July legacy observations preserved)
- `data/history/2026.07.16/` — first archive from failed swap attempt
- `data/history/2026.07.16.20260801T140801Z/` — archive taken at successful promotion

## Artifacts

- `data/normalized/catalog-meta.json` — canonical manifest with promotion provenance
- `reports/promote-report.json` — machine-readable promotion gate receipt
- `reports/catalog-refresh-contract.md` — independent refresh contract
- `P3-Ollama-Metadata-Catalog/PROVENANCE.json` — export provenance (regenerated)

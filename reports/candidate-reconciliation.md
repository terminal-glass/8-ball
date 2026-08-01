# Candidate Catalog Reconciliation

Decision-ready summary for Phase 3E promotion review. The July legacy canonical catalog is continuity baseline only; live candidate counts below are authoritative.

- Catalog version: `2026.08.01`
- Generated at: 2026-08-01T12:00:16Z
- Collection ID: `bab19a56868744a5a39e39ae8eecfa4c`

## Live inventory (authoritative)
- Source-indexed families: **234**
- Parseable source families: **232**
- Source-exception families: **2**
- Collected snapshots: **465**
- Families with snapshots: **232**
- Normalized candidate families: **232**
- Candidate canonical models: **435**
- Tags: **7269**
- Deployment combinations: **174456**
- Alias/digest merges: **965**

## Grouping integrity
- Valid: **True**
- Deployment variant tags (non-alias): **6304**
- Alias-target tags: **965**
- Alias and digest merges collapse model grouping only; each non-alias tag remains a distinct deployment variant.

## Legacy delta classification
- Shared tags: 7244
- Candidate-only tags (new live): 25
- Legacy-only tags: 2
- Legacy-only model IDs: 204 (202 digest regrouping, 2 source exceptions)

### Disposition counts
- `ambiguous_review`: 0
- `live_absent`: 0
- `regrouped`: 6975
- `renamed_aliased_digest_merged`: 269
- `source_unparseable`: 2

> Disposition counts include shared tags with digest regrouping and legacy-only tags. Legacy-only model IDs are explained in legacy_model_evidence.

## Legacy model evidence
- Digest regrouping: **202**
- Source exceptions: **2**
- Unexplained: **0**

## True current-live absences
- Count: **0**

## Regrouped or renamed (not removals)
- Regrouped tag records: **6975**
- Renamed/alias/digest-merged: **269**
- Candidate-only new live tags: **25**

## Source exceptions
- Count: **2**
- Retention policy: On promotion, retain prior canonical family/model/tag records for configured source-exception families until parser support or manual source verification is available. Source exceptions are not live absences and must not be deleted.
- `kimi-k2.5`: static_html_parse_failure
- `minimax-m2.5`: static_html_parse_failure

## Promotion decision
- Eligible: **True**
- Promotion is eligible based on structural data quality. The candidate catalog reflects current live Ollama metadata size (232 families, 435 models, 7269 tags). 1 publisher-enrichment backlog item(s) are documented and non-blocking.

### Blocker interpretations

## Structural review queue
- Count: **2**
- source_exception `kimi-k2.5`: parser_update_or_manual_review
- source_exception `minimax-m2.5`: parser_update_or_manual_review

## Publisher enrichment backlog (non-blocking)
- Count: **1**
- publisher_mapping `publisher_mapping_batch`: Review config/publishers.yaml overrides when convenient; does not block promotion of structurally valid live inventory

Artifacts:
- `/workspace/reports/candidate-reconciliation.json`
- `/workspace/reports/candidate-promotion-review.json`
- `/workspace/reports/candidate-review-queue.json`
- `/workspace/reports/candidate-source-exceptions.json`
- `/workspace/reports/candidate-mapping.json`

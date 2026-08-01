# Candidate Catalog Reconciliation

Decision-ready summary for Phase 3E promotion review. The July legacy canonical catalog is continuity baseline only; live candidate counts below are authoritative.

- Catalog version: `2026.08.01`
- Generated at: 2026-08-01T12:00:16Z
- Collection ID: `bab19a56868744a5a39e39ae8eecfa4c`

## Live inventory (authoritative)
- Index families: **232**
- Snapshots collected: **465**
- Families with snapshots: **232**
- Normalized families: **232**
- Canonical candidate models: **435**
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
- Legacy-only model IDs: 204 (202 explained by regrouping)

### Disposition counts
- `ambiguous_review`: 0
- `live_absent`: 0
- `regrouped`: 0
- `renamed_aliased_digest_merged`: 0
- `source_unparseable`: 2

> Legacy-only model IDs are usually digest regrouping, not live removals. See disposition_counts and regrouped_items for evidence.

## True current-live absences
- Count: **0**

## Regrouped or renamed (not removals)
- Regrouped tag records: **0**
- Renamed/alias/digest-merged: **0**
- Candidate-only new live tags: **25**

## Source exceptions
- Count: **2**
- `kimi-k2.5`: static_html_parse_failure
- `minimax-m2.5`: static_html_parse_failure

## Promotion decision
- Eligible: **False**
- Promotion remains blocked pending editorial review. The candidate catalog reflects current live Ollama metadata size (232 families, 435 models, 7269 tags). Legacy July canonical is continuity baseline only.

### Blocker interpretations
- Legacy grouping delta, not evidence of live catalog shrinkage. 202 legacy model IDs map to candidate tags under digest-based grouping; 2 families are source exceptions; 0 tags are true live absences.
  - Recommended: Review candidate-reconciliation.md, then acknowledge with --allow-removals only after confirming no true live absences remain.
- Publisher inference and family metadata review flags on the candidate catalog. These do not indicate missing live tags.
  - Recommended: Resolve high-traffic publisher overrides or acknowledge with --allow-review-items after editorial review.

## Human-review queue
- Count: **3**
- source_exception `kimi-k2.5`: parser_update_or_manual_review
- source_exception `minimax-m2.5`: parser_update_or_manual_review
- publisher_mapping `publisher_mapping_batch`: review config/publishers.yaml overrides before promotion; does not block accepting live tag inventory

Artifacts:
- `/workspace/reports/candidate-reconciliation.json`
- `/workspace/reports/candidate-promotion-review.json`
- `/workspace/reports/candidate-review-queue.json`
- `/workspace/reports/candidate-source-exceptions.json`
- `/workspace/reports/candidate-mapping.json`

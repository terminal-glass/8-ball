# Public Catalog Classifications

All classifications are derived deterministically from canonical `data/normalized/`
records. When evidence is insufficient, outputs use `unknown` or empty lists rather
than guessed values.

## Capability filters

**Source:** `capabilities` maps on family, model, and tag records (11 canonical keys
from `config/capabilities.yaml`).

**Rule:** include a capability in `capability_filters` when the map value is `"true"`.
Values `"false"` and `"unknown"` are excluded.

**Aggregation:** family and model classifications union capability filters across their
tags.

## Local / private suitability

**Rule:** `local_private_suitable` is `true` when at least one related tag has:

- `availability` in `{local, both}`, and
- `download_size_bytes` is a positive integer.

Cloud-only tags without downloadable artifacts do not qualify.

## Cloud / Jet suitability

**Rule:** `cloud_jet_suitable` is `true` when at least one related tag has
`availability` in `{cloud, cloud_only, both}`.

## Size buckets

**Source:** tag `parameter_count` (integer).

| Bucket | Parameter count range |
| --- | --- |
| `micro` | &lt; 1B |
| `small` | 1B – 7B |
| `medium` | 8B – 30B |
| `large` | 31B – 70B |
| `xlarge` | &gt; 70B |
| `unknown` | `parameter_count` is null |

Model and family classifications list all buckets present among their tags.

## Quantization filters

**Source:** tag `quantization` string when present.

Family/model `classifications.quantizations` lists distinct non-null quantizations
across tags.

## Unknown field tracking

`classifications.unknown_fields` lists aggregate gaps when any related tag lacks:

- `parameter_count`
- `download_size_bytes` (except cloud-only/cloud tags)
- `context_window_tokens`

## Publisher verification

**Source:** canonical `publisher_id`, `review_reasons`, and `provenance.publisher_id`.

| Status | Rule |
| --- | --- |
| `verified` | `publisher_id` is not `unknown`, and no publisher enrichment backlog reasons |
| `unverified` | `publisher_mapping_needs_review` in `review_reasons`, or derived provenance without approval |
| `unknown` | `publisher_id` is `unknown` or `unknown_publisher` in `review_reasons` |

Publisher values are never invented during publishing.

## SEO eligibility

| Record | Rule |
| --- | --- |
| Family / model | `seo_eligible: true` unless `source_exception_retained` is set on the canonical record |
| Deployment variant | always `seo_eligible: false` |

## Source status

| Value | Rule |
| --- | --- |
| `live` | default for parseable canonical records |
| `stale_source_exception` | canonical record has `source_exception_retained: true` |

# Public Catalog Consumption Contract

This document describes how **terminal.glass** (or other consumers) should read the
P4 public catalog projection without coupling to internal normalized entity files.

## Entry point

```bash
eight-ball publish-catalog
```

Output root: `P4-Public-Catalog/`

## Read order

1. **`manifest.json`** — verify `schema_version`, `canonical_catalog_version`,
   `collection_date`, and `source_provenance.source_files` checksums if needed.
2. **`index/families.json`** — family landing-page records.
3. **`index/models.json`** — model detail records with nested deployment variants.

## Page hierarchy

| Record | `page.page_type` | SEO eligible | Notes |
| --- | --- | --- | --- |
| Family | `family` | usually `true` | Catalog landing page per family slug |
| Model | `model` | usually `true` | Detail page per canonical model id |
| Deployment variant | `deployment_variant` | always `false` | Technical variant under its model |

Deployment variants preserve exact Ollama tags, pull/run commands, quantization,
parameter size, context window, availability, alias targets, and provenance. They
are selectable filters on model pages, not standalone SEO URLs.

## Source exceptions

Records with `source_status: stale_source_exception`:

- remain visible in structured data and family/model lists;
- carry `source_exception_explanation` describing non-deletion retention;
- set `page.seo_eligible: false`;
- must not appear in sitemaps or search indexes.

Configured exceptions are listed in canonical `catalog-meta.json`
(`source_exception_families`).

## Editorial status

Each family and model includes `editorial_status`:

- `technical_facts_authoritative: true` — sizes, tags, commands, capabilities from canonical source metadata.
- `publisher.verification_status` — `verified`, `unverified`, or `unknown`.
- `enrichment_backlog` — non-blocking review reasons from canonical normalization.

Consumers must not treat unverified publisher metadata as vendor-confirmed branding.

## Classifications

Deterministic filter fields live under `classifications` on families, models, and
variants. See `CLASSIFICATIONS.md` for derivation rules.

## Versioning

Regenerate after each canonical promotion. The manifest links to
`reports/catalog-promotion-receipt.md` for the promotion record matching
`canonical_catalog_version`.

## Non-goals

This projection does not:

- build HTML or routes;
- sync to external repositories;
- download or mirror model weights;
- invent marketing descriptions.

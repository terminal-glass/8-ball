# P4 Public Catalog

Consumer-ready publishing projection derived deterministically from the canonical
`data/normalized/` catalog. This output is metadata only and does not download model
weights or generate website HTML.

## Generation

```bash
eight-ball publish-catalog
```

Reproduces:

| Artifact | Purpose |
| --- | --- |
| `manifest.json` | Schema version, provenance, counts, index paths |
| `index/families.json` | Family landing-page projections |
| `index/models.json` | Model detail-page projections with deployment variants |
| `../reports/public-catalog-publishing.md` | Concise publishing summary |

## Consumption (terminal.glass)

Future `terminal.glass` `/models` work should treat this directory as the stable
read-only contract:

1. Read `manifest.json` for catalog version, collection date, and checksums.
2. Load `index/families.json` for family landing pages (`page.seo_eligible`).
3. Load `index/models.json` for model detail pages and nested `deployment_variants`.
4. Never promote deployment variants to standalone SEO pages (`page.seo_eligible` is
   always `false` on variants).
5. Render `source_status: stale_source_exception` records for transparency but exclude
   them from sitemaps/search (`page.seo_eligible: false`).

See `CONSUMPTION.md` and `CLASSIFICATIONS.md` for field-level contracts.

## Source of truth

Canonical entities remain authoritative in `data/normalized/`. Regenerate this
projection after each canonical promotion; do not hand-edit generated files.

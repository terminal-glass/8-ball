# Catalog version history
#
# `eight-ball promote --apply --confirm` archives the previous canonical
# normalized catalog here before replacing `data/normalized/`.
#
# Layout:
#   data/history/<YYYY.MM.DD>/
#     publishers.json
#     families.json
#     models.json
#     tags.json
#     capabilities.json
#     catalog-meta.json
#     archive-meta.json
#
# Legacy observations in data/families/ are never modified by promote.
#
# catalog-changes.json is the append-only change history. Promotion adds a
# row that lists removed and added Ollama tags. The established row records
# canonical catalog 2026.08.01. Do not delete removed upstream tags from
# this history.

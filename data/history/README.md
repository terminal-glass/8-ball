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

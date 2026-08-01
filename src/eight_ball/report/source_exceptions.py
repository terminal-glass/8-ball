from __future__ import annotations

from eight_ball.collect.manifest import snapshot_policy


def known_source_exception_slugs() -> set[str]:
    slugs: set[str] = set()
    for entry in snapshot_policy().get("known_static_parse_failures", []):
        slug = entry.get("family_slug")
        if isinstance(slug, str) and slug:
            slugs.add(slug)
    return slugs


SOURCE_EXCEPTION_RETENTION_POLICY = (
    "On promotion, retain prior canonical family/model/tag records for configured "
    "source-exception families until parser support or manual source verification "
    "is available. Source exceptions are not live absences and must not be deleted."
)

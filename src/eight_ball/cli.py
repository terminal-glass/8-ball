from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eight_ball.collect.manifest import (
    begin_collection,
    load_collection_state,
    save_collection_state,
    utc_now_iso,
    write_manifest,
)
from eight_ball.collect.ollama import collect_families, collect_ollama_library
from eight_ball.config import load_json, write_json
from eight_ball.export.installer_datasets import build_p2_indexes, export_p3_catalog
from eight_ball.generate.outputs import generate_outputs
from eight_ball.normalize.catalog import normalize_legacy_catalog
from eight_ball.normalize.ollama_web import (
    normalize_ollama_from_manifest,
    normalize_ollama_snapshots,
)
from eight_ball.paths import (
    CANDIDATE_GENERATED_DIR,
    CANDIDATE_INDEXES_DIR,
    CANDIDATE_NORMALIZED_DIR,
    FIXTURES_DIR,
    GENERATED_DIR,
    INDEXES_DIR,
    LEGACY_FAMILIES_DIR,
    NORMALIZED_DIR,
    RAW_DIR,
    REPO_ROOT,
    REPORTS_DIR,
    SAMPLE_FAMILIES,
    SNAPSHOTS_DIR,
)
from eight_ball.recreate.plan import (
    build_recreate_plan,
    discover_family_slugs_from_index,
    write_recreate_plan,
    write_recreate_plan_markdown,
)
from eight_ball.recreate.promote import promote_candidate_catalog
from eight_ball.report.compare import compare_catalogs, write_comparison_report
from eight_ball.report.summary import coverage_summary, write_reports
from eight_ball.validate.catalog import ValidationError, validate_catalog


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Limit normalization to the representative six-model sample.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cached snapshots and fixtures only; no live network requests.",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use test fixtures under tests/fixtures for collection inputs.",
    )
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="Use candidate paths; never overwrite legacy normalized data.",
    )
    parser.add_argument(
        "--source",
        choices=("legacy", "ollama"),
        default="legacy",
        help="Normalization source: legacy family JSON or parsed Ollama snapshots.",
    )
    parser.add_argument(
        "--families",
        default="",
        help="Comma-separated family slugs for Ollama collection/normalization.",
    )
    parser.add_argument(
        "--from-index",
        action="store_true",
        help=(
            "Discover family slugs from the Ollama library index snapshot. "
            "Use with --offline/--fixture for cached indexes, or after collecting the index."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume live collection using cached snapshots and collection state.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Path to a collection manifest for manifest-driven normalization.",
    )


def _family_slugs_from_args(args: argparse.Namespace) -> list[str]:
    if args.families:
        return [slug.strip() for slug in args.families.split(",") if slug.strip()]
    if args.sample:
        return list(SAMPLE_FAMILIES)
    return []


def _discover_families_from_index(*, fixture: bool, offline: bool) -> list[str]:
    return discover_family_slugs_from_index(fixture=fixture, offline=offline)


def _require_ollama_family_selection(args: argparse.Namespace) -> list[str]:
    slugs = _family_slugs_from_args(args)
    if slugs:
        return slugs
    if getattr(args, "from_index", False) or args.fixture or args.offline:
        discovered = _discover_families_from_index(fixture=args.fixture, offline=args.offline)
        if discovered:
            return discovered
    print(
        "Ollama normalization requires an explicit family selection. "
        "Pass --sample, --families <slug,...>, or --from-index with an available "
        "library index (--offline/--fixture).",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _catalog_paths(args: argparse.Namespace) -> tuple:
    if args.candidate or args.source == "ollama":
        return CANDIDATE_NORMALIZED_DIR, CANDIDATE_GENERATED_DIR, CANDIDATE_INDEXES_DIR
    return NORMALIZED_DIR, GENERATED_DIR, INDEXES_DIR


def _stage_fixture_snapshots(family_slugs: list[str]) -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    fixture_root = FIXTURES_DIR / "snapshots"
    names = ["ollama-library-index.html"]
    for slug in family_slugs:
        names.extend([f"{slug}.html", f"{slug}-tags.html"])
    for name in names:
        source = fixture_root / name
        if source.exists():
            target = SNAPSHOTS_DIR / name
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _resolve_manifest_path(args: argparse.Namespace) -> Path | None:
    if args.manifest:
        return Path(args.manifest)
    if args.fixture:
        fixture_manifest = FIXTURES_DIR / "manifests" / "six-family-sample.json"
        if fixture_manifest.exists():
            return fixture_manifest
    if args.candidate:
        latest_path = RAW_DIR / "latest-manifest.json"
        if latest_path.exists():
            latest = load_json(latest_path)
            manifest_path = Path(latest["path"])
            if not manifest_path.is_absolute():
                manifest_path = REPO_ROOT / manifest_path
            if manifest_path.exists():
                return manifest_path
    return None


def cmd_plan(args: argparse.Namespace) -> int:
    """Offline recreate plan: no network, no writes to legacy paths."""
    family_slugs = _family_slugs_from_args(args) or None
    sample_only = bool(args.sample)
    # Default plan uses the library index when available; --sample keeps the small set.
    if not sample_only and family_slugs is None and not args.from_index:
        # Prefer a full index plan when an index snapshot/fixture exists.
        args.from_index = True
    try:
        plan = build_recreate_plan(
            fixture=args.fixture,
            offline=True,
            sample_only=sample_only,
            family_slugs=family_slugs,
        )
    except ValueError as exc:
        print(f"Plan failed: {exc}", file=sys.stderr)
        return 2
    json_path = write_recreate_plan(plan)
    md_path = write_recreate_plan_markdown(plan)
    print(
        "Recreate plan: "
        f"{plan['selected_family_count']} selected / "
        f"{plan['index_family_count']} index / "
        f"{plan['legacy_family_count']} legacy families; "
        f"{plan['estimated_page_fetches']} estimated metadata page fetches."
    )
    print(
        "Publisher preview: "
        f"{plan['publisher_preview']['unknown_publisher_count']} unknown, "
        f"{plan['publisher_preview']['inferred_needs_review_count']} inferred needing review."
    )
    print(f"Plan written to {json_path} and {md_path}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    fixture_dir = FIXTURES_DIR if args.fixture else None
    family_slugs = _family_slugs_from_args(args)
    offline = args.offline or args.fixture
    manifest = begin_collection()
    state = load_collection_state()

    if args.fixture and family_slugs:
        _stage_fixture_snapshots(family_slugs)

    collect_ollama_library(
        offline=offline,
        fixture_dir=fixture_dir,
        candidate=args.candidate,
        manifest=manifest,
        write=False,
        resume=args.resume,
        state=state,
    )
    save_collection_state(state)

    if not family_slugs and args.from_index:
        family_slugs = _discover_families_from_index(fixture=args.fixture, offline=offline)
        if not family_slugs:
            print(
                "No families discovered from library index. "
                "Collect/cache ollama-library-index.html first or use --fixture.",
                file=sys.stderr,
            )
            return 2
        print(f"Discovered {len(family_slugs)} families from library index.")

    if family_slugs:
        if args.fixture:
            _stage_fixture_snapshots(family_slugs)
        collect_families(
            family_slugs,
            offline=offline,
            fixture_dir=fixture_dir,
            candidate=args.candidate,
            manifest=manifest,
            resume=args.resume,
            state=state,
        )
    else:
        write_manifest(manifest, candidate=args.candidate)
        save_collection_state(state)

    print("Collection complete.")
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    if args.source == "ollama":
        manifest_path = _resolve_manifest_path(args)
        if manifest_path is not None:
            family_slugs = _family_slugs_from_args(args) or None
            catalog = normalize_ollama_from_manifest(manifest_path, family_slugs=family_slugs)
            summary = coverage_summary(catalog)
            print(
                "Normalized candidate catalog from manifest: "
                f"{summary['families']} families, {summary['models']} models, {summary['tags']} tags"
            )
            return 0

        family_slugs = _require_ollama_family_selection(args)
        snapshot_dir = SNAPSHOTS_DIR if not args.fixture else FIXTURES_DIR / "snapshots"
        if args.fixture:
            _stage_fixture_snapshots(family_slugs)
        catalog = normalize_ollama_snapshots(
            family_slugs=family_slugs,
            snapshot_dir=snapshot_dir,
            retrieved_at=utc_now_iso(),
        )
        summary = coverage_summary(catalog)
        print(
            "Normalized candidate catalog from Ollama snapshots: "
            f"{summary['families']} families, {summary['models']} models, {summary['tags']} tags"
        )
        return 0

    if args.candidate:
        print("Legacy normalization does not support --candidate.", file=sys.stderr)
        return 1

    families_dir = FIXTURES_DIR / "families" if args.fixture else LEGACY_FAMILIES_DIR
    catalog = normalize_legacy_catalog(sample_only=args.sample, families_dir=families_dir)
    summary = coverage_summary(catalog)
    print(
        "Normalized catalog: "
        f"{summary['families']} families, {summary['models']} models, {summary['tags']} tags"
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    normalized_dir, generated_dir, indexes_dir = _catalog_paths(args)
    try:
        report = validate_catalog(
            include_artifacts=True,
            normalized_dir=normalized_dir,
            generated_dir=generated_dir,
            indexes_dir=indexes_dir,
        )
    except ValidationError as exc:
        failure_report = {
            "valid": False,
            "error_count": len(exc.errors),
            "warning_count": len(exc.warnings),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        write_reports(validation_report=failure_report, normalized_dir=normalized_dir)
        print(f"Validation failed with {len(exc.errors)} error(s).", file=sys.stderr)
        for error in exc.errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        return 1
    write_reports(validation_report=report, normalized_dir=normalized_dir)
    print("Validation passed.")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    normalized_dir, generated_dir, indexes_dir = _catalog_paths(args)
    summary = generate_outputs(
        normalized_dir=normalized_dir,
        generated_dir=generated_dir,
        indexes_dir=indexes_dir,
    )
    print(f"Generated {summary['deployment_combinations']} deployment combinations for {summary['tags']} tags.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    normalized_dir, _, _ = _catalog_paths(args)
    report_name = "candidate-catalog-report.md" if args.candidate or args.source == "ollama" else "catalog-report.md"
    path = write_reports(
        normalized_dir=normalized_dir,
        report_path=REPORTS_DIR / report_name,
    )
    print(f"Report written to {path}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    family_slugs = set(_family_slugs_from_args(args)) or None
    parse_failures: list[dict] | None = None
    meta_path = CANDIDATE_NORMALIZED_DIR / "catalog-meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        if meta.get("parse_failures"):
            parse_failures = meta["parse_failures"]
    comparison = compare_catalogs(family_filter=family_slugs, parse_failures=parse_failures)
    path = write_comparison_report(comparison)
    print(
        "Comparison complete: "
        f"{comparison.shared_tags} shared, "
        f"{len(comparison.candidate_only_tags)} candidate-only, "
        f"{len(comparison.legacy_only_tags)} legacy-only tags."
    )
    print(f"Report written to {path}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    dry_run = not args.apply
    if args.apply and not args.confirm:
        print(
            "Refusing promote --apply without --confirm. "
            "This archives data/normalized and replaces it with the candidate catalog.",
            file=sys.stderr,
        )
        return 2
    try:
        result = promote_candidate_catalog(
            dry_run=dry_run,
            apply=args.apply and args.confirm,
            allow_review_items=args.allow_review_items,
            allow_removals=args.allow_removals,
        )
    except (FileNotFoundError, OSError, ValueError, PermissionError) as exc:
        print(f"Promote failed: {exc}", file=sys.stderr)
        return 1

    write_json(REPORTS_DIR / "promote-report.json", result)
    print(
        "Promote "
        f"{'dry-run' if result['dry_run'] else 'applied'}: "
        f"candidate {result['candidate_counts']} -> current {result['current_counts']}"
    )
    print(f"Eligible: {result['eligible']}")
    for blocker in result["blockers"]:
        print(f"  - BLOCKED: {blocker}")
    for note in result["notes"]:
        print(f"  - {note}")
    if result.get("archive_path"):
        print(f"Archive: {result['archive_path']}")
    print(f"Report written to {REPORTS_DIR / 'promote-report.json'}")
    return 0 if result["eligible"] else 1


def cmd_all(args: argparse.Namespace) -> int:
    if args.source == "ollama" and not args.sample and not args.families and not args.from_index:
        print(
            "Ollama pipeline requires --sample, --families, or --from-index "
            "for explicit family selection.",
            file=sys.stderr,
        )
        return 2

    if cmd_collect(args) != 0:
        return 1
    if cmd_normalize(args) != 0:
        return 1
    normalized_dir, generated_dir, indexes_dir = _catalog_paths(args)
    try:
        validation_report = validate_catalog(
            include_artifacts=False,
            normalized_dir=normalized_dir,
        )
    except ValidationError as exc:
        failure_report = {
            "valid": False,
            "error_count": len(exc.errors),
            "warning_count": len(exc.warnings),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        write_reports(validation_report=failure_report, normalized_dir=normalized_dir)
        print(f"Validation failed with {len(exc.errors)} error(s).", file=sys.stderr)
        return 1
    generation_summary = generate_outputs(
        normalized_dir=normalized_dir,
        generated_dir=generated_dir,
        indexes_dir=indexes_dir,
    )
    try:
        validate_catalog(
            include_artifacts=True,
            normalized_dir=normalized_dir,
            generated_dir=generated_dir,
            indexes_dir=indexes_dir,
        )
    except ValidationError as exc:
        failure_report = {
            "valid": False,
            "error_count": len(exc.errors),
            "warning_count": len(exc.warnings),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        write_reports(
            validation_report=failure_report,
            generation_summary=generation_summary,
            normalized_dir=normalized_dir,
        )
        print(
            f"Post-generation validation failed with {len(exc.errors)} error(s).",
            file=sys.stderr,
        )
        return 1
    path = write_reports(
        validation_report=validation_report,
        generation_summary=generation_summary,
        normalized_dir=normalized_dir,
        report_path=REPORTS_DIR / (
            "candidate-catalog-report.md" if args.candidate or args.source == "ollama" else "catalog-report.md"
        ),
    )
    if args.source == "ollama":
        family_slugs = set(_family_slugs_from_args(args)) or None
        write_comparison_report(compare_catalogs(family_filter=family_slugs))
    print(
        "Pipeline complete: "
        f"{generation_summary['deployment_combinations']} deployment combinations written. "
        f"Report: {path}"
    )
    return 0


def cmd_export_datasets(args: argparse.Namespace) -> int:
    p2_summary = build_p2_indexes()
    print(
        "P2 indexes written: "
        f"{p2_summary['digitalocean_plan_count']} DigitalOcean plans, "
        f"{p2_summary['lightsail_bundle_count']} Lightsail bundles."
    )
    provenance = export_p3_catalog()
    counts = provenance["counts"]
    print(
        "P3 export written: "
        f"{counts['families']} families, {counts['models']} models, "
        f"{counts['tags']} tags from catalog {provenance['catalog_version']} "
        f"(commit {str(provenance['source_commit'])[:12]})."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eight-ball", description="8-BALL Ollama metadata catalog tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in [
        ("plan", cmd_plan),
        ("collect", cmd_collect),
        ("normalize", cmd_normalize),
        ("validate", cmd_validate),
        ("generate", cmd_generate),
        ("report", cmd_report),
        ("compare", cmd_compare),
        ("all", cmd_all),
    ]:
        sub = subparsers.add_parser(name)
        _add_common_args(sub)
        sub.set_defaults(handler=handler)

    promote = subparsers.add_parser(
        "promote",
        help="Dry-run or apply promotion of candidate catalog into data/normalized.",
    )
    promote.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show promote plan without writing (default).",
    )
    promote.add_argument(
        "--apply",
        action="store_true",
        help="Apply promotion after archiving the current canonical catalog.",
    )
    promote.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --apply to confirm irreversible canonical replacement.",
    )
    promote.add_argument(
        "--allow-review-items",
        action="store_true",
        help="Explicitly acknowledge unresolved actionable review records.",
    )
    promote.add_argument(
        "--allow-removals",
        action="store_true",
        help="Explicitly acknowledge canonical families/models/tags absent from candidate.",
    )
    promote.set_defaults(handler=cmd_promote)

    export_datasets = subparsers.add_parser(
        "export-datasets",
        help="Rebuild committed P2 provider indexes and the P3 catalog export.",
    )
    export_datasets.set_defaults(handler=cmd_export_datasets)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

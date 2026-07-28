from __future__ import annotations

import argparse
import sys

from eight_ball.collect.manifest import utc_now_iso
from eight_ball.collect.ollama import collect_families, collect_ollama_library
from eight_ball.generate.outputs import generate_outputs
from eight_ball.normalize.catalog import normalize_legacy_catalog
from eight_ball.normalize.ollama_web import normalize_ollama_snapshots
from eight_ball.paths import (
    CANDIDATE_GENERATED_DIR,
    CANDIDATE_INDEXES_DIR,
    CANDIDATE_NORMALIZED_DIR,
    FIXTURES_DIR,
    GENERATED_DIR,
    INDEXES_DIR,
    LEGACY_FAMILIES_DIR,
    NORMALIZED_DIR,
    REPORTS_DIR,
    SAMPLE_FAMILIES,
    SNAPSHOTS_DIR,
)
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


def _family_slugs(args: argparse.Namespace) -> list[str]:
    if args.families:
        return [slug.strip() for slug in args.families.split(",") if slug.strip()]
    if args.sample:
        return list(SAMPLE_FAMILIES)
    return []


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


def cmd_collect(args: argparse.Namespace) -> int:
    fixture_dir = FIXTURES_DIR if args.fixture else None
    family_slugs = _family_slugs(args)
    offline = args.offline or args.fixture

    if args.fixture and family_slugs:
        _stage_fixture_snapshots(family_slugs)

    if offline:
        collect_ollama_library(offline=True, fixture_dir=fixture_dir, candidate=args.candidate)
    else:
        collect_ollama_library(offline=False, candidate=args.candidate)

    if family_slugs:
        collect_families(
            family_slugs,
            offline=offline,
            fixture_dir=fixture_dir,
            candidate=args.candidate,
        )

    print("Collection complete.")
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    if args.source == "ollama":
        family_slugs = _family_slugs(args) or list(SAMPLE_FAMILIES)
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
    family_slugs = set(_family_slugs(args)) if _family_slugs(args) else None
    comparison = compare_catalogs(family_filter=family_slugs)
    path = write_comparison_report(comparison)
    print(
        "Comparison complete: "
        f"{comparison.shared_tags} shared, "
        f"{len(comparison.candidate_only_tags)} candidate-only, "
        f"{len(comparison.legacy_only_tags)} legacy-only tags."
    )
    print(f"Report written to {path}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
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
        write_comparison_report(compare_catalogs(family_filter=set(_family_slugs(args))))
    print(
        "Pipeline complete: "
        f"{generation_summary['deployment_combinations']} deployment combinations written. "
        f"Report: {path}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eight-ball", description="8-BALL Ollama metadata catalog tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in [
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

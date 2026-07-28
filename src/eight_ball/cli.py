from __future__ import annotations

import argparse
import sys

from eight_ball.collect.ollama import collect_ollama_library
from eight_ball.generate.outputs import generate_outputs
from eight_ball.normalize.catalog import normalize_legacy_catalog
from eight_ball.paths import FIXTURES_DIR, LEGACY_FAMILIES_DIR, SAMPLE_FAMILIES
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


def cmd_collect(args: argparse.Namespace) -> int:
    fixture_dir = FIXTURES_DIR if args.fixture else None
    if args.offline or args.fixture:
        from eight_ball.paths import SNAPSHOTS_DIR

        fixture_snapshot = FIXTURES_DIR / "snapshots" / "ollama-library-index.html"
        if fixture_snapshot.exists():
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            target = SNAPSHOTS_DIR / "ollama-library-index.html"
            if not target.exists():
                target.write_text(fixture_snapshot.read_text(encoding="utf-8"), encoding="utf-8")
        collect_ollama_library(offline=True)
    else:
        collect_ollama_library(offline=False)
    if args.sample:
        from eight_ball.collect.ollama import collect_family_snapshot

        for slug in SAMPLE_FAMILIES:
            collect_family_snapshot(slug, offline=args.offline or args.fixture, fixture_dir=fixture_dir)
    print("Collection complete.")
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    families_dir = FIXTURES_DIR / "families" if args.fixture else LEGACY_FAMILIES_DIR
    catalog = normalize_legacy_catalog(sample_only=args.sample, families_dir=families_dir)
    summary = coverage_summary(catalog)
    print(
        "Normalized catalog: "
        f"{summary['families']} families, {summary['models']} models, {summary['tags']} tags"
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        report = validate_catalog()
    except ValidationError as exc:
        write_reports(validation_report={"valid": False, "error_count": len(exc.errors), "errors": exc.errors})
        print(f"Validation failed with {len(exc.errors)} error(s).", file=sys.stderr)
        for error in exc.errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        return 1
    write_reports(validation_report=report)
    print("Validation passed.")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    summary = generate_outputs()
    print(f"Generated {summary['deployment_combinations']} deployment combinations for {summary['tags']} tags.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    path = write_reports()
    print(f"Report written to {path}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    steps = [cmd_collect, cmd_normalize, cmd_validate, cmd_generate, cmd_report]
    for step in steps:
        code = step(args)
        if code != 0:
            return code
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

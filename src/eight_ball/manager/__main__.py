from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eight_ball.manager.argv import ArgvRejected
from eight_ball.manager.catalog_view import browse, load_catalog
from eight_ball.manager.consult import consult
from eight_ball.manager.hardware import detect_hardware
from eight_ball.manager.lifecycle import (
    list_state,
    pull_model,
    remove_model,
    suitability_for,
    use_model,
)
from eight_ball.manager.ollama_http import OllamaClient
from eight_ball.manager.refresh import adopt_snapshot
from eight_ball.manager.release import verify_manifest, write_manifest
from eight_ball.paths import REPO_ROOT


def _catalog(path: str) -> dict:
    return load_catalog(Path(path) if path else None)


def cmd_manifest(_args: argparse.Namespace) -> int:
    manifest = write_manifest(REPO_ROOT)
    print(
        f"Wrote component release manifest for catalog {manifest['catalog_version']} "
        f"and installer suite {manifest['installer_suite_version']}."
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    failures = verify_manifest(manifest, root=REPO_ROOT)
    if failures:
        print("Release verification failed.", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Release manifest verified.")
    return 0


def cmd_detect(_args: argparse.Namespace) -> int:
    print(json.dumps(detect_hardware(), indent=2))
    return 0


def cmd_browse(args: argparse.Namespace) -> int:
    rows = browse(
        _catalog(args.catalog),
        query=args.query,
        local_downloads_only=not args.include_hosted,
        hardware=detect_hardware(),
    )
    print(json.dumps(rows, indent=2))
    return 0


def cmd_suitability(args: argparse.Namespace) -> int:
    try:
        result = suitability_for(_catalog(args.catalog), args.tag, detect_hardware())
    except ArgvRejected as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def _client(args: argparse.Namespace) -> OllamaClient:
    return OllamaClient(args.ollama)


def cmd_pull(args: argparse.Namespace) -> int:
    hardware = detect_hardware()
    try:
        result = pull_model(
            _catalog(args.catalog),
            _client(args),
            args.tag,
            free_bytes=hardware.get("disk_free_bytes"),
            hardware=hardware,
            policy={
                "allow_unknown_size": args.allow_unknown_size,
                "allow_unattended_fallback": args.allow_unattended_fallback,
            },
        )
    except ArgvRejected as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_use(args: argparse.Namespace) -> int:
    try:
        result = use_model(_catalog(args.catalog), _client(args), args.tag, args.prompt)
    except ArgvRejected as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_list(args: argparse.Namespace) -> int:
    print(json.dumps(list_state(_client(args)), indent=2))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser()
    path = home / ".config" / "8-ball" / "assignments.json"
    assignments: list[dict[str, str]] = []
    if path.exists():
        assignments = json.loads(path.read_text(encoding="utf-8"))
    try:
        result = remove_model(
            _catalog(args.catalog),
            _client(args),
            args.tag,
            assignments,
            decision=args.decision,
            reassign_to=args.reassign_to,
        )
    except ArgvRejected as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if result.get("removed") or result.get("status") == "reassigned":
        from eight_ball.manager.secrets import write_private_file

        write_private_file(path, (json.dumps(assignments, indent=2) + "\n").encode(), home=home)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_consult(args: argparse.Namespace) -> int:
    hardware = detect_hardware()
    catalog = _catalog(args.catalog)
    try:
        from eight_ball.manager.ollama_http import OllamaClient, OllamaError

        client = OllamaClient(args.ollama, timeout=5)
        installed = {model.get("name") or model.get("model") for model in client.list_models()}
        installed.discard(None)
        measurement = None
        measurement_error = None
        from eight_ball.scale import load_scale

        canary_tag = load_scale()["canary"]["tag"]
        if canary_tag in installed:
            try:
                measurement = client.generate(canary_tag, "Say ok.")
            except OllamaError as exc:
                measurement_error = str(exc)
    except OllamaError as exc:
        installed = set()
        measurement = None
        measurement_error = str(exc)
    result = consult(
        catalog,
        ram_bytes=hardware.get("ram_bytes"),
        disk_free_bytes=hardware.get("disk_free_bytes"),
        vram_bytes=hardware.get("vram_bytes"),
        installed=installed,
        measurement=measurement,
        measurement_error=measurement_error,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    metadata = {
        "source_repository": args.source_repository,
        "source_ref": args.source_ref,
        "source_sha": args.source_sha,
        "schema_version": args.schema_version,
        "catalog_version": args.catalog_version,
    }
    result = adopt_snapshot(Path(args.candidate), Path(args.store), metadata)
    print(json.dumps(result["receipt"], indent=2))
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="8.4a-model-manager",
        description="Experimental free model manager. No paid license check.",
    )
    parser.add_argument("--catalog", default="", help="Normalized catalog directory.")
    parser.add_argument("--ollama", default="http://127.0.0.1:11434", help="Local Ollama HTTP API.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("manifest").set_defaults(handler=cmd_manifest)
    verify = sub.add_parser("verify-release")
    verify.add_argument("--manifest", default="install/releases/v0.8.0/component-release-manifest.json")
    verify.set_defaults(handler=cmd_verify)
    sub.add_parser("detect").set_defaults(handler=cmd_detect)

    browse_parser = sub.add_parser("browse")
    browse_parser.add_argument("--query", default="")
    browse_parser.add_argument("--include-hosted", action="store_true")
    browse_parser.set_defaults(handler=cmd_browse)

    suit = sub.add_parser("suitability")
    suit.add_argument("tag")
    suit.set_defaults(handler=cmd_suitability)

    pull = sub.add_parser("pull")
    pull.add_argument("tag")
    pull.add_argument("--allow-unknown-size", action="store_true")
    pull.add_argument("--allow-unattended-fallback", action="store_true")
    pull.set_defaults(handler=cmd_pull)

    use = sub.add_parser("use")
    use.add_argument("tag")
    use.add_argument("prompt")
    use.set_defaults(handler=cmd_use)

    sub.add_parser("list").set_defaults(handler=cmd_list)

    remove = sub.add_parser("remove")
    remove.add_argument("tag")
    remove.add_argument("--decision", choices=["stop", "reassign", "remove"])
    remove.add_argument("--reassign-to")
    remove.add_argument("--home", default=str(Path.home()))
    remove.set_defaults(handler=cmd_remove)

    sub.add_parser("consult").set_defaults(handler=cmd_consult)

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--candidate", required=True)
    refresh.add_argument("--store", required=True)
    refresh.add_argument("--source-repository", required=True)
    refresh.add_argument("--source-ref", required=True)
    refresh.add_argument("--source-sha", required=True)
    refresh.add_argument("--schema-version", required=True)
    refresh.add_argument("--catalog-version", required=True)
    refresh.set_defaults(handler=cmd_refresh)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

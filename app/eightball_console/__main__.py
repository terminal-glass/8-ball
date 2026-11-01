"""eightball-console CLI.

  serve                       run the web console (loopback 127.0.0.1:8788 by default)
  scan  [--out FILE]          hardware scan -> 8ball.host-scan.v1 (stdout or atomic file)
  build --scan FILE --out FILE  validated profile -> 8ball.host-profile.v1 (atomic publish)
  check [--profile FILE]      validate a profile; exit 0 valid, 3 not ready (prints the status)
  user-add NAME [--role admin|viewer] --password-file FILE   add a basic-auth user
  console-view TOKEN          read-only job log viewer (run by ttyd)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as config_mod


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eightball-console")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    s = sub.add_parser("scan")
    s.add_argument("--out")
    s.add_argument("--no-ollama", action="store_true", help="do not record the local Ollama version")
    b = sub.add_parser("build")
    b.add_argument("--scan", required=True)
    b.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--profile")
    c.add_argument("--json", action="store_true")
    u = sub.add_parser("user-add")
    u.add_argument("name")
    u.add_argument("--role", default="admin", choices=["admin", "viewer"])
    u.add_argument("--password-file", required=True)
    v = sub.add_parser("console-view")
    v.add_argument("token", nargs="*")
    a = ap.parse_args(argv)
    cfg = config_mod.load(a.config)

    if a.cmd == "serve":
        import uvicorn

        from .server import create_app
        uvicorn.run(create_app(cfg), host=cfg.listen_host, port=cfg.listen_port, proxy_headers=False,
                    server_header=False, log_level="info", access_log=False)
        return 0
    if a.cmd == "scan":
        from .producer import scan, write_atomic
        doc = scan(str(cfg.models_dir), None if a.no_ollama else cfg.instances[0].base_url)
        if a.out:
            write_atomic(Path(a.out), doc)
            print(f"scan written: {a.out} ({len(doc['unknowns'])} unknown field(s))")
        else:
            json.dump(doc, sys.stdout, indent=2)
            print()
        return 0
    if a.cmd == "build":
        from .catalog import Catalog
        from .nerds import menu
        from .producer import build, write_atomic
        scan_doc = json.loads(Path(a.scan).read_text())
        prof = build(scan_doc, Catalog(cfg.catalog_root, cfg.catalog_commit), menu())
        write_atomic(Path(a.out), prof)
        cls = prof["classification"]
        print(f"profile written: {a.out} state={prof['state']} platform={prof['platform']['id']} "
              f"lane={prof['lane']['lane_path']} catalog_type={cls['catalog_deployment_type_id']} "
              f"P#=unknown M-tier=unclassified unknowns={len(prof['unknowns'])}")
        return 0
    if a.cmd == "check":
        from .profile import load
        res = load(Path(a.profile) if a.profile else cfg.profile_path, cfg.profile_max_age_days)
        if a.json:
            print(json.dumps({k: v for k, v in res.items() if k != "profile"}))
        else:
            print(f"{res['status']}: {res['path']}" + ("" if not res["problems"] else " - " + "; ".join(res["problems"])))
        return 0 if res["status"] == "valid" else 3
    if a.cmd == "user-add":
        from .auth import Users
        pw = Path(a.password_file).read_text().strip()
        if len(pw) < 12:
            print("password must be at least 12 characters", file=sys.stderr)
            return 2
        Users(cfg.users_file).add(a.name, a.role, pw)
        print(f"user {a.name} ({a.role}) saved to {cfg.users_file}")
        return 0
    if a.cmd == "console-view":
        from .console import view
        return view(cfg.jobs_dir, cfg.secret_file, a.token)
    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate or check the hardware browsing page without fetching or running models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eight_ball.generate.hardware_guide import render_hardware_guide


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if the guide is stale; write nothing."
    )
    args = parser.parse_args()
    target = ROOT / "hardware" / "README.md"
    content = render_hardware_guide(ROOT)
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            print(
                "Hardware guide is stale. Run python3 scripts/generate-hardware-guide.py",
                file=sys.stderr,
            )
            return 1
        print("Hardware guide matches canonical sources.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print("Wrote hardware/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Select the largest model size with confirmed lane fit for a C10 install lane."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json_url(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def profiles_base() -> str:
    return os.environ.get("EIGHTBALL_PROFILES_BASE", "").strip()


def find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    while current != current.parent:
        if (current / "profiles").is_dir() and (current / "install").is_dir():
            return current
        current = current.parent
    return None


def resolve_local_repo_root() -> Path:
    hint = os.environ.get("EIGHTBALL_REPO_ROOT", "").strip()
    if hint:
        root = Path(hint)
        if (root / "profiles").is_dir():
            return root
    found = find_repo_root(Path.cwd())
    if found is not None:
        return found
    raise SystemExit(
        "Could not locate profiles/. Set EIGHTBALL_REPO_ROOT or EIGHTBALL_PROFILES_BASE."
    )


def load_profile_document(relative_path: str) -> Any:
    base = profiles_base()
    if base.startswith("http://") or base.startswith("https://"):
        url = f"{base.rstrip('/')}/{relative_path.lstrip('/')}"
        try:
            return fetch_json_url(url)
        except urllib.error.URLError as exc:
            raise SystemExit(f"Missing remote profile document: {url} ({exc})") from exc
    root = resolve_local_repo_root()
    path = Path(base) / relative_path if base else root / relative_path
    if not path.is_file():
        raise SystemExit(f"Missing profile document: {path}")
    return load_json(path)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: c10-select-model.py <model-slug> <lane-path> [legacy-assumption-ignored]",
            file=sys.stderr,
        )
        return 2

    model_slug = sys.argv[1]
    lane_path = sys.argv[2]

    model_page = load_profile_document(f"profiles/{model_slug}.json")
    lane_data = load_profile_document(f"profiles/{model_slug}/{lane_path}/lane.json")
    fit_by_ref = {row["ollama_ref"]: row for row in lane_data.get("size_fit", [])}

    selected = None
    fallback_chain = []
    for size in model_page.get("sizes", []):
        ref = size["ollama_ref"]
        fit = fit_by_ref.get(ref, {})
        fit_status = fit.get("fit_status")
        if fit_status is None and fit.get("fits"):
            fit_status = "fit"
        if fit_status == "fit" and fit.get("fits"):
            selected = ref
            break
        fallback_chain.append(
            {
                "ollama_ref": ref,
                "fit_status": fit_status or ("unknown" if not fit.get("fits") else "no_fit"),
                "reason": fit.get("reason", "does not fit lane"),
                "missing_evidence": fit.get("missing_evidence", []),
            }
        )

    if not selected:
        output = {
            "model_slug": model_slug,
            "lane_path": lane_path,
            "selection_status": "unverified",
            "selected_ollama_ref": None,
            "promoted_size_slug": model_page.get("promoted_size_slug"),
            "fallback_chain": fallback_chain,
            "message": "No size has a confirmed lane fit; runtime evidence or a smaller verified lane is required.",
        }
        print(json.dumps(output))
        return 1

    output = {
        "model_slug": model_slug,
        "lane_path": lane_path,
        "selection_status": "selected",
        "selected_ollama_ref": selected,
        "promoted_size_slug": model_page.get("promoted_size_slug"),
        "fallback_chain": fallback_chain,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

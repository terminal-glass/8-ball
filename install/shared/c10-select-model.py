#!/usr/bin/env python3
"""Select the largest model size that fits detected hardware for a C10 lane."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    while current != current.parent:
        if (current / "profiles").is_dir() and (current / "install").is_dir():
            return current
        current = current.parent
    raise SystemExit("Could not locate repository root with profiles/ and install/")


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: c10-select-model.py <model-slug> <lane-path> <provider-assumption.json>", file=sys.stderr)
        return 2

    model_slug = sys.argv[1]
    lane_path = sys.argv[2]
    assumption_path = Path(sys.argv[3])
    repo_root = find_repo_root(Path.cwd())

    model_page_path = repo_root / "profiles" / f"{model_slug}.json"
    if not model_page_path.is_file():
        raise SystemExit(f"Missing model page: {model_page_path}")

    model_page = load_json(model_page_path)
    lane_json = repo_root / "profiles" / model_slug / lane_path / "lane.json"
    if not lane_json.is_file():
        raise SystemExit(f"Missing lane profile: {lane_json}")

    lane_data = load_json(lane_json)
    fit_by_ref = {row["ollama_ref"]: row for row in lane_data.get("size_fit", [])}

    selected = None
    fallback_chain = []
    for size in model_page.get("sizes", []):
        ref = size["ollama_ref"]
        fit = fit_by_ref.get(ref, {})
        if fit.get("fits"):
            selected = ref
            break
        fallback_chain.append({"ollama_ref": ref, "reason": fit.get("reason", "does not fit lane")})

    if not selected:
        # Last resort: smallest size in page
        sizes = model_page.get("sizes", [])
        if sizes:
            selected = sizes[-1]["ollama_ref"]
            fallback_chain.append({"ollama_ref": selected, "reason": "fallback to smallest listed size"})

    output = {
        "model_slug": model_slug,
        "lane_path": lane_path,
        "provider_assumption": str(assumption_path),
        "selected_ollama_ref": selected,
        "promoted_size_slug": model_page.get("promoted_size_slug"),
        "fallback_chain": fallback_chain,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

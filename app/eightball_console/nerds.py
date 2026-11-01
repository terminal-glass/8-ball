"""Happy Nerds menu: the 50 curated families, resolved to exact catalog tags and per-host fit."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import fit
from .catalog import Catalog

MENU_FILE = Path(__file__).parent / "data" / "nerds-menu.v1.json"
MAX_COMPATIBLE = 50


@lru_cache(maxsize=1)
def menu() -> dict[str, Any]:
    return json.loads(MENU_FILE.read_text(encoding="utf-8"))


def _norm(ref: str) -> str:
    return ref if ":" in ref else ref + ":latest"


def resolve(catalog: Catalog, profile: dict[str, Any] | None, installed: set[str] | None,
            disk_free_gb: float | None = None) -> dict[str, Any]:
    m = menu()
    host = fit.host_capacity(profile)
    installed_n = {_norm(x) for x in (installed or set())}
    families = []
    compatible = []
    for entry in m["featured"]:
        slug = entry["family_slug"]
        fam_doc = catalog.family(slug)
        variants = []
        for s in catalog.sizes(slug):
            ref = s["ollama_ref"]
            f = fit.evaluate(ref, s, host, disk_free_gb)
            if profile is None and f["state"] != "cloud":
                f = {**f, "state": "unknown", "color": "grey", "label": "Unknown",
                     "reasons": ["no valid host profile"]}
            variants.append({
                "ref": ref, "size_slug": s.get("size_slug"), "quantization": s.get("quantization"),
                "parameter_count": s.get("parameter_count"), "download_size_bytes": s.get("download_size_bytes"),
                "cloud": f["state"] == "cloud", "installed": _norm(ref) in installed_n, "fit": f,
                "requirements": fit.requirements(s), "provenance": s.get("provenance"),
            })
        local_ok = [v for v in variants if v["fit"]["state"] in ("fits", "constrained")]
        def size_key(v: dict[str, Any]) -> float:
            return float(v["download_size_bytes"] or 0)
        greens = [v for v in local_ok if v["fit"]["state"] == "fits"]
        suggested = max(greens or local_ok, key=size_key) if local_ok else None
        if suggested and len(compatible) < MAX_COMPATIBLE:
            compatible.append(suggested["ref"])
        families.append({
            "family_slug": slug, "display_name": entry.get("display_name"), "category": entry.get("category"),
            "bot_line": entry.get("bot_line"), "kind": "embedding" if entry.get("category") == "embedding" else "generate",
            "in_catalog": fam_doc is not None or bool(variants),
            "description": (fam_doc or {}).get("description") if isinstance(fam_doc, dict) else None,
            "suggested_ref": suggested["ref"] if suggested else None,
            "installed_refs": [v["ref"] for v in variants if v["installed"]],
            "variants": variants,
        })
    return {
        "schema_version": m["schema_version"], "curated_at": m.get("curated_at"), "rules": m.get("rules", []),
        "categories": m["categories"], "fit_policy": fit.POLICY_ID, "legend": fit.LABELS,
        "catalog_commit": catalog.commit,
        "tier": {"p_identity": None, "m_tier": None, "status": "unknown/unclassified",
                 "reason": "P# and M1-M6 are not defined in the catalog; fit is per tag from estimates"},
        "compatible_refs": compatible, "families": families,
    }

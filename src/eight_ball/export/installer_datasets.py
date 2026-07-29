"""Build committed P2 provider indexes and the P3 catalog export.

P2: deterministic indexes over the static provider datasets.
P3: validated Ollama metadata snapshot references plus a compact
hardware-tier model-selection index that installer-authoring work can
consume. All derived numbers are labeled estimated; no installer logic,
no model payloads, and no `8.sh` generation live here.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from eight_ball.config import hardware_profiles_config, load_json, write_json
from eight_ball.estimate.hardware import estimate_memory_gb
from eight_ball.paths import NORMALIZED_DIR, REPO_ROOT
from eight_ball.provenance import utc_now_iso

P1_DIR = REPO_ROOT / "P1-Estimator"
P2_DIR = REPO_ROOT / "P2-Provider-Datasets"
P3_DIR = REPO_ROOT / "P3-Ollama-Metadata-Catalog"

NORMALIZED_FILES = (
    "publishers.json",
    "families.json",
    "models.json",
    "tags.json",
    "capabilities.json",
    "catalog-meta.json",
)

# Per-profile cap keeps the selection index compact enough for shell consumers.
MAX_SELECTIONS_PER_PROFILE = 25


def _repo_head_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# P2 indexes
# ---------------------------------------------------------------------------

def _digitalocean_plans() -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for path in sorted((P2_DIR / "providers" / "digitalocean").glob("*.json")):
        plans.extend(load_json(path))
    return plans


def _lightsail_bundles() -> list[dict[str, Any]]:
    return load_json(
        P2_DIR / "providers" / "lightsail" / "linux-unix-public-ipv4-bundles.json"
    )


def build_p2_indexes(*, p2_dir: Path = P2_DIR) -> dict[str, Any]:
    """Write providers.json, plans.json, and provider-summary.json for P2."""
    indexes_dir = p2_dir / "indexes"
    indexes_dir.mkdir(parents=True, exist_ok=True)

    do_plans = _digitalocean_plans()
    ls_bundles = _lightsail_bundles()

    providers = [
        {
            "provider_id": "digitalocean",
            "display_name": "DigitalOcean",
            "dataset_paths": sorted(
                str(path.relative_to(p2_dir))
                for path in (p2_dir / "providers" / "digitalocean").glob("*.json")
            ),
            "plan_count": len(do_plans),
        },
        {
            "provider_id": "lightsail",
            "display_name": "AWS Lightsail",
            "dataset_paths": ["providers/lightsail/linux-unix-public-ipv4-bundles.json"],
            "plan_count": len(ls_bundles),
        },
        {
            "provider_id": "nocloudgpt",
            "display_name": "NoCloudGPT internal planning",
            "dataset_paths": [
                "providers/nocloudgpt/appliance-overhead.json",
                "providers/nocloudgpt/deployment-templates.json",
            ],
            "plan_count": 0,
        },
    ]

    plans: list[dict[str, Any]] = []
    for plan in do_plans:
        plans.append(
            {
                "provider_id": "digitalocean",
                "plan_id": plan["plan_slug"],
                "display_name": plan["display_name"],
                "vcpu": plan["vcpu"],
                "ram_gb": plan["ram_gb"],
                "disk_gb": plan["disk_gb"],
                "monthly_price_usd": plan["monthly_price_usd"],
                "source_url": plan["source_url"],
            }
        )
    for bundle in ls_bundles:
        plans.append(
            {
                "provider_id": "lightsail",
                "plan_id": bundle["bundle_id"],
                "display_name": bundle["display_name"],
                "vcpu": bundle["vcpu"],
                "ram_gb": bundle["ram_gb"],
                "disk_gb": bundle["disk_gb"],
                "monthly_price_usd": bundle["monthly_price_usd"],
                "source_url": bundle["source_url"],
            }
        )

    summary = {
        "generated_at": utc_now_iso(),
        "digitalocean_plan_count": len(do_plans),
        "lightsail_bundle_count": len(ls_bundles),
        "total_plan_count": len(plans),
        "provider_count": len(providers),
    }

    write_json(indexes_dir / "providers.json", providers)
    write_json(indexes_dir / "plans.json", plans)
    write_json(indexes_dir / "provider-summary.json", summary)
    return summary


# ---------------------------------------------------------------------------
# P3 catalog export
# ---------------------------------------------------------------------------

def _required_overhead_reserves() -> dict[str, float]:
    """Sum required RAM/disk reserves from the P1 overhead dataset."""
    reserves_path = P1_DIR / "data" / "NC" / "overhead-reserves.json"
    ram_gb = 0.0
    disk_gb = 0.0
    trial_ram_gb = 0.0
    if reserves_path.exists():
        for item in load_json(reserves_path):
            if not item.get("required"):
                continue
            ram_gb += float(item.get("reserved_ram_gb") or 0)
            disk_gb += float(item.get("reserved_disk_gb") or 0)
            if item.get("component") in {"Ubuntu operating system", "Ollama service"}:
                trial_ram_gb += float(item.get("reserved_ram_gb") or 0)
    else:
        trial_ram_gb = 3.0
        ram_gb = 5.5
        disk_gb = 156.0
    return {
        "appliance_required_ram_gb": round(ram_gb, 2),
        "appliance_required_disk_gb": round(disk_gb, 2),
        "trial_required_ram_gb": round(trial_ram_gb, 2),
    }


def _default_tags_by_model(
    models: list[dict[str, Any]],
    tags_by_identifier: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for model in models:
        default_tag = model.get("default_tag")
        tag = tags_by_identifier.get(default_tag or "")
        if tag is not None:
            selected.append(tag)
    return selected


def _selection_entry(tag: dict[str, Any], estimates: dict[str, Any]) -> dict[str, Any]:
    return {
        "ollama_identifier": tag["ollama_identifier"],
        "model_id": tag.get("model_id"),
        "pull_command": tag.get("pull_command"),
        "run_command": tag.get("run_command"),
        "download_size_bytes": tag.get("download_size_bytes"),
        "download_size_text": tag.get("download_size_text"),
        "parameter_count": tag.get("parameter_count"),
        "quantization": tag.get("quantization"),
        "availability": tag.get("availability"),
        "estimated_min_system_ram_gb": estimates.get("min_system_ram_gb"),
        "estimated_recommended_system_ram_gb": estimates.get("recommended_system_ram_gb"),
        "estimated_min_vram_gb": estimates.get("min_vram_gb"),
        "confidence": "estimated",
    }


def build_model_selection_index(
    *,
    normalized_dir: Path = NORMALIZED_DIR,
) -> dict[str, Any]:
    """Compact per-hardware-profile model candidates from the canonical catalog.

    Selection rule (deterministic): default tags of each model whose
    estimated recommended system RAM fits the profile budget after required
    overhead reserves; sorted by download size descending (largest fitting
    model first), capped per profile.
    """
    models = load_json(normalized_dir / "models.json")
    tags = load_json(normalized_dir / "tags.json")
    tags_by_identifier = {tag["ollama_identifier"]: tag for tag in tags}
    candidates = _default_tags_by_model(models, tags_by_identifier)
    overheads = _required_overhead_reserves()
    profiles = hardware_profiles_config().get("profiles", [])

    selections: dict[str, Any] = {}
    for profile in profiles:
        profile_id = profile["id"]
        system_ram = float(profile.get("system_ram_gb") or 0)
        vram = float(profile.get("vram_gb") or 0)
        cpu_only = bool(profile.get("cpu_only"))
        ram_budget = max(system_ram - overheads["trial_required_ram_gb"], 0.0)

        fitting: list[tuple[int, dict[str, Any]]] = []
        for tag in candidates:
            if tag.get("availability") not in {"local", "both"}:
                continue
            size = tag.get("download_size_bytes")
            if size is None:
                continue
            estimates = estimate_memory_gb(tag)
            required_ram = estimates.get("recommended_system_ram_gb")
            if required_ram is None or required_ram > ram_budget:
                continue
            if not cpu_only:
                min_vram = estimates.get("min_vram_gb") or 0.0
                if min_vram > vram:
                    continue
            fitting.append((int(size), _selection_entry(tag, estimates)))

        fitting.sort(key=lambda item: (-item[0], item[1]["ollama_identifier"]))
        selections[profile_id] = {
            "display_name": profile.get("display_name"),
            "system_ram_gb": system_ram,
            "vram_gb": vram,
            "cpu_only": cpu_only,
            "model_ram_budget_gb": round(ram_budget, 2),
            "candidate_count": len(fitting),
            "candidates": [entry for _size, entry in fitting[:MAX_SELECTIONS_PER_PROFILE]],
        }

    catalog_meta = load_json(normalized_dir / "catalog-meta.json")
    return {
        "generated_at": utc_now_iso(),
        "catalog_version": catalog_meta.get("catalog_version"),
        "confidence": "estimated",
        "notes": [
            "Derived deterministically from the committed normalized catalog.",
            "RAM/VRAM estimates are heuristic planning values, not vendor guarantees.",
            "Overhead reserves come from P1-Estimator required components.",
            "Candidates are default tags with published download sizes, largest first.",
        ],
        "overhead_reserves_gb": _required_overhead_reserves(),
        "max_candidates_per_profile": MAX_SELECTIONS_PER_PROFILE,
        "profiles": selections,
    }


def export_p3_catalog(
    *,
    normalized_dir: Path = NORMALIZED_DIR,
    p3_dir: Path = P3_DIR,
) -> dict[str, Any]:
    """Write the P3 provenance record and compact catalog indexes.

    The full normalized catalog stays canonical under data/normalized/ in
    this same repository; P3 records the exact source and publishes compact
    installer-consumable indexes.
    """
    indexes_dir = p3_dir / "indexes"
    indexes_dir.mkdir(parents=True, exist_ok=True)

    catalog_meta = load_json(normalized_dir / "catalog-meta.json")
    counts = {
        "publishers": len(load_json(normalized_dir / "publishers.json")),
        "families": len(load_json(normalized_dir / "families.json")),
        "models": len(load_json(normalized_dir / "models.json")),
        "tags": len(load_json(normalized_dir / "tags.json")),
    }

    source_files = {}
    for name in NORMALIZED_FILES:
        path = normalized_dir / name
        if path.exists():
            source_files[name] = {
                "path": str(path.relative_to(REPO_ROOT)),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }

    selection = build_model_selection_index(normalized_dir=normalized_dir)
    write_json(indexes_dir / "model-selection.json", selection)

    summary = {
        "generated_at": selection["generated_at"],
        "catalog_version": catalog_meta.get("catalog_version"),
        "counts": counts,
        "profiles": len(selection["profiles"]),
        "total_candidates": sum(
            profile["candidate_count"] for profile in selection["profiles"].values()
        ),
    }
    write_json(indexes_dir / "catalog-summary.json", summary)

    provenance = {
        "generated_at": selection["generated_at"],
        "source_repository": "terminal-glass/8-ball",
        "source_commit": _repo_head_commit(),
        "catalog_version": catalog_meta.get("catalog_version"),
        "catalog_source_id": catalog_meta.get("catalog_source_id"),
        "normalized_dir": str(normalized_dir.relative_to(REPO_ROOT)),
        "source_files": source_files,
        "counts": counts,
        "exports": [
            "indexes/model-selection.json",
            "indexes/catalog-summary.json",
        ],
        "policy": {
            "metadata_only": True,
            "model_payloads_included": False,
            "installer_scripts_included": False,
        },
    }
    write_json(p3_dir / "PROVENANCE.json", provenance)
    return provenance

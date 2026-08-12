"""DigitalOcean Droplet provider-plan compatibility projection for C10.1-9."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_DIR = REPO_ROOT / "AGENTS" / "data-science" / "profile-mapping"
SNAPSHOT_ID = "2026-08-12"
RAW_SNAPSHOT_JSON = MAPPING_DIR / f"digitalocean-raw-sizes-{SNAPSHOT_ID}.json"
CATALOG_JSON = MAPPING_DIR / "digitalocean-base-pilot-catalog.json"
CATALOG_CSV = MAPPING_DIR / "digitalocean-base-pilot-catalog.csv"
SELECTION_MD = MAPPING_DIR / "digitalocean-base-pilot-selection.md"
PILOT_MENU_JSON = MAPPING_DIR / "8ball-base-pilot-menu.json"

COMPAT_DIR = REPO_ROOT / "profiles" / "provider-compatibility" / "digitalocean"
OUTPUT_CATALOG_JSON = COMPAT_DIR / "catalog.json"
OUTPUT_CATALOG_CSV = COMPAT_DIR / "catalog.csv"
CPU_COMPAT_CSV = COMPAT_DIR / "cpu-plan-compatibility.csv"
GPU_COMPAT_CSV = COMPAT_DIR / "gpu-plan-compatibility.csv"
REPORT_JSON = REPO_ROOT / "data" / "generated" / "digitalocean-capability-report.json"
REPORT_MD = REPO_ROOT / "docs" / "C10.1-9-digitalocean-capability-report.md"

P2_CPU_DIR = (
    REPO_ROOT / "AGENTS" / "data-science" / "ollama-mapping" / "P2-Provider-Datasets" / "providers" / "digitalocean"
)

CPU_FAMILY_FILES = {
    "basic": P2_CPU_DIR / "basic.json",
    "general-purpose": P2_CPU_DIR / "general-purpose.json",
    "cpu-optimized": P2_CPU_DIR / "cpu-optimized.json",
    "memory-optimized": P2_CPU_DIR / "memory-optimized.json",
}

ALLOWED_CPU_FAMILIES = frozenset(CPU_FAMILY_FILES)
REQUIRED_GPU_SLUGS = frozenset(
    {
        "gpu-mi300x1-192gb",
        "gpu-mi300x8-1536gb",
        "gpu-h100x1-80gb",
        "gpu-h100x8-640gb",
        "gpu-h200x1-141gb",
        "gpu-h200x8-1128gb",
        "gpu-l40sx1-48gb",
        "gpu-4000adax1-20gb",
        "gpu-6000adax1-48gb",
    }
)

DOCS_FEATURES_URL = "https://docs.digitalocean.com/products/droplets/details/features/"
DOCS_SIZES_API_URL = "https://docs.digitalocean.com/reference/api/reference/sizes/"
PRICING_URL = "https://www.digitalocean.com/pricing/droplets"
RETRIEVED_AT_UTC = "2026-08-12T00:00:00Z"

CATALOG_COLUMNS = [
    "provider",
    "provider_size_slug",
    "plan_family",
    "service_class",
    "pilot_included",
    "availability_status",
    "vcpus",
    "memory_gib",
    "boot_disk_gib",
    "scratch_disk_gib",
    "gpu_vendor",
    "gpu_model",
    "gpu_count",
    "gpu_memory_gib",
    "cpu_architecture",
    "region_availability",
    "source_url",
    "source_locator",
    "source_snapshot_path",
    "retrieved_at_utc",
    "runtime_verification_required",
    "notes",
]

COMPAT_COLUMNS = [
    "model_id",
    "model_slug",
    "size_slug",
    "ollama_ref",
    "target_lane",
    "provider_size_slug",
    "plan_family",
    "service_class",
    "pilot_menu_band",
    "pilot_candidate_chain",
    "classification",
    "model_fit_proven",
    "runtime_trial_required",
    "memory_gib",
    "boot_disk_gib",
    "scratch_disk_gib",
    "gpu_vendor",
    "gpu_model",
    "gpu_count",
    "gpu_memory_gib",
    "model_minimum_ram_gb",
    "model_minimum_disk_free_gb",
    "model_minimum_vram_gb",
    "ram_gate",
    "disk_gate_visible",
    "gpu_vram_gate",
    "compatibility_status",
    "source_paths",
]

PILOT_OLLAMA_REFS = frozenset(
    {
        "qwen3:0.6b",
        "qwen3:1.7b",
        "qwen3:4b",
        "qwen3:8b",
        "qwen3:14b",
    }
)

FALLBACK_BAND = "fallback-under-4gb"
SELECTION_COUNT = 6

GPU_DOC_ROWS: list[dict[str, Any]] = [
    {
        "provider_size_slug": "gpu-mi300x1-192gb",
        "gpu_vendor": "AMD",
        "gpu_model": "MI300X",
        "gpu_count": 1,
        "gpu_memory_gib": 192,
        "memory_gib": 240,
        "vcpus": 20,
        "boot_disk_gib": 720,
        "scratch_disk_gib": 5120,
        "source_locator": "On-Demand GPU Droplets / AMD / MI300X",
    },
    {
        "provider_size_slug": "gpu-mi300x8-1536gb",
        "gpu_vendor": "AMD",
        "gpu_model": "MI300X",
        "gpu_count": 8,
        "gpu_memory_gib": 1536,
        "memory_gib": 1920,
        "vcpus": 160,
        "boot_disk_gib": 2046,
        "scratch_disk_gib": 40960,
        "source_locator": "On-Demand GPU Droplets / AMD / MI300X (8x)",
    },
    {
        "provider_size_slug": "gpu-h100x1-80gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "H100",
        "gpu_count": 1,
        "gpu_memory_gib": 80,
        "memory_gib": 240,
        "vcpus": 20,
        "boot_disk_gib": 720,
        "scratch_disk_gib": 5120,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / H100",
    },
    {
        "provider_size_slug": "gpu-h100x8-640gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "H100",
        "gpu_count": 8,
        "gpu_memory_gib": 640,
        "memory_gib": 1920,
        "vcpus": 160,
        "boot_disk_gib": 2046,
        "scratch_disk_gib": 40960,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / H100 (8x)",
    },
    {
        "provider_size_slug": "gpu-h200x1-141gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "H200",
        "gpu_count": 1,
        "gpu_memory_gib": 141,
        "memory_gib": 240,
        "vcpus": 24,
        "boot_disk_gib": 720,
        "scratch_disk_gib": 5120,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / H200",
    },
    {
        "provider_size_slug": "gpu-h200x8-1128gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "H200",
        "gpu_count": 8,
        "gpu_memory_gib": 1128,
        "memory_gib": 1920,
        "vcpus": 192,
        "boot_disk_gib": 2046,
        "scratch_disk_gib": 40960,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / H200 (8x)",
    },
    {
        "provider_size_slug": "gpu-l40sx1-48gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "L40s",
        "gpu_count": 1,
        "gpu_memory_gib": 48,
        "memory_gib": 64,
        "vcpus": 8,
        "boot_disk_gib": 500,
        "scratch_disk_gib": None,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / L40s",
    },
    {
        "provider_size_slug": "gpu-4000adax1-20gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "RTX 4000",
        "gpu_count": 1,
        "gpu_memory_gib": 20,
        "memory_gib": 32,
        "vcpus": 8,
        "boot_disk_gib": 500,
        "scratch_disk_gib": None,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / RTX 4000",
    },
    {
        "provider_size_slug": "gpu-6000adax1-48gb",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "RTX 6000",
        "gpu_count": 1,
        "gpu_memory_gib": 48,
        "memory_gib": 64,
        "vcpus": 8,
        "boot_disk_gib": 500,
        "scratch_disk_gib": None,
        "source_locator": "On-Demand GPU Droplets / NVIDIA / RTX 6000",
    },
]

MEMORY_OPTIMIZED_EXTRA = {
    "provider": "digitalocean",
    "family": "Memory Optimized",
    "plan_slug": "m-24vcpu-192gb",
    "display_name": "Memory Optimized 24 vCPU / 192 GiB",
    "vcpu": 24,
    "ram_gb": 192,
    "disk_gb": 600,
    "architecture": "x86_64",
    "source_url": PRICING_URL,
    "verified_at_utc": RETRIEVED_AT_UTC,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _family_slug(family_name: str) -> str:
    mapping = {
        "Basic": "basic",
        "General Purpose": "general-purpose",
        "CPU Optimized": "cpu-optimized",
        "Memory Optimized": "memory-optimized",
    }
    return mapping[family_name]


def _load_p2_cpu_family(family_slug: str) -> list[dict[str, Any]]:
    path = CPU_FAMILY_FILES[family_slug]
    rows = json.loads(path.read_text(encoding="utf-8"))
    if family_slug == "memory-optimized":
        slugs = {row["plan_slug"] for row in rows}
        if "m-24vcpu-192gb" not in slugs:
            rows.append(dict(MEMORY_OPTIMIZED_EXTRA))
    return rows


def _cpu_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["ram_gb"], row["vcpu"], row["disk_gb"], row["plan_slug"])


def select_evenly_distributed(sorted_rows: list[dict[str, Any]], count: int = SELECTION_COUNT) -> list[dict[str, Any]]:
    n = len(sorted_rows)
    if n <= count:
        return list(sorted_rows)
    indices = [round(i * (n - 1) / (count - 1)) for i in range(count)]
    return [sorted_rows[i] for i in indices]


def selection_algorithm_description() -> str:
    return (
        "For each allowed CPU family, sort plans by "
        "(memory_gib, vcpus, boot_disk_gib, provider_size_slug) ascending, then select "
        f"{SELECTION_COUNT} evenly distributed indices with "
        "`index_i = round(i * (n - 1) / ({SELECTION_COUNT} - 1))` for i in 0..{SELECTION_COUNT - 1}, "
        "always including the smallest and largest available entry."
    )


def build_raw_cpu_sizes(repo_root: Path = REPO_ROOT) -> dict[str, list[dict[str, Any]]]:
    families: dict[str, list[dict[str, Any]]] = {}
    for family_slug in sorted(ALLOWED_CPU_FAMILIES):
        rows = _load_p2_cpu_family(family_slug)
        normalized = []
        for row in sorted(rows, key=_cpu_sort_key):
            normalized.append(
                {
                    "provider_size_slug": row["plan_slug"],
                    "plan_family": family_slug,
                    "vcpus": row["vcpu"],
                    "memory_gib": row["ram_gb"],
                    "boot_disk_gib": row["disk_gb"],
                    "cpu_architecture": row.get("architecture", "x86_64"),
                    "source_url": row.get("source_url", PRICING_URL),
                    "source_locator": f"{row.get('family', family_slug)} / {row['plan_slug']}",
                }
            )
        families[family_slug] = normalized
    return families


def build_raw_snapshot_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    cpu_families = build_raw_cpu_sizes(repo_root)
    payload = {
        "schema_version": "c10.digitalocean-raw-sizes.v1",
        "snapshot_id": SNAPSHOT_ID,
        "source_url": DOCS_FEATURES_URL,
        "retrieved_at_utc": RETRIEVED_AT_UTC,
        "source_method": "documentation",
        "source_version_or_etag": None,
        "supplementary_sources": [
            {
                "source_url": PRICING_URL,
                "source_method": "documentation",
                "role": "CPU Droplet pricing tables including memory-optimized m-24vcpu-192gb",
            },
            {
                "source_url": DOCS_SIZES_API_URL,
                "source_method": "documentation",
                "role": "Sizes API reference; live listing unavailable without authentication in this environment",
            },
        ],
        "cpu_families": cpu_families,
        "gpu_on_demand": GPU_DOC_ROWS,
        "selection_algorithm": selection_algorithm_description(),
        "notes": (
            "CPU sizes captured from committed P2 provider datasets sourced from official "
            "DigitalOcean pricing pages, supplemented by the official Droplet features "
            "documentation for on-demand GPU configurations. No live API or doctl listing was "
            "available in the build environment."
        ),
    }
    canonical = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    payload["source_sha256"] = _sha256_bytes(canonical.encode("utf-8"))
    return payload


def _selected_cpu_slugs(cpu_families: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for family_slug in sorted(cpu_families):
        sorted_rows = sorted(cpu_families[family_slug], key=lambda r: (
            r["memory_gib"], r["vcpus"], r["boot_disk_gib"], r["provider_size_slug"]
        ))
        picked = select_evenly_distributed(sorted_rows)
        selected[family_slug] = [row["provider_size_slug"] for row in picked]
    return selected


def _band_for_memory_gb(memory_gib: float) -> str:
    if memory_gib < 4:
        return "fallback-under-4gb"
    if memory_gib < 8:
        return "pilot-4gb"
    if memory_gib < 12:
        return "pilot-8gb"
    if memory_gib < 24:
        return "pilot-12gb"
    return "pilot-24gb-plus"


def _normalize_cpu_record(row: dict[str, Any], *, snapshot_rel: str) -> dict[str, Any]:
    return {
        "provider": "digitalocean",
        "provider_size_slug": row["provider_size_slug"],
        "plan_family": row["plan_family"],
        "service_class": "cpu",
        "pilot_included": True,
        "availability_status": "documented",
        "vcpus": row["vcpus"],
        "memory_gib": row["memory_gib"],
        "boot_disk_gib": row["boot_disk_gib"],
        "scratch_disk_gib": None,
        "gpu_vendor": None,
        "gpu_model": None,
        "gpu_count": None,
        "gpu_memory_gib": None,
        "cpu_architecture": row.get("cpu_architecture", "x86_64"),
        "region_availability": None,
        "source_url": row["source_url"],
        "source_locator": row["source_locator"],
        "source_snapshot_path": snapshot_rel,
        "retrieved_at_utc": RETRIEVED_AT_UTC,
        "runtime_verification_required": False,
        "notes": None,
    }


def _normalize_gpu_record(row: dict[str, Any], *, snapshot_rel: str) -> dict[str, Any]:
    return {
        "provider": "digitalocean",
        "provider_size_slug": row["provider_size_slug"],
        "plan_family": "gpu-on-demand",
        "service_class": "gpu",
        "pilot_included": True,
        "availability_status": "documented",
        "vcpus": row["vcpus"],
        "memory_gib": row["memory_gib"],
        "boot_disk_gib": row["boot_disk_gib"],
        "scratch_disk_gib": row["scratch_disk_gib"],
        "gpu_vendor": row["gpu_vendor"],
        "gpu_model": row["gpu_model"],
        "gpu_count": row["gpu_count"],
        "gpu_memory_gib": row["gpu_memory_gib"],
        "cpu_architecture": None,
        "region_availability": None,
        "source_url": DOCS_FEATURES_URL,
        "source_locator": row["source_locator"],
        "source_snapshot_path": snapshot_rel,
        "retrieved_at_utc": RETRIEVED_AT_UTC,
        "runtime_verification_required": True,
        "notes": (
            "Driver, CUDA/ROCm, region availability, image compatibility, and Ollama support "
            "require runtime verification; GPU memory is separate from Droplet system memory."
        ),
    }


def build_catalog_from_snapshot(snapshot: dict[str, Any], repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    snapshot_rel = str(RAW_SNAPSHOT_JSON.relative_to(repo_root))
    selected_slugs = _selected_cpu_slugs(snapshot["cpu_families"])
    cpu_records: list[dict[str, Any]] = []
    for family_slug in sorted(snapshot["cpu_families"]):
        slug_set = set(selected_slugs[family_slug])
        for row in snapshot["cpu_families"][family_slug]:
            if row["provider_size_slug"] in slug_set:
                cpu_records.append(_normalize_cpu_record(row, snapshot_rel=snapshot_rel))
    cpu_records.sort(key=lambda r: (r["plan_family"], r["memory_gib"], r["vcpus"], r["provider_size_slug"]))

    gpu_records = [
        _normalize_gpu_record(row, snapshot_rel=snapshot_rel) for row in snapshot["gpu_on_demand"]
    ]
    gpu_records.sort(key=lambda r: r["provider_size_slug"])

    plan_to_band = {
        record["provider_size_slug"]: _band_for_memory_gb(record["memory_gib"])
        for record in cpu_records + gpu_records
    }

    return {
        "schema_version": "c10.digitalocean-base-pilot-catalog.v1",
        "snapshot_id": snapshot["snapshot_id"],
        "source_snapshot_path": snapshot_rel,
        "selection_algorithm": snapshot["selection_algorithm"],
        "selected_cpu_slugs_by_family": selected_slugs,
        "plan_counts": {"cpu": len(cpu_records), "gpu": len(gpu_records), "total": len(cpu_records) + len(gpu_records)},
        "plan_to_band": plan_to_band,
        "plans": cpu_records + gpu_records,
    }


def render_selection_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# DigitalOcean base-pilot CPU selection",
        "",
        f"Snapshot: `{catalog['snapshot_id']}`",
        "",
        "## Selection algorithm",
        "",
        catalog["selection_algorithm"],
        "",
        "## Selected CPU slugs by family",
        "",
    ]
    for family_slug, slugs in sorted(catalog["selected_cpu_slugs_by_family"].items()):
        lines.append(f"### `{family_slug}`")
        lines.append("")
        for slug in slugs:
            lines.append(f"- `{slug}`")
        lines.append("")
    lines.extend(
        [
            "## GPU on-demand slugs (all nine documented self-service plans)",
            "",
        ]
    )
    for plan in catalog["plans"]:
        if plan["service_class"] == "gpu":
            lines.append(f"- `{plan['provider_size_slug']}`")
    lines.append("")
    return "\n".join(lines)


def write_catalog_csv(path: Path, plans: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for plan in plans:
            row = {key: plan.get(key) for key in CATALOG_COLUMNS}
            for key, value in row.items():
                if value is None:
                    row[key] = ""
                elif isinstance(value, bool):
                    row[key] = str(value).lower()
            writer.writerow(row)


def ensure_committed_catalog_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build catalog artifacts from committed P2/docs inputs when missing (bootstrap only)."""
    if RAW_SNAPSHOT_JSON.is_file() and CATALOG_JSON.is_file():
        return json.loads(CATALOG_JSON.read_text(encoding="utf-8"))

    snapshot = build_raw_snapshot_payload(repo_root)
    RAW_SNAPSHOT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RAW_SNAPSHOT_JSON.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    catalog = build_catalog_from_snapshot(snapshot, repo_root)
    CATALOG_JSON.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_catalog_csv(CATALOG_CSV, catalog["plans"])
    SELECTION_MD.write_text(render_selection_markdown(catalog), encoding="utf-8")
    return catalog


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_catalog(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    path = repo_root / "AGENTS" / "data-science" / "profile-mapping" / "digitalocean-base-pilot-catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_pilot_menu(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return json.loads((repo_root / "AGENTS" / "data-science" / "profile-mapping" / "8ball-base-pilot-menu.json").read_text(encoding="utf-8"))


def _band_lookup(menu: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {band["pilot_menu_band"]: band for band in menu.get("bands", [])}


def _chain_for_band(menu: dict[str, Any], band_id: str) -> list[str]:
    return list(_band_lookup(menu)[band_id]["ordered_pilot_candidates"])


def _disk_threshold_gb(menu: dict[str, Any], band_id: str, ollama_ref: str) -> float | None:
    band = _band_lookup(menu)[band_id]
    mib = band.get("disk_thresholds_mib", {}).get(ollama_ref)
    if mib is None:
        return None
    return round(mib / 1024, 4)


def load_model_id_by_ollama_ref(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    tags_path = repo_root / "data" / "normalized" / "tags.json"
    tags = json.loads(tags_path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for tag in tags:
        oid = tag.get("ollama_identifier")
        mid = tag.get("model_id")
        if oid and mid:
            mapping[oid] = mid
    return mapping


def load_model_pages(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    profiles = repo_root / "profiles"
    pages: dict[str, dict[str, Any]] = {}
    for path in sorted(profiles.glob("*.json")):
        if path.name in {"c10-index.json", "manifest.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == "c10.model-page.v1":
            pages[path.stem] = payload
    return pages


def _model_requirements(ollama_ref: str, menu: dict[str, Any], band_id: str) -> dict[str, float | None]:
    if ollama_ref not in PILOT_OLLAMA_REFS:
        return {
            "model_minimum_ram_gb": None,
            "model_minimum_disk_free_gb": None,
            "model_minimum_vram_gb": None,
        }
    return {
        "model_minimum_ram_gb": None,
        "model_minimum_disk_free_gb": _disk_threshold_gb(menu, band_id, ollama_ref),
        "model_minimum_vram_gb": None,
    }


def _evaluate_gates(
    *,
    plan: dict[str, Any],
    band_id: str,
    ollama_ref: str,
    chain: list[str],
    requirements: dict[str, float | None],
    gpu_lane: bool,
) -> dict[str, str]:
    ram_gate = "unknown"
    if band_id != FALLBACK_BAND and ollama_ref in chain:
        ram_gate = "band-only"
    disk_gate_visible = "unknown"
    disk_need = requirements["model_minimum_disk_free_gb"]
    if disk_need is not None:
        if plan["boot_disk_gib"] >= disk_need:
            disk_gate_visible = "nominal-pass"
        else:
            disk_gate_visible = "nominal-fail"
    gpu_gate = "unknown" if gpu_lane else "not-applicable"
    return {
        "ram_gate": ram_gate,
        "disk_gate_visible": disk_gate_visible,
        "gpu_vram_gate": gpu_gate,
    }


def _compatibility_status(*, band_id: str, ollama_ref: str, chain: list[str]) -> str:
    if band_id == FALLBACK_BAND:
        return "unknown"
    if ollama_ref not in PILOT_OLLAMA_REFS:
        return "not_proven"
    if ollama_ref not in chain:
        return "not_proven"
    return "unknown"


def build_compatibility_row(
    *,
    model_id: str,
    model_slug: str,
    size: dict[str, Any],
    plan: dict[str, Any],
    menu: dict[str, Any],
    target_lane: str,
) -> dict[str, Any]:
    slug = plan["provider_size_slug"]
    band_id = plan.get("pilot_menu_band") or _band_for_memory_gb(plan["memory_gib"])
    chain = _chain_for_band(menu, band_id)
    ollama_ref = size["ollama_ref"]
    requirements = _model_requirements(ollama_ref, menu, band_id)
    gpu_lane = plan["service_class"] == "gpu"
    gates = _evaluate_gates(
        plan=plan,
        band_id=band_id,
        ollama_ref=ollama_ref,
        chain=chain,
        requirements=requirements,
        gpu_lane=gpu_lane,
    )
    status = _compatibility_status(band_id=band_id, ollama_ref=ollama_ref, chain=chain)
    source_paths = [
        str(CATALOG_JSON.relative_to(REPO_ROOT)),
        str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
        str(RAW_SNAPSHOT_JSON.relative_to(REPO_ROOT)),
    ]
    if ollama_ref in PILOT_OLLAMA_REFS:
        source_paths.append("install/cloud/digitalocean/cpu-droplet/8.2.sh")
    return {
        "model_id": model_id,
        "model_slug": model_slug,
        "size_slug": size["size_slug"],
        "ollama_ref": ollama_ref,
        "target_lane": target_lane,
        "provider_size_slug": slug,
        "plan_family": plan["plan_family"],
        "service_class": plan["service_class"],
        "pilot_menu_band": band_id,
        "pilot_candidate_chain": "|".join(chain),
        "classification": "runtime_menu_band_only",
        "model_fit_proven": False,
        "runtime_trial_required": True,
        "memory_gib": plan["memory_gib"],
        "boot_disk_gib": plan["boot_disk_gib"],
        "scratch_disk_gib": plan.get("scratch_disk_gib"),
        "gpu_vendor": plan.get("gpu_vendor"),
        "gpu_model": plan.get("gpu_model"),
        "gpu_count": plan.get("gpu_count"),
        "gpu_memory_gib": plan.get("gpu_memory_gib"),
        "model_minimum_ram_gb": requirements["model_minimum_ram_gb"],
        "model_minimum_disk_free_gb": requirements["model_minimum_disk_free_gb"],
        "model_minimum_vram_gb": requirements["model_minimum_vram_gb"],
        "ram_gate": gates["ram_gate"],
        "disk_gate_visible": gates["disk_gate_visible"],
        "gpu_vram_gate": gates["gpu_vram_gate"],
        "compatibility_status": status,
        "source_paths": "|".join(source_paths),
    }


def build_compatibility_rows(
    model_pages: dict[str, dict[str, Any]],
    plans: list[dict[str, Any]],
    menu: dict[str, Any],
    model_id_map: dict[str, str],
    *,
    target_lane: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_slug in sorted(model_pages):
        page = model_pages[model_slug]
        for size in page.get("sizes", []):
            ollama_ref = size["ollama_ref"]
            model_id = model_id_map.get(ollama_ref, model_slug)
            for plan in plans:
                plan_with_band = dict(plan)
                plan_with_band["pilot_menu_band"] = menu.get("digitalocean_plan_to_band", {}).get(
                    plan["provider_size_slug"],
                    _band_for_memory_gb(plan["memory_gib"]),
                )
                rows.append(
                    build_compatibility_row(
                        model_id=model_id,
                        model_slug=model_slug,
                        size=size,
                        plan=plan_with_band,
                        menu=menu,
                        target_lane=target_lane,
                    )
                )
    return rows


def write_compat_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPAT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["model_fit_proven"] = str(out["model_fit_proven"]).lower()
            out["runtime_trial_required"] = str(out["runtime_trial_required"]).lower()
            for key in (
                "model_minimum_ram_gb",
                "model_minimum_disk_free_gb",
                "model_minimum_vram_gb",
                "scratch_disk_gib",
                "gpu_vendor",
                "gpu_model",
                "gpu_count",
                "gpu_memory_gib",
            ):
                if out.get(key) is None:
                    out[key] = ""
            writer.writerow(out)


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["compatibility_status"] for row in rows))


def build_report(
    catalog: dict[str, Any],
    cpu_rows: list[dict[str, Any]],
    gpu_rows: list[dict[str, Any]],
    size_count: int,
) -> dict[str, Any]:
    cpu_plans = [p for p in catalog["plans"] if p["service_class"] == "cpu"]
    gpu_plans = [p for p in catalog["plans"] if p["service_class"] == "gpu"]
    runtime_required = sum(1 for p in catalog["plans"] if p.get("runtime_verification_required"))
    return {
        "schema_version": "c10.digitalocean-capability-report.v1",
        "snapshot_id": catalog["snapshot_id"],
        "plan_counts": catalog["plan_counts"],
        "selected_cpu_slugs_by_family": catalog["selected_cpu_slugs_by_family"],
        "size_count_formula": "N = sum(len(model_page['sizes']) for model_page in profiles/*.json c10.model-page.v1)",
        "size_count": size_count,
        "compatibility_row_counts": {
            "cpu": len(cpu_rows),
            "gpu": len(gpu_rows),
            "cpu_formula": f"N × {len(cpu_plans)} = {size_count} × {len(cpu_plans)} = {len(cpu_rows)}",
            "gpu_formula": f"N × {len(gpu_plans)} = {size_count} × {len(gpu_plans)} = {len(gpu_rows)}",
        },
        "compatibility_status_counts": {
            "cpu": _status_counts(cpu_rows),
            "gpu": _status_counts(gpu_rows),
        },
        "runtime_verification_required_plan_count": runtime_required,
        "model_requirements_formula_generated": False,
        "source_paths": [
            str(RAW_SNAPSHOT_JSON.relative_to(REPO_ROOT)),
            str(CATALOG_JSON.relative_to(REPO_ROOT)),
            str(PILOT_MENU_JSON.relative_to(REPO_ROOT)),
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# C10.1-9 DigitalOcean Droplet capability report",
        "",
        "Generated by `scripts/generate-c10-profiles.py` via `scripts/c10_digitalocean_compatibility.py`.",
        "",
        "## Plan inventory",
        "",
        f"- CPU base-pilot plans: **{report['plan_counts']['cpu']}**",
        f"- GPU on-demand plans: **{report['plan_counts']['gpu']}**",
        "",
        "## Compatibility projection row counts",
        "",
        f"- CPU: {report['compatibility_row_counts']['cpu_formula']}",
        f"- GPU: {report['compatibility_row_counts']['gpu_formula']}",
        "",
        "## Evidence posture",
        "",
        f"- Plans requiring runtime verification: **{report['runtime_verification_required_plan_count']}**",
        f"- Model requirements formula-generated in this pass: **{report['model_requirements_formula_generated']}**",
        "",
        "Disk gate visibility compares boot disk only; scratch disk is never added to boot disk.",
        "Compatibility rows use `runtime_menu_band_only` classification and do not claim model fit.",
    ]
    return "\n".join(lines) + "\n"


def update_provider_readme() -> None:
    readme = REPO_ROOT / "profiles" / "provider-compatibility" / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    marker = "## DigitalOcean Droplets (C10.1-9)"
    if marker in text:
        return
    addition = "\n".join(
        [
            "",
            "## DigitalOcean Droplets (C10.1-9)",
            "",
            "- `digitalocean/catalog.json` and `catalog.csv` — 33-plan base-pilot provider snapshot",
            "- `digitalocean/cpu-plan-compatibility.csv` — 24 CPU plans × all C10 sizes",
            "- `digitalocean/gpu-plan-compatibility.csv` — 9 on-demand GPU plans × all C10 sizes",
            "",
            "Source tables:",
            "- `AGENTS/data-science/profile-mapping/digitalocean-raw-sizes-2026-08-12.json`",
            "- `AGENTS/data-science/profile-mapping/digitalocean-base-pilot-catalog.json`",
            "- `AGENTS/data-science/profile-mapping/digitalocean-base-pilot-selection.md`",
            "- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`",
            "",
            "Regenerate with `python3 scripts/generate-c10-profiles.py`.",
            "",
        ]
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")


def generate_digitalocean_compatibility(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    catalog = load_catalog(repo_root)
    menu = load_pilot_menu(repo_root)
    if "digitalocean_plan_to_band" not in menu:
        menu = dict(menu)
        menu["digitalocean_plan_to_band"] = catalog["plan_to_band"]

    model_pages = load_model_pages(repo_root)
    model_id_map = load_model_id_by_ollama_ref(repo_root)
    size_count = sum(len(page["sizes"]) for page in model_pages.values())

    cpu_plans = [p for p in catalog["plans"] if p["service_class"] == "cpu"]
    gpu_plans = [p for p in catalog["plans"] if p["service_class"] == "gpu"]

    cpu_rows = build_compatibility_rows(
        model_pages,
        cpu_plans,
        menu,
        model_id_map,
        target_lane="cloud/digitalocean/cpu-droplet",
    )
    gpu_rows = build_compatibility_rows(
        model_pages,
        gpu_plans,
        menu,
        model_id_map,
        target_lane="cloud/digitalocean/gpu-droplet",
    )

    COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CATALOG_JSON.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_catalog_csv(OUTPUT_CATALOG_CSV, catalog["plans"])
    write_compat_csv(CPU_COMPAT_CSV, cpu_rows)
    write_compat_csv(GPU_COMPAT_CSV, gpu_rows)
    update_provider_readme()

    report = build_report(catalog, cpu_rows, gpu_rows, size_count)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_report_markdown(report), encoding="utf-8")

    return {
        "cpu_plan_count": len(cpu_plans),
        "gpu_plan_count": len(gpu_plans),
        "size_count": size_count,
        "cpu_compat_rows": len(cpu_rows),
        "gpu_compat_rows": len(gpu_rows),
        "cpu_status_counts": report["compatibility_status_counts"]["cpu"],
        "gpu_status_counts": report["compatibility_status_counts"]["gpu"],
    }


def validate_digitalocean_sources(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    if not RAW_SNAPSHOT_JSON.is_file():
        errors.append(f"Missing raw snapshot: {RAW_SNAPSHOT_JSON}")
        return errors
    if not CATALOG_JSON.is_file():
        errors.append(f"Missing catalog: {CATALOG_JSON}")
        return errors

    snapshot = json.loads(RAW_SNAPSHOT_JSON.read_text(encoding="utf-8"))
    for field in ("source_url", "retrieved_at_utc", "source_method", "source_sha256"):
        if snapshot.get(field) in (None, ""):
            errors.append(f"Raw snapshot missing {field}")

    catalog = load_catalog(repo_root)
    plans = catalog.get("plans", [])
    cpu_plans = [p for p in plans if p["service_class"] == "cpu"]
    gpu_plans = [p for p in plans if p["service_class"] == "gpu"]
    if len(cpu_plans) != 24:
        errors.append(f"Expected 24 CPU plans, found {len(cpu_plans)}")
    if len(gpu_plans) != 9:
        errors.append(f"Expected 9 GPU plans, found {len(gpu_plans)}")

    gpu_slugs = {p["provider_size_slug"] for p in gpu_plans}
    if gpu_slugs != REQUIRED_GPU_SLUGS:
        missing = REQUIRED_GPU_SLUGS - gpu_slugs
        extra = gpu_slugs - REQUIRED_GPU_SLUGS
        if missing:
            errors.append(f"Missing required GPU slugs: {sorted(missing)}")
        if extra:
            errors.append(f"Unexpected GPU slugs: {sorted(extra)}")

    for plan in plans:
        for field in CATALOG_COLUMNS:
            if field not in plan:
                errors.append(f"Plan {plan.get('provider_size_slug')} missing field {field}")
        if plan.get("source_snapshot_path") in (None, ""):
            errors.append(f"Plan {plan['provider_size_slug']} missing source_snapshot_path")
        if plan.get("source_url") in (None, ""):
            errors.append(f"Plan {plan['provider_size_slug']} missing source_url")
        if plan["service_class"] == "cpu" and plan["plan_family"] not in ALLOWED_CPU_FAMILIES:
            errors.append(f"CPU plan {plan['provider_size_slug']} has disallowed family {plan['plan_family']}")
        if plan["service_class"] == "gpu":
            slug = plan["provider_size_slug"]
            if "contract" in slug or "spot" in slug:
                errors.append(f"GPU plan must not be contract or spot: {slug}")
            if plan.get("gpu_memory_gib") == plan.get("memory_gib"):
                errors.append(f"GPU plan conflates GPU and system RAM: {slug}")
            if plan.get("scratch_disk_gib") is not None and plan.get("boot_disk_gib") is not None:
                if plan["scratch_disk_gib"] == plan["boot_disk_gib"]:
                    errors.append(f"Scratch disk must not equal boot disk: {slug}")

    if not CPU_COMPAT_CSV.is_file() or not GPU_COMPAT_CSV.is_file():
        errors.append("Missing DigitalOcean compatibility CSV outputs")
    else:
        model_pages = load_model_pages(repo_root)
        size_count = sum(len(page["sizes"]) for page in model_pages.values())
        cpu_rows = load_csv_rows(CPU_COMPAT_CSV)
        gpu_rows = load_csv_rows(GPU_COMPAT_CSV)
        if len(cpu_rows) != size_count * 24:
            errors.append(f"CPU compatibility rows {len(cpu_rows)} != N×24 ({size_count * 24})")
        if len(gpu_rows) != size_count * 9:
            errors.append(f"GPU compatibility rows {len(gpu_rows)} != N×9 ({size_count * 9})")
        for rows, label in ((cpu_rows, "cpu"), (gpu_rows, "gpu")):
            for row in rows:
                if row.get("classification") != "runtime_menu_band_only":
                    errors.append(f"{label} row missing runtime_menu_band_only classification")
                if row.get("model_fit_proven") == "true":
                    errors.append(f"{label} row claims model_fit_proven without evidence")
                if row.get("runtime_trial_required") != "true":
                    errors.append(f"{label} row must set runtime_trial_required=true")

    index_csv = repo_root / "profiles" / "index.csv"
    if index_csv.is_file():
        with index_csv.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        if row_count != 2878:
            errors.append(
                f"profiles/index.csv row count changed unexpectedly: {row_count} (expected 2878)"
            )

    return errors

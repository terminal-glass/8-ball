# C10.1-9 — DigitalOcean Droplet Capability Catalog

Work in the real `terminal-glass/8-ball` repository from current `main`.

Create a new, focused PR. This is the DigitalOcean counterpart to the merged
AWS Lightsail capability work. It adds provider-plan facts and an 8-BALL
base-pilot projection; it does **not** rebuild C10, alter the install scripts,
or manufacture model-sizing facts.

Before editing, inspect the current locations, schema, generator hooks, and
tests created by the merged Lightsail capability PR. Extend that existing
provider-capability mechanism exactly. Do not create a second catalog schema
or an incompatible directory tree.

Save this exact handoff in the repository before doing other work:

```text
AGENTS/history/cursorFileC10.1-9-digitalocean-droplet-capability-catalog.md
```

## Objective

Commit a reproducible, source-backed snapshot of the DigitalOcean Droplet
plans that matter to the 8-BALL base pilot, then generate separate
DigitalOcean CPU and GPU compatibility projections from it.

The target catalog is **33 provider plans**:

- **24 CPU plans:** six representative, source-backed plans from each of the
  four included CPU families: Basic, General Purpose, CPU-Optimized, and
  Memory-Optimized.
- **9 GPU plans:** every currently documented self-service, on-demand GPU
  Droplet configuration listed below.

This is a deliberately bounded provider snapshot, not a promise that these
are the only DigitalOcean plans or that every plan is available in every
region.

## Non-negotiable boundaries

1. Preserve the canonical C10 profile matrix exactly:
  - 10 install lanes
  - model folders and size JSON files
  - JSON stages `3-cpu.json`, `4-ram.json`, `5-hard_disk.json`,
    `6-CPU_only.json`, and `7-video_card.json`
  - `profiles/c10-index.json` and its established generated indexes
  Do not change its row count, model inventory, lane schema, generator
  contract, or selection behavior merely because this catalog adds 33
  DigitalOcean plans.
2. Do **not** create model RAM, VRAM, disk, CUDA, or GPU requirements from a
   formula. Unknown model requirements remain `null`. A provider having more
   RAM, VRAM, or disk is a machine fact; it is not evidence that a particular
   model has been proven to fit.
3. Keep the DigitalOcean expansion outside the one-row-per-model-size-lane C10
   index. Provider-plan compatibility is a projection, not new profile leaves.
   Never create `33 × model × size` directories or add those rows to the core
   matrix.
4. Use current DigitalOcean primary sources only, with provenance captured per
   plan. Do not scrape a reseller, blog, price-comparison page, or search
   snippet. Do not put API tokens, account IDs, region credentials, or live
   account data in the repository.
5. Do not include Spot GPU plans (interruptible and variable-priced) or
   contract-only GPU plans in this base pilot. Do not include Storage-Optimized
   CPU plans in the 24-plan initial pilot. They can be a later explicitly
   sourced extension.

## Source snapshot

Use the official DigitalOcean plan documentation plus the official Sizes API
or `doctl compute size list` **only when already authenticated in the existing**
**environment**. Never request a token from the user and never print one.

Primary sources for this snapshot:

```text
https://docs.digitalocean.com/products/droplets/details/features/
https://docs.digitalocean.com/reference/api/reference/sizes/
```

The committed source snapshot must record:

```text
source_url
retrieved_at_utc
source_method             # documentation, API, or doctl
source_version_or_etag    # null when unavailable
source_sha256
```

For the 24 CPU rows, use a deterministic selection from the captured official
size listing:

1. Filter to currently available CPU plans in these four families only:
   `basic`, `general-purpose`, `cpu-optimized`, `memory-optimized`.
2. Sort each family by `(memory_gib, vcpus, disk_gib, provider_size_slug)`.
3. Select six evenly distributed capacity rungs per family, always including
   the smallest and largest available entry. The selection algorithm and the
   resulting selected slugs must be written into the catalog metadata.
4. If the authenticated official listing is unavailable, do **not** invent
   CPU slugs, memory, vCPU, or disk values to get to 24. Stop the execution and
   report the source-access blocker rather than opening a partial or fabricated
   PR.

The source is dynamic, so this PR must commit both the raw source snapshot and
the normalized, selected 33-plan catalog. Regeneration must use the committed
snapshot by default; it must not make network calls during normal validation.

## Required GPU rows

The current on-demand, self-service GPU catalog has these nine documented
size slugs. Preserve the published GPU memory, system memory, vCPU, boot disk,
scratch-disk, vendor, and GPU model fields with the source citation for each.

```text
gpu-mi300x1-192gb
gpu-mi300x8-1536gb
gpu-h100x1-80gb
gpu-h100x8-640gb
gpu-h200x1-141gb
gpu-h200x8-1128gb
gpu-l40sx1-48gb
gpu-4000adax1-20gb
gpu-6000adax1-48gb
```

Record GPU memory separately from system RAM. Preserve unknown driver,
CUDA/ROCm, region availability, image compatibility, and Ollama support as
`null` or `runtime_verification_required`; do not infer them from the GPU name.

## Required data and output

Use the same source and output directories as the existing Lightsail pass. If
the existing names differ, follow those existing names rather than creating
parallel ones. The result must include the logical equivalents of:

```text
AGENTS/data-science/profile-mapping/
  digitalocean-raw-sizes-<snapshot-id>.json
  digitalocean-base-pilot-catalog.json
  digitalocean-base-pilot-catalog.csv
  digitalocean-base-pilot-selection.md

profiles/<existing-provider-capability-location>/digitalocean/
  catalog.json
  catalog.csv
  cpu-plan-compatibility.csv
  gpu-plan-compatibility.csv
```

Every normalized catalog record needs at least:

```text
provider
provider_size_slug
plan_family
service_class              # cpu or gpu
pilot_included
availability_status
vcpus
memory_gib
boot_disk_gib
scratch_disk_gib
gpu_vendor
gpu_model
gpu_count
gpu_memory_gib
cpu_architecture
region_availability
source_url
source_locator
source_snapshot_path
retrieved_at_utc
runtime_verification_required
notes
```

Use JSON `null` for unknown numeric/text fields, never a made-up `0`, empty
string, or a guessed capability.

## Base-pilot / 8.2 projection

Read the current public `8.2.sh` candidate ladder. It is the source of truth
for the initial pilot categories:

|Detected system RAM|Runtime candidate order             |
|-------------------|------------------------------------|
|under 4 GiB        |`qwen3:0.6b`                        |
|4–under 8 GiB      |`qwen3:1.7b`, then `qwen3:0.6b`     |
|8–under 12 GiB     |`qwen3:4b`, then smaller candidates |
|12–under 24 GiB    |`qwen3:8b`, then smaller candidates |
|24 GiB or more     |`qwen3:14b`, then smaller candidates|

The compatibility projections may state the plan's **runtime candidate band**
and the current 8.2 fallback sequence. They must also state all of the
following:

```text
classification = runtime_menu_band_only
model_fit_proven = false
runtime_trial_required = true
```

The plan's boot-disk fact may be compared to the current 8.2 download-space
threshold for an informational `disk_gate_visible` field. It must not claim a
model fit. Scratch space is not boot space and must never be added to the boot
disk value.

## Compatibility files

Generate one row per **model-size record × selected DigitalOcean plan** in the
two separate compatibility CSVs, retaining source and conservative status.

- CPU output contains `N × 24` rows.
- GPU output contains `N × 9` rows.

`N` is the actual current distinct model-size count; calculate it from the
canonical C10 source. Print the formula and result. The compatibility rows must
use `unknown`/`not_proven` where C10 does not have source-backed requirements.
They must never transform `null` model requirements into a pass/fail decision.

## Validator and tests

Extend the existing C10/provider validators and focused tests. They must fail
when any of these are true:

- the selected catalog is not exactly 33 plans: 24 CPU + 9 GPU;
- a plan lacks per-field provenance or a source snapshot path;
- an included CPU record is outside one of the four allowed CPU families;
- a GPU record is Spot, contract-only, or missing one of the nine required
  on-demand slugs;
- GPU RAM and system RAM were conflated;
- scratch disk was treated as persistent boot disk;
- core C10 matrix dimensions changed;
- a projection claims `model_fit_proven: true` without source-backed model
  requirements;
- a normal regeneration contacts the network or creates an unstable timestamp;
- running generation twice changes tracked output.

Run at minimum:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
bash scripts/validate-catalog.sh
git diff --check

# Run the provider generator and validator again from the committed snapshots.
# The second run must leave the worktree clean.
<existing-provider-generator-command>
<existing-provider-validator-command>
git diff --exit-code
```

Use the repository's actual command names in place of the two placeholders and
report them explicitly. Keep the PR draft until CI is green.

## Final Cursor report

Report:

1. Current branch and base commit.
2. Exact files added/changed.
3. CPU source method and the 24 selected provider size slugs, grouped by
   family.
4. The nine GPU rows and their source snapshot path.
5. `N × 24` and `N × 9` compatibility-row counts.
6. Proof the 10-lane C10 matrix and its indexes did not expand or change
   schema.
7. Unknown/`runtime_verification_required` counts.
8. Every validation command and result.
9. Commit SHA and PR URL.

Do not modify Windows payloads, provider-install scripts, or user-facing model
selection logic in this pass. This pass is provider data plus conservative,
auditable categorization only.

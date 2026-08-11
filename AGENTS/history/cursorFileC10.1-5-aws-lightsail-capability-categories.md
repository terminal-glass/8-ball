# C10.1-5 — AWS Lightsail Capability Categories and Pilot Menu Projection

Work in the real `terminal-glass/8-ball` repository, on a new branch from the
current `main` after the C10.1 RAM contract is present. This is a focused data
and generator task. Do **not** rewrite the profile tree, regenerate unrelated
provider data, change the Windows scripts, or alter the public installer
scripts in this pass.

Before editing, save this exact prompt at:

```text
AGENTS/history/cursorFileC10.1-5-aws-lightsail-capability-categories.md
```

## Objective

Make the AWS Lightsail CPU and GPU branches useful, auditable parameter data.
Create a source-backed Lightsail plan table and a separate 8-BALL **base-pilot**
**Happy Nerds menu** projection. Then teach the existing C10 generator and
validator to expose those provider capacities to every model-size record
without inventing model requirements or claiming a model was successfully run.

The point is to freeze one clean provider-capability pattern that later passes
can reuse for DigitalOcean, Ubuntu, Mac, and Windows. This is parameter
software for selection; it is not a Windows implementation task and it does
not change `trial-install.sh`, `8.1.sh`, `8.2.sh`, or `8.3.sh`.

## Non-negotiable distinctions

Keep these three data layers separate. Do not collapse them into one boolean.

1. **Provider capacity** — published RAM, vCPUs, and included SSD for a named
   Lightsail plan.
2. **8-BALL pilot policy** — the existing `8.2.sh` five-model fallback menu.
   This is internal policy, not a vendor claim or a measured benchmark.
3. **Model requirement / compatibility** — model-specific RAM, VRAM, and disk
   requirements. These must remain `null` or `unknown` unless current,
   provenance-preserving C10 input already supplies them.

`included_ssd_gb` is not the same thing as free disk at install time. The
profiles may say a plan has nominal capacity; the installer must still perform
its existing runtime free-disk check.

Do not create a new model folder, size folder, or a second profile schema.
Do not create any `provider-assumptions` contract unless that exact directory
and schema already exist in current `main`; if it does exist, preserve it and
project this data through its established format only.

## Canonical lanes in scope

Only these two lanes receive provider-plan enrichment in this pass:

```text
cloud/aws-lightsail/cpu
cloud/aws-lightsail/gpu
```

All ten install/profile lanes remain present and unchanged. Do not work on the
Windows payload extension in this PR.

## Source inputs and evidence rules

Use the repository's existing `AGENTS/data-science/profile-mapping/` location
for the committed provider source snapshot and the pilot-policy input. Do not
put working CSVs under the Ollama mapping source tree.

Create these source files (names may differ only if current `main` already has
canonical equivalents):

```text
AGENTS/data-science/profile-mapping/aws-lightsail-linux-bundles.csv
AGENTS/data-science/profile-mapping/aws-lightsail-research-gpu-bundles.csv
AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json
AGENTS/data-science/profile-mapping/aws-lightsail-source-snapshot.json
```

The source snapshot must contain the retrieval date, the official URL, a short
content description, and a per-field provenance statement. Use only these
official sources for the supplied values:

```text
https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html
https://docs.aws.amazon.com/lightsail-for-research/latest/ug/blueprints-plans.html
```

The current base-pilot policy comes from the existing `8.2.sh` functions
`build_candidate_list` and `minimum_disk_mb_for_model`. Preserve the original
script path, function names, and a source locator/line range in the policy
file. Do not present this policy as provider-published data.

Every plan row must contain at least:

```text
provider,product_line,provider_plan_id,display_name,target_lane,
plan_class,addressing,vcpu_count,system_ram_gb,included_ssd_gb,
accelerator_present,gpu_model,gpu_vram_gb,
source_url,source_retrieved_at,evidence_level,notes
```

Use stable, human-readable plan IDs. Do not use display name alone as a key.

## Exact Lightsail capacity snapshot to commit

These are the **11 Linux/Unix general-purpose bundles with public IPv4**. They
are the base pilot catalog—not every possible AWS plan family.

|provider_plan_id                        |RAM GB|vCPUs|included SSD GB|
|----------------------------------------|-----:|----:|--------------:|
|`lightsail-linux-gp-nano-0.5gb-ipv4`    |0.5   |2    |20             |
|`lightsail-linux-gp-micro-1gb-ipv4`     |1     |2    |40             |
|`lightsail-linux-gp-small-2gb-ipv4`     |2     |2    |60             |
|`lightsail-linux-gp-medium-4gb-ipv4`    |4     |2    |80             |
|`lightsail-linux-gp-large-8gb-ipv4`     |8     |2    |160            |
|`lightsail-linux-gp-xlarge-16gb-ipv4`   |16    |4    |320            |
|`lightsail-linux-gp-2xlarge-32gb-ipv4`  |32    |8    |640            |
|`lightsail-linux-gp-4xlarge-64gb-ipv4`  |64    |16   |1280           |
|`lightsail-linux-gp-8xlarge-128gb-ipv4` |128   |32   |1280           |
|`lightsail-linux-gp-12xlarge-192gb-ipv4`|192   |48   |1280           |
|`lightsail-linux-gp-16xlarge-256gb-ipv4`|256   |64   |1280           |

Set all of these to:

```text
target_lane=cloud/aws-lightsail/cpu
product_line=lightsail-linux-general-purpose
plan_class=general-purpose
addressing=public-ipv4
accelerator_present=false
gpu_model=null
gpu_vram_gb=null
evidence_level=provider_published
```

These are the **three Lightsail for Research GPU plans**:

|provider_plan_id            |RAM GB|vCPUs|included SSD GB|
|----------------------------|-----:|----:|--------------:|
|`lightsail-research-gpu-xl` |16    |4    |50             |
|`lightsail-research-gpu-2xl`|32    |8    |50             |
|`lightsail-research-gpu-4xl`|64    |16   |50             |

Set all three to:

```text
target_lane=cloud/aws-lightsail/gpu
product_line=lightsail-for-research
plan_class=gpu
addressing=provider-documentation-not-applicable
accelerator_present=true
gpu_model=null
gpu_vram_gb=null
evidence_level=provider_published
```

The AWS plan table confirms that the GPU plans include an accelerator, but the
referenced source does **not** name the card or its VRAM. Keep both fields
`null`; record `gpu_runtime_verification_required=true` in the row notes or
structured metadata. Do not infer CUDA support, GPU offload, Ollama support,
or a VRAM fit from the word `GPU`.

## Base-pilot Happy Nerds menu (exact policy)

Encode this policy in `8ball-base-pilot-menu.json`, sourced from the existing
8.2 script. It applies only to the pilot selections below; it is not a
mathematical model-sizing formula for all 7,271 C10 size records.

|policy band         |physical RAM condition|ordered pilot candidates                                       |pilot disk threshold                      |
|--------------------|----------------------|---------------------------------------------------------------|------------------------------------------|
|`fallback-under-4gb`|`< 4 GB`              |`qwen3:0.6b`                                                   |3 GiB / 3072 MiB                          |
|`pilot-4gb`         |`>= 4 GB and < 8 GB`  |`qwen3:1.7b`, `qwen3:0.6b`                                     |4 GiB / 4096 MiB for 1.7b; 3 GiB for 0.6b |
|`pilot-8gb`         |`>= 8 GB and < 12 GB` |`qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`                         |6 GiB / 6144 MiB for 4b; then fall back   |
|`pilot-12gb`        |`>= 12 GB and < 24 GB`|`qwen3:8b`, `qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`             |9 GiB / 9216 MiB for 8b; then fall back   |
|`pilot-24gb-plus`   |`>= 24 GB`            |`qwen3:14b`, `qwen3:8b`, `qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`|14 GiB / 14336 MiB for 14b; then fall back|

Map each of the 14 provider plans to exactly one `pilot_menu_band`. Therefore:

```text
0.5 / 1 / 2 GB CPU plans              -> fallback-under-4gb
4 GB CPU plan                          -> pilot-4gb
8 GB CPU plan                          -> pilot-8gb
16 GB CPU plan and GPU XL              -> pilot-12gb
32 / 64 / 128 / 192 / 256 GB CPU plans -> pilot-24gb-plus
GPU 2XL and GPU 4XL                    -> pilot-24gb-plus
```

Every plan record must also keep an ordered `pilot_candidate_chain` and an
explicit `runtime_model_test_required=true`. The chain is a candidate order,
not a guaranteed fit. It must never overwrite model-specific requirements.

## Generator and output requirements

Update the existing canonical C10 generator and validator; do not add a
parallel generator. Keep the current 10-lane tree, current size-file shape,
current C10.1 `4-ram.json` schema, and current `profiles/index.csv` row count
contract intact.

Create generated plan-level compatibility projections outside the model folder
tree. Recommended paths:

```text
profiles/provider-compatibility/aws-lightsail-cpu.csv
profiles/provider-compatibility/aws-lightsail-gpu.csv
profiles/provider-compatibility/README.md
data/generated/aws-lightsail-capability-report.json
docs/C10.1-5-aws-lightsail-capability-report.md
```

Do not add provider plan IDs as new `/profiles/<model>/...` directory levels.
Do not add provider plans as new root lanes. Do not multiply the canonical
`profiles/index.csv` into one row per provider plan.

Each compatibility projection row must contain:

```text
model_id,model_slug,size_slug,ollama_ref,target_lane,provider_plan_id,
pilot_menu_band,pilot_candidate_chain,system_ram_gb,included_ssd_gb,
accelerator_present,gpu_model,gpu_vram_gb,
model_minimum_ram_gb,model_minimum_disk_free_gb,model_minimum_vram_gb,
ram_gate,disk_capacity_gate,gpu_vram_gate,compatibility_status,
runtime_model_test_required,source_paths
```

Allowed values:

```text
ram_gate: pass | fail | unknown
disk_capacity_gate: nominal-pass | fail | unknown
gpu_vram_gate: not-applicable | pass | fail | unknown
compatibility_status: capacity-candidate | no-fit | unknown
```

Rules:

- `capacity-candidate` means only that all **known** required capacity gates
  pass; it does not mean model tested, production-ready, or GPU accelerated.
- If a model requirement is `null`, the matching gate is `unknown` and
  `compatibility_status` is `unknown` unless the model is one of the explicit
  five base-pilot candidates with a documented policy threshold.
- A nominal provider SSD comparison never replaces the installer free-disk
  measurement. Use `nominal-pass`, not `pass`.
- GPU rows always keep `gpu_vram_gate=unknown` while GPU VRAM is `null`.
  Their CPU-side RAM and disk gates may still be evaluated.
- Model-specific VRAM/RAM/disk values must come from existing normalized C10
  data with provenance. Never derive them from parameter count, quantization,
  a KV-cache formula, a fixed safety margin, the plan name, or the pilot menu.

For the five explicit pilot model tags only, project the pilot policy as
`source_kind=validated_internal_planning` and preserve the source path and
function locator. Do not generalize that policy to a different model family or
size based only on "similar" parameter count.

## Validation gates

Add focused tests/validation proving all of the following:

1. Exactly 11 CPU base-pilot plan rows and exactly 3 GPU-research plan rows
   are present with unique `(provider, product_line, provider_plan_id)` keys.
2. Every row has a source URL, retrieval date, evidence level, lane, RAM,
   vCPU, SSD, and policy-band mapping.
3. The plan-to-menu map matches the table above exactly.
4. The 0.5/1/2 GB plans are not called proven fits; they only expose the
   fallback chain and require a real runtime test.
5. GPU plans retain `gpu_model=null`, `gpu_vram_gb=null`, and
   `gpu_vram_gate=unknown` until runtime detection proves otherwise.
6. No model-specific requirement is introduced by a formula or copied from a
   different model family.
7. `profiles/index.csv` keeps its existing one-row-per-model-size-lane count;
   plan expansion appears only in the two companion compatibility CSVs.
8. All generated files are tracked, deterministic, and not hidden by
   `.gitignore`.
9. C10.1 RAM `size_ram_fit` content remains present and conservative.

Run in this order (using the repository's actual current script names when
they differ):

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
bash scripts/validate-catalog.sh
git diff --check

# Determinism proof: regenerate once more without a timestamp-only diff.
python3 scripts/generate-c10-profiles.py
git diff --exit-code
```

Do not run a broad web scrape. The committed source snapshot and the two named
official AWS pages are the complete scope for this pass.

## Required final report

Report:

1. The 14 plan records and their two target lanes.
2. Exact base-pilot policy and plan-to-band counts.
3. Generated CPU and GPU compatibility row counts.
4. Count of `capacity-candidate`, `no-fit`, and `unknown` rows per lane.
5. Confirmation that GPU model and VRAM are still unknown, not guessed.
6. Confirmation that model requirements were not formula-generated.
7. Changed files, test output, determinism result, and commit SHA.

Keep the PR draft until all checks are green. Do not claim the data proves a
model runs; that proof remains the installed machine's real pull-and-inference
test.

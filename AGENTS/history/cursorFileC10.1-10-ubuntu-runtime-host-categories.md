# C10.1-10 — Ubuntu Runtime Host Capability Categories

Work in the real `terminal-glass/8-ball` repository from current `main`.

Create a focused draft PR. This is the Ubuntu counterpart to the AWS Lightsail
and DigitalOcean capability work. It covers **both Ubuntu virtual machines and**
**Ubuntu standalone/bare-metal hosts in one contract**. Do not split them into
separate installer trees or pretend that Ubuntu has a fixed plan catalog.

Before editing, inspect the current provider-capability mechanism, generated
paths, schemas, generator hooks, and tests established by the Lightsail work.
Extend that mechanism. Do not create a competing data hierarchy, another C10
generator, or an incompatible selector contract.

Save this exact handoff before doing other work:

```text
AGENTS/history/cursorFileC10.1-10-ubuntu-runtime-host-categories.md
```

## Objective

Create a committed, deterministic **Ubuntu host capability taxonomy** and a
runtime observation contract for the existing Ubuntu lanes:

```text
ubuntu/cpu
ubuntu/cuda
```

The taxonomy distinguishes host topology without requiring the user to choose
it manually:

```text
bare-metal
virtual-machine
unknown
```

At install time, the real host supplies its own facts: usable system RAM,
visible CPU threads/architecture, free space on the Ollama data filesystem,
and GPU state. A VM is not assumed small, CPU-only, or unable to have GPU
passthrough. A bare-metal Ubuntu host is not assumed to have a GPU.

This pass creates reusable categorical data and runtime-evidence rules. It
does **not** change public installer payloads, model selection logic, C10
model-size data, or the core 10-lane matrix.

## Non-negotiable boundaries

1. Preserve the canonical C10 contract exactly: 10 install lanes, the current
   model and size records, JSON stages `3-cpu.json`, `4-ram.json`,
   `5-hard_disk.json`, `6-CPU_only.json`, `7-video_card.json`, and all C10
   generated indexes. Do not add model-size rows, profile leaves, or change
   C10 row arithmetic.
2. Do not calculate or invent model RAM, VRAM, CPU, disk, CUDA, or performance
   requirements. A runtime host fact is not proof that any model fits. Unknown
   model requirements stay `null`; compatibility is `unknown`/`not_proven`
   unless both sides are independently source-backed.
3. Do not maintain a static list of "Ubuntu VM plans" or "Ubuntu standalone
   machines." Final RAM, CPU, disk, and GPU values are observed on the actual
   host. Committed files define categories, evidence fields, and fallbacks.
4. Do not infer a cloud provider from virtualization output, hostname, MAC,
   DMI strings, or IP ranges. `kvm`, `vmware`, `oracle`, `microsoft`, `qemu`,
   and similar output identifies virtualization at most; provider is `null`
   unless a separately selected provider lane supplies sourced provider data.
5. A detected display adapter is not CUDA-ready. Ubuntu CUDA requires a
   successful `nvidia-smi` query at runtime. Otherwise retain a non-ready or
   unknown GPU state and use CPU-safe fallback. Do not declare AMD/Intel GPU,
   ROCm, VRAM, or Ollama acceleration from `lspci` alone.
6. Do not change Windows, Mac, AWS, DigitalOcean, cloud-provider scripts, or
   user-facing `8.2.sh` behavior in this PR.

## Required committed taxonomy

Use the source and output roots already selected by the Lightsail capability
work. Preserve its exact layout. The result includes logical equivalents of:

```text
AGENTS/data-science/profile-mapping/
  ubuntu-runtime-observation-contract.md
  ubuntu-runtime-capability-taxonomy.json
  ubuntu-runtime-capability-taxonomy.csv

profiles/<existing-provider-capability-location>/ubuntu/
  runtime-observation-contract.json
  host-capability-categories.json
  host-capability-categories.csv
```

The taxonomy has **10 stable records**:

```text
3 topology categories × 2 Ubuntu lanes + 4 GPU runtime-state categories
```

Required topology × lane rows:

|Host topology    |Target lane  |
|-----------------|-------------|
|`bare-metal`     |`ubuntu/cpu` |
|`bare-metal`     |`ubuntu/cuda`|
|`virtual-machine`|`ubuntu/cpu` |
|`virtual-machine`|`ubuntu/cuda`|
|`unknown`        |`ubuntu/cpu` |
|`unknown`        |`ubuntu/cuda`|

Required GPU states:

```text
nvidia-cuda-ready
gpu-present-not-cuda-ready
no-supported-gpu-detected
gpu-state-unknown
```

Every record has a stable ID and at least these fields:

```text
target_lane
host_topology
runtime_detection_required
runtime_evidence_commands
cpu_architecture
visible_cpu_threads
system_ram_gib
ollama_filesystem_path
free_disk_gib
gpu_runtime_state
gpu_vendor
gpu_model
gpu_memory_gib
cuda_runtime_ready
virtualization_kind
provider
classification
model_fit_proven
runtime_trial_required
unknown_fields
notes
```

Use JSON `null` for values not established by a category. Do not use `0`, an
empty string, or a made-up default for unknown RAM, disk, GPU, VRAM, CUDA,
provider, or virtualization information.

Every taxonomy record must preserve these values:

```text
classification = runtime-observed-host-category
model_fit_proven = false
runtime_trial_required = true
```

## Runtime observation contract

Document a minimal Linux-runtime evidence contract. The command sequence must
be safe on normal Ubuntu, prefer machine-readable output where practical, and
degrade to `unknown` if a tool is unavailable or ambiguous. Use existing helpers
where they exist; otherwise define the contract but do not wire it into public
installer scripts in this PR.

|Fact             |Preferred evidence                                                                 |Rule                                                                |
|-----------------|-----------------------------------------------------------------------------------|--------------------------------------------------------------------|
|Host topology    |`systemd-detect-virt`                                                              |Preserve status/output; unrecognized output is `unknown`.           |
|VM detail        |`systemd-detect-virt --vm` and/or `lscpu -J`                                       |Optional detail only; never infer provider.                         |
|OS / architecture|`/etc/os-release`, `uname -m`                                                      |Record observed values, not an imagined release target.             |
|CPU threads      |`nproc`, `lscpu -J`                                                                |Record visible/assigned threads; do not derive performance class.   |
|System RAM       |`/proc/meminfo`                                                                    |Record observed physical memory; never a model requirement.         |
|Model filesystem |configured Ollama/8-BALL data path then `df -P`                                    |Use free space on that filesystem only; never sum mounts.           |
|GPU presence     |`nvidia-smi` first, then `lspci -nn` when available                                |Adapter discovery is not CUDA readiness.                            |
|CUDA state       |successful `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits`|Only success yields `nvidia-cuda-ready`; retain per-device evidence.|

No command output, serial number, MAC address, hostname, IP address, user
name, or credential may be committed. Tests use only sanitized fixtures.

## Happy Nerds runtime-menu bands

Read the current public `8.2.sh` candidate ladder rather than copying an old
version. The supplied baseline has five ordered system-RAM bands:

|Detected RAM   |Runtime candidates                  |
|---------------|------------------------------------|
|under 4 GiB    |`qwen3:0.6b`                        |
|4–under 8 GiB  |`qwen3:1.7b`, then `qwen3:0.6b`     |
|8–under 12 GiB |`qwen3:4b`, then smaller candidates |
|12–under 24 GiB|`qwen3:8b`, then smaller candidates |
|24 GiB or more |`qwen3:14b`, then smaller candidates|

Generate exactly five shared runtime-menu-band records, sourced from the
actual current script. Each must include:

```text
ram_band_id
lower_bound_gib
upper_bound_gib_or_null
runtime_trial_candidates
source_script_path
source_script_version
classification = runtime_menu_band_only
model_fit_proven = false
runtime_trial_required = true
```

The existing `minimum_disk_mb_for_model` values may be documented only as the
current runtime download guard. Do not export them as universal catalog model
disk requirements.

## Output rules

Generate only:

1. 10 taxonomy rows: six topology × lane rows plus four GPU-state rows;
2. five runtime-menu-band rows; and
3. a small lane-to-runtime-contract projection for `ubuntu/cpu` and
   `ubuntu/cuda`.

Do **not** generate a `model-size × Ubuntu topology × RAM band` cross-product.
There is no provider plan to justify it. The core C10 index remains exactly one
row per model-size-lane combination.

## Validator and focused tests

Extend existing C10/provider validators and focused tests. They must fail if:

- the taxonomy is not exactly 10 rows with the six topology/lane combinations
  and four GPU states;
- there are not exactly five bands matching the current `8.2` ladder;
- unknown machine capacity is filled with `0`, `""`, or a formula;
- a provider is inferred from VM/hypervisor output;
- `lspci` alone marks CUDA ready or supplies VRAM;
- GPU data is aggregated without retaining per-device evidence;
- a provider capability or the core C10 index changes dimensions/schema;
- any taxonomy/projection claims `model_fit_proven: true`; or
- normal generation makes a network call, adds an unstable timestamp, or is
  dirty after a second generation.

Run at minimum:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
bash scripts/validate-catalog.sh
git diff --check

# Use actual current provider/taxonomy commands.
# Run generation twice from committed inputs; the second run must be clean.
<existing-provider-generator-command>
<existing-provider-validator-command>
git diff --exit-code
```

Report actual command names. Keep the PR draft until CI is green.

## Final Cursor report

Report the branch and base commit; all files changed; the six topology/lane
IDs, four GPU-state IDs, and five RAM-band IDs; proof that VM detection never
infers provider; all fields preserved as runtime-unknown; current C10
model-size × 10-lane arithmetic proving it did not expand; validation results;
deterministic-generation proof; commit SHA; and PR URL.

Do not modify public installer scripts in this pass. A later reviewed task can
wire the tested observation contract into Ubuntu `8.1`/`8.2` helpers.

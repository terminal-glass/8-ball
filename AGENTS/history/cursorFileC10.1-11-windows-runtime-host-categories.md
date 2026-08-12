# C10.1-11 — Windows Runtime Host Categories

Work in the real `terminal-glass/8-ball` repository from the current `main`.

This is the Windows counterpart to the Ubuntu runtime-host capability pass. It
is parameter and evidence work for the existing `windows/cpu` and
`windows/cuda` lanes. It is **not** the Windows installer implementation pass.

Save this complete handoff first as:

```text
AGENTS/history/cursorFileC10.1-11-windows-runtime-host-categories.md
```

## Objective

Create one source-backed, deterministic Windows runtime capability projection
that lets the future Windows 8-BALL installer classify the machine it actually
finds. It must work for both a physical Windows computer and a Windows VM.

Do not turn Windows editions, laptop marketing labels, or display-adapter names
into fictional capacity claims. The installer will measure the host at runtime.

Preserve all current C10 and C10.1 contracts:

- the ten canonical install lanes;
- the model-first `profiles/<model-slug>/...` tree;
- generated model/size data and its provenance;
- `4-ram.json` conservative-null semantics;
- provider capability projections kept separate from the core model-size-lane
  index;
- the current `8.2` Happy Nerds runtime trial/fallback behavior.

Do not regenerate an incompatible profiles schema. Do not replace JSON stage
files with `.ps1` or `.sh` files. Do not implement or rewrite the Windows
`trial-install.ps1`, `8.1.ps1`, `8.2.ps1`, or `8.3.ps1` scripts in this task.

## Existing lane contract

The two Windows lanes already exist and remain exactly:

```text
install/windows/cpu/
install/windows/cuda/
profiles/<model-slug>/windows/cpu/
profiles/<model-slug>/windows/cuda/
```

Windows is one of the ten canonical lanes, not a cloud provider. Do not add
`install/windows/vm`, `install/windows/physical`, or model-specific Windows
lanes. Physical-versus-VM is a measured runtime property, recorded as data.

WSL is not native Windows for this projection. If detected, report
`os_family=wsl` and let the Ubuntu/Linux runtime flow own it; do not silently
file it under either native Windows lane.

## First: continue the established provider-capability schema

Before editing, inspect the merged AWS Lightsail and any merged DigitalOcean or
Ubuntu capability work. Reuse their directory conventions, JSON/CSV column
names, report format, provenance fields, generator entry point, and validator
style.

If the DigitalOcean or Ubuntu PR is still unmerged, do **not** depend on it.
Build from current `main` and make this Windows addition independently
mergeable. Do not copy an unmerged schema merely because it exists on another
branch.

Place Windows source notes, runtime category definitions, generated projection,
and validation evidence alongside the existing provider/runtime capability
artifacts. If no stable generated destination yet exists, use the narrow,
documented location below rather than scattering Windows facts through every
model profile:

```text
AGENTS/data-science/profile-mapping/windows/
data/generated/capability-catalog/windows/
```

The core `profiles/c10-index.json` or equivalent model-size-lane index must
remain one row per model-size-lane. Do not multiply it by Windows hardware
classes.

## Windows observation contract

Create a machine-readable source/contract document and generated example or
schema for a future PowerShell collector. It must emit the existing normalized
environment artifact names where they are defined, particularly:

```text
EIGHTBALL_OS_FAMILY="windows"
EIGHTBALL_PROVIDER="windows" | "bare_metal" | "unknown"
EIGHTBALL_INSTANCE_CLASS="..." | "unknown"
EIGHTBALL_RAM_MB="<measured integer>"
EIGHTBALL_CPU_THREADS="<measured integer>"
EIGHTBALL_DISK_FREE_GB="<measured integer>"
EIGHTBALL_GPU_PRESENT="yes" | "no" | "unknown"
EIGHTBALL_GPU_NAME="..." | "unknown"
EIGHTBALL_GPU_VRAM_MB="<measured integer>" | "unknown"
```

Add Windows-specific fields only where the current capability schema permits
them, such as:

```text
windows_host_kind = physical | hyperv_vm | vmware_vm | virtualbox_vm | other_vm | unknown
windows_architecture = x64 | arm64 | x86 | unknown
windows_gpu_runtime = nvidia_smi_verified | gpu_present_unverified | no_gpu_detected | unknown
windows_cuda_lane_eligible = yes | no | unknown
windows_gpu_vram_source = nvidia_smi | unknown
```

Keep values deterministic. Use `unknown`, `null`, or the existing schema's
equivalent when a fact cannot be established.

The planned PowerShell collector may use these evidence sources:

|Fact                         |Preferred Windows evidence                                                                                      |Rule                                                                                             |
|-----------------------------|----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
|OS and architecture          |`Get-CimInstance Win32_OperatingSystem`; `[Environment]::Is64BitOperatingSystem`; architecture environment value|Record Windows only after confirming it is native Windows; do not classify WSL as native Windows.|
|Host topology                |`Win32_ComputerSystem.Model`, `Win32_ComputerSystem.Manufacturer`, and `Win32_ComputerSystem.HypervisorPresent` |Map only clearly evidenced values; otherwise `unknown`.                                          |
|Installed RAM                |`Win32_ComputerSystem.TotalPhysicalMemory`                                                                      |Record physical/assigned RAM in MiB. Do not use currently free RAM as installed RAM.             |
|CPU threads                  |`Win32_Processor.NumberOfLogicalProcessors`                                                                     |Sum valid values; record a measured integer.                                                     |
|Install-destination free disk|`Get-PSDrive` / volume backing the actual intended install path                                                 |Measure that destination, not an arbitrary drive.                                                |
|GPU presence                 |`Win32_VideoController`                                                                                         |Presence alone is not CUDA evidence.                                                             |
|NVIDIA identity and VRAM     |successful `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits`                             |This is the only source in this pass that may set measured NVIDIA VRAM and CUDA eligibility.     |

Never use `Win32_VideoController.AdapterRAM` as verified usable VRAM. It may be
truncated, shared, virtual, or driver-dependent. It can support
`gpu_present_unverified` only.

Native Windows on ARM64 must remain `architecture=arm64` and compatibility
`unknown` unless the real Windows installer and runtime prerequisites prove it
works. Do not imply x64/ARM64 parity.

## The two categorical decisions

The projection must make exactly two routing classifications, based on actual
evidence:

|Classification|Criteria                                                                                                   |Consequence                                                  |
|--------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
|`windows/cpu` |Native Windows is observed; no successful NVIDIA runtime verification                                      |CPU lane. GPU is absent, unverified, unsupported, or unknown.|
|`windows/cuda`|Native Windows plus successful `nvidia-smi` query with a non-empty NVIDIA GPU name and positive VRAM result|CUDA lane candidate only. It is not a model-fit guarantee.   |

If the host is Windows but `nvidia-smi` is absent/fails, select `windows/cpu`
as the safe current lane and record CUDA capability as `unknown` or `no` based
on the evidence. Do not fail a CPU install merely because a display adapter is
present.

If GPU detection finds multiple NVIDIA GPUs, preserve one record per GPU or the
existing schema's equivalent and calculate an explicit aggregate only when the
schema already supports it. Do not assume VRAM can be pooled. The future
selector must be able to see the largest verified single-GPU VRAM value.

## Base-pilot Happy Nerds categories

Use the actual current `8.2.sh` menu as the **only** initial Windows local-model
candidate policy. It is a conservative trial ladder, not a generalized model
requirement table and not a claim that a candidate will run.

Record it as a versioned runtime policy projection with this exact mapping:

|Measured installed RAM|Candidate order                                                |
|----------------------|---------------------------------------------------------------|
|24 GiB or more        |`qwen3:14b`, `qwen3:8b`, `qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`|
|12–<24 GiB            |`qwen3:8b`, `qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`             |
|8–<12 GiB             |`qwen3:4b`, `qwen3:1.7b`, `qwen3:0.6b`                         |
|4–<8 GiB              |`qwen3:1.7b`, `qwen3:0.6b`                                     |
|under 4 GiB           |`qwen3:0.6b`                                                   |

Record the paired base-pilot free-disk gate from the same `8.2.sh` source:

|Candidate   |Required free disk before trial|
|------------|-------------------------------|
|`qwen3:14b` |14 GiB                         |
|`qwen3:8b`  |9 GiB                          |
|`qwen3:4b`  |6 GiB                          |
|`qwen3:1.7b`|4 GiB                          |
|`qwen3:0.6b`|3 GiB                          |

The rounding used in the display text may differ slightly from the underlying
MiB source values; preserve the source values and source file/line provenance
in the data.

For GPU/VRAM, create categories for reporting and future selection only:

```text
no_gpu_or_unknown
gpu_present_unverified
nvidia_smi_verified_vram_under_8_gib
nvidia_smi_verified_vram_8_to_under_16_gib
nvidia_smi_verified_vram_16_to_under_24_gib
nvidia_smi_verified_vram_24_gib_or_more
```

These are **not** model-fit bands. This pass must not set or infer
`minimum_vram_gb`, `recommended_vram_gb`, a GPU model fit, or a CUDA model
compatibility result for any model-size record.

## Required outputs

Create only the smallest necessary, deterministic artifacts:

1. A Windows runtime-host category/source document in the established
   `AGENTS/data-science/profile-mapping/` capability area.
2. A checked-in Windows capability projection (JSON and/or CSV consistent with
   the existing provider work) containing:
  - source metadata and schema version;
  - the two canonical Windows lanes;
  - topology, architecture, RAM, disk, and GPU evidence rules;
  - the five RAM candidate categories;
  - the five per-candidate disk gates;
  - GPU evidence/reporting categories with no fit claims;
  - an explicit `runtime_verification_required: true` or established
    equivalent.
3. Focused generator/validator/test updates only if required to ensure the
   artifacts are deterministic, tracked, and not ignored.
4. A short generated report stating counts and known intentionally-unknown
   fields.

Do not emit one file per model or one row per model-size for this Windows host
category pass. Do not change `4-ram.json` model requirements. Do not add a
generic provider-assumptions layer unless that exact schema is already merged
on current `main` and is the established capability destination.

## Validation and acceptance

Run the repository's appropriate existing commands, then at minimum:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
git diff --check
```

Also add or run focused checks that prove:

- exactly the existing `windows/cpu` and `windows/cuda` lanes are referenced;
- no Windows VM/physical sublanes were added;
- the five RAM categories and five disk gates match current `8.2.sh` source
  facts;
- `nvidia-smi` is required for `windows/cuda` eligibility and measured VRAM;
- `AdapterRAM` cannot become verified VRAM;
- WSL is not categorized as native Windows;
- no model-size record gains a fabricated RAM, VRAM, disk, or compatibility
  requirement;
- a second generation run produces no diff;
- all generated files are tracked and not ignored.

If PowerShell is available, syntax-check any PowerShell fixture or collector
that this task adds:

```powershell
pwsh -NoProfile -Command "Get-ChildItem -Recurse install,profiles -Filter *.ps1 | ForEach-Object { [scriptblock]::Create((Get-Content -Raw $_.FullName)) | Out-Null }"
```

If PowerShell is unavailable in the CI runner, do not invent a passing result.
Report that it was unavailable and keep the task scoped to data/contract work.

## Commit and report

Create a dedicated branch and PR from current `main`. Keep this independently
mergeable from any in-flight Ubuntu, DigitalOcean, or Glass Ball PR.

Suggested commit message:

```text
feat(c10.1): add Windows runtime capability categories
```

Report:

- source files and exact `8.2.sh` policy locations used;
- artifacts created or changed;
- lane count (must remain 10 overall; Windows contributes 2);
- RAM, disk, and GPU category counts;
- all intentionally unknown facts/compatibilities;
- command results and deterministic-regeneration result;
- branch name, PR URL, and commit SHA.

Do not say Windows installation or CUDA model support is complete. This is the
conservative parameter layer needed before the real Windows installer pass.

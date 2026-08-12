# C10.1-13 — CUDA Runtime and Software Mapping

Work in the current `terminal-glass/8-ball` repository after the queued macOS
capability pass has completed. Start from the branch's current committed state;
do not discard queued work or reset/rewrite earlier commits.

Save this complete handoff first, unchanged, as:

```text
AGENTS/history/cursorFileC10.1-13-cuda-runtime-software-mapping.md
```

## Objective

Create one conservative CUDA runtime-and-software observation contract for the
four existing CUDA-capable install lanes:

```text
ubuntu/cuda
windows/cuda
cloud/digitalocean/gpu-droplet
cloud/aws-lightsail/gpu
```

This is software and hardware mapping, not the CUDA installer implementation.
It must make a future installer able to see what NVIDIA devices, driver, CUDA
interfaces, and Ollama-ready conditions actually exist on the current machine.
It must not manufacture model VRAM requirements, pretend that a cloud GPU plan
has a particular card, or mark model sizes as a confirmed fit.

Preserve the current C10/C10.1 model-first structure, generated 10-lane matrix,
provider-plan projections, runtime host categories, and 8.2 Happy Nerds trial
behavior. Do not create C11, a second profile index, model-size directories, or
a replacement installer architecture.

## Source-backed support policy

Record a versioned, auditable software-policy source under:

```text
AGENTS/data-science/profile-mapping/
```

The policy must identify its source URL and retrieval date. At the time of this
handoff, Ollama's official hardware-support documentation states:

```text
NVIDIA compute capability >= 5.0
driver >= 550
for compute capability 5.0 through 6.2: driver >= 570
```

Do not hide those values in code. Store them as policy data with provenance so
the next catalog refresh can update them intentionally. A device that cannot
report the required field remains `unknown`; do not guess from a product name.

This policy determines only `ollama_nvidia_support`:

```text
supported | unsupported | unknown
```

It does **not** determine whether any particular model fits in VRAM.

## Runtime observation contract

Add or extend one cross-platform CUDA observer. It may use a small shell helper
for Linux and a PowerShell helper for Windows, but both must emit the same
normalized schema. The observer must never require `sudo` just to inspect
hardware and must safely return unknown data when NVIDIA software is absent.

Use `nvidia-smi` as the primary evidence source. When the command exits
successfully, collect every visible GPU, not only GPU zero:

```text
uuid
name
driver_version
memory.total
compute_capability (when the installed nvidia-smi exposes it)
```

Prefer a CSV/no-header query with one row per GPU. Preserve the raw command
version and a sanitized observation timestamp/source note; do not store output
that could include secrets, environment variables, paths under a user home, or
customer identifiers.

Record these normalized fields for each device where observed:

```text
gpu_index
gpu_uuid
gpu_name
gpu_vendor=nvidia
gpu_memory_mb
compute_capability
driver_version
driver_reported_cuda_api_max_version
cuda_toolkit_version
cuda_visible
ollama_nvidia_support
observation_status
source_command
```

Rules:

1. `driver_reported_cuda_api_max_version` is **not** the installed CUDA toolkit.
   Parse a CUDA version shown by `nvidia-smi` only into that driver/API field.
   Set `cuda_toolkit_version` only when `nvcc --version` or an equally direct,
   platform-appropriate toolkit observation proves it. Otherwise use `null`.
2. Do not substitute `lspci`, Device Manager display names, provider-plan labels,
   WMI adapter memory, or a model-name lookup for a successful `nvidia-smi` CUDA
   observation.
3. If `nvidia-smi` is missing, fails, or sees no device, record
   `observation_status=unavailable` and all device capability values as unknown.
   Do not label the machine CUDA-ready.
4. A successful `nvidia-smi` with an unknown compute capability can prove an
   NVIDIA device and driver, but `ollama_nvidia_support` remains `unknown`.
5. In a multi-GPU host, preserve all device records. Do not silently select the
   first device. If `CUDA_VISIBLE_DEVICES` is already set, record its sanitized
   value and resolve a UUID only when the mapping is unambiguous. Numeric device
   ordering is not a persistent identity.
6. Never write host-observed VRAM into a catalog model's `minimum_vram_gb`,
   `recommended_vram_gb`, `fit_status`, or `7-video_card.json` requirements.
   Host capacity belongs in runtime/provider capability data.

## Lane selection rules

The CUDA observer provides capacity evidence; it must not fabricate provider
identity. Select the lane only when OS and provider context independently prove
it:

|Observed context                                                  |Allowed lane                    |
|------------------------------------------------------------------|--------------------------------|
|Linux, non-provider/bare-metal context, CUDA observation available|`ubuntu/cuda`                   |
|Windows, CUDA observation available                               |`windows/cuda`                  |
|DigitalOcean provider context plus CUDA observation available     |`cloud/digitalocean/gpu-droplet`|
|AWS Lightsail provider context plus CUDA observation available    |`cloud/aws-lightsail/gpu`       |
|Unknown OS/provider or CUDA unavailable                           |no confident CUDA lane          |

Do not put macOS in a CUDA lane. Apple Silicon acceleration is Metal/unified
memory and stays under `mac/apple-silicon`; it is deliberately out of scope.
Do not introduce AMD ROCm or Vulkan routes in this pass. Capture neither as a
CUDA success nor as an error; those are future, separate accelerator mappings.

## Required data and code changes

1. Add a documented, versioned CUDA software-support policy in
   `AGENTS/data-science/profile-mapping/`, with source URL, retrieval date,
   policy fields, and explicit unknown behavior.
2. Add the smallest shared runtime-observation schema and helpers necessary for
   Linux and Windows to produce the same per-device records. Use normal JSON or
   shell-safe environment artifacts already established by C1; do not create a
   competing profile hierarchy.
3. Update focused generator/validator support only as needed to assert the four
   canonical CUDA lanes, schema validity, and no corruption of the C10 profile
   matrix.
4. Preserve provider-plan facts already created for Lightsail and DigitalOcean.
   A provider plan may remain GPU/VRAM-unknown until this runtime observer sees
   a real instance.
5. Add focused tests for:
  - supported/unsupported/unknown policy results at the exact boundary values;
  - `nvidia-smi` failure or absence producing no CUDA-ready classification;
  - multiple GPUs retaining separate UUID-backed records;
  - driver-reported CUDA API version not being called a toolkit installation;
  - `CUDA_VISIBLE_DEVICES` not being converted into an unstable permanent
    numeric GPU identity;
  - no runtime VRAM observation changing a catalog model-size fit;
  - each of the four CUDA lanes and neither Mac lane being selected only with
    the required OS/provider context.
6. Do not edit the public `install/**` payload scripts, configure a driver,
   install CUDA, set environment variables, perform a live GPU test, or add
   connectors/Jets in this pass.

## Required verification

Run the current repository checks and focused tests:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
bash scripts/validate-catalog.sh
git diff --check
```

Run the generator twice. The second run must produce no generated diff:

```bash
python3 scripts/generate-c10-profiles.py
git diff --exit-code
```

Confirm in the report:

```text
10 canonical lanes remain unchanged
4 canonical CUDA lanes are present
all observed GPU values have a source/provenance field
no model requirement or fit status was created from GPU observation
no Mac lane is classified CUDA
```

## Commit and report

Use one focused commit, for example:

```text
feat(c10.1): map CUDA runtime capabilities
```

Report the branch name, changed files, test outputs, policy source/version,
matrix counts before and after, unknown/unsupported handling, and commit SHA.
Keep the PR draft until all checks are green.

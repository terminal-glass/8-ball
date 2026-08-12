# C10.1-12 — macOS Runtime Host Categories

Work in the current `terminal-glass/8-ball` repository from current `origin/main`.

Save this complete handoff first, unchanged, as:

```text
AGENTS/history/cursorFileC10.1-12-macos-runtime-host-categories.md
```

## Objective

Add the macOS runtime-host capability layer for the two existing canonical lanes:

```text
mac/apple-silicon
mac/intel
```

This is the macOS counterpart to the Ubuntu and Windows runtime-host passes.
It records what the installer can actually observe on a Mac and maps that
observation to the existing `8.2` Happy Nerds trial ladder. It does **not**
implement macOS installer scripts, create CUDA support, or declare that an
arbitrary catalog model fits.

Preserve the current C10/C10.1 model-first profile tree, generator, validator,
the ten canonical lanes, and current provider-capability work. Do not rebuild
or expand the core model × size × lane matrix.

## Non-negotiable classification rules

1. `mac/apple-silicon` means a host observed as `arm64` by macOS. It is not a
   CUDA lane. Apple Silicon uses unified memory; do not copy system RAM into a
   `VRAM` field or claim a dedicated VRAM amount.
2. `mac/intel` means a host observed as `x86_64`. It is also not a CUDA lane.
   An Intel Mac may expose an Intel, AMD, or historical NVIDIA display adapter,
   but this pass must not claim CUDA readiness from its name or memory field.
3. A display adapter record is hardware evidence only. `metal` capability,
   GPU model, GPU memory, and virtualization status are `unknown`/`null` unless
   the runtime command actually returns that field.
4. Total physical memory and free install-volume space are observed facts.
   They are not model requirements and must never change a profile size record
   from unknown into `fit`.
5. The `8.2` ladder is a runtime trial order, not a universal compatibility
   guarantee. A candidate is only successful after download and an actual local
   inference test. Preserve the existing conservative fallback behavior.
6. Do not scrape Apple product pages or maintain a static Mac SKU catalog. Mac
   capacity varies by the actual physical machine and by VM assignment.

## Runtime observation contract

Implement or extend one small, shell-safe macOS observation helper used by the
Mac lane metadata/profile projection. Keep it data/metadata focused; do not
turn this PR into the Mac installer implementation.

On macOS, collect these facts where the command succeeds:

|Fact               |Preferred observation                 |Required handling                                                                              |
|-------------------|--------------------------------------|-----------------------------------------------------------------------------------------------|
|OS version         |`sw_vers -productVersion`             |store raw version or `null`                                                                    |
|kernel architecture|`uname -m`                            |`arm64` → Apple Silicon; `x86_64` → Intel; other → unsupported/unknown                         |
|CPU brand          |`sysctl -n machdep.cpu.brand_string`  |`null` on failure; do not infer cores from the name                                            |
|logical CPU threads|`sysctl -n hw.logicalcpu`             |positive integer or `null`                                                                     |
|physical memory    |`sysctl -n hw.memsize`                |convert bytes to integer MiB; `null` on failure                                                |
|free install disk  |`df -Pk <install-root>`               |convert available KiB to integer MiB; this is the conservative free-space value                |
|display adapters   |`system_profiler SPDisplaysDataType`  |retain only observed chipset/vendor/Metal/memory text; do not parse an absent field into a fact|
|virtualization     |supported OS signal only, when present|otherwise `unknown`; do not label a Mac VM or bare metal from a guess                          |

The helper must run without `sudo` and degrade safely when `system_profiler` is
slow, unavailable, or returns partial data. It must not use Linux-only commands
such as `/proc/meminfo`, `nproc`, `lspci`, or `nvidia-smi` as its primary Mac
source.

Emit normalized metadata compatible with the C1 environment-artifact contract.
Use the existing field names where they already exist; otherwise add only the
smallest documented macOS fields needed. At minimum, the resulting record must
make these values available:

```text
os_family=macos
architecture=arm64|x86_64|unknown
target_lane=mac/apple-silicon|mac/intel|unknown
provider=mac
topology=bare_metal|virtual_machine|unknown
physical_memory_mb=<integer|null>
free_install_disk_mb=<integer|null>
cpu_threads=<integer|null>
gpu_present=yes|no|unknown
gpu_name=<observed value|null>
gpu_memory_mb=<observed value|null>
metal_status=supported|unsupported|unknown
cuda_status=not_applicable
```

For Apple Silicon, `gpu_memory_mb` normally remains `null`: unified memory must
be represented by `physical_memory_mb`, never fabricated as dedicated VRAM.

## Happy Nerds trial categories

Keep the same runtime categories already encoded in `8.2.sh`:

|Observed physical memory |Trial order                                                  |
|-------------------------|-------------------------------------------------------------|
|≥ 24 GiB                 |`qwen3:14b`, then 8b, 4b, 1.7b, 0.6b                         |
|≥ 12 GiB                 |`qwen3:8b`, then 4b, 1.7b, 0.6b                              |
|≥ 8 GiB                  |`qwen3:4b`, then 1.7b, 0.6b                                  |
|≥ 4 GiB                  |`qwen3:1.7b`, then 0.6b                                      |
|< 4 GiB or memory unknown|`qwen3:0.6b` only; record unknown measurement when applicable|

Use the existing per-candidate free-disk safeguards in `8.2.sh` (14b: 14 GiB,
8b: 9 GiB, 4b: 6 GiB, 1.7b: 4 GiB, 0.6b: 3 GiB) as runtime guards only.
Do not transpose these values into global catalog RAM/disk requirements.

## Required repository changes

1. Add macOS runtime-host category documentation/data under the existing
   `AGENTS/data-science/profile-mapping/` organization. It must describe the
   two lanes, observed fields, unknown handling, and the exact `8.2` trial
   bands above.
2. Add the smallest generator/validator support necessary to verify that both
   canonical Mac lanes remain present and that their capability metadata is
   schema-valid.
3. Preserve `profiles/<model-slug>/mac/apple-silicon/` and
   `profiles/<model-slug>/mac/intel/` for every model. Do not create model-size
   directories, new Mac provider-plan folders, or a second index.
4. Add focused tests for:
  - `arm64` selecting only `mac/apple-silicon`;
  - `x86_64` selecting only `mac/intel`;
  - unknown architecture selecting no confident Mac lane;
  - Apple Silicon unified memory not becoming `gpu_memory_mb`/VRAM;
  - missing hardware output remaining `null`/`unknown`;
  - no Mac observation changing a catalog model-size fit to `fit`.
5. Do not edit `install/mac/**` payload scripts in this pass. Mac script work
   belongs to a later implementation stage.
6. Do not modify the CUDA lanes or connector/Jet integration in this pass.

## Verification

Run the repository's current commands plus focused tests:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
bash scripts/validate-catalog.sh
git diff --check
```

Run the generator twice. The second run must leave no generated diff:

```bash
python3 scripts/generate-c10-profiles.py
git diff --exit-code
```

Also confirm that the core count is unchanged by this capability pass:

```text
10 canonical lanes
mac/apple-silicon and mac/intel present for every generated model
no profile row added solely because a Mac observation was added
```

## Commit and report

Use one focused commit, for example:

```text
feat(c10.1): add macOS runtime host categories
```

Report the branch name, changed files, test outputs, final matrix counts,
unknown/unsupported handling, and commit SHA. Keep the PR draft until checks
are green. Do not claim CUDA, dedicated Apple-Silicon VRAM, universal model
fit, or Mac installer-script completion.

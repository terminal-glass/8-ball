# macOS runtime observation contract (C10.1-12)

Native macOS evidence contract for `mac/apple-silicon` and `mac/intel` lanes.
Committed taxonomy rows define categories only — not fixed Mac SKU capacities.

## Normalized record fields

| Field | Values | Notes |
| --- | --- | --- |
| `os_family` | `macos` | Native macOS only |
| `architecture` | `arm64`, `x86_64`, `unknown` | From `uname -m` |
| `target_lane` | `mac/apple-silicon`, `mac/intel`, `unknown` | arm64/x86_64 mapping only |
| `provider` | `mac` | Not a cloud provider lane |
| `topology` | `bare_metal`, `virtual_machine`, `unknown` | Hypervisor signal when present |
| `physical_memory_mb` | integer or null | Unified memory on Apple Silicon |
| `gpu_memory_mb` | integer or null | Normally null on Apple Silicon |
| `cuda_status` | `not_applicable` | Mac lanes are never CUDA lanes |

## Facts and evidence

| Fact | Preferred observation | Rule |
| --- | --- | --- |
| os_version | `sw_vers -productVersion` | Store raw version or null; native macOS only. |
| kernel_architecture | `uname -m` | arm64 maps to mac/apple-silicon; x86_64 maps to mac/intel; other yields unknown lane. |
| cpu_brand | `sysctl -n machdep.cpu.brand_string` | Null on failure; do not infer core count from marketing name. |
| cpu_threads | `sysctl -n hw.logicalcpu` | Positive integer or null. |
| physical_memory | `sysctl -n hw.memsize` | Convert bytes to integer MiB; observed fact only, not a model requirement. |
| free_install_disk | `df -Pk <install-root>` | Available KiB on install destination converted to MiB. |
| display_adapters | `system_profiler SPDisplaysDataType` | Retain observed chipset/vendor/Metal text only; do not parse absent fields. |
| virtualization | `sysctl -n hw.optional.hypervisor when present` | Otherwise unknown; do not guess bare metal versus VM. |

## Boundaries

- Do not use `/proc/meminfo`, `nproc`, `lspci`, or `nvidia-smi` as primary Mac sources.
- Display adapters are hardware evidence only; Metal and GPU memory stay unknown unless observed.
- Apple Silicon unified memory must not be copied into `gpu_memory_mb`.
- Observed RAM/disk facts must not change catalog model-size fit records.

## Observation helper

Shell helper: `scripts/macos-observe-host.sh`

# Windows runtime observation contract (C10.1-11)

Minimal native-Windows evidence contract for `windows/cpu` and `windows/cuda` lanes.
Committed taxonomy rows define categories and evidence rules only — not fixed capacities.

## Normalized artifact fields

| Field | Allowed values | Notes |
| --- | --- | --- |
| `EIGHTBALL_OS_FAMILY` | windows | wsl | wsl excludes native Windows lanes |
| `EIGHTBALL_PROVIDER` | windows | bare_metal | unknown | Not a cloud provider lane |
| `EIGHTBALL_INSTANCE_CLASS` | <observed> | unknown | Marketing labels are not capacity claims |
| `EIGHTBALL_RAM_MB` | <measured integer> | From TotalPhysicalMemory |
| `EIGHTBALL_CPU_THREADS` | <measured integer> | Sum of logical processors |
| `EIGHTBALL_DISK_FREE_GB` | <measured integer> | Install destination only |
| `EIGHTBALL_GPU_PRESENT` | yes | no | unknown | Win32_VideoController presence |
| `EIGHTBALL_GPU_NAME` | <observed> | unknown | nvidia-smi name when verified |
| `EIGHTBALL_GPU_VRAM_MB` | <measured integer> | unknown | nvidia-smi only; never AdapterRAM |

## Windows extension fields

| Field | Allowed values |
| --- | --- |
| `windows_host_kind` | physical | hyperv_vm | vmware_vm | virtualbox_vm | other_vm | unknown |
| `windows_architecture` | x64 | arm64 | x86 | unknown |
| `windows_gpu_runtime` | nvidia_smi_verified | gpu_present_unverified | no_gpu_detected | unknown |
| `windows_cuda_lane_eligible` | yes | no | unknown |
| `windows_gpu_vram_source` | nvidia_smi | unknown |

## Facts and evidence

| Fact | Preferred evidence | Rule |
| --- | --- | --- |
| os_and_architecture | `Get-CimInstance Win32_OperatingSystem; [Environment]::Is64BitOperatingSystem; PROCESSOR_ARCHITECTURE` | Record native Windows only. WSL must set os_family=wsl and must not use either windows lane. |
| host_topology | `Win32_ComputerSystem.Model, Manufacturer, HypervisorPresent` | Map only clearly evidenced windows_host_kind values; otherwise unknown. Do not infer cloud provider. |
| installed_ram | `Win32_ComputerSystem.TotalPhysicalMemory` | Record physical/assigned RAM in MiB as EIGHTBALL_RAM_MB. Never use free RAM as installed RAM. |
| cpu_threads | `Win32_Processor.NumberOfLogicalProcessors` | Sum valid logical processors; record EIGHTBALL_CPU_THREADS as measured integer. |
| install_destination_free_disk | `Get-PSDrive / volume for configured install path` | Measure the actual intended install destination only. |
| gpu_presence | `Win32_VideoController` | Presence alone is not CUDA evidence. AdapterRAM cannot become verified VRAM. |
| nvidia_identity_and_vram | `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` | Only successful nvidia-smi may set measured NVIDIA VRAM and windows/cuda lane eligibility. |

## WSL boundary

WSL is not native Windows. When detected, set `os_family=wsl` and route to the
Ubuntu/Linux runtime flow. Do not file WSL hosts under `windows/cpu` or `windows/cuda`.

## CUDA and VRAM boundary

`Win32_VideoController.AdapterRAM` must never become verified VRAM. Only successful
`nvidia-smi` may set measured NVIDIA VRAM and `windows/cuda` lane eligibility.
Retain per-device GPU evidence; expose the largest verified single-GPU VRAM value.

## ARM64 boundary

Native Windows on ARM64 records `windows_architecture=arm64`. Compatibility remains
`unknown` unless runtime prerequisites prove support. Do not imply x64/ARM64 parity.

## Sanitization

No live command output, serial numbers, hostnames, MAC addresses, IP addresses,
user names, or credentials may be committed. Tests use sanitized fixtures only.

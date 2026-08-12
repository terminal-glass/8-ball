# CUDA runtime observation contract (C10.1-13)

Cross-platform NVIDIA CUDA evidence contract for the four canonical CUDA install
lanes. Committed taxonomy rows define categories only — not fixed GPU SKUs or
model VRAM requirements.

## Canonical CUDA lanes

```text
ubuntu/cuda
windows/cuda
cloud/digitalocean/gpu-droplet
cloud/aws-lightsail/gpu
```

## Per-device normalized fields

| Field | Values | Notes |
| --- | --- | --- |
| `gpu_index` | integer | Index from nvidia-smi query order; not a persistent identity |
| `gpu_uuid` | string or null | Persistent device UUID when nvidia-smi reports it |
| `gpu_name` | string or null | Observed adapter name |
| `gpu_vendor` | `nvidia` | Fixed when sourced from nvidia-smi |
| `gpu_memory_mb` | integer or null | From `memory.total`; host capacity only |
| `compute_capability` | string or null | When nvidia-smi exposes it |
| `driver_version` | string or null | Per-device or header driver version |
| `driver_reported_cuda_api_max_version` | string or null | CUDA API version from nvidia-smi header; not toolkit |
| `cuda_toolkit_version` | string or null | Only from `nvcc --version` or direct toolkit probe |
| `cuda_visible` | string or null | Sanitized `CUDA_VISIBLE_DEVICES` when set |
| `ollama_nvidia_support` | `supported`, `unsupported`, `unknown` | From policy data only |
| `observation_status` | `available`, `unavailable` | Per device or envelope |
| `source_command` | string | Evidence command for each field group |

## Envelope fields

| Field | Values | Notes |
| --- | --- | --- |
| `os_family` | `linux`, `windows`, `unknown` | Lane selection input |
| `provider_context` | `null`, `digitalocean`, `aws-lightsail` | Must be observed independently |
| `target_lane` | lane id or `unknown` | Selected only with OS + provider + CUDA evidence |
| `devices` | array | One record per visible GPU |
| `cuda_visible_devices_env` | string or null | Sanitized environment value |
| `cuda_visible_resolved_uuid` | string or null | Only when mapping is unambiguous |
| `nvidia_smi_version` | string or null | Command version string |
| `observation_timestamp` | ISO-8601 UTC | Sanitized collection time |
| `observation_note` | string | Non-secret source note |

## Primary evidence

```text
nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits
```

Header line supplies driver-reported CUDA API max version. Optional toolkit probe:

```text
nvcc --version
```

## Lane selection

| Observed context | Allowed lane |
| --- | --- |
| Linux, non-provider context, CUDA available | `ubuntu/cuda` |
| Windows, CUDA available | `windows/cuda` |
| DigitalOcean provider context + CUDA available | `cloud/digitalocean/gpu-droplet` |
| AWS Lightsail provider context + CUDA available | `cloud/aws-lightsail/gpu` |
| Unknown OS/provider or CUDA unavailable | no confident CUDA lane |

## Boundaries

- No `sudo` required for observation.
- Do not substitute lspci, Device Manager, WMI, or provider-plan labels for nvidia-smi.
- Multi-GPU hosts retain every device record.
- `CUDA_VISIBLE_DEVICES` is recorded but numeric indices are not permanent IDs.
- Host VRAM observations must not change catalog model fit or `7-video_card.json`.
- macOS lanes are never CUDA. ROCm and Vulkan are out of scope for this pass.

## Observation helpers

- Linux: `scripts/cuda-observe-linux.sh`
- Windows: `scripts/cuda-observe-windows.ps1`

Policy: `AGENTS/data-science/profile-mapping/cuda/ollama-nvidia-support-policy.json`

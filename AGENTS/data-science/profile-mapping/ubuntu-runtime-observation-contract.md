# Ubuntu runtime observation contract (C10.1-10)

Minimal Linux-runtime evidence contract for Ubuntu CPU and CUDA install lanes.
Values are observed on the actual host at install time; committed taxonomy rows
define categories and evidence rules only — not fixed machine capacities.

## Facts and evidence

| Fact | Preferred evidence | Rule |
| --- | --- | --- |
| host_topology | `systemd-detect-virt` | Preserve status/output; unrecognized output is unknown. Map none to bare-metal, vm/kvm/qemu/vmware/microsoft/oracle to virtual-machine; provider stays null. |
| vm_detail | `systemd-detect-virt --vm and/or lscpu -J` | Optional detail only; never infer provider from hypervisor strings. |
| os_architecture | `/etc/os-release, uname -m` | Record observed values, not an imagined release target. |
| cpu_threads | `nproc, lscpu -J` | Record visible/assigned threads; do not derive performance class. |
| system_ram | `/proc/meminfo` | Record observed physical memory; never a model requirement. |
| model_filesystem | `configured Ollama/8-BALL data path then df -P` | Use free space on that filesystem only; never sum mounts. |
| gpu_presence | `nvidia-smi first, then lspci -nn when available` | Adapter discovery is not CUDA readiness. |
| cuda_state | `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` | Only successful nvidia-smi yields nvidia-cuda-ready; retain per-device evidence. |

## Provider boundary

Hypervisor strings from `systemd-detect-virt` (kvm, qemu, vmware, oracle, microsoft)
identify virtualization kind at most. They must **not** infer cloud provider.
Provider remains `null` unless a separately selected provider lane supplies sourced data.

## CUDA boundary

A PCI display adapter from `lspci` is not CUDA-ready. Only a successful
`nvidia-smi` query yields `nvidia-cuda-ready`. Retain per-device GPU evidence;
do not aggregate VRAM across devices without per-device records.

## Sanitization

No command output, serial number, MAC address, hostname, IP address, user name,
or credential may be committed. Tests use sanitized fixtures only.

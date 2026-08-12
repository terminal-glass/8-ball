#!/usr/bin/env bash
# C10.1-12 macOS runtime host observation helper (metadata contract only).
# Safe without sudo; degrades to null/unknown when commands fail.
# Not wired into public install/mac payloads in this pass.
set -euo pipefail

INSTALL_ROOT="${1:-${HOME}}"

if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Darwin" ]]; then
  python3 - "${INSTALL_ROOT}" <<'PY'
import json, sys
install_root = sys.argv[1]
print(json.dumps({
    "os_family": "macos",
    "architecture": "unknown",
    "target_lane": "unknown",
    "provider": "mac",
    "topology": "unknown",
    "os_version": None,
    "cpu_brand": None,
    "physical_memory_mb": None,
    "free_install_disk_mb": None,
    "cpu_threads": None,
    "gpu_present": "unknown",
    "gpu_name": None,
    "gpu_memory_mb": None,
    "metal_status": "unknown",
    "cuda_status": "not_applicable",
    "install_root": install_root,
    "observation_status": "non_darwin_host",
}, indent=2))
PY
  exit 0
fi

OS_VERSION="$(sw_vers -productVersion 2>/dev/null || true)"
ARCH="$(uname -m 2>/dev/null || true)"
CPU_BRAND="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || true)"
CPU_THREADS="$(sysctl -n hw.logicalcpu 2>/dev/null || true)"
MEM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || true)"
FREE_KIB="$(df -Pk "${INSTALL_ROOT}" 2>/dev/null | awk 'NR==2 {print $4}' || true)"
DISPLAYS="$(system_profiler SPDisplaysDataType 2>/dev/null || true)"
HYPERVISOR="$(sysctl -n hw.optional.hypervisor 2>/dev/null || true)"

export OS_VERSION ARCH CPU_BRAND CPU_THREADS MEM_BYTES FREE_KIB DISPLAYS HYPERVISOR INSTALL_ROOT
python3 <<'PY'
import json
import os
import re

install_root = os.environ.get("INSTALL_ROOT", os.path.expanduser("~"))
arch = (os.environ.get("ARCH") or "").strip() or None
os_version = (os.environ.get("OS_VERSION") or "").strip() or None
cpu_brand = (os.environ.get("CPU_BRAND") or "").strip() or None

def positive_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return None
    return parsed if parsed > 0 else None

cpu_threads = positive_int(os.environ.get("CPU_THREADS"))
mem_bytes = positive_int(os.environ.get("MEM_BYTES"))
physical_memory_mb = mem_bytes // (1024 * 1024) if mem_bytes else None
free_install_disk_mb = positive_int(os.environ.get("FREE_KIB"))
if free_install_disk_mb is not None:
    free_install_disk_mb //= 1024

if arch == "arm64":
    target_lane = "mac/apple-silicon"
elif arch == "x86_64":
    target_lane = "mac/intel"
else:
    target_lane = "unknown"

hypervisor = (os.environ.get("HYPERVISOR") or "").strip()
if hypervisor == "1":
    topology = "virtual_machine"
elif hypervisor == "0":
    topology = "bare_metal"
else:
    topology = "unknown"

displays = os.environ.get("DISPLAYS") or ""
gpu_present = "unknown"
gpu_name = None
gpu_memory_mb = None
metal_status = "unknown"

if displays:
    names = re.findall(r"^\s*Chipset Model:\s*(.+)$", displays, re.MULTILINE)
    if names:
        gpu_present = "yes"
        gpu_name = names[0].strip()
    elif "Display Type:" in displays or "Graphics:" in displays:
        gpu_present = "yes"
    else:
        gpu_present = "no"
    if re.search(r"Metal:\s*Supported", displays, re.IGNORECASE):
        metal_status = "supported"
    elif re.search(r"Metal:\s*Not Supported", displays, re.IGNORECASE):
        metal_status = "unsupported"

# Apple Silicon unified memory: never fabricate dedicated VRAM.
if target_lane == "mac/apple-silicon":
    gpu_memory_mb = None

payload = {
    "os_family": "macos",
    "architecture": arch or "unknown",
    "target_lane": target_lane,
    "provider": "mac",
    "topology": topology,
    "os_version": os_version,
    "cpu_brand": cpu_brand,
    "physical_memory_mb": physical_memory_mb,
    "free_install_disk_mb": free_install_disk_mb,
    "cpu_threads": cpu_threads,
    "gpu_present": gpu_present,
    "gpu_name": gpu_name,
    "gpu_memory_mb": gpu_memory_mb,
    "metal_status": metal_status,
    "cuda_status": "not_applicable",
    "install_root": install_root,
    "observation_status": "observed",
}
print(json.dumps(payload, indent=2))
PY

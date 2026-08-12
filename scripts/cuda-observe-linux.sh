#!/usr/bin/env bash
# C10.1-13 CUDA runtime observation helper for Linux (metadata contract only).
# Safe without sudo; degrades to unavailable when nvidia-smi is absent.
# Not wired into public install payloads in this pass.
set -euo pipefail

OS_FAMILY="${CUDA_OBSERVE_OS_FAMILY:-linux}"
PROVIDER_CONTEXT="${CUDA_OBSERVE_PROVIDER_CONTEXT:-}"

if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Linux" ]]; then
  OS_FAMILY="unknown"
fi

CUDA_VISIBLE_RAW="${CUDA_VISIBLE_DEVICES:-}"
NVCC_OUTPUT=""
NVIDIA_SMI_CSV=""
NVIDIA_SMI_HEADER=""
NVIDIA_SMI_VERSION=""
OBSERVATION_NOTE="non-linux host or nvidia-smi unavailable"

if [[ "$OS_FAMILY" == "linux" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    NVIDIA_SMI_VERSION="$(nvidia-smi --version 2>/dev/null | head -n 1 || true)"
    NVIDIA_SMI_HEADER="$(nvidia-smi 2>/dev/null | head -n 3 || true)"
    NVIDIA_SMI_CSV="$(nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits 2>/dev/null || true)"
    OBSERVATION_NOTE="linux nvidia-smi primary evidence"
  else
    OBSERVATION_NOTE="nvidia-smi command missing on linux host"
  fi
  if command -v nvcc >/dev/null 2>&1; then
    NVCC_OUTPUT="$(nvcc --version 2>/dev/null || true)"
  fi
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export OS_FAMILY PROVIDER_CONTEXT CUDA_VISIBLE_RAW NVCC_OUTPUT NVIDIA_SMI_CSV NVIDIA_SMI_HEADER NVIDIA_SMI_VERSION OBSERVATION_NOTE REPO_ROOT
python3 - <<'PY'
import importlib.util
import json
import os
from pathlib import Path

repo_root = Path(os.environ["REPO_ROOT"])
module_path = repo_root / "scripts" / "c10_cuda_compatibility.py"
spec = importlib.util.spec_from_file_location("c10_cuda_compatibility", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {module_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

payload = module.build_observation_from_nvidia_smi(
    os_family=os.environ.get("OS_FAMILY", "unknown"),
    provider_context=os.environ.get("PROVIDER_CONTEXT") or None,
    nvidia_smi_csv=os.environ.get("NVIDIA_SMI_CSV") or None,
    nvidia_smi_header=os.environ.get("NVIDIA_SMI_HEADER") or None,
    nvcc_output=os.environ.get("NVCC_OUTPUT") or None,
    cuda_visible_devices=os.environ.get("CUDA_VISIBLE_RAW") or None,
    nvidia_smi_version=os.environ.get("NVIDIA_SMI_VERSION") or None,
    observation_note=os.environ.get("OBSERVATION_NOTE") or None,
)
print(json.dumps(payload, indent=2))
PY

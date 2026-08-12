# C10.1-13 CUDA runtime observation helper for Windows (metadata contract only).
# Safe without elevation; degrades to unavailable when nvidia-smi is absent.
# Not wired into public install payloads in this pass.
param(
    [string]$OsFamily = "windows",
    [string]$ProviderContext = ""
)

$ErrorActionPreference = "SilentlyContinue"

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    $OsFamily = "unknown"
}

$CudaVisibleRaw = $env:CUDA_VISIBLE_DEVICES
$NvccOutput = ""
$NvidiaSmiCsv = ""
$NvidiaSmiHeader = ""
$NvidiaSmiVersion = ""
$ObservationNote = "non-windows host or nvidia-smi unavailable"

if ($OsFamily -eq "windows") {
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        $NvidiaSmiVersion = (& nvidia-smi --version 2>$null | Select-Object -First 1)
        $NvidiaSmiHeader = (& nvidia-smi 2>$null | Select-Object -First 3) -join "`n"
        $NvidiaSmiCsv = (& nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits 2>$null)
        $ObservationNote = "windows nvidia-smi primary evidence"
    }
    else {
        $ObservationNote = "nvidia-smi command missing on windows host"
    }
    $nvcc = Get-Command nvcc -ErrorAction SilentlyContinue
    if ($nvcc) {
        $NvccOutput = (& nvcc --version 2>$null) -join "`n"
    }
}

$env:OS_FAMILY = $OsFamily
$env:PROVIDER_CONTEXT = $ProviderContext
$env:CUDA_VISIBLE_RAW = $CudaVisibleRaw
$env:NVCC_OUTPUT = $NvccOutput
$env:NVIDIA_SMI_CSV = $NvidiaSmiCsv
$env:NVIDIA_SMI_HEADER = $NvidiaSmiHeader
$env:NVIDIA_SMI_VERSION = $NvidiaSmiVersion
$env:OBSERVATION_NOTE = $ObservationNote

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Output '{"observation_status":"unavailable","observation_note":"python unavailable"}'
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$modulePath = Join-Path $repoRoot "scripts\c10_cuda_compatibility.py"

$py = @"
import importlib.util
import json
import os
from pathlib import Path

module_path = Path(r"$modulePath")
spec = importlib.util.spec_from_file_location("c10_cuda_compatibility", module_path)
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
"@

& $python.Path -c $py

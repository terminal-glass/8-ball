# Example normalized collector output schema for C10.1-11.
# This file is a contract fixture only; it is not wired into public installers.
# Requires PowerShell 5.1+ / pwsh.

param(
    [string]$InstallPath = $env:LOCALAPPDATA
)

$ErrorActionPreference = 'Stop'

function Get-NativeWindowsProbe {
    $os = Get-CimInstance Win32_OperatingSystem
    $system = Get-CimInstance Win32_ComputerSystem
    $processors = Get-CimInstance Win32_Processor

    $logical = 0
    foreach ($cpu in $processors) {
        if ($cpu.NumberOfLogicalProcessors) {
            $logical += [int]$cpu.NumberOfLogicalProcessors
        }
    }

    $gpuPresent = 'unknown'
    $gpuName = 'unknown'
    $gpuVramMb = 'unknown'
    $gpuRuntime = 'unknown'
    $cudaEligible = 'unknown'
    $vramSource = 'unknown'

    $controllers = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
    if ($controllers.Count -gt 0) {
        $gpuPresent = 'yes'
        $gpuRuntime = 'gpu_present_unverified'
        $cudaEligible = 'no'
    } else {
        $gpuPresent = 'no'
        $gpuRuntime = 'no_gpu_detected'
        $cudaEligible = 'no'
    }

    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $smi = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $smi) {
            $first = ($smi | Select-Object -First 1)
            if ($first -match '^(?<name>.+),\s*(?<vram>\d+)') {
                $gpuName = $Matches.name.Trim()
                $gpuVramMb = [int]$Matches.vram
                $gpuRuntime = 'nvidia_smi_verified'
                $cudaEligible = 'yes'
                $vramSource = 'nvidia_smi'
            }
        }
    }

  return [ordered]@{
        EIGHTBALL_OS_FAMILY = 'windows'
        EIGHTBALL_PROVIDER = 'unknown'
        EIGHTBALL_INSTANCE_CLASS = 'unknown'
        EIGHTBALL_RAM_MB = [int]([math]::Round($system.TotalPhysicalMemory / 1MB))
        EIGHTBALL_CPU_THREADS = $logical
        EIGHTBALL_DISK_FREE_GB = $null
        EIGHTBALL_GPU_PRESENT = $gpuPresent
        EIGHTBALL_GPU_NAME = $gpuName
        EIGHTBALL_GPU_VRAM_MB = $gpuVramMb
        windows_host_kind = 'unknown'
        windows_architecture = 'unknown'
        windows_gpu_runtime = $gpuRuntime
        windows_cuda_lane_eligible = $cudaEligible
        windows_gpu_vram_source = $vramSource
        gpus = @()
    }
}

Get-NativeWindowsProbe | ConvertTo-Json -Depth 4

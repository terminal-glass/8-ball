# C10.1-11 normalized Windows runtime collector (metadata contract only).
# Safe without elevation; degrades to unknown when probes fail.
# Not wired into public install payloads in this pass.
# Requires PowerShell 5.1+ / pwsh.

param(
    [string]$InstallPath = $env:LOCALAPPDATA
)

$ErrorActionPreference = 'SilentlyContinue'

function New-UnknownCollectorRecord {
    param(
        [string]$OsFamily = 'unknown',
        [string]$TargetLane = 'unknown',
        [bool]$NativeWindowsLaneEligible = $false,
        [string]$CudaLaneEligible = 'unknown'
    )

    return [ordered]@{
        EIGHTBALL_OS_FAMILY = $OsFamily
        EIGHTBALL_PROVIDER = 'unknown'
        EIGHTBALL_INSTANCE_CLASS = 'unknown'
        EIGHTBALL_RAM_MB = $null
        EIGHTBALL_CPU_THREADS = $null
        EIGHTBALL_DISK_FREE_GB = $null
        EIGHTBALL_GPU_PRESENT = 'unknown'
        EIGHTBALL_GPU_NAME = 'unknown'
        EIGHTBALL_GPU_VRAM_MB = 'unknown'
        windows_host_kind = 'unknown'
        windows_architecture = 'unknown'
        windows_gpu_runtime = 'unknown'
        windows_cuda_lane_eligible = $CudaLaneEligible
        windows_gpu_vram_source = 'unknown'
        native_windows_lane_eligible = $NativeWindowsLaneEligible
        target_lane = $TargetLane
        gpus = @()
    }
}

function Test-IsWslEnvironment {
    if ($env:WSL_DISTRO_NAME) {
        return $true
    }
    if ($IsLinux -and (Test-Path -LiteralPath '/proc/version')) {
        $procVersion = Get-Content -LiteralPath '/proc/version' -Raw -ErrorAction SilentlyContinue
        if ($procVersion -match '(?i)microsoft|WSL') {
            return $true
        }
    }
    return $false
}

function Get-InstallPathFreeDiskGb {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    try {
        $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
        $root = [System.IO.Path]::GetPathRoot($resolved.Path)
        if ([string]::IsNullOrWhiteSpace($root)) {
            return $null
        }

        $driveId = $root.TrimEnd('\')
        if ($driveId.Length -lt 2) {
            return $null
        }

        $disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter ("DeviceID='{0}'" -f $driveId) -ErrorAction SilentlyContinue
        if ($null -eq $disk -or $null -eq $disk.FreeSpace) {
            return $null
        }

        return [int][math]::Floor([double]$disk.FreeSpace / 1GB)
    }
    catch {
        return $null
    }
}

function Get-NativeWindowsProbe {
    param(
        [string]$InstallPath
    )

    $record = New-UnknownCollectorRecord -OsFamily 'windows' -TargetLane 'unknown' -NativeWindowsLaneEligible $true -CudaLaneEligible 'unknown'

    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
    $system = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction SilentlyContinue
    $processors = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction SilentlyContinue)

    if ($system -and $system.TotalPhysicalMemory) {
        $record.EIGHTBALL_RAM_MB = [int][math]::Round([double]$system.TotalPhysicalMemory / 1MB)
    }

    $logical = 0
    foreach ($cpu in $processors) {
        if ($cpu.NumberOfLogicalProcessors) {
            $logical += [int]$cpu.NumberOfLogicalProcessors
        }
    }
    if ($logical -gt 0) {
        $record.EIGHTBALL_CPU_THREADS = $logical
    }

    $diskFreeGb = Get-InstallPathFreeDiskGb -Path $InstallPath
    if ($null -ne $diskFreeGb) {
        $record.EIGHTBALL_DISK_FREE_GB = $diskFreeGb
    }

    if ($os) {
        $arch = $os.OSArchitecture
        if ($arch -match '64') {
            if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
                $record.windows_architecture = 'arm64'
            }
            else {
                $record.windows_architecture = 'x64'
            }
        }
        elseif ($arch -match '32') {
            $record.windows_architecture = 'x86'
        }
    }

    $gpuPresent = 'unknown'
    $gpuName = 'unknown'
    $gpuVramMb = 'unknown'
    $gpuRuntime = 'unknown'
    $cudaEligible = 'unknown'
    $vramSource = 'unknown'
    $gpus = @()

    $controllers = @(Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue)
    if ($controllers.Count -gt 0) {
        $gpuPresent = 'yes'
        $gpuRuntime = 'gpu_present_unverified'
        $cudaEligible = 'no'
        $vramSource = 'unknown'
    }
    else {
        $gpuPresent = 'no'
        $gpuRuntime = 'no_gpu_detected'
        $cudaEligible = 'no'
        $vramSource = 'unknown'
    }

    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $smi = & nvidia-smi --query-gpu=index,uuid,name,memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $smi) {
            $verified = @()
            foreach ($line in @($smi)) {
                if ($line -match '^(?<index>\d+),\s*(?<uuid>[^,]+),\s*(?<name>[^,]+),\s*(?<vram>\d+)') {
                    $verified += [ordered]@{
                        gpu_index = [int]$Matches.index
                        gpu_uuid = $Matches.uuid.Trim()
                        gpu_name = $Matches.name.Trim()
                        gpu_memory_mb = [int]$Matches.vram
                        gpu_vram_source = 'nvidia_smi'
                    }
                }
            }
            if ($verified.Count -gt 0) {
                $gpus = $verified
                $first = $verified[0]
                $gpuName = $first.gpu_name
                $gpuVramMb = $first.gpu_memory_mb
                $gpuRuntime = 'nvidia_smi_verified'
                $cudaEligible = 'yes'
                $vramSource = 'nvidia_smi'
            }
        }
    }

    $record.EIGHTBALL_GPU_PRESENT = $gpuPresent
    $record.EIGHTBALL_GPU_NAME = $gpuName
    $record.EIGHTBALL_GPU_VRAM_MB = $gpuVramMb
    $record.windows_gpu_runtime = $gpuRuntime
    $record.windows_cuda_lane_eligible = $cudaEligible
    $record.windows_gpu_vram_source = $vramSource
    $record.gpus = $gpus

    if ($cudaEligible -eq 'yes') {
        $record.target_lane = 'windows/cuda'
    }
    elseif ($gpuPresent -in @('yes', 'no')) {
        $record.target_lane = 'windows/cpu'
    }

    return $record
}

try {
    if (Test-IsWslEnvironment) {
        $output = New-UnknownCollectorRecord -OsFamily 'wsl' -TargetLane 'unknown' -NativeWindowsLaneEligible $false -CudaLaneEligible 'no'
        $output | ConvertTo-Json -Depth 6 -Compress:$false
        exit 0
    }

    if ($env:OS -ne 'Windows_NT' -and -not $IsWindows) {
        $output = New-UnknownCollectorRecord
        $output | ConvertTo-Json -Depth 6 -Compress:$false
        exit 0
    }

    $output = Get-NativeWindowsProbe -InstallPath $InstallPath
    $output | ConvertTo-Json -Depth 6 -Compress:$false
    exit 0
}
catch {
    $fallback = New-UnknownCollectorRecord
    $fallback | ConvertTo-Json -Depth 6 -Compress:$false
    exit 0
}

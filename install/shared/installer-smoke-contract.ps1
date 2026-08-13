# Shared no-mutation help/preflight contract for public Windows installer entrypoints (C10.2-5).
#Requires -Version 5.1

function Get-InstallerSmokeUsage {
    param(
        [string]$ScriptName,
        [string]$Lane,
        [string]$Checks
    )
    @"
Usage: .\$ScriptName [options]

Lane: $Lane

$Checks

Options:
  -Help       Show this help without mutating the host
  -Preflight  Report lane identity and planned checks without installing software
"@
}

function Invoke-InstallerSmokePreflight {
    param(
        [string]$Lane,
        [string]$Checks,
        [string]$LaneMode = 'cpu'
    )

    Write-Output "lane: $Lane"
    Write-Output 'mode: preflight (no installation performed)'
    Write-Output 'planned_checks:'
    Write-Output $Checks

    if ($env:WSL_DISTRO_NAME) {
        [Console]::Error.WriteLine("unsupported: lane $Lane requires native Windows (WSL detected)")
        exit 2
    }
    if ($env:OS -ne 'Windows_NT' -and -not $IsWindows) {
        [Console]::Error.WriteLine("unsupported: lane $Lane requires native Windows; detected OS=$($env:OS)")
        exit 2
    }

    if ($LaneMode -eq 'cuda') {
        Write-Output 'cuda_evidence: would require nvidia-smi output on a CUDA-capable host (no driver installation in preflight)'
    }
    else {
        Write-Output 'cuda_evidence: not required for CPU lane'
    }
    exit 0
}

function Test-InstallerSmokeFlags {
    param(
        [switch]$Help,
        [switch]$Preflight,
        [string]$ScriptName,
        [string]$Lane,
        [string]$Checks,
        [string]$LaneMode = 'cpu'
    )

    if ($Help) {
        Get-InstallerSmokeUsage -ScriptName $ScriptName -Lane $Lane -Checks $Checks | Write-Host
        exit 0
    }
    if ($Preflight) {
        Invoke-InstallerSmokePreflight -Lane $Lane -Checks $Checks -LaneMode $LaneMode
    }
}

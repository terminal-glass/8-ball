# install/windows/trial-install.ps1 — dispatch to canonical Windows lane when appropriate.
#Requires -Version 5.1
param(
    [string]$Model,
    [string]$Manifest,
    [switch]$NoMotd,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir 'lib\Windows-Common.ps1')

if ($Help) {
    Write-Host 'Usage: .\trial-install.ps1 [-Model TAG] [-NoMotd] [-Manifest PATH] [-Help]'
    Write-Host 'Dispatches to install\windows\cpu or install\windows\cuda when CUDA evidence is present.'
    exit 0
}

Assert-NonElevated
Assert-NativeWindows

$cudaLane = Join-Path $ScriptDir 'cuda\trial-install.ps1'
$cpuLane = Join-Path $ScriptDir 'cpu\trial-install.ps1'
$useCuda = $false
$repoRoot = Find-RepoRoot -StartDir $ScriptDir
if ($repoRoot) {
    $observe = Join-Path $repoRoot 'scripts\cuda-observe-windows.ps1'
    if (Test-Path -LiteralPath $observe) {
        try {
            $cuda = & $observe -OsFamily windows -ProviderContext '' | ConvertFrom-Json
            if ($cuda.observation_status -eq 'available' -and $cuda.devices.Count -gt 0) {
                $unsupported = $false
                foreach ($device in $cuda.devices) {
                    if ($device.ollama_nvidia_support -eq 'unsupported') { $unsupported = $true }
                }
                if (-not $unsupported) { $useCuda = $true }
            }
        }
        catch {
            $useCuda = $false
        }
    }
}

$target = if ($useCuda) { $cudaLane } else { $cpuLane }
$args = @()
if ($Model) { $args += '-Model'; $args += $Model }
if ($Manifest) { $args += '-Manifest'; $args += $Manifest }
if ($NoMotd) { $args += '-NoMotd' }
& $target @args

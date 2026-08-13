# 8.2.ps1 — Windows Happy Nerds model trial ladder with local inference verification (CUDA lane).
#Requires -Version 5.1
param(
    [string]$Model,
    [switch]$Help,
    [switch]$Preflight
)

if ($Help) {
    Write-Host @'
Usage: .\8.2.ps1 [-Model OLLAMA_TAG] [-Help]

Lane: windows/cuda

Runs the Happy Nerds trial ladder with CUDA acceleration when evidence is available.
'@
    exit 0
}

$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cuda'
$script:WinLogPrefix = '8.2'
$script:WinLaneMode = 'cuda'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')
. (Join-Path $ScriptDir '..\..\shared\installer-smoke-contract.ps1')
if ($Preflight) {
    Invoke-InstallerSmokePreflight -Lane 'windows/cuda' -Checks @'
- Verify catalog manifest availability
- Would run the Happy Nerds trial ladder with local inference checks during a real install
'@ -LaneMode 'cuda'
}

Assert-NonElevated
Assert-NativeWindows
Resolve-EightballRoot
Assert-LoopbackOllamaApi

if (-not (Test-Path -LiteralPath $script:ObservationFile)) {
    throw 'Missing runtime observation. Run 8.1.ps1 first.'
}
try {
    $null = Invoke-RestMethod -Uri "$($script:OllamaApi)/api/tags" -Method Get -TimeoutSec 5
}
catch {
    throw 'Ollama is not responding. Run 8.1.ps1 first.'
}

Save-ModelsBeforeTrial
$acceleration = 'cuda'
if (Test-Path -LiteralPath $script:CudaObservationFile) {
    $cudaObs = Get-Content -LiteralPath $script:CudaObservationFile -Raw | ConvertFrom-Json
    if ($cudaObs.observation_status -ne 'available') {
        $acceleration = 'cpu'
    }
}

$ramGiB = Get-RamGiBFromObservation
$freeDiskGiB = Get-FreeDiskGiBFromObservation
if ($Model) {
    Assert-ModelTag -Tag $Model
    $candidates = @($Model)
}
else {
    $candidates = Get-FilteredCandidates -RamGiB $ramGiB -FreeDiskGiB $freeDiskGiB
}
if ($candidates.Count -eq 0) { throw 'No trial candidates remain after disk guards.' }

$selected = $null
$status = 'FAILED'
$exe = Find-OllamaExecutable
foreach ($candidate in $candidates) {
    Write-WinLog "Trying candidate $candidate"
    & $exe pull $candidate
    if (-not $?) {
        Remove-ModelIfNew -Model $candidate
        continue
    }
    if (Test-ModelGenerate -Model $candidate) {
        $selected = $candidate
        $status = 'PASSED'
        break
    }
    Remove-ModelIfNew -Model $candidate
}

if (-not $selected) {
    Write-ResultRecord -Model 'none' -Status $status -Acceleration $acceleration
    throw 'No candidate passed the local inference test.'
}

Write-ResultRecord -Model $selected -Status $status -Acceleration $acceleration
Write-WinLog "Selected model $selected; result written to $($script:ResultFile)"

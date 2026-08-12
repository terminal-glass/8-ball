# 8.2.ps1 — Windows Happy Nerds model trial ladder with local inference verification (CPU lane).
#Requires -Version 5.1
param([string]$Model,
    [switch]$Help,
    [switch]$Preflight)

$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cpu'
$script:WinLogPrefix = '8.2'
$script:WinLaneMode = 'cpu'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')
. (Join-Path $ScriptDir '..\..\shared\installer-smoke-contract.ps1')
Test-InstallerSmokeFlags -Help:$Help -Preflight:$Preflight -ScriptName '8.2.ps1' -Lane $script:WinTargetLane -Checks @'
- Verify runtime observation and loopback Ollama API availability
- Would run the Happy Nerds trial ladder during a real install
'@ -LaneMode 'cpu'


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
$acceleration = 'cpu'

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

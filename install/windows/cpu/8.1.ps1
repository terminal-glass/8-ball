# 8.1.ps1 — Windows foundation: Ollama verification and runtime observation (CPU lane).
#Requires -Version 5.1
param(
    [switch]$Help,
    [switch]$Preflight
)
$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cpu'
$script:WinLogPrefix = '8.1'
$script:WinLaneMode = 'cpu'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')
. (Join-Path $ScriptDir '..\..\shared\installer-smoke-contract.ps1')
Test-InstallerSmokeFlags -Help:$Help -Preflight:$Preflight -ScriptName '8.1.ps1' -Lane $script:WinTargetLane -Checks @'
- Verify native Windows host, loopback Ollama API settings, and runtime observation
- Would verify Ollama CLI availability during a real install
'@ -LaneMode 'cpu'

Assert-NonElevated
Assert-NativeWindows
Resolve-EightballRoot
Assert-LoopbackOllamaApi
Assert-WindowsRelease

Write-WindowsObservation
Write-WinLog "Wrote runtime observation to $($script:ObservationFile)"

Assert-OllamaCli
Wait-OllamaApi
Write-WinLog "Foundation step complete for $($script:WinTargetLane)"

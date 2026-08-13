# 8.1.ps1 — Windows foundation: Ollama verification and runtime observation (CPU lane).
#Requires -Version 5.1
param(
    [switch]$Help,
    [switch]$Preflight
)

if ($Help) {
    Write-Host @'
Usage: .\8.1.ps1 [-Help]

Lane: windows/cpu

Verifies native Windows, loopback Ollama API settings, and runtime observation during install.
Does not install NVIDIA/CUDA drivers.
'@
    exit 0
}

$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cpu'
$script:WinLogPrefix = '8.1'
$script:WinLaneMode = 'cpu'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')
. (Join-Path $ScriptDir '..\..\shared\installer-smoke-contract.ps1')
if ($Preflight) {
    Invoke-InstallerSmokePreflight -Lane 'windows/cpu' -Checks @'
- Verify native Windows host and loopback Ollama API settings
- Would observe Ollama runtime without installing during --preflight
'@ -LaneMode 'cpu'
}

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

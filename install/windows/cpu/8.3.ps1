# 8.3.ps1 — Windows completion card and user-level status helper (CPU lane).
#Requires -Version 5.1
param(
    [switch]$Help,
    [switch]$Preflight
)
$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cpu'
$script:WinLogPrefix = '8.3'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MotdTemplate = Join-Path $ScriptDir 'assets\first-MOTD.txt'
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')
. (Join-Path $ScriptDir '..\..\shared\installer-smoke-contract.ps1')
Test-InstallerSmokeFlags -Help:$Help -Preflight:$Preflight -ScriptName '8.3.ps1' -Lane $script:WinTargetLane -Checks @'
- Verify completion card template
- Would print MOTD and write user-level status helper during a real install
'@ -LaneMode 'cpu'

Assert-NonElevated
Assert-NativeWindows
Resolve-EightballRoot
Assert-LoopbackOllamaApi

if (-not (Test-Path -LiteralPath $MotdTemplate)) {
    throw "Missing completion card template: $MotdTemplate"
}

$selectedModel = 'unknown'
$modelStatus = 'UNKNOWN'
$ollamaStatus = 'STOPPED'
try {
    $null = Invoke-RestMethod -Uri "$($script:OllamaApi)/api/tags" -Method Get -TimeoutSec 5
    $ollamaStatus = 'RUNNING'
}
catch { }

if (Test-Path -LiteralPath $script:ResultFile) {
    foreach ($line in Get-Content -LiteralPath $script:ResultFile) {
        if ($line -match '^Model:\s*(.+)$') { $selectedModel = $Matches[1].Trim() }
        if ($line -match '^Model test:\s*PASSED$') { $modelStatus = 'READY' }
    }
}

$card = Get-Content -LiteralPath $MotdTemplate -Raw
$card = $card.Replace('__OLLAMA_STATUS__', $ollamaStatus)
$card = $card.Replace('__MODEL_STATUS__', $modelStatus)
$card = $card.Replace('__SELECTED_MODEL__', $selectedModel)
$card = $card.Replace('__EIGHTBALL_ROOT__', $env:EIGHTBALL_ROOT)
Write-Host $card

Write-StatusHelper
Write-WinLog "Wrote status helper at $($script:StatusScript)"
Write-WinLog "Jets are optional and require a separate 'ollama signin'; this installer does not activate them."

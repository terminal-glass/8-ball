# trial-install.ps1 — public 8-BALL Windows trial installer (CUDA lane).
#Requires -Version 5.1
param(
    [string]$Model,
    [string]$Manifest,
    [switch]$NoMotd,
    [switch]$Help
)

if ($Help) {
    Write-Host @'
Usage: .\trial-install.ps1 [options]

Public free/trial 8-BALL installer for native Windows CUDA (windows/cuda).

Options:
  -Model TAG        Request a specific Ollama tag (passed to 8.2.ps1)
  -NoMotd           Run 8.1 and 8.2 only
  -Manifest PATH    Accepted for compatibility; Windows trial uses the Happy Nerds ladder
  -Help             Show this help without mutating the host
'@
    exit 0
}

$ErrorActionPreference = 'Stop'
$script:WinTargetLane = 'windows/cuda'
$script:WinLogPrefix = 'trial-install'
$script:WinLaneMode = 'cuda'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir '..\lib\Windows-Common.ps1')

foreach ($name in @('8.1.ps1', '8.2.ps1', '8.3.ps1')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ScriptDir $name))) {
        throw "Missing required lane payload: $(Join-Path $ScriptDir $name). This trial bundle must include its full lane scripts locally."
    }
}

try {
    Assert-NonElevated
    Assert-NativeWindows
    Resolve-EightballRoot
    if (-not (Test-Path -LiteralPath $script:LogFile)) {
        New-Item -ItemType File -Path $script:LogFile -Force | Out-Null
    }
    if ($Model) { Assert-ModelTag -Tag $Model }

    Write-WinLog '[1/3] Verifying Windows, CUDA evidence, Ollama, and runtime observation'
    & (Join-Path $ScriptDir '8.1.ps1')

    Write-WinLog '[2/3] Running Happy Nerds trial ladder'
    if ($Model) {
        & (Join-Path $ScriptDir '8.2.ps1') -Model $Model
    }
    else {
        & (Join-Path $ScriptDir '8.2.ps1')
    }

    if (-not $NoMotd) {
        Write-WinLog '[3/3] Printing completion card and status helper'
        & (Join-Path $ScriptDir '8.3.ps1')
    }
    else {
        Write-WinLog '[3/3] Skipping completion card (-NoMotd)'
    }

    Write-WinLog "Trial install complete. Log: $($script:LogFile)"
    Write-WinLog "Result: $($script:ResultFile)"
    Write-WinLog "Status: $($script:StatusScript)"
}
catch {
    Write-Error $_.Exception.Message
    if ($script:LogFile -and (Test-Path -LiteralPath $script:LogFile)) {
        Write-Host '--- last log lines ---'
        Get-Content -LiteralPath $script:LogFile -Tail 30
    }
    exit 1
}

# install/windows/trial-install.ps1 — dispatch to canonical Windows lane when appropriate.
#Requires -Version 5.1
param(
    [string]$Model,
    [string]$Manifest,
    [switch]$NoMotd,
    [switch]$Help
)

if ($Help) {
    Write-Host @'
Usage: .\trial-install.ps1 [-Model TAG] [-NoMotd] [-Manifest PATH] [-Help]

Dispatches to install\windows\cpu\trial-install.ps1 or install\windows\cuda\trial-install.ps1
using local nvidia-smi evidence from Windows-Common.ps1 (no driver installation).

Options:
  -Model TAG        Request a specific Ollama tag (passed to the selected lane)
  -NoMotd           Run 8.1 and 8.2 only
  -Manifest PATH    Accepted for compatibility
  -Help             Show this help without mutating the host
'@
    exit 0
}

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir 'lib\Windows-Common.ps1')

Assert-NonElevated
Assert-NativeWindows

$cudaLane = Join-Path $ScriptDir 'cuda\trial-install.ps1'
$cpuLane = Join-Path $ScriptDir 'cpu\trial-install.ps1'
$useCuda = (Resolve-WindowsTrialLaneDispatch) -eq 'cuda'

$target = if ($useCuda) { $cudaLane } else { $cpuLane }
$args = @()
if ($Model) { $args += '-Model'; $args += $Model }
if ($Manifest) { $args += '-Manifest'; $args += $Manifest }
if ($NoMotd) { $args += '-NoMotd' }
& $target @args

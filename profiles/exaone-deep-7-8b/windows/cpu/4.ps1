# C10 profile step 4 — Hard Disk Gate
# Model: exaone-deep-7-8b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] exaone-deep-7-8b / windows/cpu — Hard Disk Gate"

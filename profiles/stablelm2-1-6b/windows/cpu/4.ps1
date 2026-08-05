# C10 profile step 4 — Hard Disk Gate
# Model: stablelm2-1-6b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] stablelm2-1-6b / windows/cpu — Hard Disk Gate"

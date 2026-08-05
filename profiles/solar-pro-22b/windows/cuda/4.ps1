# C10 profile step 4 — Hard Disk Gate
# Model: solar-pro-22b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] solar-pro-22b / windows/cuda — Hard Disk Gate"

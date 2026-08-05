# C10 profile step 3 — Deployment Lane
# Model: devstral-small-2-24b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] devstral-small-2-24b / windows/cuda — Deployment Lane"

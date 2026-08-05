# C10 profile step 3 — Deployment Lane
# Model: granite-embedding-30m  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] granite-embedding-30m / windows/cpu — Deployment Lane"

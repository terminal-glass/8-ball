# C10 profile step 3 — Deployment Lane
# Model: snowflake-arctic-embed-33m  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] snowflake-arctic-embed-33m / windows/cuda — Deployment Lane"

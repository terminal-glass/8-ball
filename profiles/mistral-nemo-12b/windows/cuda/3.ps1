# C10 profile step 3 — Deployment Lane
# Model: mistral-nemo-12b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] mistral-nemo-12b / windows/cuda — Deployment Lane"

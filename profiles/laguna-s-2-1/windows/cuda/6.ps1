# C10 profile step 6 — CPU Gate
# Model: laguna-s-2-1  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '6'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] laguna-s-2-1 / windows/cuda — CPU Gate"

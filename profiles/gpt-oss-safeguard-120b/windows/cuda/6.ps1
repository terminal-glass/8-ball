# C10 profile step 6 — CPU Gate
# Model: gpt-oss-safeguard-120b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '6'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] gpt-oss-safeguard-120b / windows/cuda — CPU Gate"

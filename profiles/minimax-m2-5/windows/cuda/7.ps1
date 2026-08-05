# C10 profile step 7 — GPU Gate
# Model: minimax-m2-5  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '7'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] minimax-m2-5 / windows/cuda — GPU Gate"

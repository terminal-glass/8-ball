# C10 profile step 5 — RAM Gate
# Model: laguna-xs-2  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '5'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] laguna-xs-2 / windows/cuda — RAM Gate"

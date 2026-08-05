# C10 profile step 5 — RAM Gate
# Model: nous-hermes2-mixtral  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '5'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] nous-hermes2-mixtral / windows/cuda — RAM Gate"

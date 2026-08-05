# C10 profile step 4 — Hard Disk Gate
# Model: minicpm-v4-6  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] minicpm-v4-6 / windows/cuda — Hard Disk Gate"

# C10 profile step 4 — Hard Disk Gate
# Model: kimi-k2-7-code  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] kimi-k2-7-code / windows/cuda — Hard Disk Gate"

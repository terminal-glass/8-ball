# C10 profile step 7 — GPU Gate
# Model: qwen2-5-coder-0-5b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '7'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] qwen2-5-coder-0-5b / windows/cuda — GPU Gate"

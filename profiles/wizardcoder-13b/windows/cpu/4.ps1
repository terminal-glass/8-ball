# C10 profile step 4 — Hard Disk Gate
# Model: wizardcoder-13b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] wizardcoder-13b / windows/cpu — Hard Disk Gate"

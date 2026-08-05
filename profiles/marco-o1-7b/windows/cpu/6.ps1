# C10 profile step 6 — CPU Gate
# Model: marco-o1-7b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '6'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] marco-o1-7b / windows/cpu — CPU Gate"

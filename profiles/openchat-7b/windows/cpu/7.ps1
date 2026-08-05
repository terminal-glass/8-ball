# C10 profile step 7 — GPU Gate
# Model: openchat-7b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '7'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] openchat-7b / windows/cpu — GPU Gate"

# C10 profile step 3 — Deployment Lane
# Model: gemma4-26b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] gemma4-26b / windows/cpu — Deployment Lane"

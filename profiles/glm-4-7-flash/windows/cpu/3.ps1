# C10 profile step 3 — Deployment Lane
# Model: glm-4-7-flash  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] glm-4-7-flash / windows/cpu — Deployment Lane"

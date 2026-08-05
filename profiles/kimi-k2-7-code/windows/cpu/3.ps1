# C10 profile step 3 — Deployment Lane
# Model: kimi-k2-7-code  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '3'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] kimi-k2-7-code / windows/cpu — Deployment Lane"

# C10 profile step 7 — GPU Gate
# Model: north-mini-code-1-0  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '7'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] north-mini-code-1-0 / windows/cpu — GPU Gate"

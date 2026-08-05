# C10 profile step 5 — RAM Gate
# Model: gpt-oss-120b  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '5'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] gpt-oss-120b / windows/cpu — RAM Gate"

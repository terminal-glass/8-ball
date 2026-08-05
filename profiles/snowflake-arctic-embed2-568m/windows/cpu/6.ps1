# C10 profile step 6 — CPU Gate
# Model: snowflake-arctic-embed2-568m  Lane: windows/cpu
$ErrorActionPreference = 'Stop'
$ProfileStep = '6'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] snowflake-arctic-embed2-568m / windows/cpu — CPU Gate"

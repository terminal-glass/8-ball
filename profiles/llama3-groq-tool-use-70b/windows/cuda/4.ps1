# C10 profile step 4 — Hard Disk Gate
# Model: llama3-groq-tool-use-70b  Lane: windows/cuda
$ErrorActionPreference = 'Stop'
$ProfileStep = '4'
$LaneJson = Join-Path $PSScriptRoot 'lane.json'
$ProfileSizes = Join-Path $PSScriptRoot 'profile-sizes.csv'
if (-not (Test-Path $LaneJson)) { throw "Missing lane metadata: $LaneJson" }
Write-Host "[profile-step-$ProfileStep] llama3-groq-tool-use-70b / windows/cuda — Hard Disk Gate"

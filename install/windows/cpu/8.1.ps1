# 8.1.ps1 — public 8-BALL installer lane script (Windows / PowerShell)
# Lane: windows/cpu (windows-cpu)
$ErrorActionPreference = 'Stop'
$EIGHTBALL_INSTALL_LANE = 'windows/cpu'
$EIGHTBALL_LANE_ID = 'windows-cpu'
Write-Host '8-BALL Windows installer lane is metadata-only in this repository.'
Write-Host 'Use profiles/<model>/$EIGHTBALL_INSTALL_LANE/ for AGENTS-backed fit data.'
Write-Host 'Full Windows installer execution is not yet available in trial payloads.'
exit 1

# Shared Windows installer helpers for 8-BALL public trial lanes (C10.2-3).
#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

$script:DefaultOllamaApi = 'http://127.0.0.1:11434'
$script:OllamaWindowsDocsUrl = 'https://docs.ollama.com/windows'
$script:MinWindowsBuild = 19045

function Write-WinLog {
    param([string]$Message)
    $prefix = if ($script:WinLogPrefix) { $script:WinLogPrefix } else { 'windows' }
    Write-Host "[$prefix] $Message"
}

function Assert-NonElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '8-BALL Windows installers must run as your normal user account, not elevated as Administrator. Re-run without elevation.'
    }
}

function Test-IsWslEnvironment {
    if ($env:WSL_DISTRO_NAME) { return $true }
    return $false
}

function Assert-NativeWindows {
    if (Test-IsWslEnvironment) {
        throw @"
WSL is not a native Windows install target for 8-BALL.
Use the Ubuntu lane instead: install/ubuntu/cpu/trial-install.sh
"@
    }
    if ($env:OS -ne 'Windows_NT' -and -not $IsWindows) {
        throw "This installer supports native Windows only. Detected OS=$($env:OS)"
    }
}

function Assert-WindowsRelease {
    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $build = [int]$os.BuildNumber
        if ($build -lt $script:MinWindowsBuild) {
            throw "Windows 10 22H2 (build $script:MinWindowsBuild)+ is required. Detected build $build."
        }
    }
    catch {
        if ($_.Exception.Message -match 'Windows 10') { throw }
        throw 'Unable to verify Windows release. Windows 10 22H2+ is required.'
    }
}

function Resolve-EightballRoot {
    $defaultRoot = Join-Path $env:LOCALAPPDATA '8-BALL'
    $root = if ($env:EIGHTBALL_ROOT) { $env:EIGHTBALL_ROOT } else { $defaultRoot }

    if (-not [System.IO.Path]::IsPathRooted($root)) {
        throw 'EIGHTBALL_ROOT must be an absolute path.'
    }
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Path $root -Force | Out-Null
    }
    $item = Get-Item -LiteralPath $root
    if (-not $item.PSIsContainer) {
        throw "Install state root is not a directory: $root"
    }
    try {
        $probe = Join-Path $root '.write-probe'
        [System.IO.File]::WriteAllText($probe, 'ok')
        Remove-Item -LiteralPath $probe -Force
    }
    catch {
        throw "Install state root is not writable by the current user: $root"
    }

    $env:EIGHTBALL_ROOT = $root
    $script:LogFile = Join-Path $root '8ball-trial.log'
    $script:ObservationFile = Join-Path $root 'runtime-observation.json'
    $script:CudaObservationFile = Join-Path $root 'cuda-runtime-observation.json'
    $script:ResultJson = Join-Path $root '8ball-result.json'
    $script:ResultFile = Join-Path $root '8ball-result.txt'
    $script:StatusScript = Join-Path $root 'bin\8ball-status.ps1'
}

function Assert-LoopbackOllamaApi {
    $api = if ($env:OLLAMA_API) { $env:OLLAMA_API } else { $script:DefaultOllamaApi }
    $uri = [Uri]$api
    if ($uri.Scheme -ne 'http') {
        throw "OLLAMA_API must use http loopback. Refusing: $api"
    }
    $hostName = $uri.Host.ToLowerInvariant()
    if ($hostName -notin @('127.0.0.1', 'localhost', '[::1]')) {
        throw "OLLAMA_API must use a loopback address (127.0.0.1 or localhost). Refusing: $api"
    }
    $env:OLLAMA_API = $api
    $script:OllamaApi = $api
}

function Assert-ModelTag {
    param([string]$Tag)
    if ($Tag -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$') {
        throw "Invalid Ollama model tag: $Tag"
    }
}

function Find-RepoRoot {
    param([string]$StartDir = (Get-Location).Path)
    $dir = $StartDir
    while ($dir) {
        $collector = Join-Path $dir 'AGENTS\data-science\profile-mapping\windows\collector-example.ps1'
        if (Test-Path -LiteralPath $collector) { return $dir }
        $parent = Split-Path -Parent $dir
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

function Get-InstallPathFreeDiskGb {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    try {
        $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
        $root = [System.IO.Path]::GetPathRoot($resolved.Path)
        if ([string]::IsNullOrWhiteSpace($root)) { return $null }
        $driveId = $root.TrimEnd('\')
        $disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter ("DeviceID='{0}'" -f $driveId) -ErrorAction SilentlyContinue
        if ($null -eq $disk -or $null -eq $disk.FreeSpace) { return $null }
        return [int][math]::Floor([double]$disk.FreeSpace / 1GB)
    }
    catch { return $null }
}

function Write-WindowsObservationFallback {
    $record = [ordered]@{
        EIGHTBALL_OS_FAMILY = 'windows'
        EIGHTBALL_RAM_MB = $null
        EIGHTBALL_CPU_THREADS = $null
        EIGHTBALL_DISK_FREE_GB = $null
        windows_architecture = 'unknown'
        windows_cuda_lane_eligible = 'unknown'
        windows_gpu_vram_source = 'unknown'
        target_lane = 'unknown'
        native_windows_lane_eligible = $true
    }
    $system = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction SilentlyContinue
    if ($system -and $system.TotalPhysicalMemory) {
        $record.EIGHTBALL_RAM_MB = [int][math]::Round([double]$system.TotalPhysicalMemory / 1MB)
    }
    $logical = 0
    foreach ($cpu in @(Get-CimInstance -ClassName Win32_Processor -ErrorAction SilentlyContinue)) {
        if ($cpu.NumberOfLogicalProcessors) { $logical += [int]$cpu.NumberOfLogicalProcessors }
    }
    if ($logical -gt 0) { $record.EIGHTBALL_CPU_THREADS = $logical }
    $diskFree = Get-InstallPathFreeDiskGb -Path $env:EIGHTBALL_ROOT
    if ($null -ne $diskFree) { $record.EIGHTBALL_DISK_FREE_GB = $diskFree }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $record.windows_architecture = 'arm64' }
    elseif ($env:PROCESSOR_ARCHITECTURE -match '64') { $record.windows_architecture = 'x64' }
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $record.windows_cuda_lane_eligible = 'unknown'
    }
    else {
        $record.windows_cuda_lane_eligible = 'no'
    }
    $record.target_lane = 'windows/cpu'
    ($record | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $script:ObservationFile -Encoding UTF8
}

function Get-OllamaNvidiaSupportInline {
    param(
        [string]$ComputeCapability,
        [string]$DriverVersion
    )
    if ([string]::IsNullOrWhiteSpace($ComputeCapability) -or [string]::IsNullOrWhiteSpace($DriverVersion)) {
        return 'unknown'
    }
    $cc = 0.0
    if (-not [double]::TryParse(($ComputeCapability -replace ',', '.'), [ref]$cc)) { return 'unknown' }
    $driverMajor = $null
    if ($DriverVersion -match '^(\d+)') { $driverMajor = [int]$Matches[1] } else { return 'unknown' }
    if ($cc -lt 5.0) { return 'unsupported' }
    if ($driverMajor -lt 550) { return 'unsupported' }
    if ($cc -ge 5.0 -and $cc -le 6.2 -and $driverMajor -lt 570) { return 'unsupported' }
    return 'supported'
}

function Get-CudaEvidenceReadOnly {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{
            observation_status = 'unavailable'
            devices = @()
        }
    }
    $csv = & nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits 2>$null
    if (-not $csv) {
        return [pscustomobject]@{ observation_status = 'unavailable'; devices = @() }
    }
    $devices = @()
    foreach ($line in @($csv)) {
        $parts = $line -split ',\s*'
        if ($parts.Count -lt 6) { continue }
        $support = Get-OllamaNvidiaSupportInline -ComputeCapability $parts[5] -DriverVersion $parts[3]
        $devices += [ordered]@{
            gpu_index = [int]$parts[0]
            gpu_uuid = $parts[1]
            gpu_name = $parts[2]
            driver_version = $parts[3]
            gpu_memory_mb = [int]$parts[4]
            compute_capability = $parts[5]
            ollama_nvidia_support = $support
        }
    }
    return [pscustomobject]@{
        os_family = 'windows'
        observation_status = if ($devices.Count -gt 0) { 'available' } else { 'unavailable' }
        devices = $devices
        cuda_runtime_ready = ($devices.Count -gt 0)
    }
}

function Resolve-WindowsTrialLaneDispatch {
    $cuda = Get-CudaEvidenceReadOnly
    if ($cuda.observation_status -ne 'available' -or -not $cuda.devices -or $cuda.devices.Count -eq 0) {
        return 'cpu'
    }
    foreach ($device in $cuda.devices) {
        if ($device.ollama_nvidia_support -eq 'unsupported') {
            return 'cpu'
        }
    }
    return 'cuda'
}

function Write-CudaObservationFallback {
    $payload = Get-CudaEvidenceReadOnly
    ($payload | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $script:CudaObservationFile -Encoding UTF8
    return $payload
}

function Write-WindowsObservation {
    $repoRoot = Find-RepoRoot -StartDir $PSScriptRoot
    $collector = $null
    if ($repoRoot) {
        $collector = Join-Path $repoRoot 'AGENTS\data-science\profile-mapping\windows\collector-example.ps1'
    }
    if ($collector -and (Test-Path -LiteralPath $collector)) {
        $json = & $collector -InstallPath $env:EIGHTBALL_ROOT
        $json | Set-Content -LiteralPath $script:ObservationFile -Encoding UTF8
        return
    }
    Write-WindowsObservationFallback
}

function Write-CudaObservation {
    $repoRoot = Find-RepoRoot -StartDir $PSScriptRoot
    if ($repoRoot) {
        $observe = Join-Path $repoRoot 'scripts\cuda-observe-windows.ps1'
        if (Test-Path -LiteralPath $observe) {
            $json = & $observe -OsFamily windows -ProviderContext ''
            $json | Set-Content -LiteralPath $script:CudaObservationFile -Encoding UTF8
            return ($json | ConvertFrom-Json)
        }
    }
    return Write-CudaObservationFallback
}

function Assert-CudaLaneEligibility {
    $cuda = Write-CudaObservation
    if ($cuda.observation_status -ne 'available' -or -not $cuda.devices -or $cuda.devices.Count -eq 0) {
        throw @"
This CUDA lane requires working nvidia-smi evidence.
8-BALL does not install NVIDIA drivers.
Use the CPU lane instead: install/windows/cpu/trial-install.ps1
"@
    }
    foreach ($device in $cuda.devices) {
        if ($device.ollama_nvidia_support -eq 'unsupported') {
            throw @"
NVIDIA software on this host is outside the supported Ollama policy for CUDA.
8-BALL does not install drivers or CUDA SDKs.
Use the CPU lane instead: install/windows/cpu/trial-install.ps1
"@
        }
    }
}

function Get-ManualOllamaInstallMessage {
    return @"
Ollama for Windows is not installed.

Manual steps:
1. Download the official Ollama Windows installer from $script:OllamaWindowsDocsUrl
2. Run OllamaSetup.exe and complete setup as your normal user
3. Launch Ollama once and confirm the tray app is running
4. Re-run this installer without elevation

The installer does not download or run OllamaSetup.exe automatically.
"@
}

function Find-OllamaExecutable {
    $candidates = @()
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe')
    }
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $candidates += $cmd.Source }
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            $script:OllamaExe = $path
            return $path
        }
    }
    return $null
}

function Assert-OllamaCli {
  if (-not (Find-OllamaExecutable)) {
        throw (Get-ManualOllamaInstallMessage)
    }
}

function Wait-OllamaApi {
    $deadline = (Get-Date).AddMinutes(2)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-RestMethod -Uri "$($script:OllamaApi)/api/tags" -Method Get -TimeoutSec 5
            Write-WinLog "Ollama API is responding at $($script:OllamaApi)"
            return
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw @"
Ollama API did not become ready at $($script:OllamaApi).
Launch Ollama from the Start menu, then re-run this installer.
"@
}

function Get-RamGiBFromObservation {
    $obs = Get-Content -LiteralPath $script:ObservationFile -Raw | ConvertFrom-Json
    $mb = $obs.EIGHTBALL_RAM_MB
    if ($null -eq $mb -or [int]$mb -le 0) { return 0 }
    return [int]([math]::Floor([double]$mb / 1024))
}

function Get-FreeDiskGiBFromObservation {
    $obs = Get-Content -LiteralPath $script:ObservationFile -Raw | ConvertFrom-Json
    $gb = $obs.EIGHTBALL_DISK_FREE_GB
    if ($null -eq $gb -or [int]$gb -le 0) { return 0 }
    return [int]$gb
}

function Get-CandidateLadder {
    param([int]$RamGiB)
    if ($RamGiB -ge 24) { return @('qwen3:14b', 'qwen3:8b', 'qwen3:4b', 'qwen3:1.7b', 'qwen3:0.6b') }
    if ($RamGiB -ge 12) { return @('qwen3:8b', 'qwen3:4b', 'qwen3:1.7b', 'qwen3:0.6b') }
    if ($RamGiB -ge 8) { return @('qwen3:4b', 'qwen3:1.7b', 'qwen3:0.6b') }
    if ($RamGiB -ge 4) { return @('qwen3:1.7b', 'qwen3:0.6b') }
    return @('qwen3:0.6b')
}

function Get-DiskGuardGiB {
    param([string]$Model)
    switch ($Model) {
        'qwen3:14b' { return 14 }
        'qwen3:8b' { return 9 }
        'qwen3:4b' { return 6 }
        'qwen3:1.7b' { return 4 }
        'qwen3:0.6b' { return 3 }
        default { return 0 }
    }
}

function Get-FilteredCandidates {
    param(
        [int]$RamGiB,
        [int]$FreeDiskGiB
    )
    $out = @()
    foreach ($candidate in (Get-CandidateLadder -RamGiB $RamGiB)) {
        if ($FreeDiskGiB -ge (Get-DiskGuardGiB -Model $candidate)) {
            $out += $candidate
        }
    }
    return $out
}

function Get-InstalledModels {
    $exe = Find-OllamaExecutable
    if (-not $exe) { return @() }
    $lines = & $exe list 2>$null
    if (-not $lines) { return @() }
    $models = @()
    foreach ($line in $lines | Select-Object -Skip 1) {
        if ($line -match '^\s*(\S+)') { $models += $Matches[1] }
    }
    return $models
}

function Save-ModelsBeforeTrial {
    Get-InstalledModels | Set-Content -LiteralPath (Join-Path $env:EIGHTBALL_ROOT '.models-before-trial') -Encoding ASCII
}

function Test-ModelWasInstalledBefore {
    param([string]$Model)
    $path = Join-Path $env:EIGHTBALL_ROOT '.models-before-trial'
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    return (Select-String -LiteralPath $path -Pattern "^$([regex]::Escape($Model))$" -Quiet)
}

function Test-ModelGenerate {
    param([string]$Model)
    $body = @{
        model = $Model
        prompt = 'Reply with only: 8-BALL READY'
        stream = $false
    } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Uri "$($script:OllamaApi)/api/generate" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 120
    return ($response.response -match '(?i)8-BALL READY')
}

function Remove-ModelIfNew {
    param([string]$Model)
    if (Test-ModelWasInstalledBefore -Model $Model) {
        Write-WinLog "Keeping pre-existing model $Model"
        return
    }
    Write-WinLog "Removing newly pulled model that failed verification: $Model"
    $exe = Find-OllamaExecutable
    if ($exe) { & $exe rm $Model 2>$null | Out-Null }
}

function Write-ResultRecord {
    param(
        [string]$Model,
        [string]$Status,
        [string]$Acceleration
    )
    $obs = Get-Content -LiteralPath $script:ObservationFile -Raw | ConvertFrom-Json
  $cudaObs = $null
    if (Test-Path -LiteralPath $script:CudaObservationFile) {
        $cudaObs = Get-Content -LiteralPath $script:CudaObservationFile -Raw | ConvertFrom-Json
    }
    $payload = [ordered]@{
        selected_model = $Model
        test_status = $Status
        acceleration = $Acceleration
        lane = $script:WinTargetLane
        ollama_api = $script:OllamaApi
        timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        observation = [ordered]@{
            architecture = $obs.windows_architecture
            physical_memory_mb = $obs.EIGHTBALL_RAM_MB
            free_install_disk_gb = $obs.EIGHTBALL_DISK_FREE_GB
            cpu_threads = $obs.EIGHTBALL_CPU_THREADS
            windows_gpu_vram_source = $obs.windows_gpu_vram_source
            target_lane = $obs.target_lane
            cuda_observation_status = if ($cudaObs) { $cudaObs.observation_status } else { 'not_applicable' }
        }
    }
    ($payload | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $script:ResultJson -Encoding UTF8
    $lines = @(
        "Model: $Model",
        "Install lane: $($script:WinTargetLane)",
        "Acceleration: $Acceleration",
        "Model test: $Status",
        "Ollama API: $($script:OllamaApi)",
        "Architecture: $($obs.windows_architecture)",
        "RAM MB: $($obs.EIGHTBALL_RAM_MB)",
        "Free disk GB: $($obs.EIGHTBALL_DISK_FREE_GB)",
        "CPU threads: $($obs.EIGHTBALL_CPU_THREADS)",
        "GPU VRAM source: $($obs.windows_gpu_vram_source)",
        'Jets status: OPTIONAL_AFTER_SIGNIN'
    )
    $lines | Set-Content -LiteralPath $script:ResultFile -Encoding UTF8
}

function Write-StatusHelper {
    $binDir = Join-Path $env:EIGHTBALL_ROOT 'bin'
    if (-not (Test-Path -LiteralPath $binDir)) {
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    }
    $content = @"
# 8-BALL status helper
`$Root = '$($env:EIGHTBALL_ROOT)'
`$Result = Join-Path `$Root '8ball-result.txt'
`$Api = '$($script:OllamaApi)'
Write-Host '8-BALL status'
Write-Host "State root: `$Root"
Write-Host "Result file: `$Result"
if (Test-Path -LiteralPath `$Result) { Get-Content -LiteralPath `$Result } else { Write-Host 'No result file yet. Run trial-install.ps1 first.' }
Write-Host "Local endpoint: `$Api"
Write-Host 'Jets: optional; run ollama signin separately if you want cloud models.'
Write-Host "Status helper: $($script:StatusScript)"
"@
    $content | Set-Content -LiteralPath $script:StatusScript -Encoding UTF8
}

function Invoke-TrialStep {
    param(
        [string]$Label,
        [string]$ScriptPath,
        [string[]]$Args = @()
    )
    Write-WinLog $Label
    & $ScriptPath @Args 2>&1 | Tee-Object -FilePath $script:LogFile -Append | Out-Null
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Step failed: $Label (exit $LASTEXITCODE)"
    }
}

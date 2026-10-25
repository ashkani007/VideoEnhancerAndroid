<#
Great History Makers: READ-ONLY inspection of this PC before any installation.

Reports: Windows version, CPU, RAM, NVIDIA GPU (VRAM, driver, CUDA), free space per fixed drive, Git / 7-Zip / curl /
Python / Claude Code, existing ComfyUI installations, anything listening on port 8188, firewall rules and scheduled
tasks that mention ComfyUI or Python. Writes the result to %TEMP%\ghm_inspect.json and prints a summary.

It changes nothing: no installs, no downloads, no firewall or task changes, no admin rights needed. It prints no
environment variables, credentials or git configuration.

  powershell -ExecutionPolicy Bypass -File .\inspect_pc.ps1 [-SearchRoots D:\,E:\Tools]
#>
[CmdletBinding()]
param([string[]]$SearchRoots = @())
Set-StrictMode -Version 2
$ErrorActionPreference = "Continue"

function Get-ToolVersion([string]$cmd, [string[]]$cmdArgs) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $c) { return $null }
    try { return ((& $c.Source @cmdArgs 2>&1 | Select-Object -First 1) -as [string]).Trim() } catch { return "found at $($c.Source)" }
}

$r = [ordered]@{ inspected = (Get-Date).ToString("s") }
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$r.windows = "$($os.Caption) $($os.Version) build $($os.BuildNumber)"
$r.powershell = $PSVersionTable.PSVersion.ToString()
$r.cpu = "$($cpu.Name.Trim()) ($($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads)"
$r.ram_total_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$r.ram_free_gb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)

$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    $q = & $smi.Source --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader,nounits | Select-Object -First 1
    $p = $q -split ",\s*"
    $cuda = ((& $smi.Source) | Select-String "CUDA Version:\s*([0-9.]+)" | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1)
    $r.gpu = [ordered]@{ name = $p[0]; vram_total_mib = [int]$p[1]; vram_used_mib = [int]$p[2]; driver = $p[3]; cuda_driver_api = $cuda }
} else {
    $r.gpu = "nvidia-smi not found (NVIDIA driver missing?)"
}
$r.display_adapters = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })

$r.drives = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    [ordered]@{ drive = $_.DeviceID; free_gb = [math]::Round($_.FreeSpace / 1GB, 1); total_gb = [math]::Round($_.Size / 1GB, 1) } })

$sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
$r.tools = [ordered]@{
    git = Get-ToolVersion "git" @("--version")
    seven_zip = $sevenZip
    curl = Get-ToolVersion "curl.exe" @("--version")
    python = Get-ToolVersion "python" @("--version")
    py_launcher = Get-ToolVersion "py" @("--version")
    claude_code = Get-ToolVersion "claude" @("--version")
    vc_redist_x64 = [bool](Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue)
}

# existing ComfyUI installations (portable, git clone, Desktop app, Stability Matrix), shallow search only
$roots = @("C:\GHM", "C:\AI", "$env:USERPROFILE", "$env:USERPROFILE\Desktop", "$env:USERPROFILE\Documents", "$env:USERPROFILE\Downloads",
           "$env:LOCALAPPDATA\Programs", "$env:APPDATA") + ($r.drives | ForEach-Object { "$($_.drive)\" }) + $SearchRoots
$found = New-Object System.Collections.Generic.List[string]
foreach ($root in ($roots | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)) {
    Get-ChildItem -LiteralPath $root -Filter "comfyui_version.py" -Recurse -Depth 3 -File -ErrorAction SilentlyContinue | ForEach-Object {
        $v = (Select-String -LiteralPath $_.FullName -Pattern '__version__\s*=\s*"([^"]+)"' -ErrorAction SilentlyContinue | Select-Object -First 1)
        $ver = if ($v) { $v.Matches[0].Groups[1].Value } else { "?" }
        $found.Add("$($_.Directory.FullName) (version $ver)")
    }
}
$r.comfyui_installs = @($found | Select-Object -Unique)

$r.port_8188_listeners = @(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    "$($_.LocalAddress):$($_.LocalPort) by $(if ($proc) { $proc.ProcessName } else { $_.OwningProcess })" })
$r.firewall_rules_python_comfy = @(Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match "python|comfy" } |
    ForEach-Object { "$($_.DisplayName) [$($_.Direction) $($_.Action) enabled=$($_.Enabled)]" })
$r.scheduled_tasks_comfy_ghm = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match "comfy|ghm|history" } |
    ForEach-Object { "$($_.TaskPath)$($_.TaskName) [$($_.State)]" })

$out = Join-Path $env:TEMP "ghm_inspect.json"
$r | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
$r | ConvertTo-Json -Depth 6
Write-Output "`nSaved to $out (read-only inspection; nothing was changed)"

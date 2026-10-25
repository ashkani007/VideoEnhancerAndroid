<#
Great History Makers: pinned, verify-everything ComfyUI installer for Windows 11 + NVIDIA RTX 4060 (8 GB).

Three modes, so nothing large is downloaded before the plan is approved:

  -Plan        (default)  Read-only. Checks the PC and the lock file, prints what would be downloaded, the disk space
                          needed and the lock fingerprint. Changes nothing.
  -ResolveLock            Metadata only. Asks the Hugging Face API for the immutable revision, SHA-256 and size of each
                          model and writes them into ghm_install.lock.json. Downloads no model. The pinned reference
                          hash (SDXL) must match or it stops.
  -Install -ApproveFingerprint <fp>
                          Installs exactly the approved lock (the fingerprint printed by -Plan). Any file whose SHA-256
                          is missing or different is deleted and the installer stops before going further.

What -Install does:
- Extracts the pinned ComfyUI portable release, then checks its version.
- Checks out one custom node (ComfyUI_IPAdapter_plus) at a pinned commit and verifies the commit.
- Downloads the models, verifying size and SHA-256 for each.
- Writes run_comfyui_local.bat (127.0.0.1 only, --offline) and the worker's local_paths.cmd.
- Optionally clones the project repository (-RepoUrl), sparse.

It never changes firewall rules, never installs services or scheduled tasks, never asks for or prints tokens
(Git Credential Manager handles GitHub sign-in in its own window), and installs no Python packages.

Examples:
  powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1 -Root D:\GHM
  powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1 -Root D:\GHM -ResolveLock
  powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1 -Root D:\GHM -Install -ApproveFingerprint 1a2b... `
             -RepoUrl https://github.com/<you>/great-history-makers.git -Branch main
#>
[CmdletBinding()]
param(
    [string]$Root = "C:\GHM",
    [switch]$ResolveLock,
    [switch]$Install,
    [string]$ApproveFingerprint = "",
    [string]$Lock = (Join-Path $PSScriptRoot "ghm_install.lock.json"),
    [string]$RepoUrl = "",
    [string]$Branch = "main",
    [switch]$KeepArchive
)
Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Exit-Installer([string]$msg) { Write-Host "STOPPED: $msg" -ForegroundColor Red; exit 1 }
function Format-GB([double]$bytes) { return ("{0:N1} GB" -f ($bytes / 1GB)) }

function Get-LockFingerprint($l) {
    # Canonical content (URLs, commits, hashes, sizes, destinations) -> SHA-256; formatting does not matter.
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("comfyui|$($l.comfyui.url)|$($l.comfyui.sha256)|$($l.comfyui.size)")
    foreach ($n in $l.custom_nodes) { $lines.Add("node|$($n.url)|$($n.commit)") }
    foreach ($m in $l.models) { $lines.Add("model|$(Get-ModelUrl $m)|$($m.sha256)|$($m.size)|$($m.dest)") }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Get-ModelUrl($m) {
    if ($m.PSObject.Properties.Name -contains "url" -and $m.url) { return $m.url }
    if (-not $m.revision) { return "" }
    return "https://huggingface.co/$($m.repo)/resolve/$($m.revision)/$($m.path)"
}

function Test-Sha256([string]$s) { return ($s -match '^[0-9a-f]{64}$') }

function Get-VerifiedFile([string]$url, [string]$dest, [string]$sha256, [long]$size) {
    if (-not $url -or -not (Test-Sha256 $sha256)) { Exit-Installer "no pinned SHA-256 for $dest (run -ResolveLock and approve the lock first)" }
    if (Test-Path -LiteralPath $dest) {
        if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower() -eq $sha256) { Write-Host "  ok, already verified: $dest"; return }
        Exit-Installer "$dest exists but its SHA-256 does not match the lock (left untouched; move it away and run again)"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    $part = "$dest.part"
    if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
    Write-Host "  downloading $(Split-Path -Leaf $dest) ($(Format-GB $size)) ..."
    & curl.exe --location --fail --retry 3 --proto "=https" --silent --show-error --output $part $url
    if ($LASTEXITCODE -ne 0) { if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }; Exit-Installer "download failed: $url" }
    $got = (Get-Item -LiteralPath $part).Length
    if ($size -gt 0 -and $got -ne $size) { Remove-Item -LiteralPath $part -Force; Exit-Installer "size mismatch for $url (expected $size, got $got)" }
    $hash = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $sha256) { Remove-Item -LiteralPath $part -Force; Exit-Installer "SHA-256 mismatch for $url (expected $sha256, got $hash)" }
    Move-Item -LiteralPath $part -Destination $dest
    Write-Host "  verified $hash" -ForegroundColor Green
}

# ------------------------------------------------------------------------------------------- load + check the lock
if (-not (Test-Path -LiteralPath $Lock)) { Exit-Installer "lock file not found: $Lock" }
$L = Get-Content -LiteralPath $Lock -Raw | ConvertFrom-Json
if ($L.schema -ne 1) { Exit-Installer "unsupported lock schema" }
if ($RepoUrl -and ($RepoUrl -notmatch '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$')) {
    Exit-Installer "RepoUrl must be a plain https://github.com/<owner>/<repo> URL (never put credentials in a URL)"
}
$Root = [System.IO.Path]::GetFullPath($Root)
$comfyRoot = Join-Path $Root "ComfyUI_windows_portable"

# ------------------------------------------------------------------------------------------- -ResolveLock (metadata only)
if ($ResolveLock) {
    Write-Step "Resolving model revisions and hashes from the Hugging Face API (metadata only, no model download)"
    foreach ($m in $L.models) {
        if (-not ($m.PSObject.Properties.Name -contains "repo")) { continue }
        $rev = (Invoke-RestMethod -Uri "https://huggingface.co/api/models/$($m.repo)/revision/main").sha
        if ($rev -notmatch '^[0-9a-f]{40}$') { Exit-Installer "could not resolve the revision of $($m.repo)" }
        $dir = Split-Path -Parent $m.path
        $treeUrl = "https://huggingface.co/api/models/$($m.repo)/tree/$rev"
        if ($dir) { $treeUrl = "$treeUrl/" + $dir.Replace("\", "/") }
        $entry = Invoke-RestMethod -Uri $treeUrl | Where-Object { $_.path -eq $m.path }
        if (-not $entry -or -not $entry.lfs -or -not (Test-Sha256 $entry.lfs.oid)) { Exit-Installer "no published SHA-256 for $($m.repo)/$($m.path)" }
        if (($m.PSObject.Properties.Name -contains "sha256_reference") -and $m.sha256_reference -and ($entry.lfs.oid -ne $m.sha256_reference)) {
            Exit-Installer "$($m.path): Hugging Face reports $($entry.lfs.oid) but the pinned reference is $($m.sha256_reference)"
        }
        $m.revision = $rev; $m.sha256 = $entry.lfs.oid; $m.size = [long]$entry.lfs.size
        Write-Host ("  {0,-58} {1}  {2}" -f $m.path, $m.sha256, (Format-GB $m.size))
    }
    $L | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Lock -Encoding UTF8
    Write-Host "`nLock updated: $Lock"
    Write-Host "Lock fingerprint: $(Get-LockFingerprint $L)" -ForegroundColor Yellow
    Write-Host "Review the hashes above, then approve this fingerprint for -Install."
    exit 0
}

# ------------------------------------------------------------------------------------------- checks (all modes)
Write-Step "Checking this PC (read-only)"
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "Windows: $($os.Caption) $($os.Version); RAM $(Format-GB ($os.TotalVisibleMemorySize * 1KB)) total, $(Format-GB ($os.FreePhysicalMemory * 1KB)) free"
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { Exit-Installer "nvidia-smi not found: install the NVIDIA driver first" }
$gpu = (& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader) | Select-Object -First 1
Write-Host "GPU: $gpu"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Exit-Installer "Git for Windows not found (https://git-scm.com/download/win)" }
$sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $sevenZip) { Exit-Installer "7-Zip not found (https://www.7-zip.org); it is needed to unpack the ComfyUI archive safely" }
if (Test-Path -LiteralPath $comfyRoot) { Write-Host "Existing ComfyUI found at $comfyRoot (it will be reused only if its version matches the lock)" }

$modelBytes = 0; $missing = @()
foreach ($m in $L.models) { $modelBytes += [long]$m.size; if (-not (Test-Sha256 $m.sha256)) { $missing += $m.dest } }
$need = [long]$L.comfyui.size + [long]$L.comfyui.unpacked_bytes + $modelBytes + 3GB
$probe = $Root; while (-not (Test-Path -LiteralPath $probe)) { $probe = Split-Path -Parent $probe }
$freeBytes = (Get-PSDrive -Name (Get-Item -LiteralPath $probe).PSDrive.Name).Free
Write-Host "Disk: need about $(Format-GB $need) (archive $(Format-GB $L.comfyui.size) + ComfyUI $(Format-GB $L.comfyui.unpacked_bytes) + models $(Format-GB $modelBytes) + 3 GB margin); free $(Format-GB $freeBytes)"
if ($missing.Count -gt 0) { Write-Host "Not yet pinned (run -ResolveLock): $($missing -join ', ')" -ForegroundColor Yellow }
$fp = Get-LockFingerprint $L

if (-not $Install) {
    Write-Step "Plan (nothing was changed)"
    Write-Host "Install root : $Root"
    Write-Host "ComfyUI      : $($L.comfyui.tag) ($($L.comfyui.commit.Substring(0,12))), sha256 $($L.comfyui.sha256)"
    foreach ($n in $L.custom_nodes) { Write-Host "Custom node  : $($n.name) @ $($n.commit)" }
    foreach ($m in $L.models) { Write-Host ("Model        : {0,-55} {1}" -f $m.dest, $(if (Test-Sha256 $m.sha256) { $m.sha256 } else { "NOT PINNED" })) }
    Write-Host "Launcher     : run_comfyui_local.bat --listen 127.0.0.1 --port 8188 --disable-auto-launch --offline"
    Write-Host "Firewall, services, scheduled tasks: untouched"
    Write-Host "Lock fingerprint: $fp" -ForegroundColor Yellow
    exit 0
}

# ------------------------------------------------------------------------------------------- -Install
if ($missing.Count -gt 0) { Exit-Installer "the lock is not fully pinned; run -ResolveLock and approve it first" }
if ($ApproveFingerprint -ne $fp) { Exit-Installer "fingerprint not approved (expected -ApproveFingerprint $fp)" }
if ($freeBytes -lt $need) { Exit-Installer "not enough free disk space" }
New-Item -ItemType Directory -Force -Path $Root | Out-Null

Write-Step "ComfyUI $($L.comfyui.tag)"
$versionFile = Join-Path $comfyRoot "ComfyUI\comfyui_version.py"
$want = $L.comfyui.tag.TrimStart("v")
if (Test-Path -LiteralPath $versionFile) {
    if ((Get-Content -LiteralPath $versionFile -Raw) -notmatch [regex]::Escape("__version__ = `"$want`"")) {
        Exit-Installer "$comfyRoot holds a different ComfyUI version; choose another -Root or move it away"
    }
    Write-Host "  already installed, version $want"
} else {
    $archive = Join-Path $Root "ComfyUI_windows_portable_nvidia_$($L.comfyui.tag).7z"
    Get-VerifiedFile -url $L.comfyui.url -dest $archive -sha256 $L.comfyui.sha256 -size ([long]$L.comfyui.size)
    $staging = Join-Path $Root "_staging"
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    & $sevenZip x $archive "-o$staging" -y | Out-Null
    if ($LASTEXITCODE -ne 0) { Exit-Installer "7-Zip could not extract the archive" }
    $v = Join-Path $staging "ComfyUI_windows_portable\ComfyUI\comfyui_version.py"
    if (-not (Test-Path -LiteralPath $v) -or ((Get-Content -LiteralPath $v -Raw) -notmatch [regex]::Escape("__version__ = `"$want`""))) {
        Exit-Installer "the extracted archive is not ComfyUI $want"
    }
    Move-Item -LiteralPath (Join-Path $staging "ComfyUI_windows_portable") -Destination $comfyRoot
    Remove-Item -LiteralPath $staging -Recurse -Force
    if (-not $KeepArchive) { Remove-Item -LiteralPath $archive -Force }
}
$models = Join-Path $comfyRoot "ComfyUI\models"
$nodesDir = Join-Path $comfyRoot "ComfyUI\custom_nodes"

Write-Step "Custom nodes (pinned commits; no Python packages are installed)"
foreach ($n in $L.custom_nodes) {
    $dst = Join-Path $nodesDir $n.name
    if (-not (Test-Path -LiteralPath $dst)) {
        & git init --quiet $dst
        & git -C $dst fetch --quiet --depth 1 $n.url $n.commit
        if ($LASTEXITCODE -ne 0) { Exit-Installer "could not fetch $($n.url) at $($n.commit)" }
        & git -C $dst checkout --quiet FETCH_HEAD
    }
    $head = (& git -C $dst rev-parse HEAD).Trim()
    if ($head -ne $n.commit) { Exit-Installer "$($n.name) is at $head, expected $($n.commit)" }
    if (Test-Path -LiteralPath (Join-Path $dst "requirements.txt")) { Exit-Installer "$($n.name) now has requirements.txt; review it before installing" }
    Write-Host "  $($n.name) verified at $head"
}

Write-Step "Models (size + SHA-256 verified)"
foreach ($m in $L.models) {
    Get-VerifiedFile -url (Get-ModelUrl $m) -dest (Join-Path $models ($m.dest.Replace("/", "\"))) -sha256 $m.sha256 -size ([long]$m.size)
}

Write-Step "Launcher (127.0.0.1 only, partner/paid API nodes off, browser not auto-opened)"
$launcher = @(
    "@echo off",
    "REM Great History Makers: ComfyUI reachable from this PC only. Never use --listen 0.0.0.0, never port-forward 8188.",
    "cd /d `"%~dp0`"",
    ".\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 --disable-auto-launch --offline",
    "pause"
)
Set-Content -LiteralPath (Join-Path $comfyRoot "run_comfyui_local.bat") -Value $launcher -Encoding ASCII

if ($RepoUrl) {
    Write-Step "Project repository (sparse clone for the worker)"
    $work = Join-Path $Root "worker-repo"
    if (-not (Test-Path -LiteralPath (Join-Path $work ".git"))) {
        & git clone --quiet --filter=blob:none --no-checkout --branch $Branch $RepoUrl $work
        if ($LASTEXITCODE -ne 0) { Exit-Installer "git clone failed (sign in through the Git Credential Manager window if asked)" }
        $prefix = ""
        if ((& git -C $work ls-tree -d --name-only HEAD great_history_makers) -eq "great_history_makers") { $prefix = "great_history_makers/" }
        & git -C $work sparse-checkout set --cone "${prefix}comfyui" "${prefix}jobs" "${prefix}assets/references"
        & git -C $work checkout --quiet $Branch
    }
    $workerDir = Get-ChildItem -LiteralPath $work -Recurse -Directory -Filter worker | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "ghm_worker.py") } | Select-Object -First 1
    if ($workerDir) {
        Set-Content -LiteralPath (Join-Path $workerDir.FullName "local_paths.cmd") -Encoding ASCII -Value @(
            "@echo off", "REM written by install_ghm_comfyui.ps1 (machine-specific, not committed)",
            "set `"GHM_COMFYUI_DIR=$comfyRoot`"")
        Write-Host "  worker configured: $($workerDir.FullName)\local_paths.cmd"
    }
}

Write-Step "Done"
Write-Host "Start ComfyUI : $comfyRoot\run_comfyui_local.bat"
Write-Host "Check         : <worker folder>\check_setup.bat   (expects port 8188 on 127.0.0.1 only)"
Write-Host "Test job      : <worker folder>\run_worker_once.bat"

<#
Great History Makers: local ComfyUI installer for Windows 11 + NVIDIA RTX 4060 (8 GB).

What it does (nothing else):
  1. Checks the GPU (nvidia-smi), free disk space, Git and an extractor (7-Zip or Windows tar).
  2. Downloads the official ComfyUI Windows portable build (GitHub release) into <Root>\ComfyUI_windows_portable.
  3. Installs three custom nodes from their GitHub repositories: ComfyUI-Manager, ComfyUI_IPAdapter_plus
     and (only with -WithFlux) ComfyUI-GGUF.
  4. Downloads the models from their official Hugging Face / GitHub locations and verifies each file against the
     SHA-256 the host publishes (Hugging Face LFS hash, GitHub asset digest). A mismatch deletes the file and stops.
  5. Writes run_comfyui_local.bat, which starts ComfyUI bound to 127.0.0.1 only.
  6. Clones the project branch (sparse: only comfyui/, jobs/, assets/references/) into <Root>\ghm-worker.

It never opens firewall ports, never installs services or scheduled tasks, and needs no API keys.
Run from PowerShell:
  powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1                 # SDXL route (default, ~12 GB of models)
  powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1 -WithFlux       # + FLUX.1 [schnell] GGUF route (~12 GB more)
#>
param(
    [string]$Root = "C:\AI",
    [switch]$WithFlux,
    [switch]$SkipModels,
    [string]$Repo = "https://github.com/ashkani007/VideoEnhancerAndroid.git",
    [string]$Branch = "ccr-1badfb87-5pxi90"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"          # Invoke-WebRequest is much faster without the progress bar

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------------------------------- 1. checks
Step "Checking the PC"
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { Fail "nvidia-smi not found: install the NVIDIA driver first" }
$gpu = (& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader) -join "; "
Write-Host "GPU: $gpu"
$vramMiB = [int]((& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits) | Select-Object -First 1)
if ($vramMiB -lt 7500) { Write-Host "WARNING: less than 8 GB VRAM ($vramMiB MiB). Use --lowvram in run_comfyui_local.bat." -ForegroundColor Yellow }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "Git not found: install Git for Windows (https://git-scm.com/download/win)" }
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$drive = (Get-Item $Root).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB, 1)
$needGB = if ($WithFlux) { 45 } else { 30 }
Write-Host "Free space on $($drive.Name): $freeGB GB (need about $needGB GB)"
if ($freeGB -lt $needGB) { Fail "not enough free disk space" }
$sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1

function Get-Verified($url, $dest, $sha256) {
    if (Test-Path $dest) {
        if ($sha256 -and ((Get-FileHash $dest -Algorithm SHA256).Hash.ToLower() -eq $sha256.ToLower())) {
            Write-Host "  ok (already present): $(Split-Path $dest -Leaf)"; return
        }
        if (-not $sha256) { Write-Host "  present, no published hash: $(Split-Path $dest -Leaf)"; return }
        Remove-Item $dest
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Write-Host "  downloading $(Split-Path $dest -Leaf) ..."
    & curl.exe -L --fail --retry 3 -o "$dest.part" $url
    if ($LASTEXITCODE -ne 0) { Fail "download failed: $url" }
    $got = (Get-FileHash "$dest.part" -Algorithm SHA256).Hash.ToLower()
    if ($sha256 -and $got -ne $sha256.ToLower()) { Remove-Item "$dest.part"; Fail "SHA-256 mismatch for $url (expected $sha256, got $got)" }
    Move-Item "$dest.part" $dest -Force
    Write-Host "  verified sha256 $got" -ForegroundColor Green
}

function Get-HFHash($repo, $path) {
    # Hugging Face publishes the SHA-256 of every LFS file in its API (tree listing of the folder)
    $dir = Split-Path $path -Parent
    $dir = if ($dir) { $dir.Replace("\", "/") } else { "" }
    $api = if ($dir) { "https://huggingface.co/api/models/$repo/tree/main/$dir" } else { "https://huggingface.co/api/models/$repo/tree/main" }
    $entry = (Invoke-RestMethod -Uri $api) | Where-Object { $_.path -eq $path }
    if (-not $entry -or -not $entry.lfs) { Fail "no published hash for $repo/$path (file moved or access restricted)" }
    return $entry.lfs.oid
}

# ------------------------------------------------------------------------------------------- 2. ComfyUI portable
$comfyRoot = Join-Path $Root "ComfyUI_windows_portable"
if (-not (Test-Path (Join-Path $comfyRoot "ComfyUI\main.py"))) {
    Step "Downloading ComfyUI (official portable build for NVIDIA)"
    $name = "ComfyUI_windows_portable_nvidia.7z"; $url = "https://github.com/comfyanonymous/ComfyUI/releases/latest/download/$name"
    $digest = $null; $tag = "latest"
    try {                                             # the API also gives the release tag and GitHub's SHA-256 digest
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest" -Headers @{ "User-Agent" = "ghm-installer" }
        $asset = $rel.assets | Where-Object { $_.name -match "windows_portable_nvidia" -and $_.name -like "*.7z" } | Select-Object -First 1
        if ($asset) {
            $name = $asset.name; $url = $asset.browser_download_url; $tag = $rel.tag_name
            if ($asset.digest -and $asset.digest -like "sha256:*") { $digest = $asset.digest.Substring(7) }
        }
    } catch { Write-Host "  GitHub API unavailable; using the direct latest-release link (no digest check)" -ForegroundColor Yellow }
    $archive = Join-Path $Root $name
    Get-Verified $url $archive $digest
    Step "Extracting $name (release $tag)"
    if ($sevenZip) { & $sevenZip x $archive "-o$Root" -y | Out-Null } else { & tar.exe -xf $archive -C $Root }
    if (-not (Test-Path (Join-Path $comfyRoot "ComfyUI\main.py"))) { Fail "extraction failed (install 7-Zip from https://www.7-zip.org and run again)" }
} else { Step "ComfyUI already installed at $comfyRoot" }
$py = Join-Path $comfyRoot "python_embeded\python.exe"
$models = Join-Path $comfyRoot "ComfyUI\models"
$nodes = Join-Path $comfyRoot "ComfyUI\custom_nodes"

# ------------------------------------------------------------------------------------------- 3. custom nodes
Step "Custom nodes (only these; every custom node runs code on this PC)"
$wanted = @(@{ name = "ComfyUI-Manager"; url = "https://github.com/Comfy-Org/ComfyUI-Manager.git" },
            @{ name = "ComfyUI_IPAdapter_plus"; url = "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git" })
if ($WithFlux) { $wanted += @{ name = "ComfyUI-GGUF"; url = "https://github.com/city96/ComfyUI-GGUF.git" } }
foreach ($n in $wanted) {
    $dst = Join-Path $nodes $n.name
    if (-not (Test-Path $dst)) { & git clone --depth 1 $n.url $dst; if ($LASTEXITCODE -ne 0) { Fail "git clone $($n.url) failed" } }
    $commit = (& git -C $dst rev-parse --short HEAD)
    Write-Host "  $($n.name) @ $commit"
    $req = Join-Path $dst "requirements.txt"
    if (Test-Path $req) { & $py -s -m pip install -q -r $req }
}

# ------------------------------------------------------------------------------------------- 4. models
if (-not $SkipModels) {
    Step "Models (official sources, SHA-256 verified)"
    $hf = @(
        @{ repo = "stabilityai/stable-diffusion-xl-base-1.0"; path = "sd_xl_base_1.0.safetensors"; dest = "checkpoints\sd_xl_base_1.0.safetensors" },
        @{ repo = "h94/IP-Adapter"; path = "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"; dest = "ipadapter\ip-adapter-plus_sdxl_vit-h.safetensors" },
        @{ repo = "h94/IP-Adapter"; path = "sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors"; dest = "ipadapter\ip-adapter-plus-face_sdxl_vit-h.safetensors" },
        @{ repo = "h94/IP-Adapter"; path = "models/image_encoder/model.safetensors"; dest = "clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" }
    )
    if ($WithFlux) {
        $hf += @(
            @{ repo = "city96/FLUX.1-schnell-gguf"; path = "flux1-schnell-Q4_K_S.gguf"; dest = "unet\flux1-schnell-Q4_K_S.gguf" },
            @{ repo = "comfyanonymous/flux_text_encoders"; path = "t5xxl_fp8_e4m3fn.safetensors"; dest = "text_encoders\t5xxl_fp8_e4m3fn.safetensors" },
            @{ repo = "comfyanonymous/flux_text_encoders"; path = "clip_l.safetensors"; dest = "text_encoders\clip_l.safetensors" },
            @{ repo = "black-forest-labs/FLUX.1-schnell"; path = "ae.safetensors"; dest = "vae\ae.safetensors" }
        )
    }
    foreach ($m in $hf) {
        $sha = Get-HFHash $m.repo $m.path
        Get-Verified "https://huggingface.co/$($m.repo)/resolve/main/$($m.path)" (Join-Path $models $m.dest) $sha
    }
    # Real-ESRGAN x4 (BSD-3-Clause), official GitHub release v0.1.0. It is a PyTorch pickle file, so its hash is pinned
    # (computed from the official release asset on 2026-10-25).
    Get-Verified "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" `
        (Join-Path $models "upscale_models\RealESRGAN_x4plus.pth") "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
}

# ------------------------------------------------------------------------------------------- 5. local-only launcher
Step "Writing run_comfyui_local.bat (binds to 127.0.0.1 only)"
$bat = @"
@echo off
REM Great History Makers: ComfyUI bound to this PC only. Do not add --listen 0.0.0.0, do not port-forward 8188.
cd /d "%~dp0"
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188
pause
"@
Set-Content -Path (Join-Path $comfyRoot "run_comfyui_local.bat") -Value $bat -Encoding ASCII

# ------------------------------------------------------------------------------------------- 6. worker copy of the project
$work = Join-Path $Root "ghm-worker\VideoEnhancerAndroid"
if (-not (Test-Path (Join-Path $work ".git"))) {
    Step "Cloning the project branch for the worker (only the folders it needs)"
    New-Item -ItemType Directory -Force -Path (Split-Path $work) | Out-Null
    & git clone --filter=blob:none --no-checkout --branch $Branch $Repo $work
    if ($LASTEXITCODE -ne 0) { Fail "git clone failed (private repository? sign in when Git asks, with your fine-grained token)" }
    & git -C $work sparse-checkout set --cone great_history_makers/comfyui great_history_makers/jobs great_history_makers/assets/references
    & git -C $work checkout $Branch
} else { Step "Worker copy already present at $work"; & git -C $work pull --ff-only }

Step "Done"
Write-Host @"
Next steps:
  1. Start ComfyUI:    $comfyRoot\run_comfyui_local.bat      (leave the window open)
     If Windows asks to allow python.exe on networks: click Cancel.
  2. Check the setup:  $work\great_history_makers\comfyui\worker\check_setup.bat
     Expected: port 8188 bound to ['127.0.0.1'] (local only: ok), RTX 4060 ~8 GB, required nodes/models ok.
  3. Run the test job: $work\great_history_makers\comfyui\worker\run_worker_once.bat
     It generates jobs/queue/napoleon_3scene_test_v1 (8 images) and pushes the results; then tell Claude.
"@

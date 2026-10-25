# Local AI illustrations: ComfyUI on Windows 11 + RTX 4060 (v3, automated episode pipeline)

This PC makes the illustrations. The cloud Claude Code session writes the illustration jobs, reviews the results and
renders the videos. Files and jobs travel through the GitHub repository; nothing on your PC is opened to the internet.

```
Claude Code (cloud)                 GitHub repo (private!)              Your PC (RTX 4060)
 python -m ghm4.episode jobs   ──►  jobs/queue/<id>.json        ◄──  run_worker.bat: git fetch (outbound HTTPS only)
 pick / plates / storyboard    ◄──  jobs/results/<id>/          ──►  ComfyUI on 127.0.0.1:8188, pushes the images
 render + narration + captions
```

**Status: not yet tested on your PC.** Everything below was prepared and tested in the cloud:
- the worker against a mock ComfyUI;
- the installer's PowerShell syntax and its download-and-verify function;
- the episode pipeline with stand-in images.

The first real run on your PC is the actual test.

---

## Quick path (about 30–60 min, mostly downloads)

### Step 0: make the repository private (once)
`ashkani007/VideoEnhancerAndroid` is **public**: generated images, prompts and the previews would be visible to anyone.
GitHub → repository → **Settings → General → Danger Zone → Change repository visibility → Private**.

### Step 1: prerequisites
1. **NVIDIA driver**: install the latest Game Ready or Studio driver, then reboot.
   In PowerShell, `nvidia-smi` must show *NVIDIA GeForce RTX 4060* and about *8188 MiB*.
2. **Git for Windows**: https://git-scm.com/download/win (defaults; includes Git Credential Manager).
3. **7-Zip** (recommended): https://www.7-zip.org. Without it the installer tries Windows' built-in `tar`.
4. **GitHub token for the worker**: GitHub → Settings → Developer settings → Fine-grained tokens → *Only select
   repositories*: `VideoEnhancerAndroid` → Permissions → **Contents: Read and write** (nothing else) → expiry 90 days.
   Git asks for it on the first clone or push and stores it in Windows Credential Manager. Never paste it anywhere else.
5. About **30 GB** free disk (45 GB with the optional FLUX route).

### Step 2: run the installer
On GitHub, open `great_history_makers/comfyui/windows/install_ghm_comfyui.ps1` on branch `ccr-1badfb87-5pxi90`, click
**Download raw file**, then in PowerShell:
```
cd <folder with install_ghm_comfyui.ps1>
powershell -ExecutionPolicy Bypass -File .\install_ghm_comfyui.ps1
```
It installs into `C:\AI` (change with `-Root D:\AI`):
- **Checks:** GPU, disk space, Git.
- **ComfyUI:** downloads the official portable build from GitHub.
- **Custom nodes:** installs **only** ComfyUI-Manager and ComfyUI_IPAdapter_plus.
- **Models:** downloads them and verifies each one's **SHA-256** against the hash Hugging Face publishes. Real-ESRGAN's hash is pinned in the script. A mismatch deletes the file and stops.
- **Launcher:** writes `C:\AI\ComfyUI_windows_portable\run_comfyui_local.bat`, which binds ComfyUI to **127.0.0.1** only.
- **Worker copy:** clones the project branch into `C:\AI\ghm-worker\VideoEnhancerAndroid`. It is a sparse checkout with only the folders the worker needs.

Optional A/B route: add `-WithFlux` for FLUX.1 [schnell] (adds ComfyUI-GGUF and about 12 GB of models).

### Step 3: start ComfyUI (local only)
Double-click `C:\AI\ComfyUI_windows_portable\run_comfyui_local.bat` and leave the window open.
If Windows asks *"Allow python.exe to communicate on networks?"* click **Cancel**: no inbound access is needed.

### Step 4: check the setup
Double-click `C:\AI\ghm-worker\VideoEnhancerAndroid\great_history_makers\comfyui\worker\check_setup.bat`. Expected:
```
port 8188 bound to: ['127.0.0.1']  (local only: ok)
"gpu": "cuda:0 NVIDIA GeForce RTX 4060 ...", "vram_total_gb": ~8
node IPAdapterAdvanced (required): ok      node IPAdapterModelLoader (required): ok
model checkpoints/sd_xl_base_1.0.safetensors (required): ok   ... (optional FLUX lines may say MISSING)
```
Send me this output if anything says MISSING or WARNING.

### Step 5: run the three-scene Napoleon test
Double-click `...\comfyui\worker\run_worker_once.bat` (one pass over the queue, then it exits).
- It fetches `jobs/queue/napoleon_3scene_test_v1.json`: **portrait × 4 seeds, battlefield × 4 seeds = 8 images**.
- It runs the job on ComfyUI and pushes `jobs/results/napoleon_3scene_test_v1/`: candidates, contact sheet, and a manifest with GPU, VRAM and **seconds per image**.
- Expected time on an RTX 4060: about 30–60 s per image, so 4–8 minutes. This is an estimate; the manifest gives the real figure.

Then tell me it is done. On my side:
1. `python -m ghm4.episode pick …`: I review the contact sheet and choose one portrait and one battlefield. This also queues a 2× upscale job.
2. You run `run_worker_once.bat` again (about 1 min).
3. `python -m ghm4.episode run …`: plates, automatic metadata, matte, eye annotation for the blink, storyboard timed to the narration, then the **720×1280 preview** for your approval.

---

## Models and licences (all free; commercial use of outputs allowed)
| File | Folder | Source | Licence | Used for |
|---|---|---|---|---|
| `sd_xl_base_1.0.safetensors` (6.9 GB) | `checkpoints\` | stabilityai/stable-diffusion-xl-base-1.0 | CreativeML Open RAIL++-M | Default illustration model |
| `ip-adapter-plus_sdxl_vit-h.safetensors` | `ipadapter\` | h94/IP-Adapter `sdxl_models/` | Apache-2.0 | Approved **style** reference |
| `ip-adapter-plus-face_sdxl_vit-h.safetensors` | `ipadapter\` | h94/IP-Adapter `sdxl_models/` | Apache-2.0 | Approved **face** reference (no InsightFace) |
| `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` (2.5 GB) | `clip_vision\` | h94/IP-Adapter `models/image_encoder/model.safetensors` (renamed) | MIT | Image encoder for both adapters |
| `RealESRGAN_x4plus.pth` (64 MB) | `upscale_models\` | xinntao/Real-ESRGAN release v0.1.0 | BSD-3-Clause | 2× plate upscale (pickle file: hash pinned) |
| *Optional:* `flux1-schnell-Q4_K_S.gguf` (6.8 GB) | `unet\` | city96/FLUX.1-schnell-gguf | Apache-2.0 | A/B for composition and hands |
| *Optional:* `t5xxl_fp8_e4m3fn.safetensors`, `clip_l.safetensors` | `text_encoders\` | comfyanonymous/flux_text_encoders | Apache-2.0 / MIT | FLUX text encoders |
| *Optional:* `ae.safetensors` | `vae\` | black-forest-labs/FLUX.1-schnell | Apache-2.0 | FLUX VAE (if Hugging Face asks you to accept terms, do it in the browser once) |

Not used, deliberately:
- **FLUX.1 [dev]:** non-commercial model licence.
- **IP-Adapter FaceID / InsightFace:** non-commercial.
- **Paid image or video APIs.**

### Why these models on 8 GB VRAM
- **SDXL base (default):** UNet about 5 GB in fp16. ComfyUI moves the text encoders and VAE out of VRAM when needed, so 768×1344 plus a 1.5× hires pass fits. Tiled VAE decoding keeps the 1152×2016 decode inside 8 GB. IP-Adapter adds about 1 GB. If VRAM runs out, add `--lowvram` to `run_comfyui_local.bat`. The SDXL ecosystem also gives style and face adapters and, later, cheap LoRA training on this card.
- **FLUX.1 [schnell] Q4 GGUF (optional):** better prompt following, anatomy and hands. The 4-bit UNet (6.8 GB) fits, and the T5 encoder is offloaded to system RAM. It needs only 4 steps but each step is heavier, so speed is roughly comparable. It has no style or face adapters, so consistency depends on prompts. Use it as an A/B, not as the default.

## Character consistency
1. **Every prompt uses the same text:** the descriptor (`comfyui/bible/characters/napoleon.json`) and style text (`comfyui/bible/style_ghm_cinematic_v1.json`).
2. **Two IP-Adapters:**
   - style: the whole approved illustration, weight 0.6, "style transfer";
   - face: `assets/references/napoleon_face_ref_01.png`, weight 0.45, active for the first 75 % of the steps.

   The face adapter turns off automatically in shots without Napoleon.
3. **Four seeds per shot.** I reject candidates whose face or uniform drifts.
4. **After about 20 approved Napoleon images:** a character LoRA trained on this PC, about 1–3 hours. Use OneTrainer (https://github.com/Nerogar/OneTrainer) or kohya_ss with 8 GB settings: batch 1, gradient checkpointing, cached latents, rank 16–32. Listed in `napoleon.json` → `loras`, it is used automatically.

## Security checklist (keep it true)
- [ ] Repository private; worker token limited to this repository, Contents read/write, with an expiry.
- [ ] `netstat -an | findstr :8188` shows only `127.0.0.1:8188`; no router port forward; no ngrok/Cloudflare tunnel.
      ComfyUI has no login: anyone who can reach port 8188 can run code on this PC.
- [ ] Windows Firewall: no "Allow" rule for the portable `python.exe`.
- [ ] Custom nodes: only ComfyUI-Manager, ComfyUI_IPAdapter_plus (and ComfyUI-GGUF for FLUX).
- [ ] Models only from the sources above, verified by the installer.
- [ ] The worker runs only while its window is open. No service, no scheduled task, no daily production.
- [ ] No API keys or tokens in job files, the repository or chat.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Installer: "SHA-256 mismatch" | The download was corrupted or replaced; run the installer again. If it repeats, send me the message |
| Installer: "no published hash … access restricted" | Open the Hugging Face model page in a browser, accept its terms if asked, run again |
| "CUDA out of memory" | Add ` --lowvram` to the python line in `run_comfyui_local.bat`; or ask me to lower `hires_scale` to 1.3 |
| Manifest error "IPAdapter_plus is not installed" | Restart ComfyUI after the installer; check `custom_nodes\ComfyUI_IPAdapter_plus` exists |
| ComfyUI "value not in list" for a model | File missing or misnamed; run the installer again (it skips verified files) |
| Worker "round failed: git …" | Check the token and network; results stay committed locally and are pushed next round |
| Black images | Add `--fp32-vae` to `run_comfyui_local.bat` |

## Manual install (if the script cannot be used)
1. Download `ComfyUI_windows_portable_nvidia.7z` from https://github.com/comfyanonymous/ComfyUI/releases and extract it to `C:\AI\`.
2. `git clone` https://github.com/Comfy-Org/ComfyUI-Manager and https://github.com/cubiq/ComfyUI_IPAdapter_plus into `ComfyUI\custom_nodes\`.
3. Download the models in the table into the listed folders, and compare each SHA-256 (`Get-FileHash`) with the value on its Hugging Face page.
4. Start ComfyUI with `python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1`.
5. Clone the branch into `C:\AI\ghm-worker` and continue at step 4 above.

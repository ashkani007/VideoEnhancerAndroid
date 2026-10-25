# Local AI illustrations: ComfyUI on Windows 11 + RTX 4060 (v2, for the approved ghm4 direction)

This PC makes the illustrations. The cloud Claude Code session writes the illustration jobs, reviews the results and
renders the videos. Files and jobs travel through the GitHub repository; nothing on your PC is opened to the internet.

```
Claude Code (cloud)                GitHub repo (private!)                Your PC
 writes jobs/queue/<id>.json  ──►  branch ccr-1badfb87-5pxi90  ◄──  ghm_worker.py: git fetch (outbound HTTPS)
 reviews jobs/results/<id>/   ◄──                              ──►  runs ComfyUI on 127.0.0.1:8188, pushes results
 renders with ghm4 (motion graphics, map, text, narration, captions)
```

Cost: free software and free models; only electricity (about 0.15 kW while generating, roughly €0.01 per batch of 12 images).
Plan for 1–2 hours of setup and about 30 GB of free SSD space.

---

## 0. Before anything: make the repository private
`ashkani007/VideoEnhancerAndroid` is currently **public**. Every job, prompt and generated image pushed through it,
and the preview videos already committed, can be seen and downloaded by anyone.
GitHub → the repository → **Settings → General → Danger Zone → Change repository visibility → Private**.
(Copies made while it was public cannot be recalled.) The worker works the same way with a private repository.

## 1. Check the GPU and the VRAM
1. Install the latest NVIDIA Game Ready or Studio driver (nvidia.com or the NVIDIA App) and reboot.
2. Open PowerShell and run `nvidia-smi`. It should list **NVIDIA GeForce RTX 4060** with **8188 MiB** (8 GB).
   A laptop RTX 4060 also has 8 GB. If it shows less, tell me: the workflow then uses `--lowvram` and a smaller hires pass.
3. The worker re-checks this later (`check_setup.bat`) and writes the GPU name and VRAM into every result manifest,
   so I can confirm the real VRAM and the real speed from your first batch.

## 2. Install the tools
1. **Git for Windows**: https://git-scm.com/download/win (defaults are fine; it includes Git Credential Manager).
2. **7-Zip**: https://www.7-zip.org (to unpack ComfyUI).
3. **ComfyUI portable**: https://github.com/comfyanonymous/ComfyUI → Releases → download
   `ComfyUI_windows_portable_nvidia.7z`, extract it to `C:\AI\ComfyUI_windows_portable\`.
4. Start it with `C:\AI\ComfyUI_windows_portable\run_nvidia_gpu.bat`. The UI opens at http://127.0.0.1:8188.
   ComfyUI listens only on 127.0.0.1 by default. **Never add `--listen`, never port-forward 8188 and never
   put ComfyUI behind a public tunnel**: ComfyUI has no login, and its API can write files and run custom nodes.
5. **Windows Firewall:** if Windows shows "Allow python.exe to communicate on networks?", click **Cancel** (deny).
   ComfyUI does not need inbound access; the worker only makes outgoing connections to GitHub.
6. **Verify it is local-only:** in PowerShell run `netstat -an | findstr :8188`. The only listening line must show
   `127.0.0.1:8188`. If you see `0.0.0.0:8188` or your LAN IP, close ComfyUI and remove `--listen` from the .bat file.
   (`check_setup.bat` in step 6 runs the same check.)

## 3. Download the models (all free, licences allow commercial use)
Put each file in the folder shown, inside `C:\AI\ComfyUI_windows_portable\ComfyUI\models\`. Create missing folders.

| File | Folder | Download | Licence |
|---|---|---|---|
| `sd_xl_base_1.0.safetensors` (6.9 GB) | `checkpoints\` | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 → Files | CreativeML Open RAIL++-M (commercial use allowed, use restrictions) |
| `ip-adapter-plus_sdxl_vit-h.safetensors` (0.85 GB) | `ipadapter\` | https://huggingface.co/h94/IP-Adapter → `sdxl_models/` | Apache-2.0 |
| `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` (2.5 GB) | `clip_vision\` | https://huggingface.co/h94/IP-Adapter → `models/image_encoder/model.safetensors`, **renamed** to this name | MIT |
| `RealESRGAN_x4plus.pth` (64 MB) | `upscale_models\` | https://github.com/xinntao/Real-ESRGAN/releases (v0.1.0 assets) | BSD-3-Clause |

Do not use FLUX.1 [dev] (non-commercial licence) or IP-Adapter *FaceID* models (they need InsightFace, which is
non-commercial). Fine-tuned checkpoints from model sites each have their own licence: check before using one.

## 4. Smoke test in the UI
Load the default workflow, pick `sd_xl_base_1.0.safetensors`, set the latent to **768 × 1344**, click **Run**.
An image should appear in well under a minute after the first (slower) model load.

## 5. Install the IP-Adapter nodes (style consistency)
1. Install **ComfyUI-Manager**: https://github.com/ltdrdata/ComfyUI-Manager (follow its "portable" instructions,
   or use the Manager that newer ComfyUI builds ship with).
2. Manager → **Custom Nodes Manager** → search **ComfyUI_IPAdapter_plus** (by cubiq) → Install → restart ComfyUI.
   (The project is in maintenance mode but works with current ComfyUI. Install only nodes listed here: custom nodes run
   code on your PC.)

## 6. Set up the worker
1. Make a separate folder for the worker's copy of the repository (keep it apart from any copy you edit by hand):
   ```
   mkdir C:\AI\ghm-worker
   cd C:\AI\ghm-worker
   git clone -b ccr-1badfb87-5pxi90 https://github.com/ashkani007/VideoEnhancerAndroid.git
   ```
2. **GitHub access for the worker** (it needs to read jobs and push results):
   - Recommended: a **fine-grained personal access token**: GitHub → Settings → Developer settings → Personal access
     tokens → Fine-grained → *Only select repositories*: `VideoEnhancerAndroid` → Permissions: **Contents: Read and write**
     (nothing else) → expiry 90 days. The first `git push` asks for it; Git Credential Manager stores it in Windows.
   - Never paste the token into the repository, a job file, a chat or a script.
3. Check everything (ComfyUI must be running):
   `C:\AI\ghm-worker\VideoEnhancerAndroid\great_history_makers\comfyui\worker\check_setup.bat`
   Expected: `port 8188 bound to: ['127.0.0.1'] (local only: ok)`, the GPU with about 8 GB, nodes `ok`, models `ok`
   (or `unknown` on older ComfyUI builds).

## 7. Run the first test (three new Napoleon illustrations)
1. Start ComfyUI (`run_nvidia_gpu.bat`).
2. Start the worker: double-click `...\great_history_makers\comfyui\worker\run_worker.bat`.
   It fetches the branch, finds `jobs/queue/napoleon_test3_v1.json` (3 shots × 4 seeds = 12 images), runs them,
   pushes `jobs/results/napoleon_test3_v1/` (JPEG candidates, contact sheet, manifest with GPU/VRAM/timings) and then
   keeps polling every 60 s. Close the window (or Ctrl+C) to stop. Nothing is scheduled; it only runs while open.
   `run_worker.bat --once` processes the queue once and exits.
3. Tell me when it says `-> done`. I review the contact sheet against the approved look, pick the best, and queue an
   **upscale job** (2× RealESRGAN → 2304 × 4032 plates) that the worker runs the same way.
4. Full-quality PNG copies stay on your PC in `great_history_makers\comfyui\candidates\` (not uploaded).

Expected speed on an RTX 4060 (estimate; the manifest records the real numbers): 768 × 1344 base, 30 steps,
plus the 1.5× hires pass (1152 × 2016) ≈ 30–60 s per image with IP-Adapter, so ≈ 6–12 minutes for the test batch.

## 8. Character consistency roadmap
1. **Now:** a fixed character descriptor (`bible/characters/napoleon.json`) + the approved image as an IP-Adapter
   style reference + seed search; I reject candidates that drift from the approved face and costume.
2. **After about 20 approved Napoleon images:** train an SDXL character LoRA on this PC with
   OneTrainer (https://github.com/Nerogar/OneTrainer) or kohya_ss (https://github.com/bmaltais/kohya_ss), using
   8 GB settings (batch 1, gradient checkpointing, cached latents, Adafactor, rank 16–32). This takes roughly 1–3 hours.
   Add the file to `models\loras\` and list it in `napoleon.json` → `loras`; every job then uses it automatically.
3. **Composition control:** the `sdxl_layout_ipadapter` workflow starts from a rough layout image (img2img), so a
   storyboard can fix where the figure, horizon and empty title space go without ControlNet models.

## Security checklist (keep it true)
- [ ] Repository private (step 0); worker token limited to this repository, Contents read/write, with an expiry.
- [ ] `netstat -an | findstr :8188` shows only `127.0.0.1:8188`; no router port forward; no ngrok/Cloudflare/remote tunnel.
- [ ] Windows Firewall: no "Allow" rule for the portable `python.exe` (Windows Security → Firewall → Allow an app).
- [ ] Custom nodes: only ComfyUI-Manager and ComfyUI_IPAdapter_plus. Every extra node runs code with your user rights.
- [ ] Models only from the sources in step 3; prefer `.safetensors`. `RealESRGAN_x4plus.pth` is a PyTorch pickle file:
      download it only from the official Real-ESRGAN GitHub release and keep ComfyUI and its bundled PyTorch updated
      (newer PyTorch versions restrict what a `.pth` file may execute when loaded).
- [ ] The worker runs only while its window is open; nothing is installed as a service or scheduled task.
- [ ] Never put API keys or tokens in job files, the repository or chat.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "CUDA out of memory" | Add ` --lowvram` to the python line in `run_nvidia_gpu.bat`; or ask me to lower `hires_scale` to 1.3 |
| Manifest error "IPAdapter_plus is not installed" | Step 5; restart ComfyUI afterwards |
| ComfyUI "value not in list" for a model | File in the wrong folder or misnamed (step 3); restart ComfyUI |
| Worker "round failed: git ..." | Check the token / network; results stay committed locally and are pushed next round |
| Black images | Launch ComfyUI with `--fp32-vae` |
| Worker refuses the server | It only talks to 127.0.0.1 / localhost by design |

# ComfyUI on Windows 11 + RTX 4060 (8 GB): setup for Great History Makers illustrations

Goal: generate the first Napoleon character candidates locally, at no per-image cost, in the style of
`assets/references/napoleon_style_reference_01.png`, then send the best ones back for review.
Everything below is free software. Model licences are listed so commercial use on Instagram stays clean.

Plan for about 1 hour of setup and about 25 GB of free disk (SSD preferred).

---

## 1. Prerequisites
1. **NVIDIA driver:** install the latest Game Ready or Studio driver from nvidia.com (or the NVIDIA App) and reboot.
2. **7-Zip** (to extract the ComfyUI package): https://www.7-zip.org
3. **Git** (optional, to get this repository): https://git-scm.com. Alternatively, download the branch as a ZIP from GitHub.

## 2. Install ComfyUI (portable build)
1. Open https://github.com/comfyanonymous/ComfyUI → **Releases** → download the Windows portable package for NVIDIA
   GPUs (file name like `ComfyUI_windows_portable_nvidia.7z`).
2. Extract it to a short path, e.g. `C:\AI\ComfyUI_windows_portable\`.
3. Double-click `run_nvidia_gpu.bat`. A console opens, and after the first start the UI appears at **http://127.0.0.1:8188**.
   Keep this console window open while generating.

(Alternative: the ComfyUI Desktop installer from https://www.comfy.org works too. Paths then differ; use its
"Open models folder" menu.)

## 3. Download the models
Put each file in the folder shown (inside `C:\AI\ComfyUI_windows_portable\ComfyUI\`).

| File | Folder | Source | Licence |
|---|---|---|---|
| `sd_xl_base_1.0.safetensors` (about 6.9 GB) | `models\checkpoints\` | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 (Files tab) | CreativeML Open RAIL++-M: commercial use allowed, with use-based restrictions |
| `RealESRGAN_x4plus.pth` (about 64 MB, for the 2× upscale workflow) | `models\upscale_models\` | https://github.com/xinntao/Real-ESRGAN/releases (v0.1.0 assets) | BSD-3-Clause |

Do **not** use FLUX.1 [dev] for this channel: its licence is non-commercial. FLUX.1 [schnell] is Apache-2.0 and
optional (section 8). Fine-tuned checkpoints from model-sharing sites each have their own licence; check it before use.

Restart ComfyUI (close the console, run `run_nvidia_gpu.bat` again) after adding models.

## 4. Smoke test in the UI
1. In the browser UI, load the default workflow (menu → *Workflow* → *Load Default*, or it opens by default).
2. In **Load Checkpoint**, select `sd_xl_base_1.0.safetensors`.
3. In **Empty Latent Image**, set width 768 and height 1344 (a native SDXL portrait size close to 9:16).
4. Click **Queue** (Run). An image should appear within a minute; the first run is slower because the model loads.

Our workflow `workflows/napoleon_sdxl_api.json` is this same default graph (checkpoint → two prompts →
empty latent 768×1344 → KSampler 30 steps, CFG 6, dpmpp_2m / karras → decode → save), in ComfyUI's API format
so the batch script can drive it.

## 5. Get the Great History Makers files
```
cd C:\AI
git clone -b ccr-1badfb87-5pxi90 https://github.com/ashkani007/VideoEnhancerAndroid.git
```
The files you need are in `C:\AI\VideoEnhancerAndroid\great_history_makers\comfyui\`:
`generate.py`, `workflows\`, `prompts\`.

## 6. Generate the first 8 Napoleon candidates
With ComfyUI running, open a second terminal (PowerShell) and use the Python that ships with the portable build
(the script needs only the standard library):
```
cd C:\AI\VideoEnhancerAndroid\great_history_makers\comfyui
C:\AI\ComfyUI_windows_portable\python_embeded\python.exe generate.py prompts\napoleon_character_v1.json
```
- One image per seed (8 seeds), saved to `comfyui\candidates\napoleon_character_v1\` plus `run_log.json` with the
  seconds per image (that is the real speed on your GPU; please keep the log).
- For 2× upscaled versions (about 1536×2688, enough for 1080×1920 crops), add
  `--workflow workflows\napoleon_sdxl_upscale_api.json`.
- To try other wording, copy the prompt file, edit `positive` / `negative` / `seeds` / `name`, and run it again.

## 7. Send the results for review
Pick the 2–3 best candidates and either upload them in this chat, or commit them to
`great_history_makers/assets/references/candidates/` and push. Also send `run_log.json`.
I'll review them against the reference (face, expression, proportions, light, palette, costume accuracy), refine the
prompt, and only after your approval build the character sheet.

## 8. Next steps (after the first look is approved)
1. **Style consistency with IP-Adapter:** install *ComfyUI-Manager* (https://github.com/ltdrdata/ComfyUI-Manager),
   then via the Manager install the custom nodes **ComfyUI_IPAdapter_plus** (https://github.com/cubiq/ComfyUI_IPAdapter_plus)
   and the SDXL IP-Adapter Plus model and CLIP-Vision model listed in that project's README. In the graph, add
   *IPAdapter Unified Loader* + *IPAdapter Advanced* between the checkpoint and the KSampler, load the style reference with
   *Load Image*, set weight type **style transfer** and weight 0.4–0.7. Avoid the *FaceID* variants: they depend on
   InsightFace models licensed for non-commercial use only.
2. **Character consistency:** once a Napoleon design is approved, a small LoRA trained on 15–30 approved images
   (e.g. with kohya_ss) keeps his face identical across shots. 8 GB VRAM is enough for SDXL LoRA training with memory-saving settings, though slowly.
3. **FLUX.1 [schnell] (optional, Apache-2.0):** an fp8 or GGUF build runs on 8 GB with system-RAM offloading (your
   32 GB RAM helps), using 4 steps and CFG 1. It is slower to load than SDXL, so try it only if SDXL can't reach the look.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "CUDA out of memory" | Edit `run_nvidia_gpu.bat` and add ` --lowvram` at the end of the python line; keep 768×1344 (upscale afterwards) |
| Black or grey images | Use the SDXL fp16-fix VAE (`madebyollin/sdxl-vae-fp16-fix` on Hugging Face) via a *Load VAE* node, or launch with `--fp32-vae` |
| `generate.py` cannot connect | ComfyUI must be running and reachable at http://127.0.0.1:8188 (check the console) |
| Model missing in the list | File in the wrong folder, or ComfyUI not restarted after copying |
| Faces too generic or cartoonish | Keep the negative prompt; raise steps to 35–40; next step is IP-Adapter style transfer (section 8.1) |

Speed: expect seconds to a few tens of seconds per 768×1344 image on an RTX 4060 once the model is loaded. This is
an estimate; `run_log.json` gives the measured value.

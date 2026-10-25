# Local AI illustrations: ComfyUI on Windows 11 + RTX 4060 (v4, reviewed installer)

This PC makes the illustrations. Claude writes illustration jobs, reviews the results and renders the videos. Jobs and
images travel through a **private** GitHub repository; nothing on the PC is opened to the internet.

```
Claude (cloud or local)              Private GitHub repo                Your PC (RTX 4060)
 python -m ghm4.episode jobs   ──►  jobs/queue/<id>.json        ◄──  run_worker_once.bat (outbound HTTPS only)
 pick / plates / storyboard    ◄──  jobs/results/<id>/          ──►  ComfyUI on 127.0.0.1:8188, pushes the images
```

**Status:** not installed or tested on the PC yet. The installer was revised after the independent review:
- pinned versions;
- hash-locked downloads;
- one custom node;
- local-only launcher;
- no hardcoded paths;
- no tokens.

Details and static-check results: [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md).

## How it gets installed
The plan is that a **Claude Code session running on your PC** performs the installation, with your approval at each gate.
Follow [`windows/LOCAL_INSTALL_PLAN.md`](windows/LOCAL_INSTALL_PLAN.md):
1. **Enable local execution:** install Git for Windows and Claude Code, clone the repository, start `claude` in it.
2. **Phase 1 (read-only):** `windows/inspect_pc.ps1` reports the GPU, RAM, disk, existing ComfyUI installs, port 8188, firewall rules and scheduled tasks.
3. **Phases 2–3 (no large downloads):** the installer's plan mode, then `-ResolveLock`, which takes the model hashes from Hugging Face metadata. **You approve the plan and the lock fingerprint.**
4. **Phase 4:** `install_ghm_comfyui.ps1 -Root <your folder> -Install -ApproveFingerprint <fp> [-RepoUrl <private repo>]`.
5. **Phases 5–6:** smoke test (`run_comfyui_local.bat`, `check_setup.bat`), then the first job (`run_worker_once.bat`: 8 Napoleon images).

## What gets installed (all pinned in `windows/ghm_install.lock.json`)
| Component | Version / pin | Size | Licence |
|---|---|---|---|
| ComfyUI Windows portable (NVIDIA) | v0.39.0, sha256 `3dca3478…ae039` | 2.0 GB archive, 4.4 GB installed | GPL-3.0 |
| ComfyUI_IPAdapter_plus | commit `a0f451a5…` | < 1 MB | GPL-3.0 |
| SDXL base 1.0 | Hugging Face revision + sha256 (resolved, approved) | 6.9 GB | CreativeML Open RAIL++-M |
| IP-Adapter Plus SDXL + Plus-Face SDXL | idem | ≈ 1.7 GB | Apache-2.0 |
| CLIP ViT-H/14 image encoder | idem | ≈ 2.5 GB | MIT |
| Real-ESRGAN x4plus | sha256 `4fa0d389…82f1` | 64 MB | BSD-3-Clause |

- **Total installed:** ≈ 15.6 GB. The installer requires about 21 GB free before it starts.
- **RAM:** 16 GB minimum, 32 GB comfortable.
- **Not installed:** ComfyUI-Manager, other custom nodes, pip packages, the FLUX route, InsightFace or FaceID.
- **Never changed:** firewall rules, services, scheduled tasks.

## Running it day to day
- **Start ComfyUI:** `<root>\ComfyUI_windows_portable\run_comfyui_local.bat`. It is bound to 127.0.0.1, `--offline` (paid partner API nodes off) and does not auto-open a browser.
  If Windows asks to allow `python.exe` on networks, click **Cancel**.
- **Check:** `<worker folder>\check_setup.bat`. It reports the port binding (must be `127.0.0.1` only), ComfyUI's own launch flags, the GPU and VRAM, and the required nodes and models.
- **Process jobs once:** `<worker folder>\run_worker_once.bat`. Or `run_worker.bat` to poll every 60 s while the window is open.
- **Paths:** they come from `local_paths.cmd`, written by the installer and never committed, or from the `GHM_COMFYUI_DIR` variable. Nothing is hardcoded.
- **Close ComfyUI when you are not generating:** it has no login, and anything on this PC can talk to 127.0.0.1:8188.

## Character consistency
- **Same text everywhere:** the descriptor and style text come from `comfyui/bible/`.
- **Two IP-Adapters:** style (the approved illustration) and face (`assets/references/napoleon_face_ref_01.png`). The face adapter is off in shots without the character.
- **Seeds:** four per shot, so the best candidate can be chosen.
- **Later:** after about 20 approved images, a character LoRA trained on this PC (OneTrainer or kohya_ss, 8 GB settings).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `STOPPED: … SHA-256 mismatch` / `fingerprint not approved` | Do not work around it. The file or lock changed; report it and re-run `-Plan` / `-ResolveLock` for review |
| `7-Zip not found` | Install 7-Zip from https://www.7-zip.org (needed for the archive's BCJ2 filter) |
| "CUDA out of memory" | Add ` --lowvram` to the launcher line, or ask Claude to lower `hires_scale` to 1.3 |
| Worker: "remote URL contains credentials" | `git remote set-url origin https://github.com/<you>/<repo>.git` and sign in through Git Credential Manager |
| Worker: "GHM_COMFYUI_DIR is not set" | Re-run the installer with `-RepoUrl`, or create `local_paths.cmd` as the message shows |

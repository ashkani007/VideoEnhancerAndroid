# Local installation plan (Claude Code running on the Windows 11 PC)

Status 2026-10-25:
- The cloud Claude Code session has **no access** to the PC: no computer-use or remote-device tools, no Remote Control session.
- Everything below is prepared and tested in the cloud: PowerShell parsing, PSScriptAnalyzer, the installer's gates against mocks, and the install path on Linux with the real pinned downloads.
- Nothing has run on Windows yet.

## A. Enable local execution (minimum steps for you, about 10 minutes)
1. **Git for Windows**: https://git-scm.com/download/win, default options. Claude Code on Windows uses its Git Bash, and the worker uses Git with Git Credential Manager (browser sign-in, no token copy-paste).
2. **Claude Code**: in PowerShell run `irm https://claude.ai/install.ps1 | iex` (Anthropic's native installer), then `claude --version`.
3. **The project**: once the dedicated private repository exists (section D), clone it into a folder of your choice, for example:
   `git clone https://github.com/<you>/<private-ghm-repo>.git D:\GHM\repo`
   Until then, clone branch `ccr-1badfb87-5pxi90` of the current repository.
4. **Start a local session** in that folder: `cd D:\GHM\repo` (or `...\great_history_makers`), then `claude`. Sign in with the same Claude account.
   Optionally run `claude remote-control` instead; the session then also shows up in the Claude Code app.
5. **Keep the default permission mode**, so Claude asks before every command. Tell it:
   *"Read comfyui/windows/LOCAL_INSTALL_PLAN.md and do phase 1 only."*

## B. Phases and approval gates (the local Claude session follows these exactly)
| Phase | What happens | Changes to the PC | Gate |
|---|---|---|---|
| 1 Inspect | `powershell -ExecutionPolicy Bypass -File comfyui\windows\inspect_pc.ps1` (add `-SearchRoots` for other drives) | None (writes `%TEMP%\ghm_inspect.json`) | Report GPU/VRAM, RAM, free disk, existing ComfyUI, port 8188 listeners, firewall rules, scheduled tasks to the user |
| 2 Plan | `install_ghm_comfyui.ps1 -Root <chosen dir>` (default mode = plan) | None | User chooses the install folder and drive |
| 3 Resolve lock | `install_ghm_comfyui.ps1 -ResolveLock` | Edits `ghm_install.lock.json` only (Hugging Face metadata; no model download) | **User reviews the hashes and approves the final plan + lock fingerprint** |
| 4 Install | `install_ghm_comfyui.ps1 -Root <dir> -Install -ApproveFingerprint <fp> [-RepoUrl <private repo>]` | About 2 GB + 11 GB of downloads into `<dir>`, all hash-verified | Only after the explicit approval in phase 3 |
| 5 Smoke test | Start `run_comfyui_local.bat`; run `check_setup.bat`; `netstat -an \| findstr :8188` must show only 127.0.0.1 | ComfyUI running while the window is open | Report the check output |
| 6 Test job | `run_worker_once.bat`: 8 images for `napoleon_3scene_test_v1`, results pushed to the repository | Images in the repo; full PNGs stay local | Report seconds per image and VRAM; the cloud session continues with the preview |

## C. Rules for the local session (non-negotiable)
- Do not run phase 4 without the user's explicit approval of the plan and the lock fingerprint in this conversation.
- Never change firewall rules (`netsh`, `New-NetFirewallRule`, `Set-NetFirewall*`), never create scheduled tasks or services, and never add `--listen 0.0.0.0` or any tunnel.
- Never install extra custom nodes, ComfyUI-Manager or Python packages, and never run ComfyUI's update scripts.
- Never ask for, display, store or log GitHub tokens or API keys. GitHub sign-in goes only through the Git Credential Manager window.
- Do not touch the LensPrompt Android project or the old repository's visibility.
- Stop and report on any `STOPPED:` message from the installer. Never work around a hash or fingerprint failure.

## D. Repository: dedicated private repository (recommended, instead of changing LensPrompt's visibility)
1. On GitHub create an **empty private** repository, for example `great-history-makers` (no README, no licence file).
2. The export is prepared and tested: `great_history_makers/tools/export_ghm_repo.sh <dir>`.
   - **Contents:** `great_history_makers/` as the new root, 351 files, about 146 MB, one commit, no LensPrompt history.
   - **Videos:** the old preview videos stay in the old repository unless `--with-videos` (Git LFS) is used.
   - **Tested:** the regression suite and the worker test pass inside the exported copy.
3. Pushing it: either the local session runs the export and push (Git Bash), or the cloud session does it once you attach the new repository to it. Sign-in happens in the Git Credential Manager window either way.
4. The worker then works there without settings: it finds the project at the repository root and uses the checked-out branch, `main`.
5. **Your own decision, not done here:** the existing repository stays public and already contains the Great History Makers history. Deleting it from that history, or archiving the repository, is a separate step.

## E. What the installer will and will not do
**Will:**
- verify the pinned ComfyUI **v0.39.0** portable archive (SHA-256 `3dca3478…ae039`) and unpack it with 7-Zip into `<dir>\ComfyUI_windows_portable`;
- check out **ComfyUI_IPAdapter_plus** at commit `a0f451a5…`;
- download five models, each verified by size and SHA-256;
- write `run_comfyui_local.bat` (`--listen 127.0.0.1 --port 8188 --disable-auto-launch --offline`) and the worker's `local_paths.cmd`.

**Will not:**
- install ComfyUI-Manager, other custom nodes, pip packages or the FLUX route;
- change the firewall;
- create services or scheduled tasks;
- download anything whose hash is not pinned.

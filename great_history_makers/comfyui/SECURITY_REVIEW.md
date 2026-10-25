# Installer and worker: security review response (2026-10-25)

Scope:
- `comfyui/windows/install_ghm_comfyui.ps1`, `ghm_install.lock.json`, `inspect_pc.ps1`;
- `comfyui/worker/ghm_worker.py` and its `.bat` launchers;
- `tools/export_ghm_repo.sh`.

Nothing has been installed or run on the Windows PC yet.

## The nine review points
| # | Request | Change | Evidence |
|---|---|---|---|
| 1 | Pin ComfyUI and custom nodes | ComfyUI **v0.39.0** (commit `b0b74356…`, released 2026-10-05) portable asset pinned by SHA-256 `3dca347842ed1c6c833105fafb1669284685a3e54df41578d5f94bcc898ae039` and size. ComfyUI_IPAdapter_plus pinned to commit `a0f451a5113cf9becb0847b92884cb10cbdec0ef`, verified after checkout | Asset downloaded and hashed in the cloud. The ComfyUI sources in the archive are identical to git tag v0.39.0 (line endings normalised). Bundled Python 3.13, PyTorch 2.14.0+cu130. Node checkout tested at the pinned commit |
| 2 | Fail safely without a verified checksum | Every download needs a SHA-256 in the lock, or the installer stops before downloading. Size and hash are checked on a `.part` file, which is deleted on any mismatch. Existing files with the wrong hash are left untouched and the installer stops. `-Install` requires the **approved lock fingerprint** (canonical hash of URLs, commits, hashes, sizes and destinations), so a lock edited after approval is refused | Tested with mocks: unpinned lock refused; wrong SDXL hash from the API refused (lock left unchanged); wrong fingerprint refused; tampered lock refused. Real download plus verification passed for Real-ESRGAN; the mismatch test deleted the partial file |
| 3 | No unnecessary nodes or dependencies | Only ComfyUI_IPAdapter_plus: no requirements file, no pip installs, InsightFace not installed (only FaceID uses it; we don't). **ComfyUI-Manager removed**: the pinned ComfyUI keeps its built-in manager off unless `--enable-manager`. The FLUX/GGUF route was removed from the installer. The installer stops if the pinned node ever ships a `requirements.txt` | Node source reviewed: about 3,000 lines, no network or subprocess calls, no eval or exec |
| 4 | 127.0.0.1 only, no firewall rules, no tunnels | Launcher: `--listen 127.0.0.1 --port 8188 --disable-auto-launch --offline` (`--offline` also disables the paid partner API nodes and stops the web UI from calling out). The installer contains no firewall, service, scheduled-task or tunnel commands. `check_setup.bat` reads ComfyUI's own launch flags and the netstat binding and warns on `0.0.0.0`, `--enable-manager`, CORS or multi-user | `--listen` default and the `--offline` behaviour confirmed in the v0.39.0 source; forbidden-command scan of the scripts is clean |
| 5 | No hardcoded C:\AI | `-Root` parameter for the installer. The `.bat` files read `GHM_COMFYUI_DIR` from `local_paths.cmd`, which the installer writes and git never commits. The worker finds its repository from its own location and uses the checked-out branch | `grep` for `C:\AI` in scripts: none. Worker test passes in both repository layouts without path or branch settings |
| 6 | Dedicated private repository | `tools/export_ghm_repo.sh` exports `great_history_makers/` as a new repository root (fresh history; old videos stay behind unless `--with-videos` with LFS). Worker and installer support both layouts | Export tested: 351 files, 146 MB; the regression suite and worker tests pass inside it |
| 7 | No tokens in chat or logs | No token prompts anywhere; sign-in only through Git Credential Manager. The installer refuses repository URLs with embedded credentials. The worker refuses a credential-bearing `origin` URL and redacts `https://user:pass@`, `ghp_…`, `github_pat_…` and similar from console output, git errors and manifests | Worker test: credential URL refused, token never echoed; redaction unit-checked |
| 8 | Licences and disk space | See the next two sections | |
| 9 | Static checks and remaining risks | See the last two sections | |

## Licences (outputs may be used commercially; not legal advice)
| Component | Licence | Notes |
|---|---|---|
| ComfyUI v0.39.0, ComfyUI_IPAdapter_plus | GPL-3.0 | Copyleft applies to distributing the software. Local use to make images puts no obligations on the images |
| Bundled Python, PyTorch, NVIDIA CUDA runtime | PSF / BSD-3 / NVIDIA redistributable EULA | Shipped inside the official ComfyUI portable build |
| SDXL base 1.0 | CreativeML Open RAIL++-M | Commercial use allowed; use-based restrictions (no unlawful, harassing or defamatory use, no harmful disinformation). Fine for historical illustration |
| IP-Adapter Plus / Plus-Face SDXL (h94) | Apache-2.0 | No InsightFace (its models are non-commercial), so no FaceID |
| CLIP ViT-H/14 laion2B image encoder | MIT (OpenCLIP) | |
| Real-ESRGAN x4plus | BSD-3-Clause | PyTorch pickle format: hash pinned, and ComfyUI v0.39.0 loads it with `torch.load(weights_only=True)` (verified in source) |
| Removed from the plan | FLUX.1 [dev] (non-commercial), FaceID/InsightFace (non-commercial), FLUX schnell (Apache-2.0, removed only to keep the install minimal) | |

## Disk space and memory
| Item | Size |
|---|---|
| ComfyUI archive (deleted after a verified extraction unless `-KeepArchive`) | 2.0 GB |
| ComfyUI unpacked (Python + PyTorch + ComfyUI) | 4.4 GB |
| SDXL base | 6.9 GB |
| IP-Adapter Plus + Plus-Face | about 1.7 GB (exact sizes from `-ResolveLock`) |
| CLIP ViT-H encoder | about 2.5 GB |
| Real-ESRGAN | 0.07 GB |
| **Installed total** | **≈ 15.6 GB**; peak during install ≈ 17.6 GB |
| Installer's free-space requirement | archive + unpacked + models + 3 GB margin ≈ 20.6 GB (checked before anything is written) |
| Ongoing | Candidates about 2–3 MB per PNG on the PC; worker clone about 50–150 MB |

RAM: 16 GB works; 32 GB is comfortable, because SDXL moves its text encoders and VAE to system RAM on an 8 GB card.

## Static checks
| Tool | Target | Result |
|---|---|---|
| PowerShell parser (pwsh 7.4.6) | installer, inspection script | 0 parse errors |
| PSScriptAnalyzer 1.23.0 | installer | Only `PSAvoidUsingWriteHost` (27, accepted: interactive coloured console output). Fixed: a state-changing verb on a function, positional parameters |
| PSScriptAnalyzer 1.23.0 | inspect_pc.ps1 | No findings |
| ruff (pyflakes, bugbear) | worker, ghm4 | Clean after fixes (unused variables and imports, `raise … from None`); one accepted `lru_cache` on a method (the renderer lives for one process) |
| bandit 1.9 | worker | No medium or high findings after restricting the ComfyUI URL to http(s) on loopback (B310). Low findings accepted: `assert` in tests; `git` via subprocess with fixed argument lists and no shell (B404/B603/B607) |
| gitleaks 8.21.2 | whole repository and history (96 commits) | 3 hits, none real: two map files with `"key": "french_allies_1811"`, and a dummy `test-key-0123…` in the LensPrompt backend tests |
| Functional | installer gates (mocked Windows APIs), Linux install path with real pinned downloads, worker in both layouts | All pass |

## Unresolved or accepted risks
1. **Hugging Face model hashes are not yet pinned.** This cloud session cannot reach huggingface.co. `-ResolveLock` takes them from the official Hugging Face API at immutable revisions, and the SDXL hash is cross-checked against an independently known value. The other three are trusted to the publisher's API over TLS (trust on first use), then frozen in the lock and approved by fingerprint.
2. **The ComfyUI portable bundle is a large binary** (Python, PyTorch, CUDA DLLs) that I could not inspect file by file. Mitigations: official GitHub release, pinned hash, sources identical to the tag, 20 days old at pin time.
3. **ComfyUI_IPAdapter_plus is in maintenance mode** (last commit 2025-04-14). Pinned and reviewed, but it gets no security fixes. GPL code runs in the ComfyUI process with your user rights.
4. **ComfyUI has no authentication.** Any process on the PC (or a website, through the browser) that can reach 127.0.0.1:8188 can queue work. `--offline` limits outbound calls from the web UI; don't browse untrusted sites while ComfyUI runs, and close it when idle.
5. **Repository trust boundary.** Anyone with push access to the job repository can queue (validated, allow-listed) jobs. Keep the private repository to yourself.
6. **Python and PyTorch updates:** pinned, so they don't change silently, but they also get no patches until you re-pin a newer release through the same review process.
7. **Public history:** the existing repository is public and already contains the Great History Makers history and previews. Moving to a private repository does not remove those.

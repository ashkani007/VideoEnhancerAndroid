# Great History Makers v2: audit and migration plan

Client direction (2026-10-23): stop 2.5D character animation and per-shot procedural scenes. Move to
AI-generated illustrations, limited 2D character animation and motion graphics. Variable cost target:
under €0.50 per video, measured rather than assumed. Keep the branding, the approved voice and all previous assets.
LensPrompt stays completely separate.

## 1. Audit of the v1 pipeline

| Area | v1 module | Cost driver | v2 decision |
|---|---|---|---|
| Shot art | `episodes/*/scenes.py` (1,100–1,300 lines per episode), `mosaic/library/*` | Claude writes every figure and prop as code; days of iteration | **Retire for new episodes.** Replaced by illustration plates |
| Mosaic look | `mosaic/tessellate.py`, `painter.py` | Re-tiling per asset | **Optional filter only** (`tools/mosaicify.py` on plates), A/B for client approval |
| 2.5D figures | `turnrig.py`, `rig3d.py`, `depth.py`, `motion.py` | Multi-view rigs, IK gaits | **Retire** (kept in repo, unused) |
| Camera, grade | `scene.py` camera, `fx.CinematicGrade` | — | **Reuse** grade; new plate camera in `ghm2/anim.py` |
| Narration | ElevenLabs connector, `tools/tts_elevenlabs.py` | ~1 credit/char | **Reuse** unchanged |
| Captions | `tools/align_narration.py`, `mosaic/captions.py`, `text.caption` | Free | **Reuse** unchanged |
| Music, SFX | `mosaic/audio.py` | Free | **Reuse** unchanged |
| Brand | `tools/brand.py` | Free (2.5 min CPU) | **Reuse**; later fold into the render pass |
| QC, verify | `mosaic/qc.py`, `tools/verify_delivery.py` | Free | **Reuse** (verify now reads v2 storyboards) |
| Automation | `autopilot/` (scripts, batch, budget, ledger) | — | **Reuse**; storyboard step changes |

## 2. v2 architecture (separate stages, one folder per episode)

| # | Stage | Tool | Output | Runs on |
|---|---|---|---|---|
| 1 | Script + history check | Claude (weekly batch, client approval) | `NARRATION.txt`, `CONCEPT.md` | Cloud |
| 2 | Storyboard | Claude | `storyboard.json`: 8–12 compositions on narration words, illustration prompts, layers, rigs, graphics | Cloud |
| 3 | Illustrations | ComfyUI (API mode) + SDXL (Open RAIL++-M) or FLUX.1-schnell (Apache-2.0, GGUF fits 8 GB); one style LoRA; character reference sheet + IP-Adapter for consistency; fixed seeds | `plates/*.png` (bg, character, foreground) | RTX 4060 (local) |
| 4 | Layer split | rembg/BiRefNet cut-outs, LaMa clean plates, Depth-Anything-V2-Small for depth, MediaPipe face landmarks for eye boxes and head pivots | transparent layers + rig coordinates | RTX 4060 |
| 5 | Limited animation | `ghm2/puppet.py`: blink, head turn/tilt, hand gesture, breathing (soft displacement warps, no rigging) | applied at render | any CPU |
| 6 | Motion graphics | `ghm2/mograph.py`: vector maps (swap in Natural Earth, public domain), arrows, battle markers, timelines, animated typography. Remotion optional for complex type templates (free for individuals and companies of up to 3 people) | drawn at render | any CPU |
| 7 | Narration | ElevenLabs connector, voice `Gfpl8Yo74Is0W6cPUWWT`, **only when authorised** | `audio/narration.mp3` + aligned words | Cloud |
| 8 | Render | `python -m ghm2.render <ep>` (540×960 preview) → `--final` (1080×1920) → `tools/brand.py` → `tools/verify_delivery.py` | branded MP4, SRT, QC, verify report | Windows (NVENC) or cloud (x264) |

Composition grammar (keeps it from becoming a slideshow): every composition has exactly one motivated
camera move (push, pan or tilt toward the subject, zoom ≤ 1.10), at least one moving element (particles,
light, puppet or graphic), and a cut placed in a narration pause. Map and typography compositions alternate
with illustrated ones; no two consecutive compositions use the same move.

### Windows 11 + RTX 4060 setup (to do on the client PC)
1. Python 3.11+, `pip install numpy scipy opencv-python Pillow pocketsphinx`; FFmpeg build with NVENC (`h264_nvenc` is auto-detected by `mosaic/render.py`).
2. ComfyUI portable + SDXL base (or FLUX.1-schnell GGUF) + IP-Adapter; a small HTTP client script queues the storyboard prompts.
3. `rembg`, `simple-lama-inpainting`, Depth-Anything-V2-Small, `mediapipe`.
4. Render: `py -m ghm2.render episodes_v2\<id>` then `--final`.

Note: avoid InsightFace-based tools (e.g. some face-animation models). Their model weights are licensed for non-commercial use only.

### Where each stage can run
The cloud container has no GPU, and the model hosts (Hugging Face) are blocked, so **stages 3–4 cannot run in the
cloud session**. Two workable set-ups:
- **A. Hybrid (lowest cost):** cloud Claude writes script and storyboard and commits them; a Windows scheduled job on the
  RTX 4060 generates plates, renders and pushes back. Needs the PC on during the job.
- **B. Cloud only:** a paid image API generates the plates. Per-image prices must be measured before
  choosing; at 10–15 images per video this is likely the largest variable cost.

## 3. Cost model (per 60 s video)

| Item | Measured now | Projection (to verify) |
|---|---|---|
| ElevenLabs narration (1 take) | Ep02: 838 credits = $0.168 at the connector price (1 credit/char) | W44 scripts average ~690 chars → ~$0.14 (≈ €0.13) |
| Illustrations (local SDXL/FLUX on 4060) | not measured (no GPU here) | ~10–15 plates × ~20 s ≈ 5–10 min GPU ≈ 0.03 kWh ≈ €0.01 |
| Layer split + render + brand (local) | PoC 20 s on 4 cloud vCPUs: 405 s render + 145 s brand | 60 s ≈ 25 min CPU here; less on a desktop CPU; ≈ €0.01–0.02 electricity |
| Music, SFX, captions, QC | €0 | €0 |
| **Variable total** | PoC: **€0** (no paid calls; reused paid Ep02 narration) | **≈ €0.15** with set-up A; set-up B adds the image API cost |

Claude subscription and development time are fixed costs (excluded per brief). v2 cuts Claude's per-episode
work from ~1,100 lines of scene code to a ~150-line storyboard.

## 4. Migration milestones
1. **Done (this commit):** `ghm2` engine (plates, camera, puppet, overlays, mograph, transitions, renderer) and the 20 s PoC from existing assets; verified.
2. Client review of the PoC look; decide on the mosaic filter (A/B) for continuity with the channel's brand.
3. Windows set-up of stages 3–4, then measure real per-video GPU time and energy.
4. Style LoRA + character sheets for the first batch (W44 scripts reused; storyboards rewritten as 8–12 compositions).
5. First full 60 s v2 episode: preview → approval → final; measure the actual variable cost.
6. Update `autopilot/AUTOPILOT.md` for the hybrid or cloud set-up; schedule only after client authorisation.

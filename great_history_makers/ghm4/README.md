# ghm4: illustration plates + motion graphics (approved direction, 2026-10-25)

The client approved the look of `GreatHistoryMakers/Napoleon_20s_POC`: a new composition for each narrative beat,
motion graphics, cinematic typography, transitions, sound design, and **limited** character animation (one visible
blink in a close-up; flags, smoke, marching ranks, cloud drift). ghm4 turns that one-off renderer into a data-driven
pipeline whose illustrations come from local ComfyUI (no paid image or video services).

## Automated path (recommended): `python -m ghm4.episode run episodes_v4/<id>`
One `episode.json` per video (beats with narration cues, shot types, illustration prompts, map files, text). The
command runs every step that is possible and stops with the next action: queue the illustration job → (PC worker) →
pick candidates (`pick --auto` ranks them technically; the contact sheet is still reviewed) → (PC worker: 2× upscale)
→ plates with automatic metadata from `ghm4/presets.py` (sky line, tricolour flags, smoke band, cannon points,
marching ranks, cloth wind, matte) → `annotations.json` for eyes/hands of close-ups (`sheet` makes a grid) →
storyboard timed to the narration → render → narration + captions → verification. Example:
`episodes_v4/napoleon_3scene_test/`. Costs and timings: `ghm4/COSTS_AND_TIMING.md`. Audit: `ghm4/AUDIT_2026-10-25.md`.

## Stages (manual building blocks)
| # | Stage | Where it runs | Command / file |
|---|---|---|---|
| 1 | Script, history check, storyboard (one composition per beat) | cloud | `NARRATION.txt`, `HISTORY.md`, `storyboard.json` |
| 2 | Illustration jobs from the storyboard beats | cloud | `jobs/specs/<id>.json` → `python -m ghm4.illustrate job <spec>` |
| 3 | Generate candidates (SDXL + style and face IP-Adapters, 9:16, hires 1152×2016; optional FLUX schnell) | **your PC** | `comfyui/worker/run_worker_once.bat` |
| 4 | Review, pick, 2× upscale (2304×4032), place in the episode | cloud + PC | `ghm4.illustrate pick` / worker / `ghm4.illustrate place` |
| 5 | Plate metadata: eyes for the blink, flag poles, smoke bands, ranks; automatic matte with QA | cloud | `plates/<shot>.json`, `python -m ghm4.plate_tool overlay`, `python -m ghm4.masks make <plate> <meta>` |
| 6 | Narration: client voice file, or ElevenLabs only with explicit approval | cloud | `python -m ghm4.narrate <sb> tts [--confirm]` |
| 7 | Forced alignment and shot re-timing to the real audio | cloud | `ghm4.narrate <sb> align`, `ghm4.narrate <sb> retime` |
| 8 | Picture render (720p preview, then 1080p) | cloud | `python -m ghm4.render <sb>.timed.json [--final]` |
| 9 | Narration mix (ducked music and SFX) and burned subtitles | cloud | `python -m ghm4.narrate <sb> finish <picture.mp4>` |
| 10 | Verification and branding | cloud | `tools/verify_delivery.py`, `tools/brand.py` |
| 11 | Visual QC: flags suspicious shots (black / frozen / washed-out frames, soft or over-enlarged plates, clipped or overlapping map labels, low-contrast titles, bright subtitle background) and writes a per-shot contact sheet | cloud | `python -m ghm4.qc <storyboard> <video>` (also run by `ghm4.episode render`) |
| – | Re-render only the shots that failed review; other frames are copied | cloud | `python -m ghm4.render <sb> --patch <old_picture.mp4> --shots b02,b07` |
| – | Cloud-side 2x Real-ESRGAN for small plates or crops (hash-pinned weights, no PyTorch) | cloud | `python tools/esrgan_cpu.py <RealESRGAN_x4plus.pth> in.png out.png` |

Publishing and daily scheduling are **not** part of the pipeline until the client authorises them.

## Storyboard
See the docstring of `ghm4/render.py`. Shot types: `plate` (illustration with camera move, parallax if the plate has a
matte, effects from its metadata, blink times, cannon puffs, haze, text) and `map` (JSON map, see `ghm4/mapshot.py`).
Transitions: `whip`, `ink`, `flash`, `dissolve`, `cut`. Text items: `ghm4/text.py` (`draw_items`).
Regression example: `GreatHistoryMakers/Napoleon_20s_POC/ghm4_port/storyboard.json` reproduces the approved POC.

## Tests and status
`python -m ghm4.tests.run_all` (7 tests, about 2 min; `--quick` skips the matte model and the worker test;
`--update-golden` re-blesses golden frames after an approved visual change). Matte model: `pip install rembg onnxruntime`
(BiRefNet-general-lite, MIT, downloaded once from GitHub). Component status, timings and Claude-dependent steps:
`GreatHistoryMakers/Renderer_Demo/RENDERER_STATUS.md`. Demo storyboard: `GreatHistoryMakers/Renderer_Demo/storyboard.json`.

## Rules learned so far
- **Captions own the band around y = 1410/1920** (design y 900–990). In narrated episodes put titles and lower thirds
  above design y 840, or show them only between cues; `ghm4.narrate check` reports collisions.
- Mattes: production method `hybrid` (BiRefNet + hint outline + QA). A QA failure means no matte (one layer), never a
  wrong one. Add props (draped flags, crates, maps) with `include` polygons.
- A blink only reads in a close-up (eye ≥ about 50 px wide on screen). Mark the eye outline in the plate metadata
  after reviewing the upscaled plate.
- Plates are rendered at the resolution each shot needs (its maximum zoom), so 2304×4032 plates cost little in wide shots.
- Prompt structure: framing, scene, character descriptor, style rendering, lighting, 9:16 composition rule. Keep the
  character descriptor and style text identical across shots; vary framing, scene and light.

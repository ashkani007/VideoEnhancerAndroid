# ghm4: illustration plates + motion graphics (approved direction, 2026-10-25)

The client approved the look of `GreatHistoryMakers/Napoleon_20s_POC`: a new composition for each narrative beat,
motion graphics, cinematic typography, transitions, sound design, and **limited** character animation (one visible
blink in a close-up; flags, smoke, marching ranks, cloud drift). ghm4 turns that one-off renderer into a data-driven
pipeline whose illustrations come from local ComfyUI (no paid image or video services).

## Stages
| # | Stage | Where it runs | Command / file |
|---|---|---|---|
| 1 | Script, history check, storyboard (one composition per beat) | cloud | `NARRATION.txt`, `HISTORY.md`, `storyboard.json` |
| 2 | Illustration jobs from the storyboard beats | cloud | `jobs/specs/<id>.json` → `python -m ghm4.illustrate job <spec>` |
| 3 | Generate candidates (SDXL + IP-Adapter style, 9:16, hires 1152×2016) | **your PC** | `comfyui/worker/run_worker.bat` |
| 4 | Review, pick, 2× upscale (2304×4032), place in the episode | cloud + PC | `ghm4.illustrate pick` / worker / `ghm4.illustrate place` |
| 5 | Plate metadata: eyes for the blink, flag poles, smoke bands, ranks, optional matte | cloud | `plates/<shot>.json`, `python -m ghm4.plate_tool overlay|mask` |
| 6 | Narration: client voice file, or ElevenLabs only with explicit approval | cloud | `python -m ghm4.narrate <sb> tts [--confirm]` |
| 7 | Forced alignment and shot re-timing to the real audio | cloud | `ghm4.narrate <sb> align`, `ghm4.narrate <sb> retime` |
| 8 | Picture render (720p preview, then 1080p) | cloud | `python -m ghm4.render <sb>.timed.json [--final]` |
| 9 | Narration mix (ducked music and SFX) and burned subtitles | cloud | `python -m ghm4.narrate <sb> finish <picture.mp4>` |
| 10 | Verification and branding | cloud | `tools/verify_delivery.py`, `tools/brand.py` |

Publishing and daily scheduling are **not** part of the pipeline until the client authorises them.

## Storyboard
See the docstring of `ghm4/render.py`. Shot types: `plate` (illustration with camera move, parallax if the plate has a
matte, effects from its metadata, blink times, cannon puffs, haze, text) and `map` (JSON map, see `ghm4/mapshot.py`).
Transitions: `whip`, `ink`, `flash`, `dissolve`, `cut`. Text items: `ghm4/text.py` (`draw_items`).
Regression example: `GreatHistoryMakers/Napoleon_20s_POC/ghm4_port/storyboard.json` reproduces the approved POC.

## Rules learned so far
- **Captions own the band around y = 1410/1920** (design y 900–990). In narrated episodes put titles and lower thirds
  above design y 840, or show them only between cues; `ghm4.narrate check` reports collisions.
- A blink only reads in a close-up (eye ≥ about 50 px wide on screen). Mark the eye outline in the plate metadata
  after reviewing the upscaled plate.
- Plates are rendered at the resolution each shot needs (its maximum zoom), so 2304×4032 plates cost little in wide shots.
- Prompt structure: framing, scene, character descriptor, style rendering, lighting, 9:16 composition rule. Keep the
  character descriptor and style text identical across shots; vary framing, scene and light.

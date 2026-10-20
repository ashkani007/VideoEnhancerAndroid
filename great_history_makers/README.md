# Great History Makers — mosaic animation pipeline

A local, reusable production system for short vertical history documentaries in an
**ancient Roman mosaic style**: thousands of individual tesserae with grout, flat
illustrated figures, and restrained 2D animation. Everything runs on your own
machine with Python + FFmpeg. There is no cloud video generation and no paid service.

Episode 1: **Cyrus the Great — The Conquest of Babylon (539 BCE)**, 20 s, 9:16.

## Quick start (Windows 11)

```powershell
# one-time
winget install Gyan.FFmpeg          # or put ffmpeg.exe on PATH
py -m pip install -r requirements.txt

# 720p preview (about 1 min on 4 cores; cached tiles make re-renders faster)
py produce.py episodes\ep01_cyrus_babylon

# 1080x1920 master
py produce.py episodes\ep01_cyrus_babylon --quality final

# single frame / partial render for quick look-dev
py produce.py episodes\ep01_cyrus_babylon --still 12.5
py produce.py episodes\ep01_cyrus_babylon --frames 0 120
py produce.py episodes\ep01_cyrus_babylon --scene 2       # one scene as a standalone clip
```

Outputs go to `output/<episode>/`: MP4 (H.264, yuv420p, AAC, faststart), `.en.srt`,
an automatic `_qc.json` report and a `_contact.png` contact sheet.

**GPU:** the renderer probes **NVENC** (RTX 4060) and uses it for encoding when it is
available, otherwise libx264. Frame compositing runs on the CPU in parallel worker
processes (`--workers N`). It is light 2D work (about 0.2 s per frame at 720p per core),
so GPU compositing is not needed.

## How it works

```
episode.json ─┐ script, timing, subtitles, titles, audio cues
scenes.py ────┤ scene composition (layers, figures, camera, fx)
              ▼
mosaic/painter.py      vector art in resolution-independent design units (frame = 1080×1920)
mosaic/tessellate.py   flat art → tesserae: contour-following rows (andamento) + brick grid,
                       Voronoi cells cut by colour regions, stone colour variation, bevel, grout
mosaic/scene.py        layers with parallax; Figure = cut-out rig of separately tessellated parts
mosaic/motion.py       idle / walk-cycle / gesture recipes (small, smooth, no jitter)
mosaic/compositor.py   premultiplied compositing; gentle mesh deformation for cloaks and banners
mosaic/fx.py           dust, glow, haze, light shafts, grade, vignette, tile-by-tile transitions
mosaic/text.py         subtitles, title cards, SRT
mosaic/audio.py        synthesised score + SFX (royalty-free by construction), narration ducking
mosaic/render.py       parallel frames → FFmpeg (NVENC / x264) → mux + EBU R128 loudness
mosaic/qc.py           format checks, flicker/black-frame detection, loudness, contact sheet
```

**Why the mosaic stays stable:** each layer or body part is tessellated **once** into a
sprite. Animation moves those sprites rigidly (cut-out rigging) or bends them by at most
a few tiles (cloth). Cloth is animated with **rigid-tile deformation**: each tessera
is moved whole along the wave, and the gaps that open show grout, so stones never
stretch or melt. Water animates **per tile** (each stone changes colour; none moves).
Tile size is defined in design units, so the 720p preview and the 1080p master share
the same tile layout.

**Consistency:** characters are code (`mosaic/library/figures.py`) drawn from one
palette (`mosaic/palette.py`). Cyrus in scene 1 and in scene 3 is literally the same
asset. Future episodes reuse the library and add designs to it.

## Making a new episode

1. Copy `episodes/_template` → `episodes/epNN_topic`.
2. Research first: write `HISTORY.md` (established / propaganda / disputed / reconstruction),
   then the narration lines and `NARRATION.md`.
3. Edit `episode.json`: scenes and timing, transitions, subtitles, titles, SFX cues.
4. Compose scenes in `scenes.py` from the library (add figures or environments there if needed).
5. `--still` for look-dev, then a preview, then check `_contact.png` and `_qc.json`, then render `--quality final`.

## Narration

Put the voice-over at `episodes/<ep>/audio/narration.wav` (any sample rate, mono or stereo).
The mixer ducks the music under it automatically. ElevenLabs workflow: see
`episodes/ep01_cyrus_babylon/NARRATION.md`. No synthetic voice is generated without approval.

## Bringing in external art (references, AI plates, hand drawings)

`python tools/mosaicify.py in.png out.png --tile 8 --palette` posterises any image and
converts it to the same tesserae. Transparent PNG layers keep their alpha. You can then
load them as sprites (`make_sprite` with a draw function that pastes the image), or split a
character into head / body / arm PNGs and rig them like the library figures.
Suggested prompts for a free local SDXL/Flux model are in `episodes/ep01_cyrus_babylon/prompts.md`.

## Known limitations

- Art is procedural vector drawing: simple shapes by design. Richer plates can be added through `mosaicify`.
- Fonts: the system falls back to Caladea/DejaVu/Georgia. For a more Roman look, drop the OFL fonts
  **Cinzel** and **EB Garamond** into `assets/fonts/`; they are picked up automatically.
- The score is synthesised: tasteful and legally clean, but simple. You can replace it with a licensed track
  by mixing it into `audio/` (extend `audio.build_mix`).

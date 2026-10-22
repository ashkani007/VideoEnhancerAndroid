# Lessons learned (verified)

Each entry says how it was verified. Add new lessons at the end, with a date and an episode id.

## Client feedback (direct)
1. **The V1 style was approved:** mosaic tesserae, flat figures, warm palette (ep01 V1, 2026-10-20).
2. **"Too much like moving still images":** characters need independent motion, not just camera moves (V1 → V2).
3. **"Reused the same scenes repeatedly, looked like a slideshow":** at least 12–16 distinct shots, never loop (1b brief).
4. **"Too pale, dusty, muted, flat":** remove beige washes and recolour the source art, not only the grade (V3 brief).
5. **"Subtitles too high":** use one lower-middle position, never in the top part (V3 brief).
6. **"Videos look too flat":** the next target is a 2.5D mosaic with volume, shadows and spatial camera (2.5D brief).
7. **Branding:** the original logo only, small watermark, tasteful end signature (V4 brief).

## Technique (verified in renders)
- **Tile stability:** whole-sprite rigid moves keep tiles stable. Pixel warping (`wave_deform`) visibly stretches
  stones. Rigid-tile waves fix it; gaps must show grout colour, not background. White specks were found and fixed in V2.
- **Grade:** recolouring the palette and the art gave a much bigger and cleaner gain than grading.
  Mean saturation 0.395 → 0.604 with no clipping (V3 QA).
- **Subtitles:** PocketSphinx forced alignment matches ffmpeg silencedetect pauses within about 30 ms.
  It needs the verified transcript and constrained decoding for unclear words (1b).
- **Mix:** a voice-referenced mix (bed 20 dB under speech, 11 dB in pauses) brought ASR word mismatch on the
  final mix to the level of the clean narration (11 % vs 13 %). The first naive mix gave 49 % (1b).
- **Encode:** a 13 Mbps 2-pass encode was visually identical to the 56 Mbps master at 1:1 crops (SSIM 0.95).
  It keeps files under GitHub's 100 MB limit.
- **Composition checks:** shot sheets (one frame per shot) catch composition defects quickly. Examples: cropped guards,
  faces in the caption band, a sun hidden behind a figure.
- **Logo extraction:** a colour/brightness matte plus hole filling worked. Dark logo regions touching the background
  (the MAKERS ribbon) needed explicit restoration inside the convex hull (V4).
- **2.5D (experiment, 2026-10-21):** per-tile form shading keeps one flat colour per stone but adds visible volume.
  - The first strength (0.75) was too subtle at phone size; 1.25 / ambient 0.28 reads clearly.
  - Depth slices of one plane must overlap by about 30 units, or differential parallax opens black seams.

## Process
- Render a single shot (`--scene N` or `--still`) before a full render. Inspect crops at 1:1, not just thumbnails.
- Build the episode once in the parent before forking workers. Write cache files atomically.

## 2026-10-22: experiment C (volume, IK gait, tracking)
- **Banded sculpting beats continuous per-tile shading for volume.** Quantising each part's lit volume into 5 bands
  *before* tessellation makes tile rows follow the form. It reads as sculpted mosaic at 1:1, while continuous shading (B) was subtle.
- **Self-shadows (offset, blurred silhouettes of front parts) are the cheapest way to get joint occlusion** and
  limb-over-body depth. Parameters: offset (7, 9)·k units, blur 3·k, strength 0.45.
- **Foot planting needs two conditions:** (a) body speed = stride/period × scale with a linear stance sweep,
  verified numerically at 0.00 drift; and (b) each rank placed at the exact centre of a ground depth slice,
  otherwise the camera truck makes feet slip against the paving.
- **Stride and lift must be scaled to leg length:** stride 500 / lift 70 read as goose-stepping; 400–450 / 26–36 read naturally.
- **Measuring parallax by phase correlation per region** gives objective depth evidence (B −0.39 vs C 1.42 px/frame on the near ground).
- **Cool shadow tints lower measured saturation** (−5 %), even when exposure is matched; check the saturation of every new shadow layer.

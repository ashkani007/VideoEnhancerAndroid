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

## 2026-10-22: experiment D. FAILURE in C: orientation disconnected from the path (client feedback)
- **What went wrong:** C's soldiers were fixed-profile sprites translated along routes. The column turning into the gate
  kept facing sideways and slid into depth. Client: "movement and body orientation are disconnected from their walking paths".
- **Rule (apply to every future shot with moving figures):**
  1. Define each figure's route as a *world-space* curve on the ground (`turnrig.Path`), never as screen translation.
  2. Hip yaw = path tangent. Torso leads ~28 units and head ~70 units along the path (capped ±35° / ±50°),
     so the head turns first.
  3. Any figure whose heading changes by more than ~20° needs a multi-view rig (`turnrig.TurnSoldierAssets`:
     9 views 0–90°, mirrored); never rotate a flat sprite.
  4. Put joints in 3D and project them through the scene camera (`Ground.at_height`), so size and foot placement follow the
     road's perspective automatically.
  5. Plant feet in world space (fixed per stance, IK legs). Verify drift numerically (D: 0.0).
  6. Entering a doorway or tunnel: draw behind the front plane, clip by the opening outline at the figure's own depth,
     darken by location. Never fade out before the threshold.
  7. Verify with metrics: |body yaw − travel direction| (D ≤ 2.2°), head lead, gate-plane crossing time,
     a frame strip every 0.5 s and 1:1 crops at the threshold.
- **Timing:** a natural approach, turn and entry at about 1 m/s needs about 6.5 s. Extend test clips rather than speeding up the walk.
- **Trade-off found:** stepped ground slices limit camera motion when figures travel in depth (feet drift against the paving).
  A strong truck needs a per-pixel ground projection.

## 2026-10-22: Episode 02 (Napoleon) preview
- **Costume system generalises turnrig:** `TurnSoldierAssets(..., costume=...)` draws any uniform from a costume object
  (torso/head/hat per view angle, `tubes` for limb colours, optional weapon/pack/flag). One rig file now drives line
  infantry, Old Guard, redcoats, the winter retreat and Napoleon himself (`mosaic/library/napoleonic.py`).
- **Front views (0–180°, 17 views) are needed** as soon as figures walk *toward* camera (s12) or turn away from it (s11).
  Napoleon's hat must change silhouette with view angle (bicorne width 46 + 92·|cos θ|); a fixed hat sprite looks pasted on.
- **Shared shot helpers (`mosaic/shotkit.py`)** made 17 distinct shots feasible in one pass: `cam()` keyframe camera, smoke `puffs`,
  muzzle `burst`/`flash`, per-tile flame/water colour animation, `ground_slices`, and `finish()` looks per chapter.
- **Plan a palette arc per chapter** (warm imperial, fire red, cold winter, steel battle, sunset exile) instead of one grade;
  it raised variety without breaking the house style.
- **Silhouettes against fire:** darken figures to ×0.22 instead of drawing new art; reads as backlit and keeps tiles.
- **Caption band check must include moving figures over time**, not only the mid-shot frame: s12's walker entered the band at
  about 40 s although the end-of-path position was safe.
- **Without narration, estimated captions are a stop-gap only.** Mark `subtitles_status` PROVISIONAL in episode.json and the QA report,
  and re-align once audio exists.

## 2026-10-23: Episode 02 narration (ElevenLabs, approved)
- **Price first, then generate once:** `estimate_only` gave 1,676 credits for two takes (838 characters each) before spending.
- **Text length estimates run short for this voice:** 838 characters / 137 words took 66.0–67.1 s with eleven_v4 Max
  (about 2.1 words/s including ~0.7 s line pauses), not the 59–64 s estimated. Budget about 125 words for a 60 s Short with this voice.
- **Re-timing without re-editing:** map every timed field (scene starts, transitions, titles, SFX, melody notes) piecewise-linearly
  from the estimated line spans to the aligned line spans. One script kept all 17 shots on their lines.
- **Alignment check:** PocketSphinx line starts matched ffmpeg silencedetect within 0.03 s; years need spoken forms in
  `captions.SPOKEN` and the align transcript ("eighteen oh four").

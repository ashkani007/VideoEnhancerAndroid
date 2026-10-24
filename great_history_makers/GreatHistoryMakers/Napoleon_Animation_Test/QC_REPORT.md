# Napoleon image-to-animation test: QC report

**Output:** `final/Napoleon_Animation_Test.mp4`. ffprobe: H.264 High, 1080×1920, yuv420p, 30 fps, 150 frames, 5.00 s,
about 4.2 MB, no audio, no subtitles, no watermark. A full FFmpeg decode completed without errors.
**Source:** the approved illustration (`source/napoleon_master.png`, 941×1672).

## Pipeline actually used
No image-to-video model was available. The ElevenLabs connector in this session is restricted to voice and refuses image
and video; the machine has no GPU; model hosts are blocked. So this is a **local 2.5D animation** of the original pixels
(`project/animate.py`):
1. **Layers:** a foreground matte (Napoleon, rocks, draped flag) made with OpenCV GrabCut seeded by a hand-drawn
   silhouette (`project/mask_foreground.png`), over a background plate whose hidden area was inpainted
   (`project/background_plate.png`).
2. **Controlled local warps and repaints**, each limited to a feathered region:
   - **Eyes:** the iris drifts about 2.6 px (source) toward the horizon over 0.15–1.25 s. One blink at 0.92–1.12 s: a lid painted
     in the sampled skin colour with a lash line on its edge.
   - **Expression:** brows lower about 1–2 px and knit at the inner end; the mouth corner tightens (0.95–1.55 s).
   - **Head and hat:** −1.3° rotation about the neck plus a 2.6 px shift toward the horizon (1.5–3.4 s), feathered into the collar.
   - **Wind:** coat flaps (left edge, right panel), the draped foreground flag and the hair; the map, spyglass and crate are
     excluded (max change there 0.003 vs 0.66 in the fabric).
   - **Background:** three flags wave on a travelling wave pinned at the pole; soldiers bob in a staggered marching rhythm;
     the rider bobs; two stylized smoke layers drift across the battlefield; the smoke column billows; clouds drift.
   - **Light:** a warm sweep across the face and a slightly warmer sun (3.4–5 s).
3. **Camera:** a barely perceptible drift (0–3.4 s), then an eased push-in toward the face (3.4–5 s). The foreground
   zooms more than the background, giving real parallax.
4. **Encode:** Lanczos resampling to 1080×1920, light sharpening, x264 CRF 16.

## Inspection at 0, 1, 2, 3, 4, 5 s
`qc/frames_0_to_5s.png`, `qc/face_0_to_5s.png`, `qc/blink_sequence.png`, `qc/frame_*s.png`.

| Check | Result |
|---|---|
| Character consistency | Face, hair, hat, uniform and proportions are the original pixels in every frame; no redesign |
| Facial movement | Gaze drift, blink (closed at about 1.0 s), brows set, mouth tightens. All subtle by design |
| Head / clothing | Head and hat turn slightly; coat flaps, draped flag and hair move in the wind |
| Background | Flags wave, smoke drifts, soldiers bob, clouds drift: independent of the camera |
| Not a zoom-only clip | The motion heat map between 1.6 s and 2.1 s (camera excluded) shows change in face, hat, hair, coat, flags, smoke, soldiers and drape |
| Temporal stability | Mean frame difference 1.01. The push-in rises and falls smoothly (0.13 → 4.0 → 0.7). Largest change between consecutive frame differences: 0.31, so no flicker or pops (`qc/temporal_stats.json`) |
| Artifacts | No face morphing, melting or warped hands found. Minor: a faint lighter edge beside the collar where the inpainted plate shows during the head turn |

## Honest limitations
- **Not generative animation.** Expression changes are small warps and repaints of the existing drawing. Large acting
  (a real 3D head turn, talking, arm gestures) needs an image-to-video model or a layered character rig drawn for animation.
- **Resolution:** the source is 941 px wide, upscaled 1.15× (start) to 1.25× (end of the push). It is slightly softer than a native
  1080×1920 render; an AI upscaler (e.g. on the RTX 4060) would sharpen it.
- **Subtlety:** the head turn is about 1.3°, and the gaze and brow changes are a few pixels. They read clearly in the face crop but are gentle at
  phone size, as requested ("subtle, cinematic").

## Cost
No paid services or credits were used. Rendering took 60 s on 3 CPU workers in the cloud container (preview 35 s).

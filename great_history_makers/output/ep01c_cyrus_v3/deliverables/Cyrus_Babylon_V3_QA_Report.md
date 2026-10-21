# Cyrus the Great: The Conquest of Babylon (V3 QA report)

**Final file:** `Cyrus_Babylon_V3_Final_1080x1920.mp4`

ffprobe on the final file:

| Property | Value |
|---|---|
| Video | H.264 High, 1080×1920, 30/1 fps, yuv420p |
| Audio | AAC 48 kHz stereo |
| Duration | 56.30 s |
| Bitrate | 12.97 Mbps (2-pass) |
| Size | 91 MB |
| Watermarks / black bars | None |

The 56 Mbps CRF-16 render master stays local, outside git. The upload encode was compared with it: SSIM 0.949, and the tiles are visually identical at 1:1 crops.

## Scene-by-scene: kept, improved, replaced (18 shots)

V2 had 19 shots. In V3, 3 shots were replaced, 2 rebuilt, 2 merged into 1, 1 kept and 10 improved.

| # | Time (s) | Shot | Verdict | What was actually done |
|---|---|---|---|---|
| 01 | 0.00–2.25 | open | **Replaced** | New hero composition: glazed blue walls, Ishtar Gate, Etemenanki, golden sun; per-tile water shimmer with sun glitter; boat + rower; birds; foreground palm reveal sweeping across |
| 02 | 2.25–5.30 | camp | **Improved** | New palette and grade; Cyrus head turn and hand gesture; three waving standards; flickering fire; walking sentries |
| 03 | 5.30–8.25 | market | **Improved** | Repainted colours; walkers with varied cadence; donkey; caption band cleared of faces |
| 04 | 8.25–10.70 | opis | **Improved** | Added a close foreground rank (with standard bearer) passing the camera, dust at every footfall, greener field; four ranks plus cavalry and arrows |
| 05 | 10.70–13.60 | advance | **Improved** | Regraded; 26-soldier column with per-soldier phases; shimmering canal |
| 06 | 13.60–17.80 | citizens | **Replaced** | Was a static wall-tower shot. Now a reaction shot: rooftop and street crowd with individual reactions (look, point, talk, hand to chest, rise on toes); foreground pillar reveal; standards moving along the far wall |
| 07 | 17.80–19.60 | sources | **Improved** | Regraded and relabelled at mid-frame |
| 08 | 19.60–21.70 | entry | **Improved** | Near column lifted above the caption band; marching dust from each footfall; walk cycle with weight transfer and per-soldier variation; Cyrus not shown at the gate |
| 09 | 21.70–24.30 | hall | **Improved** | Regraded |
| 10 | 24.30–26.28 | closeup | **Kept** | Regraded only |
| 11 | 26.28–28.10 | marduk | **Improved** | Priests repositioned out of the caption band; regraded |
| 12 | 28.10–31.45 | cylinder | **Improved** | Regraded with local contrast for the clay and wedges |
| 13 | 31.45–35.55 | restoration | **Improved** | Workers repositioned; regraded |
| 14 | 35.55–38.15 | foundation | **Replaced** | Was a third consecutive inscription close-up. Now hands set the clay cylinder into a brick foundation niche (labelled reconstruction), lamp flicker, dust in the light |
| 15 | 38.15–41.50 | scribe | **Improved** | Regraded |
| 16 | 41.50–45.45 | map | **Rebuilt** | Larger scale, navy-outlined seas with wave tesserae, turquoise rivers, Zagros mountain marks, tile-by-tile reveal of the Persian realm then Babylonia in gold, labels; marked 'approximate extent' |
| 17 | 45.45–52.65 | centuries | **Merged** | V2 decay and portrait shots combined into one continuous move: tesserae fall, then fly in to form the portrait |
| 18 | 52.65–56.30 | finale | **Rebuilt** | New composition: dark silhouette on a ridge, crimson standard waving, a large sun beside him, deep navy, burgundy and orange sky, birds; short 0.35 s fade to the title (no long black) |

## Colour work actually performed

The colour changes go beyond a saturation filter.

- **Artwork recoloured at the source.** The tesserae palette was redesigned with deeper lapis and cobalt, turquoise, saturated terracotta and burnt orange, amber and gold, crimson and burgundy, emerald and olive, and navy shadows. Grout was darkened for tile separation. Every sprite was re-tessellated from these colours (cache version bumped).
- **Washes removed.** V2's beige haze bands were deleted. White glows became restrained amber sunlight at about 55 % strength, light shafts are at 60 %, and dust is at 75 %.
- **New `CinematicGrade` on every shot**, replacing the old flat grade. It adds:
  - local contrast (unsharp on luminance only, so no halos on colour edges);
  - a gentle S-curve;
  - split toning: navy shadows and golden highlights;
  - vibrance plus saturation;
  - a soft highlight knee.
  - Per-look tuning: default, interior, object, sunset.
- **Skies:** cobalt to gold gradients replace the pale bone skies.
- **The Ishtar Gate** is now saturated blue glaze against warm sandstone, a deliberate focal point in shots 1, 6 and 8.
- **Measured change, V2 draft vs V3 final** (mean over frames sampled at 3 fps):

  | Measure | V2 | V3 | Change |
  |---|---|---|---|
  | Mean saturation (HSV-style) | 0.395 | 0.604 | +53 % |
  | Mean luminance contrast | 0.125 | 0.148 | +19 % |
  | Clipped white pixels | 0 % | 0 % | none |
  | Crushed black pixels | 0 % | 0.23 % | only inside the finale silhouette |

  The saturation increase is above the 20–35 % starting target. That is because the source palette itself was replaced, not because the grade was pushed. The contact sheet shows no neon or clipped colours.

## Animation work actually performed

- **Walk cycle:** weight transfer (forward lean, a forward surge at each push-off, a drop at double support), alternating arms and legs, and a spear that counter-sways on its own pivot.
- **Per-soldier variation:** each soldier gets their own step phase, cadence (±6 %), stride and height. No group moves in lockstep.
- **Dust at every footfall** in the Opis, Entry and close Opis foreground ranks, synced to each walker's cadence.
- **Civilian reactions:** a new `react()` motion with five individually timed kinds (look, point, talk, hand to chest, rise on toes), used in the new citizens shot.
- **New motion in replaced or rebuilt shots:**
  - opening: per-tile water shimmer with sun glitter, a moving boat and rower, birds, and a foreground palm reveal;
  - foundation: hands lower the cylinder into the niche and withdraw, with lamp flicker;
  - map: a tile-by-tile territorial reveal plus a pulsing marker;
  - centuries: tiles fall, then fly in to assemble the portrait;
  - finale: the cloak and standard move in the wind, with birds.
- **Tile stability:** cloth uses rigid-tile deformation (each stone moves whole, and gaps show grout). Water, fire and light animate per tile in place. Character parts are rigid cut-outs. Nothing is warped.
- **Camera:** each shot has its own move (push-in, pull-back, lateral track, tilt, foreground reveal). There is no shake.

## Subtitles

- **Timing** comes from offline forced alignment of the original narration (PocketSphinx), word by word. None of it is estimated.
- **Wording** follows the narration exactly, in 20 phrase groups of at most two lines.
- **Placement:** one consistent lower-middle position for the whole film, y = 1410 of 1920 (73 %). It is never in the top portion and stays above the Shorts control area. The text is horizontally centred inside the safe width, clear of the right-hand icon rail.
- **Style:** ivory text with a dark outline and soft shadow. No box.
- **Composition:** V2 shots were adjusted so no face sits in the caption band (market women, Marduk priests, restoration workers, entry near column).
- **Exported** as `Cyrus_Babylon_V3_Subtitles.srt`.

## Audio

- **Narration** is the original ElevenLabs file, unchanged. Measured in the final: 0.0 ms offset, waveform correlation 0.978 against the source.
- **Speech-recognition check:** 11 % word mismatch on the final mix, against 13 % on the clean narration alone. The bed does not mask speech.
- **Mix:** voice-referenced. Music and SFX sit 20 dB under the voice while words are spoken and 11 dB under it in pauses.
- **Loudness:** −14.7 LUFS integrated, true peak −1.2 dBFS.
- **Sound design** is all synthesised in-house, so there are no licensing issues:
  - modal drone with a ney-like melody and soft frame drum;
  - wind, river water, fire, banner flutter;
  - marching feet and hooves, crowd murmur;
  - hammer taps, stylus, falling-tile clinks;
  - soft transition whooshes and an end chime.

## QC checklist

| # | Check | Result |
|---|---|---|
| 1 | Scenes visually distinct | 18 shots, see `Cyrus_Babylon_V3_ContactSheet.png` |
| 2 | Repeated footage | Automated scan of every 1 s frame against all frames more than 3 s away: 0 near-identical pairs |
| 3 | Animation continuity | Frame-difference scan: no flicker spikes outside transitions and the intentional tile-assembly shot |
| 4 | Colour saturation and consistency | One grade family per look, measured above |
| 5 | Tesserae recognisable | Checked on 1:1 crops of the final encode |
| 6 | No deformation | Rigid cut-outs and rigid-tile cloth |
| 7 | Narration intact | Offset and correlation above |
| 8 | Subtitles accurate and safely placed | Aligned timing; representative frames inspected |
| 9 | Music and SFX don't mask speech | ASR check above |
| 10 | Frozen, black or glitch frames | None detected |
| 11 | Resolution and fps | ffprobe: 1080×1920, 30/1 |
| 12 | Watched for defects | Two fixes from frame inspection: shot 6 re-composed so guards were not cropped, and the finale silhouette darkened and re-blocked. A full real-time viewing was not possible in this environment; review relied on frame sampling, crops and the automated checks above |

## Limitations

- **Artwork is drawn in code.** It was created procedurally, with no image-generation service used and no credits spent. It is consistent but simpler than hand-painted plates.
- **The map is hand-simplified.** Coastlines are simplified and boundaries are labelled "approximate extent, c. 539 BCE". Egypt (conquered 525 BCE) is deliberately excluded.
- **Narration transcript caveat (carried over from V2):** "a legitimate king" and "The famous Cyrus Cylinder" were the best-scoring wordings under offline recognition. Please confirm them by listening.
- **Rendering:** this container has no GPU, so encoding used libx264. On the RTX 4060, `render.py` uses NVENC automatically.
- **Memory:** a 1080p render needs about 2.5 GB per worker. Use `--workers 3` on a 16 GB machine.

# Napoleon 20 s proof of concept: QC report

**Output:** `final/Napoleon_20s_POC_720p.mp4`. ffprobe: H.264 High, 720×1280, yuv420p, 30 fps, 600 frames, 20.00 s; AAC
48 kHz stereo; about 14 MB. A full decode completed without errors. Audio peaks at −0.5 dBFS, mean −18 dB.
**Source art:** only the approved illustration (`../Napoleon_Animation_Test/source/napoleon_master.png`). Motion reuses
`../Napoleon_Animation_Test/project/animate.py`. Renderer: `project/render.py`, 172 s on 4 CPU workers. No paid services or credits used.

## Structure: one composition per topic
| Time | Topic | Composition | Motion | Text |
|---|---|---|---|---|
| 0.0–4.4 | Who | Wide establishing shot of the full illustration | Slow parallax pull-back; flags, smoke, marching ranks, clouds | "1805 / NAPOLEON / Europe unites against one man" (letter reveal, gold rule) |
| 4.4–9.0 | The man | Portrait close-up reframed from it (2.0→2.85×) | Push-in, gaze shift, **one blink at 7.42 s** (0.30 s), brow set | Lower third: "Napoleon Bonaparte / Emperor of the French / crowned 2 December 1804" |
| 9.0–15.0 | The campaign | New animated map in the illustration palette | Camera follows the blue French arrow Boulogne → Strasbourg → Ulm → Vienna → Austerlitz; red coalition arrow converges via Olmütz; Ulm ring and pulse; star burst | Date ticker Aug → Sep → 20 Oct → 13 Nov → 2 Dec 1805, city labels, legend |
| 15.0–20.0 | The battle | Battlefield reframed from the right side (2.2–2.5×) | Truck move with settle; flags at 2× wave strength; stronger marching bob; drifting powder smoke; three cannon flashes and puffs in sync with the sound; haze in front of the lens | "AUSTERLITZ / 2 December 1805" → "The Battle of the Three Emperors" |

**Transitions:** whip-zoom with zoom blur (A→B), painted ink wipe with a thin gold edge (B→C), push into the Austerlitz
star plus a warm flash and cross-zoom settle (C→D), fade to black. **Sound:** procedural score (minor mode), wind,
whooshes on the cuts, side drum and marching under the map, cannon, musket volley and flag flutter in the battle. All
synthesised locally (`mosaic.audio`).

## Inspection
`qc/contact_sheet.png` (15 frames), `qc/shot_*.png` (one per composition), `qc/blink_sequence.png`, `qc/temporal_stats.json`.

| Check | Result |
|---|---|
| Four different compositions | Wide figure, face close-up, flat map, battlefield. Different scale, subject and palette weight in each |
| Blink | Visible: closed from 7.49 to 7.62 s, eye about 60 px wide on the 720 px frame. The only blink in the video |
| Map | Arrows draw progressively with travelling dashes; camera follows the head; labels stay screen-size and pinned to the map |
| Battlefield | Flags wave from the pole, ranks bob, smoke drifts through the line, puffs grow, rise and fade |
| Temporal stability | Median frame difference 3.4 (film grain included). Large differences only at the whip-zoom (frames 126–132) and the wipe |
| Text safe zones | All text between y 170 and 1010 of 1280, clear of the Reels/Shorts header and caption area |
| Fixed during QC | Map too tight (read as an empty parchment) → 9 units wide; wipe edge looked like lightning → thinner and dimmer; foreground smoke read as bokeh bubbles → stretched veils; cannon puffs looked like discs → billow clusters; date ticker overlap → sequential |

## History check
Established: the Grande Armée left the Channel camps (Boulogne) in late August 1805; it crossed the Rhine in late September; Mack's
Austrian army surrendered at Ulm on 20 October; the French entered Vienna on 13 November; the Russian and Austrian armies
gathered at Olmütz; Austerlitz was fought on 2 December 1805 ("Battle of the Three Emperors"). Napoleon was crowned
Emperor on 2 December 1804. Simplified: the French arrow is one line for several corps that marched on parallel routes;
the coastline data is hand-traced (`ghm2/data/europe_simplified.json`). The illustration itself is an artistic image, not a depiction of Austerlitz.

## Honest limitations
- **Only one illustration exists**, so compositions A, B and D are reframes of the same image. The brief asked for a new
  illustration at each topic change; that needs new plates (portrait, battle) generated on the client's RTX 4060 with
  the ComfyUI setup in `../../comfyui/`. The renderer takes any plate.
- The B and D reframes are upscaled about 2.1–2.5× from a 941 px wide source. That is fine at 720p but soft at 1080p
  without an AI upscale.
- No narration in this preview. Text carries the story; timings will follow the narration once it is approved.

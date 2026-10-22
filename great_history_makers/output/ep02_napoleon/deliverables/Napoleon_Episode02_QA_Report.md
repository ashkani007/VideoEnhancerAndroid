# Napoleon, From Emperor to Exile: QA report (Episode 02, 720×1280 preview)

**Status:** PREVIEW, awaiting client approval. **No narration audio yet** (ElevenLabs generation needs approval),
so the preview carries the original score and SFX only, and **the subtitle timing is provisional (estimated)**.
The 1080×1920 final will be rendered only after approval and after the narration is generated and forced-aligned.

## Technical check (ffprobe + produce.py QC)
| Item | Result |
|---|---|
| File | `Napoleon_Episode02_Preview_720x1280.mp4`, 48.8 MB |
| Video | H.264 High, 720×1280, 30 fps, yuv420p, 1890 frames, 63.0 s, about 6.0 Mbps |
| Audio | AAC LC 48 kHz, score + SFX only (−14.8 LUFS, true peak −1.4 dBFS) |
| QC | PASSED: no flicker spikes, no black frames; mean frame difference 0.93 (no frozen stretches) |
| Branding | Original gold emblem upper-left (scaled 155 px at 1080, 60 %), 3 s end signature with @great_history_makers_en |
| Colour | Mean saturation 0.591 (mid-shot frames); worst-shot clipping 0.37 % (bright fire and sky tiles) |
| Variety | 17 distinct shots; automated near-duplicate scan of mid-shot frames: 0 pairs with r > 0.9 |

## Rubric scores (1–10) vs Episode 01 (Cyrus V3/V4, approved)
| Category | Ep01 | Ep02 | Evidence |
|---|---|---|---|
| Visual depth | 4 | **6** | Pinhole ground planes with vanishing points in shots 2, 6, 9, 11, 12 and 13; figures scale with depth; contact and cast shadows; nave colonnade parallax (s03). Maps (s04, s10) and the Arc (s16) are still frontal |
| Mosaic consistency | 8 | 8 | Tiles visible in every region; rigid-tile flags and sails; banded sculpt shading on all figures |
| Character animation | 6 | **7** | turnrig walkers with world-planted feet and path-tangent yaw (39 in s02, 28 in s06, 17 in s09 with a slower 1.35–1.42 s gait and a forward lean); Napoleon turns front-to-rear in s11 and walks toward camera in s12; arm rigs (crown lift, pointing, map hand). Turn views are discrete 11.25° steps; horses are simpler profile sprites |
| Cinematography | 6 | **7** | One camera intent per shot (push past gabions, dolly down the nave, crane down the road, crane reveal of Moscow, rack focus on the candle in s05, ship approach) |
| Colour and lighting | 7 | **8** | Planned palette arc: warm imperial, then fire red, cold winter, steel Waterloo, sunset exile. One sun per scene, depth lighting |
| Scene variety | 8 | **9** | 17 compositions, 0 near-duplicates; every line has its own picture |
| Historical accuracy | 8 | 8 | `HISTORY.md` maps all 16 lines to sources (established, propaganda, disputed, reconstruction). On-screen date notes; "Artistic reconstruction" label; the Arc (completed 1836) labelled as a legacy symbol. Uniforms and maps simplified |
| Narration sync | 9 | **n/a (pending)** | No audio yet. Cuts sit on *estimated* line boundaries and must be re-cut to the real voice |
| Subtitle quality | 8 | **5 (provisional)** | Exact approved wording, at most two lines, ivory text with an outline, no box, fixed y = 1410. Timing is ESTIMATED (breaks the house rule until alignment). Defect: s12 at about 40 s, the caption crosses Napoleon's small figure at head height |
| Engagement potential | 6 | **7** | Title and cannon shot inside the first second; picture changes every 2–5 s; strong fire/winter contrast; dusk bicorne ending into the end card |

**Overall:** gains in depth, animation, cinematography, colour and variety. Sync and subtitle quality cannot be
scored fairly until the narration exists.

## Known weaknesses and regressions (honest list)
1. **Subtitle timing is estimated**, not aligned (no audio). This will be fixed with `tools/align_narration.py` after narration.
2. **Narration length is estimated at 59–64 s** (838 characters, 137 words). It may exceed the 55–60 s target by a few seconds; I would not cut the approved script without asking.
3. **s12 caption over a face:** Napoleon's head passes through the caption band around 40 s. Fix for the final: end his path higher (q ≈ 1.75) or start the caption lower in the shot.
4. **Small figures** in s02, s06, s09 and s13: faces are a few tiles wide at phone size; Napoleon is only clearly readable in s01, s03, s05, s11, s15.
5. **Maps are simplified** (s04, s10): approximate borders c. 1811; on-screen labels are small (30–32 px at 1080).
6. **Discrete turn views** (11.25° steps) can show a slight snap during fast turns.
7. **Date notes at the top** (y 260) are small and low-contrast on bright skies (s07, s12, s16).
8. **End card:** the logo sits over the bicorne in the last 3 s. Acceptable, but the hat is hidden at the very end.

## Character reference
`episodes/ep02_napoleon/Napoleon_CharacterSheet.png`: grey redingote over the chasseur green, bicorne worn side-on
(en bataille), white breeches and boots; coronation robes (ermine, crimson velvet, gilt laurel); exile outfit.
The same costume system drives every shot.

## Not done (needs approval)
- ElevenLabs narration, voice `Gfpl8Yo74Is0W6cPUWWT` ("Max"), the exact approved 16-line script, about 838 characters per take.
- The final 1080×1920 render and branding.
- Publishing to YouTube.
- Channel handle: I used @great_history_makers_en (from the provided Instagram screenshot). I could not verify the YouTube handle from this environment; please confirm.

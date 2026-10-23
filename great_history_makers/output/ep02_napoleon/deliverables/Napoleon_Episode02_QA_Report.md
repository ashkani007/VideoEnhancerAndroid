# Napoleon, From Emperor to Exile: QA report (Episode 02, 720×1280 preview)

**Status:** PREVIEW v2 (with narration), awaiting client approval before the 1080×1920 final.
**Narration:** ElevenLabs, voice Max (`Gfpl8Yo74Is0W6cPUWWT`), model eleven_v4, approved script sent unchanged.
Two takes were generated (838 credits each, 1,676 in total, about $0.34); take 2 (66.0 s) is used and take 1 (67.1 s) is kept as an alternate.
**Captions** come from PocketSphinx forced alignment of that audio; the shots, titles, SFX and score were re-timed to the real lines.

## Technical check (ffprobe + produce.py QC)
| Item | Result |
|---|---|
| File | `Napoleon_Episode02_Preview_720x1280.mp4`, 52.9 MB |
| Video | H.264 High, 720×1280, 30 fps, yuv420p, 2046 frames, 68.2 s |
| Audio | AAC LC 48 kHz; narration + original score + SFX (−15.0 LUFS, true peak −1.4 dBFS). Narration offset in the final file 0.0 ms, correlation 0.973 with the source take |
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
| Narration sync | 9 | **9** | Offset 0.0 ms, correlation 0.973; aligned line starts match ffmpeg silence detection within 0.03 s; shot cuts sit on the real line pauses |
| Subtitle quality | 8 | **8** | 27 cues timed from forced alignment; exact approved wording; at most two lines; ivory text with an outline, no box, fixed y = 1410. The caption crosses the small figures' bodies in s12 (faces stay just above the band) |
| Engagement potential | 6 | **7** | Title and cannon shot inside the first second; picture changes every 2–5 s; strong fire/winter contrast; dusk bicorne ending into the end card |

**Overall:** gains in depth, animation, cinematography, colour and variety; sync and subtitles hold the Episode 01 level. Main regression: length (68 s vs 56 s).

## Known weaknesses and regressions (honest list)
1. **Length 68.2 s** (narration 66.0 s): over the 55–60 s target. It is still a valid Short (YouTube allows up to 3 min). Shortening needs either a script cut (client decision) or a different model/voice setting; the narration is not time-stretched.
2. **Words not checked by ear:** the alignment fits cleanly and every line pause is where expected, but a pronunciation check (Bonaparte, Elba, Saint Helena, the years) needs your listen.
3. **s12:** the caption crosses the bodies of the small figures on the beach; faces stay just above the band.
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
- The final 1080×1920 render and branding.
- Publishing to YouTube.
- Channel handle: I used @great_history_makers_en (from the provided Instagram screenshot). I could not verify the YouTube handle from this environment; please confirm.

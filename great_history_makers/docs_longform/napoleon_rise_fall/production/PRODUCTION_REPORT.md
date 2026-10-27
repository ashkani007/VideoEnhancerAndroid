# Production report: *Napoleon: The Rise and Fall of an Emperor* (status 2026-10-27)

**Format:** 1920×1080, 16:9, 30 fps, English. **Planned length:** 19:26 at the planned pace of 140 words per minute.
The final length follows the recorded voice, and is expected at about 17–19 minutes.
**Map style:** the client-approved v2 style, LOCKED (preset `ghm4/data/map_presets/ghm_original_v1.json`).

## Where each production step stands
| # | Step | Status | Output |
|---|---|---|---|
| 1 | Audit of pipeline and reusable assets | **Done** | Renderer, map system, QC, narration and caption stage, music and SFX, job queue: all reusable. Reused: 3 POC paintings (job queued), the approved v2 Ulm–Austerlitz map, the Ep01 Saint Helena map, and Ep01 map data (coalition, Elba, 1811 territories) |
| 2 | Script, complete and fact-checked | **Done** (draft 2, frozen for recording) | `NARRATION.txt`: 7 chapters, 2,277 words, 13,167 characters. Claim table with sources in `../SCRIPT.md` (one wording corrected before recording: the size of Elba) |
| 3 | Shot list and storyboard | **Done** | `SHOT_LIST.md` (planned timecodes), `shots.py` (source), `chapters/ch1–ch7/storyboard.json` (full chapter storyboards: paintings, maps, chapter cards, film title, end card, transitions, captions, music, SFX) |
| 4 | All animated maps, locked style | **Done; footage delivered** | 13 map files, 17 map shots, about 6 minutes of maps (31 % of the film). Every map passes the style lock, the size ranges (graphics scale, arrow stroke), canvas coverage and the QC label checks. Final 1080p map footage per chapter: `output/Napoleon_Doc_ChN_..._MAPS_1080p.mp4`. Checks: decode, black/freeze scan, QC stage (0 errors; one warning on chapter 5 checked as a false alarm, see `output/QC_NOTES.md`). Paper/sea base oversampled like the approved maps (≥1.5×) |
| 5 | Cinematic paintings and animation | **Blocked: image generation** | 57 new paintings plus the 3 POC paintings are designed (composition, period detail, light, motion, effects). 8 jobs (216 images, 4 candidates each) are queued for the PC worker: `jobs/queue/napoleon_doc_*` |
| 6 | Narration, subtitles, music, SFX | **Narration blocked: needs your approval to spend credits.** Music and SFX ready | Procedural music (one seed and key per chapter) and SFX cues are in each storyboard. Subtitles are generated from the forced-aligned narration (never estimated) |
| 7–9 | Chapter renders, QC, assembly | Waiting for steps 5 and 6 | The commands are in the runbook below; each chapter renders, is checked and is assembled automatically |
| 10 | Final MP4, SRT, timestamps, report | Partial | `CHAPTER_TIMESTAMPS.txt` (planned, regenerated after recording), this report |

**No placeholders:** no chapter video is released with stand-in art. The milestone videos so far are the finished map
sequences of each chapter, which are final footage. Their timing follows the planned narration and is re-timed
automatically to the recorded voice.

## Decisions needed from you
| # | Decision | Cost | Unblocks |
|---|---|---|---|
| 1 | **Narration:** approve ElevenLabs, voice Max (`Gfpl8Yo74Is0W6cPUWWT`), one take per chapter of `NARRATION.txt` | About **13,200 credits ≈ $2.65** for one complete take (based on the measured 944 credits per 946 characters). A second take of any single chapter costs about 1,700–2,400 credits | Exact timing, subtitles, final mix; the maps are then re-timed to the voice |
| 2 | **Paintings:** the image route | **A. Your PC:** RTX 4060, ComfyUI install after your approval of the hash-locked installer (about 21 GB of downloads); electricity only, about 2–4 GPU hours for 216 images.<br>**B. A paid hosted image service** you connect; priced per image before any spend.<br>**C. Licensed images you supply** | Chapter videos 1–7 |
| 3 | Optional: the two Belgian maps (chapters 1 and 7) are the only maps closer than continental scale (about 130 km across), so they show no sea. Graphics sizes stay inside the approved ranges. Keep them, or pull back to continental scale with less battle detail? | – | – |

## Runbook after approval (all steps scripted)
1. **Paintings:** PC worker → `py -m ghm4.illustrate status|pick|place` → picks into `production/plates/<shot id>.png` → 2× upscale → plate metadata, matte and QA.
2. **Narration** (per chapter): `py -m ghm4.narrate production/chapters/chN/storyboard.json tts --confirm` (or the connector) → `py production/prep_narration.py chN take.mp3` → `py -m ghm4.narrate production/chapters/chN/storyboard.json align`.
3. **Re-time and rebuild:** `py production/build.py`. Every cut and map event moves onto the real words, and the timestamps become final.
4. **Render and finish** per chapter:
   - `py -m ghm4.render production/chapters/chN/storyboard.json --final`
   - `py -m ghm4.narrate … finish picture.mp4`
   - `py -m ghm4.qc …`
   - visual review
5. **Assemble:** `py production/assemble.py`: concatenates chapters 1–7 → final MP4 (2-pass 12 Mbps delivery encode), English SRT from the same aligned caption cues, final chapter timestamps. **No publishing.**

## Issues found and fixed during production
- **Map framing:** the Belgian and several other maps were authored with canvases too small for 16:9, so they rendered wider than intended. The builder now checks and fits canvas coverage.
- **Label collisions:**
  - region labels against place labels;
  - labels under stars and the legend;
  - persistent 1806–07 labels in the 1811 view (the map was split in two).
  - All are fixed in the data; QC finds 0 warnings.
- **Soft paper texture:** several maps were resampled at about 1×. Canvases are now oversampled like the approved maps. A worker ran out of memory once, so canvases are capped at about 33 MP.
- **Preview mux** dropped the last frame when the music track ended early. Audio is now padded.
- **Elba wording** corrected before recording.

## Quality controls applied so far
- **Map style lock:**
  - no non-original features;
  - fingerprint of the drawing code unchanged (`323e1e8ecf86883f`);
  - the regression test `map_lock` now also covers all 13 documentary maps.
- **Map QC:**
  - labels never clipped, never overlapping, never under the subtitles or the legend;
  - a new canvas-coverage check stops a map from being framed wider than authored.
- **Fact-check:** every claim has a source key; one wording was corrected before recording; disputed figures are given as ranges.
- **Regression suite:** 8/8 quick tests pass.

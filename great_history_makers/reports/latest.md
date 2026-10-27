# Production report: Napoleon: The Rise and Fall of an Emperor (Great History Makers long-form documentary, 16:9 1920x1080, 30 fps, English)

**Milestone:** Script, shot list, storyboards and all chapter map sequences complete (`napoleon_doc_m1_maps`, 2026-10-27)  
**Generated:** 2026-10-27 15:46 UTC from commit `55ee176` on branch `ccr-1badfb87-5pxi90`  
**Repository:** https://github.com/ashkani007/VideoEnhancerAndroid (PUBLIC (ashkani007/VideoEnhancerAndroid); the dedicated private Great History Makers repository is not yet reachable from this session), folder `great_history_makers`  
**Overall status:** IN PRODUCTION. All 7 chapters' map sequences are finished (final 1080p footage). Paintings and narration are blocked on client decisions; no complete chapter video exists yet. Planned length 19:26 at 140 wpm, expected 17-19 min after recording.

Nothing has been published. The machine-readable version of this report is `reports/status.json`.

## Stages
| Stage | Status | Note |
|---|---|---|
| 1. Audit of pipeline and assets | done | renderer, locked map system, QC, narration/caption stage, procedural music/SFX, PC job queue reused |
| 2. Script, fact-checked | done (frozen draft 2) | production/NARRATION.txt, 7 chapters, 2,277 words, 13,167 characters; claim table with sources in SCRIPT.md |
| 3. Shot list and storyboards | done | production/SHOT_LIST.md; chapters/ch1-ch7/storyboard.json; 57 new paintings + 3 POC paintings, 17 map shots, 6 chapter cards, title, end card |
| 4. Animated maps (locked approved v2 style) | done, footage delivered | 13 map files, 17 map shots, about 6 min (31 % of the film) |
| 5. Paintings and animation | BLOCKED: image generation route | 8 jobs, 216 candidate images queued in jobs/queue/napoleon_doc_*; no GPU or image service in this cloud session |
| 6. Narration, subtitles, music, SFX | BLOCKED: narration needs credit approval | music and SFX defined per chapter; subtitles come only from forced alignment of the recorded voice |
| 7-9. Chapter renders, QC, assembly | waiting for 5 and 6 | scripted: build.py (re-time), ghm4.render, ghm4.narrate finish, ghm4.qc, assemble.py |
| 10. Final MP4, SRT, timestamps | not started | CHAPTER_TIMESTAMPS.txt exists with PLANNED timing only |

## Completed in this milestone
- 7-chapter narration frozen (draft 2) in the client's structure; one wording corrected before recording (Elba 'about thirty kilometres long').
- Production builder (production/build.py) generates maps, chapter storyboards, map-only storyboards, SHOT_LIST.md, chapter timestamps and painting jobs from NARRATION.txt + shots.py + maps_src.py; map events are anchored to narration words so re-timing to the recorded voice is automatic.
- 13 maps in the client-approved, LOCKED v2 style (preset ghm4/data/map_presets/ghm_original_v1.json); graphics scale and arrow stroke inside the measured Ep01 ranges for every map; canvas-coverage and label checks pass.
- Final 1080p map footage rendered, checked and delivered for chapters 1-7 (files listed below).
- Painting jobs queued for the client's PC worker (57 new paintings x 4 candidates).
- Final assembly script (production/assemble.py) written; only its missing-input check has been run (no chapter finals exist yet).

## Tests actually run
- Regression suite `ghm4.tests.run_all`, last run 2026-10-27 13:58 UTC: **11/11 passed**.
- Per video: full decode with ffmpeg (no errors), black-frame and freeze scan (none), frame count equals the storyboard (all 7 reels), ghm4.qc stage (clipped/overlapping labels, labels under subtitles or legend, style lock, graphics scale, sharpness): 0 errors on all 7 reels, 1 warning (chapter 5, checked, see QC notes).
- Map-style checks on all 13 documentary maps: map_style.violations, scale_issues, stroke_issues, canvas coverage: all pass. The map_lock regression test now includes the documentary maps (22 maps, drawing-code fingerprint 323e1e8ecf86883f unchanged).
- Approved v2 sample re-checked with subtitles enabled after the label changes: 0 QC warnings.

## Rendered videos
| File | Duration | Resolution | Frames | Size | Storage | QC |
|---|---|---|---|---|---|---|
| `Napoleon_Doc_Ch1_Waterloo_MAPS_1080p.mp4` | 0:16.07 (16.067 s) | 1920×1080 @ 30 fps | 482 | 24.5 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p.mp4` | 0:36.93 (36.933 s) | 1920×1080 @ 30 fps | 1108 | 56.4 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p.mp4` | 1:05.20 (65.2 s) | 1920×1080 @ 30 fps | 1956 | 89.6 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p.mp4` | 0:38.87 (38.867 s) | 1920×1080 @ 30 fps | 1166 | 59.4 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p.mp4` | 1:16.63 (76.633 s) | 1920×1080 @ 30 fps | 2299 | 89.5 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p.mp4) | 0 error(s), 1 warning(s) |
| `Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p.mp4` | 1:21.57 (81.567 s) | 1920×1080 @ 30 fps | 2447 | 89.4 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p.mp4` | 0:40.57 (40.567 s) | 1920×1080 @ 30 fps | 1217 | 61.9 MB | Git: [`docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/production/output/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p.mp4) | 0 error(s), 0 warning(s) |
| `Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4` | 0:16.50 (16.5 s) | 1920×1080 @ 30 fps | 495 | 98.2 MB | Git: [`docs_longform/napoleon_rise_fall/poc/output/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4`](https://github.com/ashkani007/VideoEnhancerAndroid/blob/ccr-1badfb87-5pxi90/great_history_makers/docs_longform/napoleon_rise_fall/poc/output/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4) | – |

### Contact sheets (12 frames with timestamps each) and preview frames
- `Napoleon_Doc_Ch1_Waterloo_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p_sheet.jpg), frames: [0002.41 s](previews/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p_t0002.41.jpg), [0006.43 s](previews/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p_t0006.43.jpg), [0010.44 s](previews/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p_t0010.44.jpg), [0014.46 s](previews/Napoleon_Doc_Ch1_Waterloo_MAPS_1080p_t0014.46.jpg)
- `Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p_sheet.jpg), frames: [0005.54 s](previews/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p_t0005.54.jpg), [0014.77 s](previews/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p_t0014.77.jpg), [0024.01 s](previews/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p_t0024.01.jpg), [0033.24 s](previews/Napoleon_Doc_Ch2_Corsica_and_the_Revolution_MAPS_1080p_t0033.24.jpg)
- `Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p_sheet.jpg), frames: [0009.78 s](previews/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p_t0009.78.jpg), [0026.08 s](previews/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p_t0026.08.jpg), [0042.38 s](previews/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p_t0042.38.jpg), [0058.68 s](previews/Napoleon_Doc_Ch3_Italy_Egypt_and_Power_MAPS_1080p_t0058.68.jpg)
- `Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p_sheet.jpg), frames: [0005.83 s](previews/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p_t0005.83.jpg), [0015.55 s](previews/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p_t0015.55.jpg), [0025.26 s](previews/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p_t0025.26.jpg), [0034.98 s](previews/Napoleon_Doc_Ch4_Coronation_Ulm_and_Austerlitz_MAPS_1080p_t0034.98.jpg)
- `Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p_sheet.jpg), frames: [0011.49 s](previews/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p_t0011.49.jpg), [0030.65 s](previews/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p_t0030.65.jpg), [0049.81 s](previews/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p_t0049.81.jpg), [0068.97 s](previews/Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p_t0068.97.jpg)
- `Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p_sheet.jpg), frames: [0012.24 s](previews/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p_t0012.24.jpg), [0032.63 s](previews/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p_t0032.63.jpg), [0053.02 s](previews/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p_t0053.02.jpg), [0073.41 s](previews/Napoleon_Doc_Ch6_Retreat_Exile_and_Return_MAPS_1080p_t0073.41.jpg)
- `Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p.mp4`: [contact sheet](previews/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p_sheet.jpg), frames: [0006.09 s](previews/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p_t0006.09.jpg), [0016.23 s](previews/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p_t0016.23.jpg), [0026.37 s](previews/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p_t0026.37.jpg), [0036.51 s](previews/Napoleon_Doc_Ch7_Waterloo_Saint_Helena_and_Legacy_MAPS_1080p_t0036.51.jpg)
- `Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4`: [contact sheet](previews/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p_sheet.jpg), frames: [0002.48 s](previews/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p_t0002.48.jpg), [0006.60 s](previews/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p_t0006.60.jpg), [0010.72 s](previews/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p_t0010.72.jpg), [0014.85 s](previews/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p_t0014.85.jpg)

### QC warnings and how they were checked
- `Napoleon_Doc_Ch5_Europe_and_Russia_MAPS_1080p.mp4`: soft: sharpness 0.27x the episode median
- Chapter 5 shot c5_map_europe 'soft: 0.27x the episode median' is relative to the chapter's hatched 1811 territory maps. Measured paper-texture energy (mean absolute Laplacian on a flat parchment patch): this shot 7.35-7.49, approved v2 sample 7.66-11.37, hatched empire shot 12.13. Judged not soft (details: docs_longform/napoleon_rise_fall/production/output/QC_NOTES.md).

## Problems and fixes
- Maps authored with canvases too small for 16:9 rendered wider than intended (graphics too small): fixed with an automatic canvas-coverage check and fit.
- Label collisions (region vs place labels, labels under battle stars and the legend, persistent 1806-07 labels in the 1811 view): fixed in the map data (Europe map split in two); QC 0 warnings.
- Parchment/sea base resampled at about 1x on several maps (softer than the approved maps): canvas oversampling raised to >=1.5x; one render worker was OOM-killed at a 36 MP canvas, so canvases are capped at about 33 MP per worker.
- Preview mux dropped the last frame when the music track ended early: audio now padded.
- A background encode once read a file while it was being re-muxed (corrupt encode, caught and redone); encodes now write to a temp file and move into place when complete.
- Background render job hit the 2-hour session limit during chapter 7; chapter 7 was re-rendered on its own.
- The two Belgian maps (chapters 1 and 7) are the only maps closer than continental scale and show no sea; graphics sizes stay in the approved ranges. Client decision pending.

## Costs
- Spent on this documentary so far: $0 (no paid service used; cloud rendering only).
- Project ledger (autopilot/LEDGER.json): 1,676 ElevenLabs credits on 2026-10-23 for an earlier Short (ep02), not this documentary.
- Pending estimate, needs approval: narration, one take per chapter of NARRATION.txt with voice Max, about 13,200 ElevenLabs credits (about $2.65), based on the measured 944 credits per 946 characters.
- Paintings: client's PC (electricity only, about 2-4 GPU hours for 216 images, after the client approves the hash-locked installer, about 21 GB of downloads) or a paid hosted service priced before any spend.

## Decisions needed from the client
1. Approve narration: about 13,200 credits (about $2.65) for one take per chapter, voice Max (Gfpl8Yo74Is0W6cPUWWT).
2. Choose the painting route: local PC (approve the installer), paid hosted service (priced first), or client-supplied licensed images.
3. Keep the two close-scale Belgian maps (no sea visible) or pull back to continental scale with less battle detail.
4. Reporting: confirm or create the dedicated PRIVATE Great History Makers repository and give this session access (see the reviewer notes).

## Next steps
1. After painting approval: generate, pick, upscale and annotate the 60 plates; QC each.
2. After narration approval: one take per chapter, prep_narration.py, forced alignment, build.py re-times every cut and map event, map reels re-rendered on the real timing.
3. Render each chapter (picture + narration mix + burned subtitles), QC and visual review, then assemble.py: final MP4, English SRT, final chapter timestamps.
4. Publish nothing; deliver for client approval.

## Notes for the reviewer
- Locked map style reference: docs_longform/napoleon_rise_fall/poc/output/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4 (client-approved 2026-10-27) and the preset ghm4/data/map_presets/ghm_original_v1.json.
- Map footage timing is PLANNED (140 wpm); it moves onto the recorded narration automatically after alignment.
- Full-quality render masters (CRF 15, about 95 MB per 16 s) stay in the ephemeral cloud container and are not in Git; the delivered files are 2-pass H.264 encodes capped under 90 MB. No approved large-file storage service is connected, so no external download links exist yet.
- The repository holding these reports is currently PUBLIC. Everything in it is project material (code, script, maps, rendered map footage); no credentials or personal files.


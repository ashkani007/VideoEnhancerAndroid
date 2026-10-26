# Napoleon Ep01: TEMP preview report (2026-10-26)

**File:** `output/Napoleon_Ep01_TEMP_PREVIEW_720x1280.mp4`. This is a **temporary preview and must not be published**.
- The animated maps, typography, motion, transitions, music, sound effects, subtitles and narration are real.
- The illustrations are stand-ins, and each one is labelled on screen.

## Measured
| Check | Result |
|---|---|
| Container | H.264 High, yuv420p, 720×1280, 30 fps; AAC LC 48 kHz stereo |
| Duration | 68.2 s, 2046 frames (all decoded; `ffprobe -count_frames`) |
| Narration sync (`tools/verify_delivery.py`) | PASS: correlation 0.975, offset 0 ms |
| Subtitles | PASS: 27/27 cues on their aligned words, start error 0 ms, wording matches the transcript; y = 1410/1920, max 2 lines |
| Black frames (≥ 0.3 s) / frozen frames (≥ 1 s) | none (`blackdetect`, `freezedetect`) |
| Loudness | −17.2 LUFS integrated, true peak −1.8 dBFS. One overall +4.9 dB gain was applied to the whole mix; nothing else changed |
| Render | 462 s for the 720p picture plus 120 s for the mix and subtitles (cloud CPU, 3 workers) |
| Visual QC | `qc/final_frames_contact.jpg` (16 frames from the delivered file) |

## Composition (14 shots)
| Shots | Count | Status |
|---|---|---|
| Animated maps: victories 1805–1811, invasion 1812, coalition 1813, Elba and the Hundred Days, Saint Helena | 5 | **Final-quality** |
| Crops of the one approved style frame: hook, "wanted more" close-up with blink, Waterloo battle | 3 | TEMP |
| Painted environment stand-ins (no characters): Notre-Dame nave, Moscow burning, the retreat in snow, Saint Helena at dusk, Arc de Triomphe, night sea | 6 | TEMP |

The 9 final AI illustrations are queued as `jobs/queue/napoleon_ep01_v1.json` (9 shots × 4 seeds) for the PC worker.

## Known issues
- **Length:** 68.2 s, 3 s over the 55–65 s target. The approved narration is 66.0 s and may not be time-stretched. The 3 s end signature (`tools/brand.py`, 1080p only) adds to this. Ways to shorten:
  - a shorter script with one new paid take;
  - or trimming the 2.3 s title hold at the end.
- **"Avoid reusing one portrait":** this cannot be met until the PC job returns, because the 3 crops come from one image.
- **Subtitle contrast:** on the white snow (29–34 s) the subtitles rely on their outline. In the final, the retreat plate gets a darker lower third, or a scrim.
- **Elba map:** the return route (Golfe-Juan → Grenoble → Lyon) partly runs alongside the exile route. This is correct, but the two are busy at 43–45 s.
- **Not branded:** `tools/brand.py` is 1080×1920 only, and the watermark would collide with the TEMP labels.

# Napoleon Ep01 TEMP preview: visual audit and corrections (2026-10-26)

**Corrected file:** `output/Napoleon_Ep01_TEMP_PREVIEW_v2_720x1280.mp4`. It is still a TEMP preview: stand-in illustrations, labelled on screen.

**Audit sheets** (every shot: start / middle / end + the frames around its outgoing transition, defects, root cause):
- `qc/audit_v1_contact.jpg`: before;
- `qc/audit_v2_contact.jpg`: after;
- `qc/audit_v2/qc_contact.jpg`: automatic QC.

## Defective scenes, root causes, fixes
| Shot | Defect (v1) | Root cause | Fix |
|---|---|---|---|
| b01 hook | "1769 – 1821" unreadable | Compositing: gold 30 px text over the white waistcoat | Date moved under the title (above the subtitle zone), stronger scrim and shadow |
| b02 coronation | Badly drawn nave: arches in the wrong plane, smeared rose window | Generation (stand-in plate code) | Plate v2: transverse pointed ribs, rose-window tracery, floor tiles |
| b03 victories | "WAGRAM 1809" and region labels cut at the frame edge; 0.8 s whiteout into b04 | Animation (no edge-aware label layout); compositing (flash at 92 %) | Map `safe_labels`; flash strength 0.5 / 0.25 s |
| b04 close-up | Flash wash; TEMP label over the cockade | Compositing | Softer flash; TEMP labels at the bottom edge |
| b05 invasion | Arrow origin leaves the frame; crude hatched blobs; unreadable gold label; MOSCOW / GRANDE ARMÉE touching | Animation (camera capped by canvas height); map data; label layout | Taller bounds, wider camera, allied hatch removed, ivory labels, moved labels |
| b06 Moscow | Grid of square "pixel" windows, rectangle tower, malformed domes | Generation | Plate v2: irregular glowing windows, tiered bell tower, onion domes, rippled reflection |
| b07 retreat | Hard horizon, floating cart, ghost road; subtitles on white | Generation; compositing | Plate v2: misty horizon, cannon in a drift, ruts, birches; lower-third scrim |
| b08 coalition | "PRUSSIARUSSIA", "LEIPZIGAUSTRIA"; BRITAIN under subtitles; cut labels | Animation (label layout) | Labels moved; `safe_labels` |
| b09 Elba | Return route drawn over the exile route; ELBA / GOLFE-JUAN under subtitles; ITALY cut | Map data; camera bounds | Historical routes separated (Avignon / Grenoble), taller bounds, camera lowered |
| b10 Waterloo | Soft image; drifting straight-edged smoke "rectangle"; coat sliver at the left edge; low-contrast date | Scaling (491 px crop at 1.77x); **renderer bug** (smoke noise not tileable after resize: wrap seam 3–4x the normal step, made hard by the threshold); camera crop | CPU Real-ESRGAN 2x (enlargement now 1.03x); `periodic_resize`; camera past the coat; top scrim |
| b11 Saint Helena map | PLYMOUTH in the title zone; labels cut; distance note under subtitles | Animation (label layout) | `safe_labels` fades the title zone; note moved above the island |
| b12 Saint Helena | Blotchy "camouflage" sea | Generation (blob noise) + effect misuse (smoke band on water) | Plate v2: perspective wave streaks and glitter path; water moves with a ripple region |
| b13 Arc de Triomphe | No defect | – | Kept (plate unchanged) |
| b14 ending | AMBITION over the island; blotchy sea | Compositing / layout | Island moved right, title in clear sky, sea redrawn |

**Encoding:** not a cause in v1 (rendered vs decoded frames 33–36 dB, grain included). The patch workflow itself introduced visible generation loss on copied frames (31 dB, banding in the glow). Patched files are now written at CRF 10, and the delivery was assembled from one clean render plus one patch of four map shots.

## Re-render strategy
1. Fixes were checked with single stills.
2. `--patch` re-rendered only the failed shots: 13 of 14, since only b13 passed; then b01 alone; then 4 maps after the second QC pass.
3. Final assembly: one clean full render plus one CRF 10 patch of the 4 maps, so there is no multi-generation loss.

## Automated checks on the corrected file
| Check | Result |
|---|---|
| Integrity | Decodes without errors; 2046/2046 frames; 720×1280 (9:16), 30 fps, H.264 High yuv420p, AAC 48 kHz; 68.2 s |
| Black / frozen | Only the intended final fade (last 0.13 s); no frozen stretch ≥ 0.5 s |
| Narration sync | PASS: correlation 0.975, offset 0 ms |
| Subtitles | 27/27 on their words, 0 ms start error, wording exact |
| Loudness | −17.2 LUFS, peak −1.8 dBFS |
| Visual QC (`ghm4.qc`) | **0 errors, 0 warnings** (v1 with the same QC: 32 warnings). INFO only: low detail in b02 / b12 / b14 comes from the flat stand-in sources, not the render (render/source detail ≥ 1.4x) |
| Regression suite | 6/6 quick tests incl. the new `qc` test; golden frames of the approved POC still match (≥ 66 dB); episode pipeline test passes |

## What QC cannot judge
Taste and drawing quality: the stand-ins are environment placeholders without characters, and **real variety still needs the 9 ComfyUI illustrations** from the PC job. QC flags measurable defects; a human still reviews every preview.

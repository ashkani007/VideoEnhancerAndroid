# Quality rubric (internal estimates, 1–10)

These scores are internal quality estimates with written evidence, not proof of audience response.
Every score must cite observable evidence: a frame or crop, a measurement or a file.
Anchors: **3** = clear problems a viewer notices · **5** = acceptable but plain · **7** = good, few
defects · **9** = professional; would hold up next to strong channels in the niche.

| Category | Observable evidence to check | 9–10 means |
|---|---|---|
| Visual depth and dimensionality | Distinct depth planes per shot; perspective/vanishing points; face thickness; cast and contact shadows; atmospheric fade; parallax differs by depth | Every shot reads in 3D at thumbnail size, with no flat cut-out look |
| Mosaic style consistency | Tiles visible in all regions at 1:1; no stretched stones in motion; one palette | Indistinguishable style across shots and episodes |
| Character animation | Planted feet (no slide or float, checked over 4 consecutive frames); varied cadence; secondary motion (spear, cloth); no synced crowds | Every visible figure has purposeful, grounded motion |
| Cinematography | Each shot has its own camera intent; no global-zoom "depth"; foreground occlusion; rack focus where useful; no exposed edges | Shots feel designed for the camera |
| Colour and lighting | One sun direction per scene; warm lights and cool shadows; measured saturation; clip <0.1 %; no neon | Rich, controlled, consistent |
| Scene variety | Count of distinct compositions; automated near-duplicate scan (0 pairs) | 14–18 distinct shots, each motivated by the narration |
| Historical accuracy | Each narration line mapped to a source in HISTORY.md; reconstructions labelled; no anachronisms flagged | Everything sourced and categorised |
| Narration synchronisation | Cuts in measured pauses; narration offset and correlation vs source | 0 ms offset, cuts on pauses |
| Subtitle quality | Forced-alignment timing; exact wording; ≤2 lines; fixed safe position; no faces in the band | Error-free |
| Viewer engagement potential | First 2 s hook; change of picture every 2–4 s; ending signature | Strong hook, no dead stretches |

## Baseline scores: Cyrus V3/V4 (approved), written 2026-10-21
| Category | Score | Evidence |
|---|---|---|
| Visual depth | **4** | Most shots are layered parallax planes with flat frontal architecture; no cast shadows; figures unshaded (V3 contact sheet) |
| Mosaic consistency | 8 | Tiles visible everywhere; rigid-tile cloth; one palette |
| Character animation | 6 | Varied walk cycles and reactions, but sinusoidal legs slide and the bob lifts the feet |
| Cinematography | 6 | Distinct moves per shot, but mostly 2D trucks/zooms of planes |
| Colour and lighting | 7 | Rich palette, no clipping; lighting direction not modelled |
| Scene variety | 8 | 18 distinct shots, 0 near-duplicates |
| Historical accuracy | 8 | HISTORY.md maps every line; reconstructions labelled |
| Narration sync | 9 | 0.0 ms offset, correlation 0.978 |
| Subtitle quality | 8 | Aligned timing, fixed position; two transcript words unconfirmed by the client |
| Engagement potential | 6 | Strong opening and branded end; flat look limits impact |

## Experiment score: shot "Gate entry" A vs B (2026-10-21)
| Category | A (V3 flat) | B (2.5D) | Evidence |
|---|---|---|---|
| Visual depth | 3 | **7** | B: vanishing point, tower thickness with lit/shaded sides, vault to a sunlit far end, receding wall, wall shadow on the road, contact/cast shadows, figures shrink with depth |
| Character animation | 6 | **7** | B: ground-locked planted walk, column walks *into* depth; A: lateral sliding gait |
| Cinematography | 5 | **7** | B: depth-correct dolly/truck, foreground palm occluder, rack focus from near rank to gate |
| Colour and lighting | 7 | **8** | B: one sun, warm and cool faces, ambient occlusion |
| Mosaic consistency | 8 | 8 | Tiles intact in both; B adds shade gradations across tiles |
| Engagement potential | 6 | 6 | B is more cinematic, but its figures are smaller and fewer than A's crowded column; foreground still sparse |

## Experiment score: B vs C (2026-10-22). See output/experiments/ab_2p5d/AB_C_Improvement_Report.md
| Category | B | C | Evidence |
|---|---|---|---|
| Visual depth | 7 | 8 | Parallax sky/gate/near = 0.05/0.27/1.42 px/frame (B: −0.01/−0.08/−0.39) |
| Character animation | 7 | 8 | IK heel-to-toe gait; stance ankle drift 0.00; per-soldier variation |
| Character volume | 4 | 7 | 5-band sculpting, self-shadows, shield rim |
| Cinematography | 7 | 7 | Tracking shot + occluder, but the pillar hides the gate early; no rack focus |
| Colour and lighting | 8 | 7 | Saturation 0.629 → 0.595; luma equal |
| Mosaic consistency | 8 | 8 | Tiles intact |
| Engagement potential | 6 | 7 | Three ranks plus a crowd, constant motion |

## Episode 02 Napoleon, 720p preview (2026-10-22, narration pending). See output/ep02_napoleon/deliverables/Napoleon_Episode02_QA_Report.md
| Category | Ep01 V3/V4 | Ep02 preview | Evidence |
|---|---|---|---|
| Visual depth | 4 | 6 | Pinhole ground planes with vanishing points, depth-scaled figures, cast shadows; maps and the Arc still frontal |
| Mosaic consistency | 8 | 8 | Tiles everywhere; rigid-tile flags and sails |
| Character animation | 6 | 7 | turnrig walkers with planted feet and path yaw; front/rear turns; discrete 11.25° views |
| Cinematography | 6 | 7 | One camera intent per shot; rack focus s05 |
| Colour and lighting | 7 | 8 | Chapter palette arc; saturation 0.591; worst clip 0.37 % |
| Scene variety | 8 | 9 | 17 shots, 0 near-duplicates |
| Historical accuracy | 8 | 8 | HISTORY.md covers all 16 lines; labels on screen |
| Narration sync | 9 | n/a | No audio yet |
| Subtitle quality | 8 | 5 (provisional) | Estimated timing; s12 face crosses the band at about 40 s |
| Engagement potential | 6 | 7 | Hook in the first second; changes every 2–5 s |

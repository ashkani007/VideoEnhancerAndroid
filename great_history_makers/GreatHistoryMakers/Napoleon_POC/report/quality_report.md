# Quality report: Napoleon 2D Animation POC

**File:** `final/Napoleon_2D_Animation_POC.mp4`. ffprobe: H.264 High, 1080×1920, yuv420p, 30/1 fps,
360 frames, 12.00 s, 4.3 MB. A full FFmpeg decode completed without errors.
**Review frames:** `report/frames_begin_mid_end.png` (0.5, 2.6, 3.9, 5.4, 6.2, 8.0, 9.0, 11.9 s).

## Reference video: not available
The Instagram recording `Screen_Recording_20261024_101117_Instagram.mp4` was **not present** in this session
(searched the container, uploads and every repository branch). Style matching to that reference was **not done**.
The look is my interpretation of "stylized editorial 2D": geometric shapes, flat colour with one cel-shadow tone,
soft gradients, thin rims and no outlines. It should be compared with the reference and adjusted once the file is shared.

## What happens on screen
| Time | Shot | Character animation | Background animation |
|---|---|---|---|
| 0–4 s | Planning room, medium shot pushing into a close-up | Eyes scan the map (saccades left → centre → right), blink at 1.22 s, hand slides across the map (IK keeps it on the table), switches to pointing and taps twice, brows knit and mouth tightens at 2.5–2.9 s (decision), breathing | Candle flame and light pool flicker, moonlit window |
| 4.0 s | Match cut on the head lift (close-up → low-angle medium) | | |
| 4–8 s | Dawn window, low angle | Eyes lead and the head lifts with a short anticipation dip; brows rise in surprise then knit; arm winds back, then thrusts to a point with overshoot (back easing); torso leans in; mouth shapes for the shouted command, then sets; blink at 6.95 s; spring-driven coat tails and epaulette fringe | Curtains sway in the breeze, candle flicker, dawn sky |
| 7.85–8.15 s | Whip-pan in the pointing direction | | |
| 8–12 s | Misty battlefield, Napoleon in the foreground | Gaze follows the columns, head turn, approving nod at 10.85 s, blinks, breathing, wind on the fringe | Two depth rows of soldiers marching (leg, knee, foot and arm cycle, body bob), three waving tricolours, drifting mist bands and smoke, swaying grass, slow parallax camera drift |

## Requirement check
| Requirement | Result | Evidence |
|---|---|---|
| Real character movement, not only camera | **Met** | Command beat (5–7 s): mean frame difference 3.48 in the arm and face region vs **0.00** on the static wall region (camera nearly still) |
| At least two facial expressions | **Met** | Neutral/reading, decisive (knit brows, tight mouth), surprised lift (raised brows), shouting command, watching. See `assets/characters/Napoleon_character_sheet.png` |
| Visible head movement | **Met** | Tilt 17° → −6° on the lift; yaw changes; nod at 10.85 s |
| Deliberate hand gesture | **Met** | Map tap (2.4–2.8 s) and the anticipation → point with overshoot (4.75–5.4 s) |
| Animated background element | **Met** | Candle, curtains, mist, smoke, flags, marching soldiers, grass |
| Smooth transitions | **Met** | Match cut on action at 4.0 s; motivated whip-pan at 7.85–8.15 s |
| Consistent character design | **Met** | One rig and palette in all three scenes |
| No broken anatomy | **Met, with notes** | No stretched or detached limbs found in full-resolution checks at 2.6, 3.8, 5.5 and 10.0 s. The IK keeps the elbow within reach limits |
| Not a slideshow | **Met** | Per-scene mean frame difference 4.0 / 2.8 / 1.9, from articulated parts rather than pans over stills |

## Honest scores (1–10)
| Criterion | Score | Notes |
|---|---|---|
| Character appeal | 7 | Clean, readable design with an iconic silhouette (bicorne, epaulettes, forelock) |
| Facial expression | 6.5 | Clear emotional beats; eyes and brows carry the acting. Mouth shapes are generic: no lip-sync without audio |
| Body motion | 6 | Good anticipation, overshoot and follow-through on the gesture. Only one view (3/4 right) exists, so no body turns; hands are simplified |
| Background animation | 6 | Several moving elements; soldiers are small and their walk cycle is basic (no foot roll) |
| Cinematography | 6.5 | Medium → close-up push, low angle, match cut, whip-pan, parallax wide shot |
| Consistency | 8 | Same rig, palette and light logic throughout |
| **Overall** | **6.5** | A genuine animated segment, not a slideshow. Short of top-tier studio polish |

## Known weaknesses (next iteration)
1. No reference-style match (file missing).
2. Single character view: needs front and profile views or a turn rig for scenes like "walks toward camera".
3. Scene 3: Napoleon's coat tails are out of frame, so the wind reads mainly on the fringe; he could do more.
4. Soldiers: add foot roll, varied heights and faces, and occlusion with mist.
5. Lighting is flat-shaded with a fixed shadow direction per scene; no cast shadows from the candle.
6. Mouth animation is not tied to audio (no narration in this POC). With narration it needs phoneme-driven visemes.

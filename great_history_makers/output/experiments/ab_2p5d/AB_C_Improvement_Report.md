# Version C: technical changes and evaluation (2026-10-22)

**Shot:** Persian troops before the Ishtar Gate. The gate is front-on, the same subject and framing as B.

**Files** (all checked with ffprobe):

| File | Format | Duration / frames |
|---|---|---|
| `AB_C_720x1280.mp4` | H.264 720×1280, 30 fps, AAC | 5.00 s, 150 frames |
| `AB_C_Comparison.mp4` | 1448×1280 (B left, C right, identical timestamps) | 5.00 s, 150 frames |
| `AB_C_ContactSheet.png` | B and C at 0.3/1.5/2.7/3.9/4.8 s, plus 1:1 crops of C's near rank | — |
| `AB_C_metrics.json` | Raw measurements | — |

## Source assets
No Blender files or depth maps exist; B was never a flattened video. Everything is procedural code (`experiments/ab_2p5d/scene_b.py`), so C was rebuilt from editable layers rather than recovered from the MP4:
- B's architecture, ground and walls are reused.
- The soldiers, gait, shadows, camera and foreground are new.

## What changed

**1. Character volume.** The new reusable rig is `mosaic/rig3d.soldier_v3`.
- **Parts:** 15 articulated pieces: torso, head, near upper arm, forearm with hand, far arm, wicker shield, quiver, spear, banner, and thigh, shin and foot for each leg. B had 9 parts and no feet.
- **Sculpted shading:** each part's lit volume is quantised into 5 tone bands *before* tiling, so rows of tesserae follow the form. Every stone is still one flat colour; there are no gradients and no plastic look.
  - Lit bands are warmed, shaded bands cooled.
  - The torso has a scale corselet; the tiara is rounded.
- **Self-shadowing:** the torso, near leg, head, arm and spear cast offset, blurred shadows onto the parts behind them. This gives occlusion at the joints and where limbs overlap the body.
- **Equipment thickness:** the shield has a darker rim band showing its edge, and the spear has a lit edge line.

**2. Walking mechanics.** The gait is `rig3d.gait_ik`.
- **Foot roll:** the foot runs through heel strike (rolling on the heel), flat foot, heel-off, then toe-off rolling over the toes.
- **Knees:** a 2-bone IK solve from the planted foot targets sets the knee bend.
- **Pelvis:** its height is set by how far the stance legs can reach, which gives a natural bob without floating.
- **Upper body:** torso lean with a push-off surge, arms in opposition with elbow flex on the back-swing, and a 5° shoulder twist. The spear is stabilised by the wrist (counter-rotates about 88 %).
- **Variation per soldier:** period 1.02–1.18 s, stride 400–450, lift 26–36, arm swing 10–16°, lean 2.5–4.5°, size ±4 %.
- **No foot sliding (measured):** during flat stance the ankle's screen x stays constant (spread 0.00 units within each stance). Body speed is derived from stride ÷ period × scale. Each rank sits exactly at the centre of a ground depth slice, so feet stay locked to the paving while the camera moves.

**3. Depth and camera.**
- **Camera:** one lateral tracking move alongside the column (ox 150 → −150, eased). Zoom is fixed at 1.0, so there is no zoom anywhere.
- **Depth planes:**
  1. sky and haze;
  2. city and ziggurat;
  3. gate and passage;
  4. far column entering the gate, plus distant townspeople reacting at the gate base;
  5. ground in 9 depth slices;
  6. middle rank (q 1.76);
  7. near rank (q 2.48);
  8. a foreground glazed pillar with a crimson standard (parallax 1.55, blurred σ 3.2) that passes the camera.
- **Measured parallax** (median horizontal motion per frame by phase correlation):

  | Region | B | C |
  |---|---|---|
  | Sky | −0.01 | 0.05 |
  | Gate | −0.08 | 0.27 |
  | Near ground | −0.39 | 1.42 |

  C's motion grows steadily with nearness (sky to gate to ground is about 1 : 5.5 : 29), which is true parallax.

**4. Shadows.** Each soldier gets one projected ground shadow of the whole silhouette (sun upper left, shadow falling back-right). Each foot gets its own contact shadow that fades as the foot lifts (fully faded by 45 units of lift). Both are recomputed every frame from the current pose, so they stay attached.

## QA checklist

| Check | Result |
|---|---|
| Visible volume | Yes. Banded form shading and limb self-shadows are visible in the 1:1 crops (contact sheet, bottom row) |
| Feet contact the ground, no sliding | Measured, see above; consecutive-frame crops show the stance foot fixed on the paving |
| Varied movement | Per-soldier timing and stride; no two soldiers share a phase |
| Meaningful parallax | See the parallax table |
| Contact shadows attached | Computed per frame from the foot targets |
| Gate quality | Unchanged sprite, crisp (B blurred it with rack focus; C keeps it sharp) |
| Tesserae stable | Rigid parts and rigid-tile banners; no warping |
| Deformation, melting, flicker | None seen; frame-difference range 4.0–19.8, smooth |
| Repeated or frozen frames | 0 frozen frames (no consecutive diff below 0.05) |
| Brightness | Mean luma B 89.0, C 89.9 |
| Colour | Saturation B 0.629, C 0.595: about 5 % lower, see regressions |

## Scores (internal estimates, QUALITY_RUBRIC.md anchors)

| Category | B | C | Evidence |
|---|---|---|---|
| Visual depth | 7 | **8** | Measured parallax gradient, 8 planes, passing foreground occluder |
| Character animation | 7 | **8** | IK heel-to-toe gait, planted feet, per-soldier variation, spear and shield secondary motion |
| Character volume (sub-score) | 4 | **7** | Banded sculpting, self-shadows, rim thickness |
| Cinematography | 7 | 7 | Real tracking shot with occlusion, but the pillar covers the gate's right tower for the first ~1.5 s, and B's rack focus is gone |
| Colour and lighting | 8 | **7** | Shading is richer, but saturation is 5 % lower than B even after a compensating grade |
| Mosaic consistency | 8 | 8 | Tiles intact; banded rows read as opus vermiculatum |
| Engagement potential | 6 | 7 | Fuller frame: 3 ranks plus a crowd; constant motion |

## Regressions and remaining weaknesses
- **Saturation −5 % vs B.** The cool-tinted shadows (ground plus self-shadows) desaturate warm areas. Grade compensation (+0.09 saturation, +6 % exposure) recovered luminance fully but not all of the saturation. Fix next: warmer shadow tint (0.66, 0.66, 0.78) instead of (0.58, 0.64, 0.82).
- **Gate partly hidden early.** The foreground pillar occludes the right tower for about 1.5 s; it should enter later or further right.
- **Profile-only figures.** The volume is sculpted shading on profile cut-outs. There are no ¾ turns, the torso twist is only implied by the shoulder (5°), and the far arm is mostly hidden by the shield.
- **Far column slides slightly** where it turns into the gate passage: planted speed is exact only for lateral paths; the depth-direction segment is not corrected.
- **Near rank is still moderate in size** (about 280 px tall at 720p), so the banded volume is clear at 1:1 but softer on a small phone screen.
- **Render cost:** about 0.65 s/frame at 720p (B: about 0.45), because of per-figure buffers and shadows.
- **Not tested at 1080p yet.** Self-shadow and contact sizes scale with pixels per unit, but this needs checking.

## Next iteration (if the client approves the direction)
1. Warmer shadow tint, and verify saturation ≥ B.
2. Delay the pillar's entrance so the gate stays clear for the first 2 s.
3. Correct planted speed for depth-direction paths: use the screen-space foot velocity.
4. A larger near rank, or a ¾ close-up shot, to show the volume at phone size.

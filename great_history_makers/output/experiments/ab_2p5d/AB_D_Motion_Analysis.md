# Version D: soldier turning and gate entry (motion analysis, 2026-10-22)

## Files

All files were checked with ffprobe.

| File | Format | Duration / frames |
|---|---|---|
| `AB_D_Gate_Entry_720x1280.mp4` | H.264 720×1280, 30 fps, AAC | 8.00 s, 240 frames |
| `AB_C_vs_D_Comparison.mp4` | 1448×1280; C (left) re-rendered at 8 s, so timestamps match | 8.00 s, 240 frames |

**Evidence:**
- `AB_D_FrameStrip.png`: the gate area every 0.5 s.
- `AB_D_Turnaround_Views.png`: one soldier at 90 / 67.5 / 45 / 22.5 / 0°.
- `AB_D_metrics.json`: all numbers below.

The clip was extended from 5 s to 8 s. A natural approach, turn and entry at walking speed (about 1 m/s) needs about 6.5 s.

## Problem in C
C's soldiers were cut-outs fixed in profile, translated sideways along constant-depth lines.
- **Body direction was unrelated to the path:** nobody turned or walked toward the arch.
- **Far column slid:** its route curved into the gate, but the figures stayed in profile, so they slid into depth.

## Source assets
The scene was rebuilt from editable assets, not from the MP4. B's procedural gate, passage, ground slices and walls are reused. The soldiers are a new rig (`mosaic/turnrig.py`).

## What was built

**1. Paths.** Two world-space curves on the paved road (`scene_d.py: PATH_R`, `PATH_L`), smoothed with Catmull-Rom:
- They start beside the road, curve onto the road's axis, run into the arch in separate lanes (X = +40 and −40), and continue into the passage. The two files never cross.
- Timing is staggered: R1 starts at s = 150, L1 at 40, R2 at −150, L2 at −230.
- Each soldier has their own cadence (0.97–1.06 s per cycle) and stride (580–610).

**2. Orientation follows the path.**
- The hips' yaw is the path tangent. The torso looks 28 units of path ahead (capped at ±35°) and the head 70 units ahead (capped at ±50°).
- So the head starts turning toward the gate first, then the shoulders, then the hips and feet.
- **Measured:** body direction stays within **0.8° (R1)** and **1.2° (L1)** of the actual direction of travel (worst case 2.2°, for L2). The head leads by up to **20–25°** during the turn.

**3. Multi-view turnaround (not a rotated flat image).**
- Torso, head, shield, quiver and boots are drawn separately at **9 views**, 0–90° in 11.25° steps:
  - **Side:** profile face.
  - **Near-side:** the face narrows.
  - **Rear ¾:** cheek and beard edge only.
  - **Rear:** back of the felt hood, quiver centred on the back.
- **Equipment changes perspective:** the wicker shield goes from full face to its edge (rim thickness band), and the spear stays in the near hand.
- Each view is built at 3 depth scales and mirrored for soldiers coming from the left.
- Arms, legs and spear are cylinders placed between joints projected in 3D.
- Sculpted banded shading uses a fixed screen-space sun, so the lit side stays upper left as the body turns: lighting is consistent.

**4. 3D joints through the scene camera.**
- Hips, knees, ankles, shoulders, elbows, wrists, neck and the spear axis are positioned in 3D, then projected through the same pinhole ground as the architecture.
- So size shrinks with distance, feet sit on the paving's perspective and paths converge on the vanishing point.
- **Measured depth on the R1 path:** q 1.68 → 0.76 (about 2.2× smaller).

**5. Planted feet.**
- Each stance has a fixed world ground point, computed from the path at mid-stance.
- In swing, the foot arcs between consecutive plants. Legs are solved with 2-bone IK toward the planted ankle, and the hips settle to what the stance leg can reach.
- **Measured:** planted-ankle drift during flat stance **0.0000 world units per frame**, for all 4 soldiers, including mid-turn.
- Contact shadows are drawn at the projected foot positions every frame, fading as each foot lifts.

**6. Gate occlusion and disappearance.**
- Soldiers beyond the gate plane are drawn *behind* the gate-front sprite and clipped by the tunnel outline at their own depth. The arch therefore covers them, and the passage walls hide anything outside the opening.
- Lighting changes with position: sunlight on the road, a 28 % drop in the tower shadow at the threshold, then exponential darkening toward the passage navy.
- **There is no fade before the doorway:** they walk under the arch fully visible.

**Event timing:**

| Soldier | Crosses the gate plane | Merges with the passage darkness |
|---|---|---|
| L1 | 4.73 s | 6.10 s |
| R1 | 5.20 s | 6.53 s |
| R2 | 7.77 s | still on screen at the clip's end |
| L2 | 7.80 s | still on screen at the clip's end |

**Required sequence:** both R1 and L1 complete the whole sequence on screen: walk toward the gate, rotate, align with the entrance, pass beneath the arch, disappear into the interior.

## Frame-by-frame checks

| Check | Result |
|---|---|
| Turning visible | Strip 0.0–4.0 s: L1/R1 turn from side to rear; views in `AB_D_Turnaround_Views.png` |
| Walks into the gate, not sideways | Paths converge on the arch; heading 82.8° → 0° (R1), −87.5° → 0° (L1) |
| Occlusion by the architecture | 1:1 crops 4.6–6.2 s: clipped to the opening; spears cut by the arch line |
| Disappears inside | Darkens into navy silhouettes against the sunlit far mouth, then out of sight |
| No sliding | Ankle drift 0.0 |
| No morphing | Discrete drawn views; tiles rigid within each view |
| Frozen frames | 0 (frame difference ≥ 0.19 between every pair of frames) |
| Colour | Saturation C 0.595 → D 0.582 (−2 %); luma 90 → 94 |

## Honest evaluation: C vs D

| Category | C | D | Notes |
|---|---|---|---|
| Path / orientation logic | 3 | **8** | Bodies now follow their paths; the head leads |
| Character turning | 1 | **7** | Real multi-view turnaround with equipment in perspective; view changes are discrete |
| Depth / perspective of motion | 7 | **8** | Figures travel through depth on the ground plane and are occluded by the gate |
| Character volume | 7 | 6 | **Regression:** D's figures are smaller (path starts at q 1.68) and the new view drawings are simpler than C's 15-part sculpted profile |
| Camera | 7 | 6 | **Regression:** a gentle drift (±25 units) instead of C's tracking shot; kept small so feet don't slip against the stepped ground slices |
| Colour | 7 | 7 | −2 % saturation vs C |
| Engagement | 7 | 7 | Clear story beat (entering the city), but a quieter, emptier foreground |

## Remaining weaknesses
- **View steps:** turnaround views change in 11.25° steps (about every 0.15–0.2 s during the turn), so the turn reads like classic drawn animation on twos, not a continuous rotation. The tiles re-tessellate at each view change.
- **Simplified rear and ¾ drawings:** no shoulder-blade or arm overlap detail. The near arm is partly hidden by the spear in the rear view.
- **Small figures:** soldiers are about 190 px tall at 720p at the start, and the foreground paving is empty.
- **Camera:** only a gentle move. A strong truck would make feet drift relative to the paving, because the ground is stepped parallax slices (fix: per-pixel ground projection).
- **No interaction between soldiers:** spacing comes from timing and lanes, not from collision avoidance.

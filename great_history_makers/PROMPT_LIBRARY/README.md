# Prompt and recipe library

This pipeline is procedural: scenes are code. "Prompts" here are therefore of two kinds:
1. `image_generation_prompts.md`: style-locked prompts for optional *local* image models
   (SDXL/Flux in ComfyUI). Any output must go through `tools/mosaicify.py`. Not used so far.
2. Scene recipes: proven shot builders worth reusing as starting points (adapt the composition; never copy it):

| Recipe | Where | Why it worked |
|---|---|---|
| Hero city across a river at golden hour | `episodes/ep01c_cyrus_v3/scenes.py: v3_open` | Saturated blue against gold sun; per-tile water glitter; foreground frond reveal |
| Marching column + dust at footfalls | `ep01c ... v3_opis`, `march_dust` | Per-walker phase and cadence; layered ranks |
| Crowd reaction shot | `ep01c ... v3_citizens` + `motion.react` | 5 reaction kinds, individual timing, foreground pillar reveal |
| Object turning (clay cylinder) | `ep01b ... shot12_cylinder` | Tiles fixed; colours sample a rolling texture |
| Tiles falling / assembling | `ep01c ... v3_centuries`, `TileScatterItem` | Rigid tesserae as particles; on-brand transition |
| Tile-reveal map | `ep01c ... v3_map` | Territory fills tile by tile; soft, labelled "approximate" |
| Silhouette finale | `ep01c ... v3_finale` | Deep sunset bands; dark rim silhouette; wind in the standard |
| **2.5D gate approach (proposal)** | `experiments/ab_2p5d/scene_b.py` | Pinhole ground, depth walkers, shadows, rack focus |
| **Sculptural soldier rig + IK gait (C)** | `mosaic/rig3d.py`: `soldier_v3`, `gait_ik`, `WalkerDraw` | 15-part rig, banded sculpting, heel-to-toe IK, self/contact/cast shadows, per-soldier variation |
| **Lateral tracking shot with depth slices (C)** | `experiments/ab_2p5d/scene_c.py` | Truck with no zoom; ranks on slice centres; blurred foreground occluder; measured parallax |
| **Path-following turning walkers (D)** | `mosaic/turnrig.py` (`Path`, `TurnSoldierAssets`, `TurnWalker`, `TurnDraw`) | World paths, head-led yaw, 9-view turnaround, 3D joints through the scene camera, planted feet, tunnel clip + depth lighting |
| **Entering a gate / doorway (D)** | `experiments/ab_2p5d/scene_d.py` (`passage_clip`, `light`) | Draw behind the front plane, clip by the opening at the figure's depth, darken with depth; no fake fades |

## Recipe: new period costume for turnrig (from Episode 02)
1. Subclass `NapoCostume` (or write a class with the same attributes): `front`, `torso_rect`, `torso(p, th)`, `head(p, th)`,
   optional `shield`, `pack`, `weapon`, `flag_kind`, `tubes = {"thigh": (col, None), "shin": (col, boot_col), "uarm": ..., "farm": (col, cuff)}`, `arm_mode`.
2. Draw each part as a function of view angle θ (0 = front, 90 = profile, 180 = back); hats must change width with θ.
3. `TurnSoldierAssets(ctx, k_ref, costume=MyCostume())` and walk it with `TurnWalker` on a world `Path` (or `idle=True`).
4. Check a turnaround with `tools/character_sheet.py` before using it in shots.

## Recipe: shot skeleton with shotkit
`c = cam(dur, z=..., ox=..., oy=...)` → build layers → `TurnDraw(ground, walkers, c, ...)` → `finish(scene, look="warm"|"cold"|"night"|"sea"|"map"|"interior", fade_out=(secs, amount))`.

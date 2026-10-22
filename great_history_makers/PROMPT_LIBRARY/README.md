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

# Style bible: Vibrant Cinematic Ancient Mosaic Animation

**Status:** approved through V3/V4 (Cyrus, Oct 2026). The 2.5D upgrade (section 6) is a
**proposal under A/B review** and is not yet the default.

## 1. Identity
Ancient Roman/Byzantine stone mosaic brought to life. Thousands of visible tesserae with
dark grout, flat stylised figures in strict profile (Near-Eastern relief convention:
frontal eye in a profile head), rich glazed architecture, a documentary tone.
Roman mosaic is a visual technique, not a claim about Achaemenid/Babylonian art.
Never use photorealism, plastic 3D, anime or generic AI fantasy art.

## 2. Tesserae
- Tiles follow the contours of every shape (two rows of andamento), then a brick-pattern fill inside.
- One flat stone colour per tile, random ±7 % luminance variation, a 3 % "odd stone" mix, bevel and grain.
- Grout is dark (40, 32, 28), about 15 % of tile size.
- Tile size (design units, frame = 1080 wide): backgrounds 8, distant architecture 6, figures 5–5.6, faces ×0.62.
- **Motion rule:** a tessera never stretches.
  - Characters are rigid cut-out parts.
  - Cloth uses rigid-tile waves: each tile moves whole and the gaps show grout.
  - Water, fire and light animate colour per tile, in place.

## 3. Palette (mosaic/palette.py, V3)
Lapis (28, 70, 172), cobalt, turquoise, terracotta (200, 80, 38), burnt orange, amber, gold (230, 172, 46),
crimson (182, 26, 40), burgundy, emerald, olive, ivory/sandstone for contrast, navy for shadows.
No beige washes and no haze bands. Measured mean saturation of the V3 final is about 0.60.

## 4. Grade (fx.CinematicGrade)
- Luminance-only local contrast, a gentle S-curve.
- Split toning: navy shadows, golden highlights. Vibrance plus saturation about 1.18–1.22.
- Soft highlight knee. No clipped whites; crushed blacks only inside intentional silhouettes.
- Glows at most 0.3, amber not white. Light shafts at most 0.06.

## 5. Typography and branding
- **Captions:** Caladea Bold (or EB Garamond if installed), 62 units, ivory with an outline, y = 1410.
- **Titles:** Caladea/Cinzel caps with letter-spacing, gold.
- **Logo:** original emblem only.
  - Watermark: upper-left, 155 px, 60 %.
  - End card: 760 px centred at y = 840, 94→100 % scale, handle below.

## 6. PROPOSED (awaiting approval): Cinematic 2.5D mosaic
See `experiments/ab_2p5d/`. If approved, this becomes section 6 "Depth rules":
- One pinhole ground plane per shot (`mosaic/depth.Ground`). Every standing thing gets scale and parallax from its depth q.
- One sun per scene, upper left by default.
  - Lit faces warm, shaded faces cool.
  - Cast shadows: towers on walls, walls on the ground.
  - Ambient occlusion at wall bases and corners.
- Architecture is drawn with thickness: side faces, vaults receding to a lit far end.
- Figures get per-tile form shading (`volume_shading`: light (−0.6, −0.8), strength 1.25, ambient 0.28).
  - Contact shadow plus projected cast shadow (`FigureItem(shadow=...)`).
  - Ground-locked walk (`motion.walk_planted` + `planted_speed`).
- Believable scale: a soldier is about 1/4 to 1/3 of the gate height.
- Camera: dolly/truck with depth-correct parallax (ground sliced by depth), foreground occluder,
  rack focus through per-layer blur. No global zoom used as "depth".

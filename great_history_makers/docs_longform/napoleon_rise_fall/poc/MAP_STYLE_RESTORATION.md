# Map style restoration (client correction, 2026-10-26)

**Approved reference:**
- the animated maps of the original Napoleon Short (`episodes_v4/napoleon_ep01`: victories 1805–11, invasion 1812, coalition 1813, Elba and the Hundred Days, Saint Helena);
- the 1805 campaign map of the approved 20s POC (`ghm4/data/maps/campaign_1805_austerlitz.json`).

All of them are rendered by `ghm4/mapshot.py`.

**Corrected sample:** `output/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_1080p.mp4` (16.5 s, 1920×1080).
**Side-by-side comparison:** `MAP_STYLE_COMPARISON.jpg`.

## What had changed in the rejected Ulm–Austerlitz map, and why it looked different
The renderer's drawing code did not change: colours, land and sea textures, coastline ripples, arrows, dots, rings, stars and typography are identical, and the approved golden frames still match. The difference came from the **new map data and new features**:

| # | Change in the rejected map | Effect on screen | Status now |
|---|---|---|---|
| 1 | **Zoom / scale:** camera 4.4–17.5 units across the 16:9 width with element scale 1.0 (graphics scale 0.25–0.40, against 0.07–0.14 in the approved maps). Camera widths were also read along the long side in 16:9 | Rivers, relief chevrons, dots and arrows 2.5–4× too large; the close zoom removed the seas, so the frame became mostly parchment | **Restored.** Camera widths are again the frame's short side (same graphics size as the vertical original); the sample uses the approved camera path (9.0 → 9.2 → 7.4). QC flags any scale outside the approved range |
| 2 | **NATO unit blocks** with corps numerals and trails | A new visual element, not in the approved maps | **Removed.** Movement is shown with the approved campaign arrows. Unit blocks are refused by the renderer without the client's approval |
| 3 | **Legend moved** to the top left, smaller | Different layout | **Restored** to the approved bottom-left legend bars (same size and spacing) |
| 4 | **Seven extra rivers and three extra ridges**, **splined rivers** | Busier terrain, curved rivers | **Restored** to the approved terrain (Rhine and Danube as straight polylines with italic names, Alpine and Carpathian chevrons). Splined rivers are refused without approval |
| 5 | **Fading arrows and labels** (`hide` / `out`) | Arrows disappeared after use | **Restored** to the approved behaviour (arrows stay once drawn). Refused without approval |
| 6 | Single strategic map redrawn from scratch (different places, routes and labels) | Different storytelling | **Restored:** the approved 1805 data (Boulogne → Strasbourg → Ulm → Vienna → Austerlitz, Ulm ring, Olmütz and the allied arrow, star, labels, dates, legend) |
| 7 | Vignette 0.18 and grain 0.006 | Slightly flatter image | **Restored** to the approved 0.24 and 0.008 |

**Kept (technical, appearance unchanged):**
- 1080p 16:9 output;
- collision-safe labels:
  - labels never clipped at the frame edge and never under the subtitles or the legend;
  - a label fades when its place leaves the frame instead of being parked at the edge;
  - region labels step aside under the legend;
- QC checks (label overlap, scale, style lock);
- accuracy notes in each map's `_about`.

**Only changes to the approved data:**
- **Timing** stretched ×2.9, for documentary narration instead of a 20 s Short.
- **The BAVARIA label** moved 0.7° north-east, because it touched "ULM · 20 OCT" (the QC overlap check found this in the original too).

## The lock (`ghm4/map_style.py`)
- **Refused** (the render stops with an explanation) unless the map JSON carries `"style_override_approved"` with the client's dated approval: non-original features (unit blocks, splined rivers, fading arrows or labels).
- **Flagged by QC:** the graphics scale (element scale ÷ camera width) outside the approved range; label collisions.
- **Regression test `map_lock`:**
  - every map in `ghm4/data/maps/` passes the lock and the scale range;
  - a map with unit blocks is refused;
  - an explicit approval key lets it through.
- **Project rules:**
  - `CLAUDE.md` and `STYLE_BIBLE.md` §6 state that the map style is locked;
  - the painterly illustration style applies to non-map scenes only.

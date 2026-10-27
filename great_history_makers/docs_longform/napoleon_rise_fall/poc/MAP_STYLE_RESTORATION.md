# Map style restoration (client correction, 2026-10-26)

**Approved reference:**
- the animated maps of the original Napoleon Short (`episodes_v4/napoleon_ep01`: victories 1805–11, invasion 1812, coalition 1813, Elba and the Hundred Days, Saint Helena);
- the 1805 campaign map of the approved 20s POC (`ghm4/data/maps/campaign_1805_austerlitz.json`).

All of them are rendered by `ghm4/mapshot.py`.

**Corrected sample (round 1):** `Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_1080p.mp4` (16.5 s, 1920×1080), superseded by v2 below (kept in git history only).
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

## Round 2: strict match against ACTUAL Ep01 frames (client review, 2026-10-27)
The client approved the routes, arrows, dates and camera movement of the first ORIGINAL_STYLE sample and asked for
strict consistency with the real Ep01 map frames, plus three fixes. The comparison was made on frames extracted from the
published Ep01 video (`episodes_v4/napoleon_ep01/preview_temp/output/Napoleon_Ep01_TEMP_PREVIEW_v2_720x1280.mp4`),
not from a description.

**Corrected sample:** `output/Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4` (16.5 s, 1920×1080).
**Contact sheet of actual frames:** `MAP_STYLE_CONTACT_SHEET_EP01_vs_SAMPLE.jpg`, six matching beats. Columns:
Ep01 frame | Ep01 centre at the same map scale | previous sample v1 | corrected sample v2, with the measured arrow
stroke and graphics scale printed on every v2 frame. Made with `tools/map_compare_sheet.py`.

| Client point | Cause (found on the frames) | Fix |
|---|---|---|
| Low-contrast VIENNA label | A second label "13 NOV" in small gold italic under "VIENNA" (and the same under ULM). Ep01 never uses gold notes on the parchment; its place labels are ivory bold caps with a shadow, dates joined to the name ("NIEMEN · 24 JUNE") | One ivory label "VIENNA · 13 NOV"; "AUSTRIAN ARMY SURRENDERS" uses the Ep01 small-caps label preset; "AUSTERLITZ · 2 DEC" replaces the gold battle note |
| Overlapping text | BAVARIA touched "ULM · 20 OCT"; the Austerlitz note overlapped the arrows and star; at the end STRASBOURG was pushed off its place and parked over the route and the Ulm ring | Labels moved off the arrows; a label whose place reaches the frame edge now fades instead of sliding over other map content (technical rule, look unchanged) |
| Oversized arrows | The closing zoom went to camera 2.0 (from the 20s POC punch-in), so arrows grew to about 60 ‰ of the frame | Route widths 27 / 24 (Ep01 range) and closing camera 6.2. Measured: arrows 12–19 ‰ of the short side through the whole shot (Ep01: 9–22, typically 13.5); graphics scale 0.108–0.161 (Ep01: 0.06–0.17) |

Unchanged: map background, land and sea textures, terrain (rivers, chevrons), colours, typography, legend, kicker and
date ticker, arrow drawing behaviour, camera path up to the closing beat. Map shots now always use the locked vignette
0.24 and grain 0.008, even inside a storyboard whose paintings use other values.

**Locked preset (reusable for all future documentaries):** `ghm4/data/map_presets/ghm_original_v1.json` with 8 actual
Ep01 reference frames in `ghm4/data/map_presets/ghm_original_v1/`. The regression test `map_lock` checks the drawing-code
fingerprint, the non-original features, and the scale and arrow-stroke ranges of every map.
The 20s POC map keeps its punch-in only as a recorded legacy exception (`legacy_exceptions`), not as a pattern.

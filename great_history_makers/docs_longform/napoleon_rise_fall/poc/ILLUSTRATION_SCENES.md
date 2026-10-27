# POC illustration scenes: design and pick sheet (2026-10-27)

The three painted scenes of the 60–90 s proof of concept, in the painterly style `ghm_painterly_v2` (non-map scenes only).
Generation job: `jobs/specs/napoleon_longform_poc_v1.json` → `jobs/queue/napoleon_longform_poc_v1.json` (4 seeds per scene,
1344×768 → 2016×1152 hires, plus 4 Napoleon age references). Nothing is generated yet: the job waits for the client's PC
worker (or another image route the client approves). No stand-in art is rendered in the meantime.

| Shot | Time (planned) | Narration cue | Composition | Motion and atmosphere | On-screen text |
|---|---|---|---|---|---|
| s1 Austerlitz dawn | 0–17 s | "December 1805. … He is thirty-six years old." | Napoleon (1805 variant) on a grey horse on the left third of a hilltop, three-quarter view looking right; staff and Guard chasseurs behind; fog-filled valley to the right with the dark Pratzen Heights rising from the mist | Slow pull-back 1.12 → 1.03, matte parallax 0.5, fog drift, a blink if the face is large enough | 2 DECEMBER 1805 · THE HILLS OF MORAVIA · artistic reconstruction note |
| s2 campaign map | 17–38 s | "Three months earlier, …" | Locked-style Ulm–Austerlitz map (approved sample v2) | Map animation; ink wipe in | Map kicker and date ticker |
| s3 Pratzen Heights | 38–58 s | "At dawn on the second of December, …" | Wide panorama: French line infantry columns climbing a frosty slope from lower left to the crest upper right; eagle and drummers in the foreground column; Russian line on the crest firing | Push-in 1.04 → 1.14, smoke bands, cannon puffs, flags, marching bob, haze 0.12; soft flash (0.45) on the cut | THE PRATZEN HEIGHTS |
| s4 retreat | 58–76 s | "Seven years later, …" | Snowbound road receding into a birch forest, the column moving from right foreground to left background, abandoned cannon, dead horse, crows | Push-in 1.0 → 1.1, falling snow and wind | NOVEMBER 1812 · THE RETREAT FROM MOSCOW |
| s5 title | 76–82 s | "This is the story …" | s4 plate under a dark scrim | Continued push | NAPOLEON · THE RISE AND FALL OF AN EMPEROR |

Times are planned. After the narration take exists, `ghm4.narrate retime` sets every cut from the aligned words. The map
paragraph runs about 20 s, so the 16.5 s map timeline is stretched to fit then; its look stays locked.

## History check of the prompts (corrections made today)
- **Headgear at Austerlitz:** French line infantry wore the **black bicorne** in 1805; the shako came in 1806–07.
  The Pratzen prompt said "shakos": corrected. STYLE_BIBLE §5 is corrected to match.
- **Light at the Pratzen:** the French attacked eastward up the slope, so the rising "sun of Austerlitz" was **in front
  of them, behind the allied line on the crest**. The prompt had the sun behind the French columns: corrected to a low sun
  behind the crest, backlighting the smoke.
- The queued job was regenerated from the corrected spec (the worker has not taken it; job id unchanged).
- Still to check on the generated images: uniform colours per nation, 1805 standards (white lozenge pattern), horse
  anatomy, no anachronistic buildings, no text in the image.

## How the candidates will be picked (per scene, 4 seeds)
1. **Reject** any image with broken anatomy (hands, horse legs), modern objects, text, cartoon or flat look, or an empty
   background (STYLE_BIBLE §2 and §9).
2. **Prefer** clear foreground / midground / background layers (needed for parallax), a calm lower fifth for the
   subtitles, and a readable focal point on the rule of thirds.
3. **Napoleon:** the s1 face must match the approved 1805 reference (picked first from the four `ref_1805` seeds).
4. Each pick then goes through the 2× upscale, plate metadata (smoke, flags, fog regions), the automatic matte with its QA
   gate, and the QC stage before it appears in the POC.

## What is needed to finish the POC
| # | Needed | Status |
|---|---|---|
| 1 | Image route for the 3 plates + 4 references (28 images) | Waiting for the client: local PC (install plan, approval gates), or a paid hosted route quoted first |
| 2 | Narration take of `NARRATION_POC.txt`, voice Max | Waiting for approval: estimate 944 credits (about $0.19) |
| 3 | Map scene | Done (sample v2, locked style) |
| 4 | Music and sound effects | Ready (procedural, $0) |

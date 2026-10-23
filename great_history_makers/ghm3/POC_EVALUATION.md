# v3 proof of concept: evaluation (Cinematic Living Illustration, Napoleon 1796)

**File:** `output/v3/poc_napoleon/GHM_v3_LivingIllustration_POC_1080x1920.mp4`, 12.6 s, 1080×1920, 30 fps.
**Shots:** A, a candlelit close-up of a decision (0–5.6 s), dissolving through smoke into B, the dawn ridge
with the columns advancing (5.6–12.6 s).
**Voice:** approved ElevenLabs voice, "But Napoleon wanted more." (reused from Episode 02, no new credits).
**Verified:** H.264/AAC 48 kHz; narration offset 0.0 ms (corr 0.856, lower than usual because the music sits
relatively higher in a 12 s clip); caption on its aligned words; original logo watermark (NCC 0.999). End card
omitted on purpose for this test. QC passed.
**Render:** 836 s on 4 cloud vCPUs for the final (about 6.6 s per frame including the painterly finish).
**Paid calls:** none.

## How it was made
No image generator is reachable here (no GPU, Hugging Face, Civitai and ModelScope are blocked), so everything is
painted by code in `ghm3/`. Shapes are signed-distance fields, form comes from height fields lit by a motivated point light,
colour comes from painter's value ramps, and a brush/canvas finish and bloom go on top. The character is a Live2D-style
rig on a 3D frame: gaze, lids, blinks, brows, mouth, and head pitch/yaw/roll.

## Scores (1–10, honest)
| Criterion | Score | Evidence |
|---|---|---|
| Character emotion | **4** | The decision beat reads (`acting_beats.png`): eyes lowered to the map, then lifted on "wanted", brows knit and mouth set on "more", catchlight appears, a punctuating blink. But the face is a smooth, mannequin-like construction with no skin or eye detail and no micro-expression. Banding streaks are visible on the lower face. It does not yet feel human. |
| Believable motion | **5** | Correct acting order (eyes lead, head follows over 0.75 s, face sets after). Saccades while reading, breathing that catches at the decision, flame flicker, smoke, wind in the coat skirts, plume, epaulette fringe, grass and flags, a marching cycle. But the soldiers are small, stiff silhouettes, the general barely moves, and the head motion is limited to a few degrees. |
| Artistic consistency | **5** | One lighting logic per shot (amber practical light vs dawn backlight), a shared palette and grade, the same brush finish, and the character matches the model sheet. But the procedural art (cravat, coat, hair mass, troops) reads as CG/clip-art next to the painted atmosphere, so the two shots don't feel like one hand. |
| Cinematic storytelling | **6** | Close-up (emotion) to wide (consequence), connected by his look and a smoke dissolve. Motivated push-in on the decision, a truck with the advance, foreground grass and the silhouette for depth. The light fails as smoke rolls in (victory turning uncertain). Both shots carry a narrative action, and the sound design follows. |
| **Overall** | **5** | The direction (acting, shot grammar, light, atmosphere) is demonstrated. The art quality is **not publishable** as premium animation. |

## What it proves and what it doesn't
- Proves the **grammar**: action per shot, eyes-led acting, cutting on a look, light-driven mood, painterly finish, no
  slideshow, no infographics.
- Does not prove the **look** of a premium animated film. Code-built faces hit a ceiling. That needs illustrated
  key art (AI-generated on the RTX 4060 or painted), separated into layers and rigged with the same parameters
  (Live2D Cubism / Inochi2D / `ghm3` rig), with optional low-resolution image-to-video for hero moments.

## Recommended next step
A 10–15 s test of the same two shots with **AI-illustrated key art** on the RTX 4060 (or another image source
the client approves), rigged and lit in `ghm3`. Then compare side by side with this version before any full episode.

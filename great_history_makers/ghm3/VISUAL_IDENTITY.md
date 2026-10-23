# Great History Makers: Cinematic Living Illustration (visual identity v3, PROPOSAL)

Status: proposal from the client brief of 2026-10-23. Replaces the mosaic look and the v2 slideshow
grammar once approved. Branding (gold emblem, handle) and the approved narration voice
(ElevenLabs `Gfpl8Yo74Is0W6cPUWWT`) stay.

## Never
Mosaic or tiled textures · stained-glass effects · flat paper-cut characters or puppet motion ·
zoom-and-pan over still images posing as animation · repeated static portraits · permanent maps,
timelines or infographic layouts on screen (a map may appear as a short, diegetic beat:
a map on a table, a hand on a chart).

## Always
- **Every shot is an action.** Someone decides, reacts, advances, hesitates or watches. Write it as a verb
  before drawing it ("he lifts his eyes and decides", not "portrait of Napoleon").
- **Acting order:** the eyes lead, the head follows, then the body; the face *sets* after a decision
  (brows lower, jaw tightens); blinks punctuate thoughts; breathing changes with emotion.
- **Shot grammar:** alternate close-ups (emotion), medium shots (gesture) and wide establishing shots
  (consequence). Use foreground elements (candle, grass, banners) for depth. One motivated camera move per shot
  (push into a decision, truck with an advance, crane to reveal). Cut on a look or an action.
- **Light tells the story:** one motivated key per scene (candle, dawn sun, fire), a cool fill, a warm rim.
  The mood shifts through light: smoke taking the sun as victory turns uncertain.
- **Painterly finish:** soft lost-and-found edges, value-driven colour ramps, visible but restrained brush texture,
  atmospheric depth (haze, smoke, dust, embers). No outlines on characters except where light dies.
- **Character consistency:** one model sheet per character per life stage (e.g. Bonaparte 1796: long straight
  dark-brown hair covering the ears, lean face, grey-blue eyes, white stock, high dark-blue collar with gold
  embroidery). Every shot is checked against it.

## Palette
Night interiors: amber key (255,180,110) against blue-black (10,8,18). Dawn exteriors: rose-gold horizon
(238,156,92) under slate (34,40,62), backlit smoke. Uniforms keep historical colours, desaturated in shadow.

## Production stack (target)
1. Key art per shot: AI illustration on the RTX 4060 (SDXL or FLUX.1-schnell + style LoRA trained on approved
   frames + character reference sheets/IP-Adapter), or commissioned paintings. Not available in the cloud container.
2. Layer split for acting: face parts (eyes, lids, brows, mouth), hair locks, head, torso, arms, cloth, props;
   clean plates behind them.
3. Rigging: Live2D-style deformers (Inochi2D is open source; Live2D Cubism has a free tier for small creators,
   check its current terms) or our own `ghm3` parameter rig (gaze, lids, blink, brows, mouth, head pitch/yaw/roll,
   breath, wind on cloth/hair).
4. Optional hero moments: a local open image-to-video model at low resolution, upscaled. Paid image-to-video
   only with approval, and only where the cost fits the €0.50/video target.
5. Scene renderer (`ghm3`): camera, light, smoke, particles, transitions, grade, captions, branding.

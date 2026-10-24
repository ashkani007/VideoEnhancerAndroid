# Napoleon 2D Animation POC: project

12-second, 1080×1920, 30 fps, H.264 proof of concept for a stylized editorial 2D animation pipeline
(no narration). Output: `../final/Napoleon_2D_Animation_POC.mp4`.

## How it works
Everything is vector art drawn and animated in Python with **Skia** (`skia-python`, the 2D engine used in
Chrome). A **skeletal cut-out rig** places each body part in its parent's coordinate frame. Frames are piped to
**FFmpeg**. No AI image generation and no paid services are used.

| File | Role |
|---|---|
| `animation_source/gfx.py` | Smooth Bezier shapes, cel shading (shadow carved with path booleans on the side away from the key light, lit-side rim), gradients, glows |
| `animation_source/anim.py` | Keyframe tracks with easing (in/out/back overshoot), damped springs for secondary motion, blinks |
| `animation_source/napoleon.py` | Napoleon rig, 3/4 view: torso (lean, breath) → head (tilt, nod, yaw) and arms (shoulder → elbow → wrist → hand poses flat/point/open/relaxed). Face rig: gaze, blink, lids, brows (raise/knit), mouth shapes (neutral, tight, shout + open amount). Two-link **IK** (`ik_arm`) puts the hand on world targets. |
| `animation_source/soldier.py` | Line infantryman rig, profile: walk cycle (thigh/knee/foot), swinging arm, musket at the slope, shako |
| `animation_source/scenes.py` | Three scenes, acting tracks, cameras, backgrounds (candle flicker, moving curtains, drifting mist and smoke, marching columns, waving flags, grass) |
| `render_scripts/render.py` | Frame renderer, transitions (match cut, whip-pan), vignette, FFmpeg encode (NVENC if available, else x264) |

## Run (Windows 11 or Linux)
```
pip install skia-python numpy opencv-python
# FFmpeg on PATH (an NVENC-enabled build uses the RTX 4060 for encoding)
cd render_scripts
python render.py --preview        # 540x960 preview  -> project/previews/
python render.py                  # 1080x1920 final  -> final/Napoleon_2D_Animation_POC.mp4
python render.py --still 5.4      # single frame check
```
On Linux, skia-python needs `libEGL` (`apt-get install libegl1`). Windows wheels include what they need.
`render.py` picks the `spawn` start method on Windows and `fork` elsewhere.

## Reuse
- New character: copy `napoleon.py` and change the palette entries and costume shapes; the skeleton, face rig and IK stay.
- New acting: add `Track` keys (time, value, easing) per parameter; springs give follow-through automatically.
- New set: background functions draw in design units (1080×1920) with parallax by camera offset.

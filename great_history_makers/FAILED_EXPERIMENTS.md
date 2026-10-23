# Failed experiments and why

| Date | Episode | Approach | Why it failed | Replacement |
|---|---|---|---|---|
| 10-20 | ep01 V1 | Sinusoidal leg swing at constant body speed | Feet slide and the figure floats with the bob | `walk_planted` (linear stance sweep, hip drop) |
| 10-20 | ep01 V1 | `wave_deform` pixel warp for cloaks/banners | Stretched tesserae | `rigid_tile_wave` |
| 10-20 | ep01 V2 | Rigid-tile wave leaving gaps transparent | White specks of background showed through | Fill gaps with grout |
| 10-20 | ep01 V1 | Estimated subtitle timing | Not tied to the real voice | Forced alignment |
| 10-21 | 1b | Whisper / Vosk / HF models | Blocked by the network policy (403) | PocketSphinx (PyPI, offline) |
| 10-21 | 1b | Naive mix (music ducked by a voice envelope) | Bed louder than voice in pauses; ASR mismatch 49 % | Voice-referenced stem levelling |
| 10-21 | 1b | Captions placed per shot, often near the top | Client rejected high captions | Fixed y = 1410 |
| 10-21 | 1b | Reusing one composition across many seconds | Client called it a slideshow | 18–19 distinct shots, each with its own motion |
| 10-21 | V2→V3 | Pale bone/sand palette + haze bands + white glows | Washed-out beige look | V3 palette, CinematicGrade, amber glows |
| 10-21 | V3 | 4 workers at 1080p plus the parent holding a copy | OOM kill | Free the parent copy, 3 workers |
| 10-21 | V3 | Workers writing the same cache file at once | Truncated npz (EOFError) | Atomic write plus validation |
| 10-21 | V3 | `pkill -f produce.py` | Killed its own shell and the render | `pgrep -f "[p]roduce.py"` |
| 10-21 | V4 | brand.py cleanup listing the wrong folder | 527 MB intermediate committed; push rejected | glob-based cleanup, .gitignore *.mkv |
| 10-21 | 2.5D | Lions drawn on a receding wall by squashing x | Read as yellow smears | Foreshortened rosettes and simplified frieze bodies |
| 10-21 | 2.5D | Volume shading strength 0.75 | Too subtle at phone size | 1.25 / ambient 0.28 |
| 10-21 | 2.5D | Ground sliced by depth with no overlap | Black seams under parallax | 30-unit overlap |
| 10-22 | 2.5D C | Gait stride 500 / foot lift 70 | Exaggerated, goose-step look | Stride 400–450, lift 26–36 |
| 10-22 | 2.5D C | Shadow tint (0.58, 0.64, 0.82) on many figures | Scene saturation −5 % vs B | Compensating grade; next: warmer tint |
| 10-22 | 2.5D C | Foreground pillar starting near centre | Covered the gate (the subject) | Start at right third; still too early |
| 10-22 | 2.5D C | Fixed-profile soldiers translated along a route curving into the gate | Bodies did not turn; slid into depth (client rejected) | `turnrig`: path-tangent yaw, 9-view turnaround, 3D joints, world-planted feet |
| 10-22 | 2.5D D | Metric: heading at s < 0 | atan2(0,0) gave 0° for walkers not yet on the path | Measure only on visible frames |
| 10-22 | ep02 | Passing the `cam` factory to TurnDraw instead of a camera function | `'function' object has no attribute 'get'` | Build `c = cam(...)` once, pass `c` to both TurnDraw and Scene |
| 10-22 | ep02 | Fixed-width bicorne on all views | Hat looked like a wide plate in front view | Width follows view angle (46 + 92·\|cos θ\|) |
| 10-22 | ep02 | Head sprite rect (-160,-260,320,460) | Tall bearskins clipped at the top | Rect (-200,-300,400,560) |
| 10-22 | ep02 | Napoleon placed behind the plan table at map height | Hidden by the table | Larger figure (k 1.25) standing higher, table in the foreground |
| 10-22 | ep02 | Return walk ending low in frame | Face crossed the caption band | Path ends at q 1.92; still crosses the band mid-walk; needs a higher path |
| 10-22 | ep02 | Writing deliverables before creating `output/<id>/deliverables` | FileNotFoundError | Create the directory first (`mkdir -p`) |
| 10-23 | 2.5D/turnrig production model | Full procedural 2.5D episodes (Ep02) | Too expensive per episode; client stopped it | v2: illustration plates + puppet warps + mograph |
| 10-23 | v2 PoC | Storyboard iterated europe_land() dict keys | `proj() missing lat` | Use `.values()`; geodata now in ghm2/data |
| 10-23 | v2 PoC | Austerlitz and Wagram labels at default offsets | Labels overlapped (battles 90 km apart) | Per-arrow label offsets |
| 10-23 | v2 look | Plates + pan/zoom + infographic maps (v2 PoC) | Client: "mosaic-style educational slideshow" | v3 Cinematic Living Illustration proposal |
| 10-23 | v3 PoC | cv2 thickness multiplied by 4 with shift=2 | All strokes 4x too thick | Thickness in real pixels |
| 10-23 | v3 PoC | Hair strands between random outline points; back-hair strands drawn after the face | Strands across the face, hair looked transparent | Flow-following strands clipped to the hair shape, correct layer order |
| 10-23 | v3 PoC | Gaussian-blurred noise scrolled with BORDER_WRAP | Vertical seams in smoke | FFT circular blur (tileable) |

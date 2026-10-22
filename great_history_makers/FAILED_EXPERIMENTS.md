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

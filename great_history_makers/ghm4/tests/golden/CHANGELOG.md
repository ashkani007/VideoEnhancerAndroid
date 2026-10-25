# Golden frame changes
- 2026-10-25: demo_10.25 / demo_12.50 / demo_14.60 re-blessed. The map camera is now clamped to the canvas; the
  victories map bounds were extended (lat 32-66) so its approved framing is unchanged, but the canvas grew, which shifts
  the paper texture and hatch phase (PSNR 34-44 dB vs the old frames, same framing and content). Before the fix the
  top/bottom edges of that view were mirrored border padding hidden under the scrims.

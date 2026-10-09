# Headset calibration

Open **Library → Headset**. The phone switches to landscape and shows a calibration pattern
for each eye. Tap the screen to hide/show the control panel; hide it while the phone is in
the headset.

## What you should see in the headset

- **Grid**: lines should look straight across the whole field of view. Bowed outward
  (pincushion) → increase *k1*; bowed inward (barrel) → decrease *k1*. Use *k2* for the outer
  edge only.
- **Green crosses**: each should sit in the middle of its lens. Adjust *Lens separation*
  first, then the per-eye *horizontal/vertical* offsets for small asymmetries.
- **Red dot / blue dot**: close your right eye — you must see only the red dot; close your
  left eye — only the blue dot. The layout follows the phone's landscape orientation, so this
  must hold either way round; if it doesn't, it is a bug. Stereo *videos* stored right-eye-first
  are fixed with the per-video *Swap left/right eyes* setting.
- **Checkerboard**: helps judge sharpness and edge distortion.

## Controls and safe ranges

| Setting | Range | Notes |
|---|---|---|
| Lens separation | 50–75 mm | Places each eye's image under its lens using the screen's physical DPI. It does **not** change optical IPD, which is fixed by the headset lenses or its IPD slider. |
| Lens height from bottom | 0–60 mm (0 = centered) | For headsets whose lenses are not vertically centered. |
| Distortion k1 / k2 | −0.10–0.60 / −0.10–0.40 | Radial pre-distortion `r' = r·(1 + k1·r² + k2·r⁴)`. |
| Per-eye optical center | ±0.15 of the eye viewport | Fine alignment per lens. |
| Image offset | ±0.25 | Moves the image content, e.g. to fix a vertical misalignment between eyes. |
| Zoom | 0.5–2.0 | Divides the field of view. |
| Field of view | 60–120° | Vertical FOV of each virtual eye camera; match it to the lens FOV to avoid swimming. |
| Edge margin | 0–0.2 | Blacks out the blurry lens edges. |

All values are clamped to these ranges when saved or imported.

## Profiles

*Save* updates the selected profile; *Save as new* creates another (names are made unique);
*Delete* is refused for the last profile. *Export* copies the profile as JSON to the clipboard;
*Import* reads a profile from the clipboard (unknown keys are ignored and all values clamped).

## Camera cutout

With *Keep image clear of camera cutout* enabled (Settings), both eye viewports are trimmed
by the same amount from the outer edges, so lens centers stay at their physical positions.

## Without a headset

Use *Phone view* in the player: one full-screen view, no distortion, drag to look around.

"""Easing, keyframes and the motivated camera (design units: 1080x1920 frame)."""
import math

import numpy as np

DW, DH = 1080, 1920


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_io(x):
    """Sine ease-in-out: slow start, slow end (camera moves never 'pop')."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def keys(kf, t, default=0.0):
    """Piecewise eased keyframes [[t, value], ...]."""
    if not kf:
        return default
    if t <= kf[0][0]:
        return kf[0][1]
    for (t0, v0), (t1, v1) in zip(kf, kf[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease_io((t - t0) / max(1e-6, t1 - t0))
    return kf[-1][1]


class Camera:
    """A single motivated move per composition: from -> to (zoom >= 1, focus point in design units).

    BASE overscale gives every plate a small margin so parallax and pans never expose edges;
    offsets are clamped per layer so a plate always covers the frame."""
    BASE = 1.06

    def __init__(self, spec, dur):
        self.a = dict(dict(zoom=1.0, x=DW / 2, y=DH / 2), **spec.get("from", {}))
        self.b = dict(self.a, **spec.get("to", {}))
        self.t0, self.t1 = spec.get("start", 0.0), spec.get("end", dur)

    def at(self, t):
        u = ease_io((t - self.t0) / max(1e-6, self.t1 - self.t0))
        return {k: self.a[k] + (self.b[k] - self.a[k]) * u for k in ("zoom", "x", "y")}

    def matrix(self, cam, depth, plate_scale, out_scale, cover=True):
        """3x3 affine: plate pixels -> output pixels for a layer at `depth` (0 far, 1 subject, >1 near)."""
        zl = self.BASE * (1.0 + (cam["zoom"] - 1.0) * depth)
        ox, oy = (cam["x"] - DW / 2) * depth, (cam["y"] - DH / 2) * depth
        if cover:
            mx, my = DW / 2 * (1 - 1 / zl), DH / 2 * (1 - 1 / zl)
            ox, oy = float(np.clip(ox, -mx, mx)), float(np.clip(oy, -my, my))
        s = out_scale * zl / plate_scale
        tx = out_scale * (DW / 2 - zl * (DW / 2 + ox))
        ty = out_scale * (DH / 2 - zl * (DH / 2 + oy))
        return np.array([[s, 0, tx], [0, s, ty], [0, 0, 1]], np.float32)

"""Vector painter used to author flat layer art (in design units).

All artwork is described in resolution-independent *units* and rasterised at a
given pixels-per-unit, so preview and final renders share the exact same design
(and, after tessellation, the exact same tile layout scaled up).
Anti-aliasing is intentionally off: tessellation needs crisp colour regions.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from .palette import P


def _col(c):
    if isinstance(c, str):
        r, g, b = P[c]
        return (r, g, b, 255)
    if len(c) == 3:
        return tuple(c) + (255,)
    return tuple(c)


def catmull_rom(points, samples=8, closed=True):
    pts = [np.asarray(p, float) for p in points]
    n = len(pts)
    out = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if closed or i > 0 else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed or i + 2 < n else pts[-1]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(pts[-1])
    return [tuple(p) for p in out]


class Painter:
    """Draws into an RGBA canvas covering unit-space rect (x0, y0, w, h)."""

    def __init__(self, x0, y0, w, h, ppu):
        self.x0, self.y0, self.ppu = x0, y0, ppu
        self.W = max(1, int(math.ceil(w * ppu)))
        self.H = max(1, int(math.ceil(h * ppu)))
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.M = np.eye(3)
        self._stack = []

    # ---- transform stack (local units -> canvas units) ----
    def push(self):
        self._stack.append(self.M.copy())

    def pop(self):
        self.M = self._stack.pop()

    def translate(self, x, y):
        self.M = self.M @ np.array([[1, 0, x], [0, 1, y], [0, 0, 1.0]])

    def scale(self, sx, sy=None):
        sy = sx if sy is None else sy
        self.M = self.M @ np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1.0]])

    def rotate(self, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        self.M = self.M @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])

    def _px(self, pts):
        a = np.asarray(pts, float).reshape(-1, 2)
        a = a @ self.M[:2, :2].T + self.M[:2, 2]
        a = (a - (self.x0, self.y0)) * self.ppu
        return [tuple(p) for p in a]

    def _lscale(self):
        return math.sqrt(abs(np.linalg.det(self.M[:2, :2]))) * self.ppu

    # ---- primitives ----
    def poly(self, pts, fill):
        if len(pts) >= 3:
            self.d.polygon(self._px(pts), fill=_col(fill))

    def smooth(self, pts, fill, samples=8):
        self.poly(catmull_rom(pts, samples), fill)

    def rect(self, x, y, w, h, fill):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], fill)

    def ellipse(self, cx, cy, rx, ry, fill, start=0, end=360, n=48):
        pts = []
        for i in range(n + 1):
            a = math.radians(start + (end - start) * i / n)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        if end - start < 360:
            pts.append((cx, cy))
        self.poly(pts, fill)

    def circle(self, cx, cy, r, fill):
        self.ellipse(cx, cy, r, r, fill)

    def line(self, pts, fill, width):
        w = max(1, int(round(width * self._lscale())))
        self.d.line(self._px(pts), fill=_col(fill), width=w, joint="curve")
        r = w / 2.0
        for p in self._px([pts[0], pts[-1]]):
            self.d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=_col(fill))

    def curve(self, pts, fill, width, samples=10):
        self.line(catmull_rom(pts, samples, closed=False), fill, width)

    def vgradient_bands(self, x, y, w, h, colors):
        """Horizontal colour bands (mosaic skies are laid in bands)."""
        n = len(colors)
        for i, col in enumerate(colors):
            self.rect(x, y + h * i / n, w, h / n + 0.5, col)

    def array(self):
        return np.array(self.img)

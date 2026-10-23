"""Screen-space light and atmosphere for illustration plates (all deterministic in t).

Every overlay is a callable f(frame, t, W, H, cam) operating on a float32 RGB frame in place.
Positions are design units (1080x1920) so specs are resolution independent."""
import math

import cv2
import numpy as np

from .anim import DW


def _rgb(c):
    return np.array(c, np.float32) / 255.0


class Particles:
    """Drifting motes: kind dust (soft, slow), embers (warm, rising, flicker), gold (sparkle)."""

    def __init__(self, n=60, kind="dust", region=(0, 0, 1, 1), color=(255, 226, 170), size=(2, 5), speed=(10, 30),
                 drift=(6, -18), seed=0, strength=0.6, depth=0.6):
        r = np.random.default_rng(seed)
        self.p0 = r.uniform(0, 1, (n, 2))
        self.sz = r.uniform(*size, n)
        self.sp = r.uniform(*speed, n)
        self.ph = r.uniform(0, 2 * math.pi, n)
        self.kind, self.region, self.col = kind, region, _rgb(color)
        self.drift, self.strength, self.depth = np.array(drift, np.float32), strength, depth

    def __call__(self, frame, t, W, H, cam):
        s = W / DW
        x0, y0, x1, y1 = self.region
        rw, rh = (x1 - x0) * DW, (y1 - y0) * 1920
        pos = self.p0 * [rw, rh] + self.drift * t * self.sp[:, None] / 20
        pos += np.stack([12 * np.sin(t * 0.7 + self.ph), 8 * np.cos(t * 0.5 + self.ph)], 1)
        pos = np.mod(pos, [rw, rh]) + [x0 * DW, y0 * 1920]
        pos -= (np.array([cam["x"] - DW / 2, cam["y"] - 960]) * self.depth)   # parallax with the camera
        layer = np.zeros(frame.shape[:2], np.float32)
        for (x, y), sz, ph in zip(pos, self.sz, self.ph):
            a = 0.55 + 0.45 * math.sin(t * (3.0 if self.kind != "dust" else 0.9) + ph)
            if self.kind == "gold":
                a = max(0.0, math.sin(t * 2.2 + ph)) ** 3
            cv2.circle(layer, (int(x * s), int(y * s)), max(1, int(sz * s)), float(a), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), max(0.8, 1.6 * s))
        frame += layer[..., None] * self.col * self.strength


class GodRays:
    """Soft light shafts from a source point (window, sun), slowly breathing."""

    def __init__(self, src, color=(255, 230, 170), strength=0.25, n=9, spread=38, length=1500, seed=3, depth=0.4):
        r = np.random.default_rng(seed)
        self.src, self.col, self.strength, self.depth = src, _rgb(color), strength, depth
        self.angles = 90 + r.uniform(-spread, spread, n)
        self.widths = r.uniform(18, 60, n)
        self.ph = r.uniform(0, 6.28, n)
        self.length = length

    def __call__(self, frame, t, W, H, cam):
        s = W / DW
        sx = (self.src[0] - (cam["x"] - DW / 2) * self.depth) * s
        sy = (self.src[1] - (cam["y"] - 960) * self.depth) * s
        layer = np.zeros(frame.shape[:2], np.float32)
        for a, w, ph in zip(self.angles, self.widths, self.ph):
            rad = math.radians(a + 2 * math.sin(t * 0.3 + ph))
            ex, ey = sx + math.cos(rad) * self.length * s, sy + math.sin(rad) * self.length * s
            nx, ny = -math.sin(rad) * w * s, math.cos(rad) * w * s
            pts = np.array([[sx, sy], [ex - nx * 3, ey - ny * 3], [ex + nx * 3, ey + ny * 3]], np.int32)
            cv2.fillConvexPoly(layer, pts, float(0.5 + 0.5 * math.sin(t * 0.8 + ph)), cv2.LINE_AA)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        fall = np.exp(-np.hypot(xx - sx, yy - sy) / (900 * s))
        layer = cv2.GaussianBlur(layer, (0, 0), 22 * s) * fall
        frame += layer[..., None] * self.col * self.strength


class Flicker:
    """Warm practical light (candle, fire) that flickers; multiplies and adds around a point."""

    def __init__(self, pos, radius=600, color=(255, 170, 90), strength=0.35, seed=5, depth=1.0):
        self.pos, self.r, self.col, self.strength, self.seed, self.depth = pos, radius, _rgb(color), strength, seed, depth
        self._g = None

    def __call__(self, frame, t, W, H, cam):
        s = W / DW
        f = 0.8 + 0.12 * math.sin(t * 13.1 + self.seed) + 0.08 * math.sin(t * 7.3 + 2 * self.seed) \
            + 0.05 * math.sin(t * 23.7)
        x = (self.pos[0] - (cam["x"] - DW / 2) * self.depth) * s
        y = (self.pos[1] - (cam["y"] - 960) * self.depth) * s
        if self._g is None or self._g[0] != (W, H):
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            self._g = ((W, H), xx, yy)
        _, xx, yy = self._g
        g = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (self.r * s * cam["zoom"]) ** 2))
        frame *= 1 + (self.col - 1 + 0.6) * (g * self.strength * f)[..., None] * 0.6
        frame += (g * self.strength * f * 0.15)[..., None] * self.col


class Vignette:
    def __init__(self, amount=0.35):
        self.amount, self._m = amount, None

    def __call__(self, frame, t, W, H, cam):
        if self._m is None or self._m.shape[:2] != frame.shape[:2]:
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            d = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / math.sqrt(2)
            self._m = (1 - self.amount * np.clip(d - 0.25, 0, 1) ** 1.6 / 0.75 ** 1.6)[..., None]
        frame *= self._m


class Grain:
    def __init__(self, amount=0.018, seed=11):
        self.amount, self.seed = amount, seed

    def __call__(self, frame, t, W, H, cam):
        r = np.random.default_rng(self.seed + int(t * 30))
        n = r.normal(0, self.amount, (H // 2, W // 2)).astype(np.float32)
        frame += cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]


def build(spec):
    kinds = {"particles": Particles, "godrays": GodRays, "flicker": Flicker, "vignette": Vignette, "grain": Grain}
    spec = dict(spec)
    return kinds[spec.pop("type")](**spec)

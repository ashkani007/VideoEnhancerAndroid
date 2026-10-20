"""Screen-space atmosphere: dust motes, glow, haze, vignette, grade, mosaic transitions."""
import math

import cv2
import numpy as np
from scipy.spatial import cKDTree

from .palette import P


def _rgb(c):
    return np.array(P[c] if isinstance(c, str) else c, np.float32) / 255.0


class Dust:
    """Slow drifting motes lit by the sun. Kept faint so tiles stay readable."""

    def __init__(self, n=140, seed=1, color="sun_hot", strength=0.35, drift=(-12, -6),
                 size=(0.8, 2.4), region=(0, 0, 1, 1), parallax=0.6):
        r = np.random.default_rng(seed)
        self.p = r.random((n, 2))
        self.size = r.uniform(*size, n)
        self.a = r.uniform(0.25, 1.0, n)
        self.ph = r.uniform(0, 6.28, n)
        self.sp = r.uniform(0.5, 1.5, n)
        self.col, self.strength, self.drift = _rgb(color), strength, drift
        self.region, self.parallax = region, parallax

    def __call__(self, frame, t, ctx, cam):
        H, W = frame.shape[:2]
        ov = np.zeros((H, W), np.uint8)
        x0, y0, x1, y1 = self.region
        s = ctx.pxpd
        for i in range(len(self.p)):
            x = (self.p[i, 0] * 1080 + self.drift[0] * self.sp[i] * t + 10 * math.sin(t * 0.7 * self.sp[i] + self.ph[i])
                 - cam.get("ox", 0) * self.parallax) % 1080
            y = (self.p[i, 1] * 1920 + self.drift[1] * self.sp[i] * t + 14 * math.sin(t * 0.5 + self.ph[i] * 2)
                 - cam.get("oy", 0) * self.parallax) % 1920
            if not (x0 * 1080 <= x <= x1 * 1080 and y0 * 1920 <= y <= y1 * 1920):
                continue
            tw = 0.6 + 0.4 * math.sin(t * 2.0 * self.sp[i] + self.ph[i])
            cv2.circle(ov, (int(x * s * 16), int(y * s * 16)), max(1, int(self.size[i] * s * 16)),
                       int(255 * self.a[i] * tw), -1, cv2.LINE_AA, shift=4)
        if self.strength > 0:
            g = cv2.GaussianBlur(ov, (0, 0), 1.2 * s + 0.4).astype(np.float32) * (self.strength / 255.0)
            frame += g[..., None] * self.col


class Glow:
    """Soft warm light from a point (sun / sky), screen blended. Optional slow breathing."""

    def __init__(self, center, radius, color="sun_hot", strength=0.3, breathe=0.0, parallax=0.3):
        self.c, self.r, self.col, self.s = center, radius, _rgb(color), strength
        self.breathe, self.parallax = breathe, parallax
        self._cache = None

    def __call__(self, frame, t, ctx, cam):
        H, W = frame.shape[:2]
        key = (H, W)
        if self._cache is None or self._cache[0] != key:
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            self._cache = (key, xx / ctx.pxpd, yy / ctx.pxpd)
        _, xx, yy = self._cache
        cx = self.c[0] - cam.get("ox", 0) * self.parallax
        cy = self.c[1] - cam.get("oy", 0) * self.parallax
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / self.r
        g = np.exp(-d * d * 2.2) * self.s * (1 + self.breathe * math.sin(t * 0.9))
        g = g[..., None] * self.col
        frame[:] = 1 - (1 - frame) * (1 - g)


class Haze:
    """Horizontal band of atmospheric haze at a screen height (design units)."""

    def __init__(self, y, height, color="sky_pale", strength=0.25, parallax=0.5):
        self.y, self.h, self.col, self.s, self.parallax = y, height, _rgb(color), strength, parallax

    def __call__(self, frame, t, ctx, cam):
        H = frame.shape[0]
        yy = np.arange(H, dtype=np.float32) / ctx.pxpd
        cy = self.y - cam.get("oy", 0) * self.parallax
        z = cam.get("zoom", 1.0)
        cy = 960 + (cy - 960) * (1 + (z - 1) * self.parallax)
        a = np.exp(-((yy - cy) / self.h) ** 2) * self.s
        frame[:] = frame * (1 - a[:, None, None]) + self.col * a[:, None, None]


class Shafts:
    """Very faint diagonal light shafts drifting slowly."""

    def __init__(self, angle=-28, strength=0.06, color="sun_hot", speed=8, seed=3):
        self.angle, self.s, self.col, self.speed = angle, strength, _rgb(color), speed
        r = np.random.default_rng(seed)
        self.bands = [(r.uniform(-600, 1600), r.uniform(40, 140), r.uniform(0.4, 1)) for _ in range(5)]
        self._g = None

    def __call__(self, frame, t, ctx, cam):
        H, W = frame.shape[:2]
        if self._g is None or self._g[0] != (H, W):
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            a = math.radians(self.angle)
            self._g = ((H, W), (xx * math.cos(a) + yy * math.sin(a)) / ctx.pxpd, yy / H)
        _, u, v = self._g
        acc = np.zeros((H, W), np.float32)
        for c, w, s in self.bands:
            acc += s * np.exp(-((u - c - self.speed * t) / w) ** 2)
        acc *= (1 - v) ** 1.5 * self.s
        frame[:] = 1 - (1 - frame) * (1 - acc[..., None] * self.col)


class Vignette:
    def __init__(self, strength=0.35, roundness=1.0):
        self.s, self.round = strength, roundness
        self._m = None

    def __call__(self, frame, t, ctx, cam):
        H, W = frame.shape[:2]
        if self._m is None or self._m.shape[:2] != (H, W):
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 * self.round + ((yy - H / 2) / (H / 2)) ** 2)
            self._m = (1 - self.s * np.clip(d - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)
        frame *= self._m


class Grade:
    """Gentle filmic grade: lift/gain/saturation, applied per scene for mood."""

    def __init__(self, gain=(1, 1, 1), lift=(0, 0, 0), gamma=1.0, sat=1.0, fade=None):
        self.gain = np.array(gain, np.float32)
        self.lift = np.array(lift, np.float32)
        self.gamma, self.sat, self.fade = gamma, sat, fade

    def __call__(self, frame, t, ctx, cam):
        np.clip(frame, 0, 1, out=frame)
        if self.gamma != 1.0:
            np.power(frame, self.gamma, out=frame)
        frame *= self.gain
        frame += self.lift * (1 - frame)
        if self.sat != 1.0:
            lum = frame @ np.array([0.299, 0.587, 0.114], np.float32)
            frame[:] = lum[..., None] + (frame - lum[..., None]) * self.sat
        if self.fade:
            frame *= self.fade(t)


class MosaicWipe:
    """Transition in which the next scene appears tile by tile (large tesserae),
    sweeping in a direction with randomised per-tile timing."""

    def __init__(self, ctx, tile=46, direction=(1, 0.4), seed=7, softness=0.18):
        H, W = ctx.H, ctx.W
        r = np.random.default_rng(seed)
        t = tile * ctx.pxpd
        ys = np.arange(t / 2, H + t, t)
        pts = []
        for i, y in enumerate(ys):
            xs = np.arange((i % 2) * t / 2, W + t, t)
            pts.append(np.c_[xs, np.full_like(xs, y)])
        pts = np.concatenate(pts) + r.uniform(-0.3 * t, 0.3 * t, (sum(len(p) for p in pts), 2))
        yy, xx = np.mgrid[0:H, 0:W]
        _, lab = cKDTree(pts).query(np.c_[xx.ravel(), yy.ravel()], workers=-1)
        lab = lab.reshape(H, W)
        d = np.array(direction, float)
        d /= np.linalg.norm(d)
        proj = (pts[:, 0] / W - 0.5) * d[0] + (pts[:, 1] / H - 0.5) * d[1]
        proj = (proj - proj.min()) / (np.ptp(proj) + 1e-6)
        delay = 0.65 * proj + 0.35 * r.random(len(pts))
        self.delay = delay.astype(np.float32)[lab]
        bnd = np.zeros((H, W), np.uint8)
        bnd[:, 1:] |= (lab[:, 1:] != lab[:, :-1])
        bnd[1:, :] |= (lab[1:, :] != lab[:-1, :])
        self.grout = cv2.dilate(bnd, np.ones((2, 2), np.uint8)).astype(bool)
        self.soft = softness

    def blend(self, a, b, p):
        m = np.clip((p * (1 + self.soft) - self.delay) / self.soft, 0, 1)
        m = m * m * (3 - 2 * m)
        out = a * (1 - m[..., None]) + b * m[..., None]
        edge = (m > 0.02) & (m < 0.98) & self.grout
        out[edge] *= 0.55
        return out

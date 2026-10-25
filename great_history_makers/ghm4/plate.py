"""An illustration plate with its motion metadata (limited, region-based animation of the original pixels).

plate.json (coordinates in plate pixels at `ref_width`; they are rescaled to the working resolution):
{
  "ref_width": 941,
  "mask": "mask.png",                 optional foreground matte -> two layers with parallax
  "background": "background.png",     optional pre-inpainted background (else inpainted automatically)
  "sky": {"y": 660, "drift": 3.0},    clouds drift (px per 5 s at the top edge)
  "flags": [{"box": [x0,y0,x1,y1], "pole_x": 772, "amp": 4.2, "freq": 1.25, "k": 68}],
  "bob": [{"box": [...], "amp": 1.3, "rate": 1.8, "feather": 30}],             marching ranks / riders
  "smoke": [{"box": [...], "feather": 45, "density": 1.0, "speed": 14}],      drifting posterized smoke
            (optional "gain_key": "battle", "default_gain": 0 -> only shots with gains {"battle": 1} show it)
  "smoke_column": [{"x": 830, "y": 665, "sx": 50, "sy": 40}],                 billowing column
  "wind": [{"box": [...], "amp": 2.0, "rate": 0.6, "feather": 20}],           cloth ripple (foreground layer)
  "sway": [{"box": [...], "pivot": [x, y], "angle": 1.5, "rate": 0.35, "feather": 20, "at": 1.0}],   hand / forearm motion
  "eyes": [{"upper": [[x,y],...], "lower": [[x,y],...], "close_y": 320, "skin": [x0,y0,x1,y1]}],
  "sun": {"x": 905, "y": 590, "r": 160}
}
"""
import json
import math
import os
import sys

import cv2
import numpy as np


def ease(u):
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def tileable_noise(h, w, sigma, seed):
    r = np.random.default_rng(seed)
    F = np.fft.rfft2(r.normal(0, 1, (h, w)))
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.rfftfreq(w)[None, :]
    F *= np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    n = np.fft.irfft2(F, s=(h, w)).astype(np.float32)
    return (n - n.min()) / (np.ptp(n) + 1e-6)


def ok(roi, min_size=2):
    """A region of interest that lies (at least partly) inside the plate."""
    return roi[2] - roi[0] >= min_size and roi[3] - roi[1] >= min_size


def blink_amount(u):
    """u in [0, 1] over the blink: close 40 %, hold 15 %, open 45 %."""
    if u < 0 or u > 1:
        return 0.0
    return u / 0.4 if u < 0.4 else (1.0 if u < 0.55 else 1 - (u - 0.55) / 0.45)


class Plate:
    def __init__(self, path, meta_path=None, factor=1.0):
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(path)
        self.meta = json.load(open(meta_path, encoding="utf-8")) if meta_path and os.path.exists(meta_path) else {}
        base = os.path.dirname(meta_path or path)
        H0, W0 = img.shape[:2]
        if factor < 0.999:
            img = cv2.resize(img, (int(round(W0 * factor)), int(round(H0 * factor))), interpolation=cv2.INTER_AREA)
        self.img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        self.H, self.W = self.img.shape[:2]
        self.k = self.W / float(self.meta.get("ref_width", W0))   # meta coordinates -> working pixels
        self.alpha = None
        m = cv2.imread(os.path.join(base, self.meta["mask"]), 0) if self.meta.get("mask") else None
        if self.meta.get("mask") and m is None:
            print(f"warning: matte {self.meta['mask']} not found; {os.path.basename(path)} renders as one layer", file=sys.stderr)
        if m is not None:
            m = cv2.resize(m, (self.W, self.H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            self.alpha = cv2.GaussianBlur(m, (0, 0), max(0.6, 0.9 * self.k))
            if self.meta.get("background"):
                b = cv2.imread(os.path.join(base, self.meta["background"]))
                self.bg = cv2.cvtColor(cv2.resize(b, (self.W, self.H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
            else:
                self.bg = self._inpaint(m)
        else:
            self.bg = self.img
        self._prep()

    def _inpaint(self, m):
        hole = cv2.dilate((m > 0.3).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
        small = cv2.resize((self.img * 255).astype(np.uint8), (self.W // 2, self.H // 2), interpolation=cv2.INTER_AREA)
        hs = cv2.resize(hole, (self.W // 2, self.H // 2), interpolation=cv2.INTER_NEAREST)
        fill = cv2.inpaint(small, hs, 18, cv2.INPAINT_TELEA)
        fill = cv2.resize(fill, (self.W, self.H), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
        h = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 3)[..., None]
        return self.img * (1 - h) + fill * h

    # ---------------------------------------------------------------- geometry helpers (working pixels)
    def box(self, b, pad=0):
        k = self.k
        x0, y0, x1, y1 = [int(round(v * k)) for v in b]
        p = int(round(pad * k))
        return max(0, x0 - p), max(0, y0 - p), min(self.W, x1 + p), min(self.H, y1 + p)

    def grid(self, roi):
        x0, y0, x1, y1 = roi
        YY, XX = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        return XX, YY

    def soft(self, b, feather, roi):
        XX, YY = self.grid(roi)
        k = self.k
        x0, y0, x1, y1 = [v * k for v in b]
        f = max(1.0, feather * k)
        dx = np.maximum(np.maximum(x0 - XX, XX - x1), 0)
        dy = np.maximum(np.maximum(y0 - YY, YY - y1), 0)
        return np.clip(1 - np.hypot(dx, dy) / f, 0, 1) ** 2

    def _prep(self):
        m, k = self.meta, self.k
        self.flags = []
        hsv = None
        for f in m.get("flags", []):
            roi = self.box(f["box"], 14)
            if not ok(roi):
                continue
            if hsv is None:
                hsv = cv2.cvtColor((self.img * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
            sub = hsv[roi[1]:roi[3], roi[0]:roi[2]].astype(np.float32)
            cloth = cv2.GaussianBlur(((sub[..., 1] > 90) | (sub[..., 2] > 225)).astype(np.float32), (0, 0), 2.0)
            XX, _ = self.grid(roi)
            pole = f["pole_x"] * k
            length = max(1.0, f["box"][2] * k - pole)
            mask = self.soft(f["box"], 6, roi) * np.maximum(cloth, 0.25) * np.clip((XX - pole) / length, 0, 1)
            self.flags.append((roi, mask, pole, f))
        self.bobs = [(r, b) for b in m.get("bob", []) for r in [self.box(b["box"], b.get("feather", 30))] if ok(r)]
        self.smokes = []
        for i, s in enumerate(m.get("smoke", [])):
            roi = self.box(s["box"], s.get("feather", 45))
            if not ok(roi):
                continue
            self.smokes.append((roi, self.soft(s["box"], s.get("feather", 45), roi) * self._bgmask(roi), s))
        if self.smokes:
            n = max(8, int(self.W / 4))
            hN = max(8, int(self.H / 4))
            self.n1 = cv2.resize(tileable_noise(hN, n, 26 * k / 4, 3), (self.W, self.H), interpolation=cv2.INTER_CUBIC)
            self.n2 = cv2.resize(tileable_noise(hN, n, 11 * k / 4, 7), (self.W, self.H), interpolation=cv2.INTER_CUBIC)
        self.eyes = []
        for e in m.get("eyes", []):
            up = np.array(e["upper"], np.float32) * k
            lo = np.array(e["lower"], np.float32) * k
            pts = np.vstack([up, lo])
            x0, y0 = np.floor(pts.min(0)).astype(int) - 4
            x1, y1 = np.ceil(pts.max(0)).astype(int) + 5
            roi = (max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1))
            sk = self.box(e["skin"])
            if not ok(roi) or not ok(sk, 1) or x0 < 0 or y0 < 0 or x1 > self.W or y1 > self.H:
                continue                                              # eye (partly) outside this plate
            mm = np.zeros((roi[3] - roi[1], roi[2] - roi[0]), np.uint8)
            cv2.fillPoly(mm, [np.round((pts - [roi[0], roi[1]]) * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
            eye = cv2.GaussianBlur(mm.astype(np.float32) / 255, (0, 0), 0.7 * max(1.0, k))
            sx0, sy0, sx1, sy1 = self.box(e["skin"])
            skin = self.img[sy0:sy1, sx0:sx1].reshape(-1, 3).mean(0)
            self.eyes.append((roi, eye, float(up[:, 1].min()), e.get("close_y", lo[:, 1].max() / k) * k, skin))
        self.winds = [(r, w) for w in m.get("wind", []) for r in [self.box(w["box"], w.get("feather", 20))] if ok(r)]
        self.sways = [(r, w) for w in m.get("sway", []) for r in [self.box(w["box"], w.get("feather", 20))] if ok(r)]

    def _bgmask(self, roi):
        if self.alpha is None:
            return 1.0
        return 1 - self.alpha[roi[1]:roi[3], roi[0]:roi[2]]

    # ---------------------------------------------------------------- per-frame layers
    @staticmethod
    def _warp(img, roi, dx, dy, XX, YY):
        x0, y0, x1, y1 = roi
        img[y0:y1, x0:x1] = cv2.remap(img, XX - dx, YY - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def background(self, tl, t, gains=None, puffs=()):
        g = dict(dict(flags=1.0, bob=1.0, smoke=1.0), **(gains or {}))
        m, k = self.meta, self.k
        bg = self.bg.copy()
        sky = m.get("sky")
        if sky and (sky["y"] + 80) * k > 2:
            y1 = min(self.H, int((sky["y"] + 80) * k))
            roi = (0, 0, self.W, y1)
            XX, YY = self.grid(roi)
            wsky = np.clip((sky["y"] * k - YY) / (80 * k), 0, 1) * (1.2 - YY / (sky["y"] * k + 40 * k))
            self._warp(bg, roi, sky.get("drift", 3.0) * k * t / 5.0 * wsky, 0 * XX, XX, YY)
        for c in m.get("smoke_column", []):
            cx, cy, sx, sy = c["x"] * k, c["y"] * k, c["sx"] * k, c["sy"] * k
            roi = (max(0, int(cx - 2 * sx)), max(0, int(cy - 2 * sy)), min(self.W, int(cx + 2 * sx)), min(self.H, int(cy + 2 * sy)))
            if not ok(roi):
                continue
            XX, YY = self.grid(roi)
            w = np.exp(-(((XX - cx) / sx) ** 2 + ((YY - cy) / sy) ** 2))
            ph = 2 * math.pi * t
            self._warp(bg, roi, w * 2.0 * k * np.sin(YY / (11 * k) + ph * 0.6),
                       w * k * (1.5 * np.sin(XX / (14 * k) + ph * 0.45) - 1.2 * t / 5.0), XX, YY)
        for roi, mask, pole, f in self.flags:
            XX, YY = self.grid(roi)
            amp = f.get("amp", 3.0) * k * g["flags"]
            ph = 2 * math.pi * ((XX - pole) / (f.get("k", 60) * k) - f.get("freq", 1.3) * t)
            self._warp(bg, roi, 0.35 * amp * mask * np.cos(ph), amp * mask * np.sin(ph), XX, YY)
        for roi, b in self.bobs:
            XX, YY = self.grid(roi)
            w = self.soft(b["box"], b.get("feather", 30), roi) * self._bgmask(roi)
            step = np.sin(2 * math.pi * b.get("rate", 1.8) * t + XX / (36 * k) * 2.3 + 0.7 * np.sin(XX / (13 * k)))
            self._warp(bg, roi, 0 * XX, b.get("amp", 1.3) * k * g["bob"] * w * step, XX, YY)
        for roi, w, s in self.smokes:
            x0, y0, x1, y1 = roi
            XX, YY = self.grid(roi)
            sp = s.get("speed", 14) * k
            sm = 0.6 * cv2.remap(self.n1, XX - sp * t, YY + 0.15 * sp * t, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP) + \
                0.4 * cv2.remap(self.n2, XX - 1.8 * sp * t, YY + 0.25 * sp * t, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            gv = g.get(s.get("gain_key", "smoke"), s.get("default_gain", 1.0))
            if gv <= 0:
                continue
            d = s.get("density", 1.0) * gv
            th = 0.52 - 0.05 * (d - 1)
            a = (np.clip((sm - th) / 0.06, 0, 1) * 0.30 + np.clip((sm - th - 0.1) / 0.05, 0, 1) * 0.22) * (1 + 0.15 * (d - 1)) * w
            col = np.array(s.get("color", [0.87, 0.78, 0.71]), np.float32)
            bg[y0:y1, x0:x1] = bg[y0:y1, x0:x1] * (1 - a[..., None]) + col * a[..., None]
        for (tc, px, py) in puffs:
            self._puff(bg, px * k, py * k, tl - tc)
        sun = m.get("sun")
        roi = None
        if sun:
            r = sun.get("r", 160) * k
            roi = self.box([sun["x"] - 2 * sun.get("r", 160), sun["y"] - 2 * sun.get("r", 160), sun["x"] + 2 * sun.get("r", 160),
                            sun["y"] + 2 * sun.get("r", 160)])
        if sun and ok(roi):
            XX, YY = self.grid(roi)
            gl = np.exp(-(((XX - sun["x"] * k) / r) ** 2 + ((YY - sun["y"] * k) / (0.9 * r)) ** 2)) * 0.05 * (0.5 + 0.5 * math.sin(0.8 * t))
            bg[roi[1]:roi[3], roi[0]:roi[2]] += gl[..., None] * np.array([1.0, 0.75, 0.45], np.float32)
        return np.clip(bg, 0, 1)

    _BLOBS = [(0, 0, 1.0), (0.85, 0.2, 0.78), (-0.8, 0.25, 0.72), (0.35, -0.6, 0.74), (-0.38, -0.5, 0.62), (1.45, 0.45, 0.52),
              (-1.4, 0.5, 0.5), (0.0, 0.55, 0.7)]

    def _puff(self, bg, cx, cy, dt):
        """Cannon: muzzle flash, then a cluster of round billows (lit top, shaded underside) that grows, rises, fades."""
        if dt < 0 or dt > 3.4:
            return
        k = self.k
        r = (3 + 19 * min(1.0, dt / 1.1) ** 0.5) * k
        px, py = cx + 8 * k * dt, cy - 7 * k * dt
        R = r * 2.6 + 24 * k
        roi = (max(0, int(px - R)), max(0, int(py - R)), min(self.W, int(px + R)), min(self.H, int(py + R)))
        if roi[2] <= roi[0] or roi[3] <= roi[1]:
            return
        X, Y = self.grid(roi)
        m = np.zeros_like(X)
        for bx, by, rr in self._BLOBS:
            rb = rr * r * (0.85 + 0.15 * math.sin(2.1 * dt + 3 * bx))
            m = np.maximum(m, np.clip((rb - np.hypot(X - px - bx * r, Y - py - by * r)) / (1.3 * k), 0, 1))
        lit = np.clip(0.55 - (Y - py) / (1.7 * r) + 0.25 * (X - px) / r, 0, 1)[..., None]
        col = np.array([0.70, 0.62, 0.62], np.float32) * (1 - lit) + np.array([0.97, 0.89, 0.79], np.float32) * lit
        a = (m * 0.88 * (1 - np.clip((dt - 1.5) / 1.9, 0, 1)) * self._bgmask(roi))[..., None]
        sl = (slice(roi[1], roi[3]), slice(roi[0], roi[2]))
        bg[sl] = bg[sl] * (1 - a) + col * a
        g = np.exp(-(((X - cx) / (12 * k)) ** 2 + ((Y - cy) / (8 * k)) ** 2)) * math.exp(-dt / 0.07) * 0.8
        bg[sl] += g[..., None] * np.array([1.0, 0.78, 0.42], np.float32)

    def foreground(self, tl, t, blinks=(), blink_dur=0.30):
        """RGBA foreground (or None for single-layer plates): wind ripples and painted blinks."""
        if self.alpha is None:
            fg = self.img.copy()
        else:
            fg = np.dstack([self.img, self.alpha])
        self.apply_fg(fg, tl, t, blinks, blink_dur)
        return fg

    def apply_fg(self, fg, tl, t, blinks=(), blink_dur=0.30):
        k = self.k
        wind = 0.6 + 0.4 * math.sin(2 * math.pi * 0.23 * t)
        for roi, w in self.winds:
            XX, YY = self.grid(roi)
            mask = self.soft(w["box"], w.get("feather", 20), roi)
            r = w.get("rate", 0.6)
            amp = w.get("amp", 2.0) * k * wind
            self._warp(fg, roi, amp * mask * np.sin(2 * math.pi * r * t + YY / (55 * k)),
                       0.4 * amp * mask * np.sin(2 * math.pi * r * t + YY / (70 * k) + 1), XX, YY)
        for roi, w in self.sways:                                 # subtle hand / forearm motion around a pivot
            XX, YY = self.grid(roi)
            mask = self.soft(w["box"], w.get("feather", 20), roi)
            px, py = w["pivot"][0] * k, w["pivot"][1] * k
            on = 1.0 if "at" not in w else min(1.0, max(0.0, (tl - w["at"]) / 0.6))
            ang = math.radians(w.get("angle", 1.5)) * math.sin(2 * math.pi * w.get("rate", 0.35) * t + w.get("phase", 0.0)) * on
            ca, sa = math.cos(ang), math.sin(ang)
            dx = ((XX - px) * ca - (YY - py) * sa + px - XX) * mask
            dy = ((XX - px) * sa + (YY - py) * ca + py - YY) * mask
            self._warp(fg, roi, dx, dy, XX, YY)
        b = max([blink_amount((tl - tb) / blink_dur) for tb in blinks] + [0.0])
        if b > 0:
            for roi, eye, top, close_y, skin in self.eyes:
                x0, y0, x1, y1 = roi
                _, YY = self.grid(roi)
                edge = top + (close_y - top) * b
                lid = eye * (YY <= edge)
                sub = fg[y0:y1, x0:x1, :3]
                sub[:] = sub * (1 - lid[..., None]) + skin * lid[..., None]
                lash = np.exp(-((YY - edge) / (1.1 * max(1.0, k))) ** 2) * (eye > 0.05) * b
                sub[:] = sub * (1 - lash[..., None]) + np.array([0.06, 0.04, 0.05], np.float32) * lash[..., None]

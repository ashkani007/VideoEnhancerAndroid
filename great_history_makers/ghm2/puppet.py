"""Limited character animation on a single illustration layer (no rig, no redraw).

- blink:   an eyelid painted over an eye box in sampled skin colour, with a lash line
- turn:    soft-region rotation about a pivot (head turn/tilt, nod) as a smooth displacement field
- gesture: the same warp on a hand/forearm region about an elbow or shoulder pivot
- breathe: a tiny vertical swell of the torso region

All coordinates are plate pixels. Warps are tiny (a few degrees / pixels) and use an inverse
displacement field with cv2.remap, so there is no ghosting or tearing at the region edge."""
import math

import cv2
import numpy as np

from .anim import keys


def _soft_ellipse(shape, cx, cy, rx, ry, feather=0.35):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    u = np.clip((1 + feather - d) / (2 * feather), 0, 1)
    return u * u * (3 - 2 * u)


def blink_amount(t, times, dur=0.16):
    """0 open .. 1 closed; fast close, short hold, slightly slower open."""
    for t0 in times:
        u = (t - t0) / dur
        if 0 <= u <= 1:
            return min(1.0, u / 0.35) if u < 0.35 else (1.0 if u < 0.5 else max(0.0, 1 - (u - 0.5) / 0.5))
    return 0.0


def paint_blink(img, eye, c):
    """img: premultiplied RGBA float plate (modified in place inside the eye ROI)."""
    if c <= 0.02:
        return
    x, y, w, h = eye
    pad = int(max(w, h))
    x0, y0 = max(0, int(x - pad)), max(0, int(y - pad))
    x1, y1 = min(img.shape[1], int(x + w + pad)), min(img.shape[0], int(y + h + pad * 1.6))
    roi = img[y0:y1, x0:x1]
    a = np.clip(roi[..., 3:4], 1e-4, 1)
    rgb = roi[..., :3] / a
    # skin = median of opaque pixels in a band just below the eye (cheek)
    band = rgb[int(y + h + 2 - y0):int(y + h + 2 + h - y0), int(x - x0):int(x + w - x0)].reshape(-1, 3)
    skin = np.median(band, axis=0) if len(band) else np.array([0.8, 0.6, 0.5])
    S = 4
    hh, ww = roi.shape[:2]
    m = np.zeros((hh * S, ww * S), np.uint8)
    cx, cy = (x + w / 2 - x0) * S, (y + h / 2 - y0) * S
    ax, ay = w / 2 * S * 1.15, h / 2 * S * 1.25
    cv2.ellipse(m, (int(cx), int(cy)), (int(ax), int(ay)), 0, 0, 360, 255, -1)
    cut = int(cy - ay + 2 * ay * c)
    m[cut:] = 0
    lid = cv2.resize(m, (ww, hh), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255.0
    line = np.zeros((hh * S, ww * S), np.uint8)
    yl = min(cut, int(cy + ay))
    half = ax * math.sqrt(max(0.0, 1 - ((yl - cy) / ay) ** 2)) if ay else 0
    cv2.line(line, (int(cx - half), yl), (int(cx + half), yl), 255, max(2, int(0.18 * h * S)), cv2.LINE_AA)
    lash = cv2.resize(line, (ww, hh), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255.0 * min(1, c * 1.5)
    shade = skin * 0.92
    rgb[:] = rgb * (1 - lid) + shade * lid
    rgb[:] = rgb * (1 - lash) + np.array([0.12, 0.08, 0.07]) * lash
    roi[..., :3] = rgb * a


class Warp:
    """Soft-region rotation/translation about a pivot, evaluated in a bounding ROI.
    deg > 0 turns the region clockwise on screen."""

    def __init__(self, shape, center, radius, pivot, feather=0.45):
        self.cx, self.cy = center
        self.rx, self.ry = radius
        self.px, self.py = pivot
        pad = 1 + feather
        self.x0 = max(0, int(min(self.cx - self.rx * pad, self.px) - 8))
        self.y0 = max(0, int(min(self.cy - self.ry * pad, self.py) - 8))
        self.x1 = min(shape[1], int(max(self.cx + self.rx * pad, self.px) + 8))
        self.y1 = min(shape[0], int(max(self.cy + self.ry * pad, self.py) + 8))
        h, w = self.y1 - self.y0, self.x1 - self.x0
        self.m = _soft_ellipse((h, w), self.cx - self.x0, self.cy - self.y0, self.rx, self.ry, feather)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx, self.yy = xx, yy

    def apply(self, img, deg=0.0, dx=0.0, dy=0.0):
        if abs(deg) < 0.02 and abs(dx) < 0.05 and abs(dy) < 0.05:
            return
        roi = img[self.y0:self.y1, self.x0:self.x1]
        r = math.radians(-deg)                      # inverse map: sample where the point came from
        px, py = self.px - self.x0, self.py - self.y0
        X, Y = self.xx - px - dx * self.m, self.yy - py - dy * self.m
        c, s = math.cos(r), math.sin(r)
        sx = px + (c * X - s * Y)
        sy = py + (s * X + c * Y)
        mapx = self.xx + (sx - self.xx) * self.m
        mapy = self.yy + (sy - self.yy) * self.m
        img[self.y0:self.y1, self.x0:self.x1] = cv2.remap(roi, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


class Puppet:
    """Applies a list of rig specs to a layer plate for time t (returns a modified copy)."""

    def __init__(self, plate, rigs):
        self.plate, self.rigs = plate, rigs
        self.warps = {}
        for i, r in enumerate(rigs):
            if r["type"] in ("turn", "gesture", "breathe"):
                self.warps[i] = Warp(plate.shape[:2], r["center"], r["radius"], r.get("pivot", r["center"]),
                                     r.get("feather", 0.45))

    def at(self, t):
        img = self.plate.copy()
        for i, r in enumerate(self.rigs):          # blinks first, so a turning head carries its eyelids
            if r["type"] == "blink":
                paint_blink(img, r["eye"], blink_amount(t, r["times"], r.get("dur", 0.16)))
        for i, r in enumerate(self.rigs):
            if r["type"] in ("turn", "gesture"):
                self.warps[i].apply(img, keys(r.get("deg"), t), keys(r.get("dx"), t), keys(r.get("dy"), t))
            elif r["type"] == "breathe":
                self.warps[i].apply(img, 0.0, 0.0, -r.get("amp", 1.5) * (0.5 - 0.5 * math.cos(2 * math.pi * t / r.get("period", 3.6))))
        return img

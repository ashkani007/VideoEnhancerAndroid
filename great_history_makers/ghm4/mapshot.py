"""Animated historical map shot, driven by a JSON file (approved look from Napoleon_20s_POC).

Map JSON (lon/lat degrees; times are shot-local seconds; label offsets in 720x1280 design units):
{
  "bounds": [lon0, lon1, lat0, lat1], "ref_lat": 48, "ppu": 220,
  "coast": "ghm2/data/europe_simplified.json",
  "rivers": [[[lon, lat], ...], ...], "relief": [[[lon, lat], ...], ...],
  "region_labels": [["FRENCH EMPIRE", lon, lat, size, "land"|"sea"|"river"], ...],
  "places": {"ULM": [9.99, 48.40], ...},
  "routes": [{"color": "blue", "points": [[lon, lat], ...], "legs": [[t0, t1, point_index], ...]},     leg ends at that point
             {"color": "red", "points": [...], "draw": [t0, t1], "width": 30, "head": 80, "hide": [t0, t1]}],
  "dots": [["ULM", t], ["OLMÜTZ", t, 14]], "rings": [["ULM", t0, t1, "red"]], "stars": [["AUSTERLITZ", t]],
  "labels": [{"place": "ULM", "text": "ULM · 20 OCT", "dx": 0, "dy": -84, "at": 1.95, "preset": "map_label", "align": "c",
              "out": [t0, t1]}],                                      ("out" optional: fade the label away)
  "regions": [{"source": "ghm2/data/napoleonic_regions.json", "key": "french_empire_1811", "color": "blue",
               "alpha": 0.42, "hatch": false, "origin": [lon, lat], "reveal": [t0, t1]}],    territory spreading from origin
  "element_scale": 1.0,                                  line/dot/label size multiplier for wide views
  "smooth_rivers": true,                                 spline the river polylines (close-up regional maps)
  "units": [{"label": "SOULT", "side": "fr", "path": [[lon, lat], ...], "times": [t, ...], "appear": t, "leave": t}],
                                                         moving army positions (unit blocks with a trail)
  "camera": [[t, lon, lat, width_in_units], ...],      width in degrees of longitude x cos(ref_lat), measured along the
                                                         frame's SHORT side (vertical: width; 16:9: height)
  Visual style: LOCKED (ghm4/map_style.py). New visual features need "style_override_approved".
  "safe_labels": true,                                   labels never leave the frame or enter the title zone (fade),
                                                         region labels follow the camera and fade out instead of being cut
  "kicker": [text, t], "dates": [[t, text], ...], "legend": [[text, color, t], ...], "fade_out": [t0, t1]
}
"""
import functools
import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import map_style
from . import text as T
from .plate import tileable_noise

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DARK = (28, 26, 34)
LABEL_COL = {"land": (110, 78, 50), "sea": (150, 175, 185), "river": (60, 95, 118)}


def backout(u):
    u = min(1.0, max(0.0, u))
    return 1 + 2.2 * (u - 1) ** 3 + 1.2 * (u - 1) ** 2


def ramp(t, t0, t1):
    return T.ease((t - t0) / (t1 - t0))


def catmull(pts, n=28):
    P = np.array(pts, np.float64)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out, idx = [], [0]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
        idx.append(len(out))
    out.append(P[-2])
    path = np.array(out)
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(path, axis=0).T))])
    return path, cum, [cum[min(i, len(cum) - 1)] for i in idx]


def partial(path, cum, L):
    k = int(np.searchsorted(cum, L))
    if k >= len(cum):
        return path
    f = (L - cum[k - 1]) / max(1e-9, cum[k] - cum[k - 1])
    return np.vstack([path[:k], path[k - 1] + (path[k] - path[k - 1]) * f])


def hermite(keys, t):
    Ts = [k[0] for k in keys]
    P = [np.array(k[1:], np.float64) for k in keys]
    if t <= Ts[0]:
        return P[0]
    if t >= Ts[-1]:
        return P[-1]
    i = max(j for j in range(len(Ts) - 1) if Ts[j] <= t)

    def tan(j):
        if j == 0:
            return P[0] * 0
        if j == len(Ts) - 1:
            return (P[j] - P[j - 1]) / (Ts[j] - Ts[j - 1])
        return (P[j + 1] - P[j - 1]) / (Ts[j + 1] - Ts[j - 1])
    h = Ts[i + 1] - Ts[i]
    s = (t - Ts[i]) / h
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * P[i] + h10 * h * tan(i) + h01 * P[i + 1] + h11 * h * tan(i + 1)


class MapShot:
    def __init__(self, path, OW, OH):
        self.cfg = json.load(open(path, encoding="utf-8"))
        c = self.cfg
        map_style.check(c, os.path.basename(path))                     # the approved map look is locked
        self.L = LAYOUT["landscape" if OW > OH else "portrait"]
        self.OW, self.OH, self.U = OW, OH, OW / float(self.L["dw"])
        self.lon0, self.lon1, self.lat0, self.lat1 = c["bounds"]
        self.kx = math.cos(math.radians(c.get("ref_lat", 48)))
        self.ppu = c.get("ppu", 220) * max(1.0, 0.85 * min(OW, OH) / 720)
        self.q = self.ppu / 220.0 * c.get("element_scale", 1.0)      # canvas sizes were authored at ppu 220
        self.CW = int((self.lon1 - self.lon0) * self.kx * self.ppu)
        self.CH = int((self.lat1 - self.lat0) * self.ppu)
        self.routes = []
        for r in c.get("routes", []):
            path, cum, wl = catmull([self.cpx(*p) for p in r["points"]])
            self.routes.append((r, path, cum, wl))
        self.base = None
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        self.XO, self.YO = xx, yy

    def cpx(self, lon, lat):
        return (lon - self.lon0) * self.kx * self.ppu, (self.lat1 - lat) * self.ppu

    def place(self, name):
        return self.cfg["places"][name]

    def build(self):
        c, q = self.cfg, self.q
        CW, CH = self.CW, self.CH
        land = np.zeros((CH, CW), np.uint8)
        polys = json.load(open(os.path.join(GHM, c.get("coast", "ghm2/data/europe_simplified.json"))))["polygons"]
        cp = [np.array([self.cpx(lo, la) for lo, la in p], np.float64) for p in polys]
        for p in cp:
            cv2.fillPoly(land, [np.round(p * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
        lf = land.astype(np.float32) / 255
        tex = cv2.resize(tileable_noise(400, 520, 6, 11), (CW, CH), interpolation=cv2.INTER_CUBIC)
        fine = cv2.resize(tileable_noise(700, 900, 1.2, 12), (CW, CH), interpolation=cv2.INTER_LINEAR)
        yy = np.linspace(0, 1, CH, dtype=np.float32)[:, None, None]
        sea = np.array([0.09, 0.15, 0.22], np.float32) * (1 - yy) + np.array([0.13, 0.22, 0.29], np.float32) * yy
        sea = sea * (0.94 + 0.10 * tex[..., None])
        dist = cv2.distanceTransform(255 - (land > 127).astype(np.uint8) * 255, cv2.DIST_L2, 5)
        rip = sum(np.exp(-((dist - k * 22 * q) / (1.6 * q)) ** 2) * (0.28 - 0.07 * k) for k in (1, 2, 3))
        sea = sea + rip[..., None] * np.array([0.35, 0.40, 0.42], np.float32)
        landc = np.array([0.86, 0.75, 0.56], np.float32) * (0.90 + 0.14 * tex[..., None])
        rim = lf * (1 - cv2.GaussianBlur(lf, (0, 0), 16 * q))
        landc = landc * (1 - 0.45 * rim[..., None])
        img = sea * (1 - lf[..., None]) + landc * lf[..., None]
        img *= (0.95 + 0.07 * fine[..., None])
        del sea, landc, dist, rip, tex, fine
        base = np.clip(img * 255, 0, 255).astype(np.uint8)
        del img
        for lon in range(int(math.ceil(self.lon0 / 4) * 4), int(self.lon1) + 1, 4):        # faint graticule
            x = int(self.cpx(lon, 50)[0])
            base[:, max(0, x - 1):x + 1] = (base[:, max(0, x - 1):x + 1] * 0.86 + 255 * 0.14).astype(np.uint8)
        for lat in range(int(math.ceil(self.lat0 / 4) * 4), int(self.lat1), 4):
            y = int(self.cpx(0, lat)[1])
            base[max(0, y - 1):y + 1] = (base[max(0, y - 1):y + 1] * 0.86 + 255 * 0.14).astype(np.uint8)
        for p in cp:
            cv2.polylines(base, [np.round(p * 4).astype(np.int32)], True, (78, 54, 34), max(2, int(3 * q)), cv2.LINE_AA, shift=2)
        rng = np.random.default_rng(4)
        for ridge in c.get("relief", []):                            # chevron hatching along mountain ranges
            pts = np.array([self.cpx(*p) for p in ridge])
            seg = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
            for dd in np.arange(0, seg[-1], 46 * q):
                x, y = np.array([np.interp(dd, seg, pts[:, 0]), np.interp(dd, seg, pts[:, 1])]) + rng.normal(0, 16 * q, 2)
                sz = rng.uniform(17, 27) * q
                ch = np.round(np.array([(x - sz, y + sz * 0.55), (x, y - sz * 0.6), (x + sz, y + sz * 0.55)]) * 4).astype(np.int32)
                cv2.polylines(base, [ch], False, (116, 86, 56), max(2, int(4 * q)), cv2.LINE_AA, shift=2)
        for river in c.get("rivers", []):
            pr = [self.cpx(*p) for p in river]
            if c.get("smooth_rivers") and len(pr) > 2:                   # spline through the river points
                pr = catmull(pr, 10)[0]
            pts = np.round(np.array(pr) * 4).astype(np.int32)
            cv2.polylines(base, [pts], False, (70, 112, 136), max(3, int(5 * q)), cv2.LINE_AA, shift=2)
        pil = Image.fromarray(base)
        d = ImageDraw.Draw(pil)
        for name, lon, lat, size, kind in ([] if c.get("safe_labels") else c.get("region_labels", [])):
            f = T.font("Italic", int(size * q))
            x, y = self.cpx(lon, lat)
            tr = size * q * 0.35
            w = sum(f.getlength(ch) for ch in name) + tr * (len(name) - 1)
            xc = x - w / 2
            for ch in name:
                d.text((xc, y), ch, font=f, fill=LABEL_COL[kind], anchor="ls")
                xc += f.getlength(ch) + tr
        self.base = np.asarray(pil).copy()
        self.regions = []
        for r in c.get("regions", []):
            polys = json.load(open(os.path.join(GHM, r["source"])))[r["key"]]
            m = np.zeros((CH, CW), np.uint8)
            pts = [np.round(np.array([self.cpx(lo, la) for lo, la in p]) * 4).astype(np.int32) for p in polys]
            cv2.fillPoly(m, pts, 255, cv2.LINE_AA, shift=2)
            m = np.minimum(m, land)                                     # territory never spills into the sea
            a = m.astype(np.float32) * (r.get("alpha", 0.42) / 255)
            if r.get("hatch"):                                          # diagonal hatching, precomputed once
                period = max(4, int(14 * self.q))
                tile = ((np.add.outer(np.arange(2 * period), np.arange(2 * period)) // period) % 2).astype(np.float32)
                a *= np.tile(tile, (CH // (2 * period) + 1, CW // (2 * period) + 1))[:CH, :CW]
            m = a                                                       # static per-pixel opacity (float32)
            ys, xs = np.nonzero(m[::8, ::8])
            ext = (xs.min() * 8, ys.min() * 8, xs.max() * 8 + 8, ys.max() * 8 + 8) if len(xs) else None
            self.regions.append((m, pts, r, ext))

    # ---------------------------------------------------------------- dynamic elements (canvas pixels in a ROI)
    def arrow(self, roi, off, path, cum, L, col, t, Tw=34, head=88):
        q = self.q
        Tw, head = int(Tw * q), head * q
        if L <= 4 * q:
            return
        body = partial(path, cum, max(1.0, L - head * 0.6))
        tip = partial(path, cum, L)
        p_end, p_prev = tip[-1], tip[max(0, len(tip) - 6)]
        dv = p_end - p_prev
        dv = dv / (np.hypot(*dv) + 1e-9)
        nrm = np.array([-dv[1], dv[0]])
        bc = p_end - dv * head
        tri = np.array([p_end + dv * 6 * q, bc + nrm * head * 0.55, bc - nrm * head * 0.55])
        Q = lambda a: np.round((a - off) * 4).astype(np.int32)       # noqa: E731
        sh = np.array([7.0, 9.0]) * q
        allp = np.vstack([body, tri]) - off + sh
        bx0, by0 = np.maximum(0, allp.min(0).astype(int) - Tw * 2)
        bx1, by1 = allp.max(0).astype(int) + Tw * 2
        bx1, by1 = min(roi.shape[1], bx1), min(roi.shape[0], by1)
        if bx1 > bx0 and by1 > by0:                                  # soft shadow, blended inside the bounding box only
            m = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
            o2 = off - sh + np.array([bx0, by0])
            QQ = lambda a: np.round((a - o2) * 4).astype(np.int32)   # noqa: E731
            cv2.polylines(m, [QQ(body)], False, 255, Tw + int(10 * q), cv2.LINE_AA, shift=2)
            cv2.fillPoly(m, [QQ(tri)], 255, cv2.LINE_AA, shift=2)
            m = cv2.GaussianBlur(m, (0, 0), 6 * q).astype(np.float32)[..., None] * (0.42 / 255)
            sub = roi[by0:by1, bx0:bx1].astype(np.float32)
            roi[by0:by1, bx0:bx1] = (sub * (1 - m)).astype(np.uint8)
        c255 = tuple(int(255 * v) for v in col)
        light = tuple(int(255 * min(1.0, v * 0.45 + 0.6)) for v in col)
        cv2.polylines(roi, [Q(body)], False, DARK, Tw + int(12 * q), cv2.LINE_AA, shift=2)
        cv2.fillPoly(roi, [Q(tri)], DARK, cv2.LINE_AA, shift=2)
        cv2.polylines(roi, [Q(tri)], True, DARK, int(10 * q), cv2.LINE_AA, shift=2)
        cv2.polylines(roi, [Q(body)], False, c255, Tw, cv2.LINE_AA, shift=2)
        cv2.fillPoly(roi, [Q(tri)], c255, cv2.LINE_AA, shift=2)
        per, dash = 110 * q, 42 * q                                  # travelling dashes = marching movement
        s0 = -per + (150 * q * t) % per
        while s0 < L - head * 1.1:
            a, b = max(0.0, s0), min(L - head * 1.1, s0 + dash)
            if b > a + 2:
                seg = partial(path, cum, b)[max(0, int(np.searchsorted(cum, a)) - 1):]
                cv2.polylines(roi, [Q(seg)], False, light, max(3, Tw // 3), cv2.LINE_AA, shift=2)
            s0 += per

    def dot(self, roi, off, lon, lat, pop, r=17):
        if pop <= 0:
            return
        x, y = self.cpx(lon, lat)
        c = (int((x - off[0]) * 4), int((y - off[1]) * 4))
        rr = max(1, int(r * self.q * backout(pop) * 4))
        cv2.circle(roi, c, rr + int(22 * self.q), DARK, -1, cv2.LINE_AA, shift=2)
        cv2.circle(roi, c, rr, (247, 237, 214), -1, cv2.LINE_AA, shift=2)

    @staticmethod
    def _bbox(roi, cx, cy, r):
        """Integer box (clipped to the ROI) around a circle of radius r at (cx, cy) in ROI pixels."""
        x0, y0 = max(0, int(cx - r)), max(0, int(cy - r))
        x1, y1 = min(roi.shape[1], int(cx + r) + 1), min(roi.shape[0], int(cy + r) + 1)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _circle_fade(self, roi, cx, cy, r, col, th, k):
        """Draw a circle outline blended with weight k, touching only its bounding box."""
        b = self._bbox(roi, cx, cy, r + th)
        if b is None or k <= 0:
            return
        x0, y0, x1, y1 = b
        part = roi[y0:y1, x0:x1]
        sub = part.copy()
        cv2.circle(sub, (int((cx - x0) * 4), int((cy - y0) * 4)), int(r * 4), col, th, cv2.LINE_AA, shift=2)
        part[:] = cv2.addWeighted(sub, k, part, 1 - k, 0)

    def ring(self, roi, off, lon, lat, p, pulse, col):
        q = self.q
        x, y = self.cpx(lon, lat)
        c = (int((x - off[0]) * 4), int((y - off[1]) * 4))
        c255 = tuple(int(255 * v) for v in col)
        R = int(108 * q * 4)
        for a0 in range(-90, int(-90 + 360 * T.easeout(p)), 24):
            cv2.ellipse(roi, c, (R, R), 0, a0, a0 + 15, c255, int(10 * q), cv2.LINE_AA, shift=2)
        if 0 < pulse < 1:
            self._circle_fade(roi, x - off[0], y - off[1], (110 + 150 * T.easeout(pulse)) * q, c255, int(6 * q), 1 - pulse)

    def star(self, roi, off, lon, lat, p, t):
        if p <= 0:
            return
        q = self.q
        x, y = self.cpx(lon, lat)
        R = 84 * q * self.cfg.get("star_scale", 1.0) * backout(p)
        ang = np.linspace(0, 2 * np.pi, 17)[:-1] + 0.25 * t
        rad = np.where(np.arange(16) % 2 == 0, R, R * 0.42)
        pts = np.stack([x - off[0] + rad * np.cos(ang), y - off[1] + rad * np.sin(ang)], 1)
        Q = np.round(pts * 4).astype(np.int32)
        cv2.fillPoly(roi, [Q], DARK, cv2.LINE_AA, shift=2)
        cv2.polylines(roi, [Q], True, DARK, int(12 * q), cv2.LINE_AA, shift=2)
        cv2.fillPoly(roi, [Q], (240, 186, 82), cv2.LINE_AA, shift=2)
        for k in range(2):                                                  # shock rings
            u = (p * 1.6 - 0.3 * k) % 1.6
            if 0 < u < 1:
                self._circle_fade(roi, x - off[0], y - off[1], R + 160 * q * T.easeout(u), (240, 196, 110), int(7 * q), 1 - u)

    def region(self, roi, off, m, pts, r, tl, bbox):
        p = ramp(tl, *r["reveal"])
        if p <= 0 or bbox is None:
            return
        x0, y0, x1, y1 = bbox                                               # region extent inside this ROI
        part = roi[y0:y1, x0:x1]
        a = m[y0:y1, x0:x1]
        if p < 1:                                                           # soft spreading front, at quarter resolution
            ox, oy = self.cpx(*r["origin"])
            far = max(np.hypot(ox - x, oy - y) for x in (0, self.CW) for y in (0, self.CH))
            h4, w4 = max(1, (y1 - y0) // 4), max(1, (x1 - x0) // 4)
            yy, xx = np.mgrid[0:h4, 0:w4].astype(np.float32)
            d = np.hypot(xx * (x1 - x0) / w4 + x0 + off[0] - ox, yy * (y1 - y0) / h4 + y0 + off[1] - oy)
            front = cv2.resize(np.clip((p * far - d) / (60 * self.q), 0, 1), (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
            a = a * front.astype(np.float32)
        if not a.any():
            return
        col = np.empty_like(part)
        col[:] = [int(255 * v) for v in T.COLORS[r.get("color", "blue")]]
        a = np.ascontiguousarray(a, np.float32)
        part[:] = cv2.blendLinear(np.ascontiguousarray(part), col, 1 - a, a)
        if p > 0.6 and not r.get("hatch"):                                  # border fades in at the end
            sub = part.copy()
            cv2.polylines(sub, [q - np.round((off + [x0, y0]) * 4).astype(np.int32) for q in pts], True, (32, 44, 92),
                          max(2, int(4 * self.q)), cv2.LINE_AA, shift=2)
            k = min(1.0, (p - 0.6) / 0.4)
            part[:] = cv2.addWeighted(sub, k, part, 1 - k, 0)

    def route_length(self, r, cum, wl, tl):
        if "draw" in r:
            return cum[-1] * ramp(tl, *r["draw"])
        L, prev = 0.0, 0
        for t0, t1, idx in r["legs"]:
            if tl >= t0:
                L = wl[prev] + (wl[idx] - wl[prev]) * ramp(tl, t0, t1)
            prev = idx
        return L

    # ---------------------------------------------------------------- moving army positions
    UNIT_COL = {"fr": ((0.20, 0.34, 0.68), (0.95, 0.93, 0.86)), "at": ((0.93, 0.92, 0.88), (0.62, 0.12, 0.12)),
                "ru": ((0.22, 0.40, 0.26), (0.95, 0.93, 0.86)), "pr": ((0.12, 0.12, 0.14), (0.95, 0.93, 0.86)),
                "gb": ((0.74, 0.17, 0.14), (0.95, 0.93, 0.86))}

    def unit_pos(self, u, tl):
        """Position of a unit along its path at shot time tl ([[lon, lat], ...] reached at "times")."""
        P, Ts = u["path"], u.get("times", [u.get("appear", 0.0)])
        if len(P) == 1 or tl <= Ts[0]:
            return P[0]
        for i in range(len(Ts) - 1):
            if tl < Ts[i + 1]:
                k = T.ease((tl - Ts[i]) / max(1e-6, Ts[i + 1] - Ts[i]))
                return [P[i][0] + (P[i + 1][0] - P[i][0]) * k, P[i][1] + (P[i + 1][1] - P[i][1]) * k]
        return P[min(len(P), len(Ts)) - 1]

    def draw_units(self, img, cv, tl, proj_ll, fade):
        """Army corps / armies as unit blocks (NATO-style infantry cross) that march along their paths, with a faint trail
        and a label; "units": [{"label", "side": fr|at|ru|pr|gb, "path", "times", "appear", "leave"}]."""
        units = self.cfg.get("units", [])
        if not units:
            return img
        U = self.U
        OWi, OHi = self.OW, self.OH
        lay = np.zeros((OHi, OWi, 3), np.float32)
        al = np.zeros((OHi, OWi), np.float32)
        for u in units:
            a = T.ease((tl - u.get("appear", 0.0)) / 0.35) * fade
            if "leave" in u:
                a *= 1 - T.ease((tl - u["leave"]) / 0.35)
            if a <= 0.01:
                continue
            body, mark = self.UNIT_COL[u.get("side", "fr")]
            # trail: positions already travelled
            Ts = u.get("times", [u.get("appear", 0.0)])
            pts = [proj_ll(*self.unit_pos(u, t)) for t in np.linspace(Ts[0], min(tl, Ts[-1]), 24)] if tl > Ts[0] else []
            if len(pts) > 1:
                m = np.zeros((OHi, OWi), np.uint8)
                cv2.polylines(m, [np.round(np.array(pts) * 4).astype(np.int32)], False, 255, max(2, int(3 * U)) * 1, cv2.LINE_AA, shift=2)
                t_a = (m.astype(np.float32) / 255) * 0.32 * a
                lay[:] = lay * (1 - t_a[..., None]) + np.array(body, np.float32) * t_a[..., None]
                al[:] = np.maximum(al, t_a)
            x, y = proj_ll(*self.unit_pos(u, tl))
            w, h = u.get("w", 44) * U, u.get("h", 28) * U
            box = np.array([[x - w / 2, y - h / 2], [x + w / 2, y - h / 2], [x + w / 2, y + h / 2], [x - w / 2, y + h / 2]])
            m = np.zeros((OHi, OWi), np.uint8)
            cv2.fillPoly(m, [np.round((box + [3 * U, 4 * U]) * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
            sh = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 3 * U) * 0.55 * a          # drop shadow
            lay[:] = lay * (1 - sh[..., None])
            al[:] = np.maximum(al, sh)
            m = np.zeros((OHi, OWi), np.uint8)
            cv2.fillPoly(m, [np.round(box * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
            fa = (m.astype(np.float32) / 255) * a
            lay[:] = lay * (1 - fa[..., None]) + np.array(body, np.float32) * fa[..., None]
            al[:] = np.maximum(al, fa)
            m = np.zeros((OHi, OWi), np.uint8)                       # frame + infantry cross
            cv2.polylines(m, [np.round(box * 4).astype(np.int32)], True, 255, max(1, int(2.2 * U)), cv2.LINE_AA, shift=2)
            for (p0, p1) in ((box[0], box[2]), (box[1], box[3])):
                cv2.line(m, tuple(np.round(p0 * 4).astype(int)), tuple(np.round(p1 * 4).astype(int)), 255, max(1, int(1.8 * U)),
                         cv2.LINE_AA, shift=2)
            ma = (m.astype(np.float32) / 255) * a
            lay[:] = lay * (1 - ma[..., None]) + np.array(mark, np.float32) * ma[..., None]
            al[:] = np.maximum(al, ma)
            if u.get("label"):
                cv.letters(u["label"], x / U + u.get("dx", 0), y / U + u.get("dy", h / U / 2 + 20), 99, "legend",
                           align="c", alpha=a, size=u.get("size", 17), track=3, shadow=0.9)
        return img * (1 - al[..., None]) + lay                     # lay is premultiplied by its coverage al

    # ---------------------------------------------------------------- frame
    def frame(self, tl):
        if self.base is None:
            self.build()
        c, OW, OH, U = self.cfg, self.OW, self.OH, self.U
        keys = [(k[0], (k[1] - self.lon0) * self.kx, self.lat1 - k[2], math.log(k[3])) for k in c["camera"]]
        cx, cy, lw = hermite(keys, tl)
        Wu = math.exp(lw) * max(1.0, OW / OH)        # camera width = the frame's SHORT side (16:9 keeps the approved scale)
        # never look past the canvas (the border would show as a mirrored strip)
        Wu = min(Wu, self.CW / self.ppu, self.CH / self.ppu * OW / OH)
        hwu, hhu = Wu / 2, Wu / 2 * OH / OW
        cx = min(max(cx, hwu), self.CW / self.ppu - hwu)
        cy = min(max(cy, hhu), self.CH / self.ppu - hhu)
        s = OW / (Wu * self.ppu)
        cxp, cyp = cx * self.ppu, cy * self.ppu
        hw, hh = Wu * self.ppu / 2, Wu * self.ppu / 2 * OH / OW
        x0, y0 = max(0, int(cxp - hw) - 6), max(0, int(cyp - hh) - 6)
        x1, y1 = min(self.CW, int(cxp + hw) + 7), min(self.CH, int(cyp + hh) + 7)
        roi = self.base[y0:y1, x0:x1].copy()
        off = np.array([x0, y0], np.float64)
        for m, pts, r, ext in self.regions:
            bb = None
            if ext:
                bx0, by0 = max(ext[0], x0) - x0, max(ext[1], y0) - y0
                bx1, by1 = min(ext[2], x1) - x0, min(ext[3], y1) - y0
                bb = (bx0, by0, bx1, by1) if bx1 > bx0 and by1 > by0 else None
            self.region(roi, off, m[y0:y1, x0:x1], pts, r, tl, bb)
        for name, t0, t1, col in c.get("rings", []):
            self.ring(roi, off, *self.place(name), ramp(tl, t0, t1), (tl - t0 - 0.25) / 0.8, T.COLORS[col])
        for r, path, cum, wl in reversed(self.routes):                # first route drawn last (on top)
            k = 1 - ramp(tl, *r["hide"]) if r.get("hide") else 1.0        # optional "hide": [t0, t1] fade-out
            if k <= 0.01:
                continue
            tgt = roi if k >= 0.99 else roi.copy()
            self.arrow(tgt, off, path, cum, self.route_length(r, cum, wl, tl), T.COLORS[r["color"]], tl, r.get("width", 34),
                       r.get("head", 88))
            if k < 0.99:
                roi[:] = cv2.addWeighted(tgt, k, roi, 1 - k, 0)
        for d in c.get("dots", []):
            self.dot(roi, off, *self.place(d[0]), (tl - d[1]) / 0.35, d[2] if len(d) > 2 else 17)
        for name, t0 in c.get("stars", []):
            self.star(roi, off, *self.place(name), (tl - t0) / 0.45, tl)
        if s < 0.95:
            small = cv2.resize(roi, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            fx_, fy_ = small.shape[1] / roi.shape[1], small.shape[0] / roi.shape[0]
        else:
            small, fx_, fy_ = roi, 1.0, 1.0
        M = np.float32([[s / fx_, 0, OW / 2 + s * (x0 - cxp)], [0, s / fy_, OH / 2 + s * (y0 - cyp)]])
        img = cv2.warpAffine(small, M, (OW, OH), flags=cv2.INTER_CUBIC if s >= 0.95 else cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT).astype(np.float32) / 255

        def proj_ll(lon, lat):                                        # output pixels
            X, Y = self.cpx(lon, lat)
            return s * (X - cxp) + OW / 2, s * (Y - cyp) + OH / 2

        def proj(name):
            return proj_ll(*self.place(name))
        for name, t0 in c.get("stars", []):
            sp = (tl - t0) / 0.45
            if sp > 0:
                ax, ay = proj(name)
                g = np.exp(-(((self.XO - ax) / (90 * U)) ** 2 + ((self.YO - ay) / (90 * U)) ** 2)) * c.get("glow", 0.35) * min(1.0, sp)
                img += g[..., None] * np.array([1.0, 0.72, 0.35], np.float32)
        L = self.L
        img = T.scrim(img, 0, L["top_scrim"], 0.8, top=True, U=U)
        img = T.scrim(img, L["bot_scrim"][0], L["bot_scrim"][1], 0.45, U=U)
        cv = T.Canvas(OW, OH, L["dw"])
        fo = c.get("fade_out")
        fade = 1 - ramp(tl, *fo) if fo else 1.0
        img = self.draw_units(img, cv, tl, proj_ll, fade)
        safe = c.get("safe_labels", False)
        if safe:                                                      # region labels drawn live, faded near the edges
            for name, lon, lat, size, kind in c.get("region_labels", []):
                X, Y = self.cpx(lon, lat)
                sx, sy = (s * (X - cxp) + OW / 2) / U, (s * (Y - cyp) + OH / 2) / U
                sz = size * self.q * s / U
                if sz < 9:
                    continue
                x0, x1 = self.label_extent(name, sx, "Italic", sz, sz * 0.35, "c")
                a = self.safe_alpha(x0, x1, sy) * fade * 0.9 * self.band_alpha(sy) * self.legend_alpha(x0, x1, sy, sz, tl)
                if a > 0.01:
                    cv.letters(name, sx, sy, 99, "map_note", "c", a, tuple(v / 255 for v in LABEL_COL[kind]), sz,
                               track=sz * 0.35, style="Italic", shadow=0.0)
        for lb in c.get("labels", []):
            px, py = proj(lb["place"])
            x, y = px / U + lb.get("dx", 0), py / U + lb.get("dy", 0)
            a = fade * (1 - ramp(tl, *lb["out"]) if lb.get("out") else 1.0)
            if safe:
                st, sz0, tr0, *_ = T.PRESETS[lb.get("preset", "map_label")]
                sz = lb.get("size") or sz0
                x0, x1 = self.label_extent(lb.get("text", lb["place"]), x, st, sz, tr0, lb.get("align", "c"))
                x += max(0.0, L["slide"][0] - x0) - max(0.0, x1 - L["slide"][1])     # slide back inside the frame
                a *= self.safe_alpha(None, None, y) * self.anchor_alpha(px / U)       # ... only while the place is on screen
            if a > 0.01:
                cv.letters(lb.get("text", lb["place"]), x, y, tl - lb["at"],
                           lb.get("preset", "map_label"), lb.get("align", "c"), a, lb.get("color"), lb.get("size"), shadow=0.85)
        if c.get("kicker"):
            cv.letters(c["kicker"][0], L["cx"], L["kicker_y"], tl - c["kicker"][1], "legend", size=22, track=6, stagger=0.015, alpha=fade,
                       col="gold", rise=16, shadow=0.5)
        dates = c.get("dates", [])
        for i, (td, txt) in enumerate(dates):
            tn = dates[i + 1][0] if i + 1 < len(dates) else 1e9
            if td <= tl < tn:                                         # the old date leaves before the new one rises
                a_in, a_out = T.ease((tl - td) / 0.25), T.ease((tl - tn + 0.18) / 0.18)
                a = a_in * (1 - a_out) * fade
                if a > 0.003:
                    cv.letters(txt, L["cx"], L["date_y"] + 26 * (1 - a_in) - 26 * a_out, 99, "ticker", alpha=a, shadow=0.6)
        for k, (txt, col, t0) in enumerate(c.get("legend", [])):
            a = T.ease((tl - t0) / 0.4) * fade
            if a > 0:
                ls = L.get("legend_size", 23)
                yb = L["legend_y"] + ls * 1.65 * k
                cv.rect(L["legend_x"], yb - ls * 0.52, L["legend_x"] + ls * 1.8, yb - ls * 0.09, a, col, 0.5)
                cv.letters(txt, L["legend_x"] + ls * 2.35, yb, 99, "legend", align="l", alpha=a, size=ls, shadow=0.6)
        return cv.apply(img)


def _label_extent(text, x, style, size, track, align):
    f = T.font(style, max(8, int(round(size))))
    w = sum(f.getlength(ch) for ch in text) + track * (len(text) - 1)
    x0 = x - w / 2 if align == "c" else (x - w if align == "r" else x)
    return x0, x0 + w


# design-space layout per format (720x1280 vertical Shorts, 1280x720 landscape documentaries)
LAYOUT = {
    "portrait": dict(dw=720, cx=360, kicker_y=176, date_y=240, top_scrim=340, bot_scrim=(900, 1280), title_zone=285,
                     bottom=1250, xl=12, xr=708, slide=(20, 700), band=(840, 1040), legend_x=70, legend_y=968),
    "landscape": dict(dw=1280, cx=640, kicker_y=70, date_y=122, top_scrim=190, bot_scrim=(540, 720), title_zone=150,
                      bottom=705, xl=14, xr=1266, slide=(24, 1256), band=(596, 700), legend_x=56, legend_y=520),
}


def _safe_alpha(self, x0, x1, y):
    """1 inside the safe area, fading to 0 when a label crosses the frame edge or enters the kicker/date zone.
    x0 = None: vertical test only (point labels are slid back inside the frame instead)."""
    L = self.L
    a = 1.0
    if x0 is not None:
        edge = min(x0 - L["xl"], L["xr"] - x1)                        # fully faded before the label reaches the edge
        a = min(1.0, max(0.0, edge / 40.0))
    a *= min(1.0, max(0.0, (y - L["title_zone"]) / 30.0)) * min(1.0, max(0.0, (L["bottom"] - y) / 30.0))
    return a


def _layout(self, tl):
    """Screen boxes (design units) of the labels at shot time tl: [(text, x0, x1, y, size, alpha, kind)], for QC."""
    c, OW, OH, U = self.cfg, self.OW, self.OH, self.U
    keys = [(k[0], (k[1] - self.lon0) * self.kx, self.lat1 - k[2], math.log(k[3])) for k in c["camera"]]
    cx, cy, lw = hermite(keys, tl)
    Wu = min(math.exp(lw) * max(1.0, OW / OH), self.CW / self.ppu, self.CH / self.ppu * OW / OH)
    hwu, hhu = Wu / 2, Wu / 2 * OH / OW
    cx = min(max(cx, hwu), self.CW / self.ppu - hwu)
    cy = min(max(cy, hhu), self.CH / self.ppu - hhu)
    s = OW / (Wu * self.ppu)
    cxp, cyp = cx * self.ppu, cy * self.ppu
    fo = c.get("fade_out")
    fade = 1 - ramp(tl, *fo) if fo else 1.0
    safe = c.get("safe_labels", False)
    out = []
    for name, lon, lat, size, kind in c.get("region_labels", []):
        X, Y = self.cpx(lon, lat)
        sx, sy = (s * (X - cxp) + OW / 2) / U, (s * (Y - cyp) + OH / 2) / U
        sz = size * self.q * s / U
        x0, x1 = _label_extent(name, sx, "Italic", sz, sz * 0.35, "c")
        a = (self.safe_alpha(x0, x1, sy) * self.band_alpha(sy) * self.legend_alpha(x0, x1, sy, sz, tl) if safe else 1.0) * fade
        if sz >= 9 and -50 < sy < OH / U + 50:
            out.append((name, x0, x1, sy, sz, a, "region"))
    for lb in c.get("labels", []):
        if tl < lb["at"] + 0.4 or (lb.get("out") and tl > lb["out"][1]):
            continue
        X, Y = self.cpx(*self.place(lb["place"]))
        x, y = (s * (X - cxp) + OW / 2) / U + lb.get("dx", 0), (s * (Y - cyp) + OH / 2) / U + lb.get("dy", 0)
        st, sz0, tr0, *_ = T.PRESETS[lb.get("preset", "map_label")]
        sz = lb.get("size") or sz0
        x0, x1 = _label_extent(lb.get("text", lb["place"]), x, st, sz, tr0, lb.get("align", "c"))
        a = fade
        if safe:
            sh = max(0.0, self.L["slide"][0] - x0) - max(0.0, x1 - self.L["slide"][1])
            x0, x1 = x0 + sh, x1 + sh
            a *= self.safe_alpha(None, None, y) * self.anchor_alpha(x - lb.get("dx", 0))
        out.append((lb.get("text", lb["place"]), x0, x1, y, sz, a, "label"))
    lb_box = self.legend_box(tl)
    if lb_box is not None:                                        # the legend block counts as a label for overlap checks
        out.append(("legend", lb_box[0], lb_box[2], lb_box[3], lb_box[3] - lb_box[1], fade, "legend"))
    for u in c.get("units", []):                                  # unit labels (they move: QC samples them too)
        if not u.get("label") or tl < u.get("appear", 0.0) + 0.3 or ("leave" in u and tl > u["leave"]):
            continue
        X, Y = self.cpx(*self.unit_pos(u, tl))
        x, y = (s * (X - cxp) + OW / 2) / U + u.get("dx", 0), (s * (Y - cyp) + OH / 2) / U + u.get("dy", u.get("h", 28) / 2 + 20)
        sz = u.get("size", 17)
        x0, x1 = _label_extent(u["label"], x, "Bold", sz, 3, "c")
        out.append((u["label"], x0, x1, y, sz, fade, "label"))
    return out


def _band_alpha(self, y):
    """Decorative region labels step aside for the subtitles."""
    b0, b1 = self.L["band"]
    return 1.0 - min(1.0, max(0.0, min(y - b0, b1 - y) / 20.0))


def _anchor_alpha(self, ax):
    """Point labels fade out when their place leaves the frame (they are never parked at the edge)."""
    return min(1.0, max(0.0, min(ax, self.L["dw"] - ax) / 30.0))


def _legend_box(self, tl):
    """Design-space box of the legend at shot time tl (None before its first entry appears)."""
    lg = [e for e in self.cfg.get("legend", []) if tl >= e[2]]
    if not lg:
        return None
    L, ls = self.L, self.L.get("legend_size", 23)
    w = max(_label_extent(txt, 0, "Bold", ls, 2, "l")[1] for txt, _, _ in lg) + ls * 2.35
    y0 = L["legend_y"] - ls * 1.0
    return (L["legend_x"] - 6, y0, L["legend_x"] + w + 6, L["legend_y"] + ls * 1.65 * (len(lg) - 1) + ls * 0.4)


def _legend_alpha(self, x0, x1, y, sz, tl):
    """Decorative region labels step aside where the legend is (like they do for the subtitles)."""
    b = self.legend_box(tl)
    if b is None or x1 < b[0] or x0 > b[2] or y - sz * 0.8 > b[3] + 6 or y < b[1] - 6:
        return 1.0
    return 0.0


MapShot.legend_box = _legend_box
MapShot.legend_alpha = _legend_alpha
MapShot.anchor_alpha = _anchor_alpha
MapShot.layout = _layout
MapShot.label_extent = staticmethod(_label_extent)
MapShot.safe_alpha = _safe_alpha
MapShot.band_alpha = _band_alpha


@functools.lru_cache(None)
def get(path, OW, OH):
    return MapShot(path, OW, OH)

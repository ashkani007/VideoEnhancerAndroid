"""Animated historical map shot, driven by a JSON file (approved look from Napoleon_20s_POC).

Map JSON (lon/lat degrees; times are shot-local seconds; label offsets in 720x1280 design units):
{
  "bounds": [lon0, lon1, lat0, lat1], "ref_lat": 48, "ppu": 220,
  "coast": "ghm2/data/europe_simplified.json",
  "rivers": [[[lon, lat], ...], ...], "relief": [[[lon, lat], ...], ...],
  "region_labels": [["FRENCH EMPIRE", lon, lat, size, "land"|"sea"|"river"], ...],
  "places": {"ULM": [9.99, 48.40], ...},
  "routes": [{"color": "blue", "points": [[lon, lat], ...], "legs": [[t0, t1, point_index], ...]},     leg ends at that point
             {"color": "red", "points": [...], "draw": [t0, t1], "width": 30, "head": 80}],
  "dots": [["ULM", t], ["OLMÜTZ", t, 14]], "rings": [["ULM", t0, t1, "red"]], "stars": [["AUSTERLITZ", t]],
  "labels": [{"place": "ULM", "text": "ULM · 20 OCT", "dx": 0, "dy": -84, "at": 1.95, "preset": "map_label", "align": "c"}],
  "regions": [{"source": "ghm2/data/napoleonic_regions.json", "key": "french_empire_1811", "color": "blue",
               "alpha": 0.42, "hatch": false, "origin": [lon, lat], "reveal": [t0, t1]}],    territory spreading from origin
  "element_scale": 1.0,                                  line/dot/label size multiplier for wide views
  "camera": [[t, lon, lat, width_in_units], ...],      width in degrees of longitude x cos(ref_lat)
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
        self.OW, self.OH, self.U = OW, OH, OW / 720.0
        self.lon0, self.lon1, self.lat0, self.lat1 = c["bounds"]
        self.kx = math.cos(math.radians(c.get("ref_lat", 48)))
        self.ppu = c.get("ppu", 220) * max(1.0, 0.85 * OW / 720)
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
            pts = np.round(np.array([self.cpx(*p) for p in river]) * 4).astype(np.int32)
            cv2.polylines(base, [pts], False, (70, 112, 136), max(3, int(5 * q)), cv2.LINE_AA, shift=2)
        pil = Image.fromarray(base)
        d = ImageDraw.Draw(pil)
        for name, lon, lat, size, kind in c.get("region_labels", []):
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

    # ---------------------------------------------------------------- frame
    def frame(self, tl):
        if self.base is None:
            self.build()
        c, OW, OH, U = self.cfg, self.OW, self.OH, self.U
        keys = [(k[0], (k[1] - self.lon0) * self.kx, self.lat1 - k[2], math.log(k[3])) for k in c["camera"]]
        cx, cy, lw = hermite(keys, tl)
        Wu = math.exp(lw)
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
            self.arrow(roi, off, path, cum, self.route_length(r, cum, wl, tl), T.COLORS[r["color"]], tl, r.get("width", 34),
                       r.get("head", 88))
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

        def proj(name):                                               # output pixels
            X, Y = self.cpx(*self.place(name))
            return s * (X - cxp) + OW / 2, s * (Y - cyp) + OH / 2
        for name, t0 in c.get("stars", []):
            sp = (tl - t0) / 0.45
            if sp > 0:
                ax, ay = proj(name)
                g = np.exp(-(((self.XO - ax) / (90 * U)) ** 2 + ((self.YO - ay) / (90 * U)) ** 2)) * c.get("glow", 0.35) * min(1.0, sp)
                img += g[..., None] * np.array([1.0, 0.72, 0.35], np.float32)
        img = T.scrim(img, 0, 340, 0.8, top=True, U=U)
        img = T.scrim(img, 900, 1280, 0.45, U=U)
        cv = T.Canvas(OW, OH)
        fo = c.get("fade_out")
        fade = 1 - ramp(tl, *fo) if fo else 1.0
        for lb in c.get("labels", []):
            px, py = proj(lb["place"])
            cv.letters(lb.get("text", lb["place"]), px / U + lb.get("dx", 0), py / U + lb.get("dy", 0), tl - lb["at"],
                       lb.get("preset", "map_label"), lb.get("align", "c"), fade, lb.get("color"), lb.get("size"), shadow=0.85)
        if c.get("kicker"):
            cv.letters(c["kicker"][0], 360, 176, tl - c["kicker"][1], "legend", size=22, track=6, stagger=0.015, alpha=fade,
                       col="gold", rise=16, shadow=0.5)
        dates = c.get("dates", [])
        for i, (td, txt) in enumerate(dates):
            tn = dates[i + 1][0] if i + 1 < len(dates) else 1e9
            if td <= tl < tn:                                         # the old date leaves before the new one rises
                a_in, a_out = T.ease((tl - td) / 0.25), T.ease((tl - tn + 0.18) / 0.18)
                a = a_in * (1 - a_out) * fade
                if a > 0.003:
                    cv.letters(txt, 360, 240 + 26 * (1 - a_in) - 26 * a_out, 99, "ticker", alpha=a, shadow=0.6)
        for k, (txt, col, t0) in enumerate(c.get("legend", [])):
            a = T.ease((tl - t0) / 0.4) * fade
            if a > 0:
                yb = 968 + 38 * k
                cv.rect(70, yb - 12, 112, yb - 2, a, col, 0.5)
                cv.letters(txt, 124, yb, 99, "legend", align="l", alpha=a, shadow=0.6)
        return cv.apply(img)


@functools.lru_cache(None)
def get(path, OW, OH):
    return MapShot(path, OW, OH)

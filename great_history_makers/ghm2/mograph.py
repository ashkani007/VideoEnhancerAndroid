"""Motion graphics: animated typography, historical maps (vector), arrows, markers and timelines.

Everything is drawn crisply at output resolution each frame (cv2 anti-aliased vector drawing,
Pillow text), in the channel palette: imperial blue, gold, parchment, ivory."""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from mosaic.text import _font
from .anim import DW, DH, ease_out, smooth

GOLD = (236, 196, 104)
IVORY = (246, 236, 212)
INK = (34, 24, 18)
BLUE = (38, 70, 150)
PARCH = (222, 200, 156)
SEA = (22, 46, 62)


def _pm(img):
    a = np.asarray(img).astype(np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a


def over(frame, pm, x, y, op=1.0):
    """Composite a premultiplied RGBA image with its top-left at (x, y) output pixels."""
    if op <= 0:
        return
    h, w = pm.shape[:2]
    H, W = frame.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    L = pm[y0 - y:y1 - y, x0 - x:x1 - x]
    frame[y0:y1, x0:x1] *= 1 - L[..., 3:4] * op
    frame[y0:y1, x0:x1] += L[..., :3] * op


def text_image(text, size, kind="title", color=IVORY, tracking=0.0, stroke=0, glow=None):
    font = _font(kind, int(size))
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    widths = [d0.textlength(ch, font=font) for ch in text]
    sp = tracking * size
    w = int(sum(widths) + sp * max(0, len(text) - 1) + size)
    h = int(size * 1.6)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = size / 2
    for ch, cw in zip(text, widths):
        d.text((x, size * 0.2), ch, font=font, fill=tuple(color) + (255,), stroke_width=stroke,
               stroke_fill=(16, 11, 8, 235))
        x += cw + sp
    sh = Image.new("RGBA", img.size, (10, 7, 5, 0))
    sh.putalpha(img.split()[3].filter(ImageFilter.GaussianBlur(size * 0.08)).point(lambda v: int(v * 0.8)))
    out = Image.alpha_composite(sh, img)
    if glow:
        g = Image.new("RGBA", img.size, tuple(glow) + (0,))
        g.putalpha(img.split()[3].filter(ImageFilter.GaussianBlur(size * 0.25)).point(lambda v: int(v * 0.7)))
        out = Image.alpha_composite(g, out)
    return out


class Text:
    """Animated text: anim = wipe (soft left-to-right reveal + rise), stamp (scale settle), fade."""

    def __init__(self, text, start, end, y, size=60, kind="title", color=IVORY, tracking=0.0, anim="wipe",
                 x=DW / 2, stroke=0, glow=None, align="center", fade=0.35):
        self.text, self.start, self.end, self.y, self.x = text, start, end, y, x
        self.size, self.kind, self.color, self.tracking = size, kind, color, tracking
        self.anim, self.stroke, self.glow, self.align, self.fade = anim, stroke, glow, align, fade
        self._cache = {}

    def _img(self, s):
        if s not in self._cache:
            im = text_image(self.text, self.size * s, self.kind, self.color, self.tracking, int(self.stroke * s),
                            self.glow)
            self._cache[s] = (_pm(im), im.size)
        return self._cache[s]

    def __call__(self, frame, t, W, H, cam):
        if not (self.start <= t <= self.end):
            return
        s = W / DW
        pm, (w, h) = self._img(s)
        u = (t - self.start) / 0.7
        op = min(1.0, (self.end - t) / self.fade)
        x = self.x * s - (w / 2 if self.align == "center" else 0)
        y = self.y * s - h / 2
        if self.anim == "stamp":
            k = 1.0 + 0.14 * (1 - ease_out(u))
            img = cv2.resize(pm, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_LINEAR)
            over(frame, img, x - (w * k - w) / 2, y - (h * k - h) / 2, op * smooth(u * 2.5))
            return
        if self.anim == "wipe":
            edge = ease_out(u) * (w + 60 * s) - 30 * s
            ramp = np.clip((edge - np.arange(w)) / (30 * s), 0, 1).astype(np.float32)
            img = pm * ramp[None, :, None]
            over(frame, img, x, y + 18 * s * (1 - ease_out(u)), op)
            return
        over(frame, pm, x, y, op * smooth(u))


# ----------------------------------------------------------------------------------------- maps
def proj(lon, lat, ox=60.0, oy=470.0, k=19.0):
    return ox + (lon + 11) * k, oy + (63 - lat) * k * 1.36


class Map:
    """Animated historical map.

    spec keys: land [[(lon,lat)...]], regions [{poly, color, alpha, start, dur, origin(lon,lat), border}],
    places [{name, lonlat, start}], arrows [{from, to, start, dur, color, bend, label, year}],
    timeline {y, years [y0, y1], start}, camera {from, to} (design units, zoom >= 1)."""

    def __init__(self, spec, camera):
        self.spec, self.cam = spec, camera
        self._bg = {}
        self._labels = {}

    def _xf(self, cam, W):
        s = W / DW
        z, fx, fy = cam["zoom"], cam["x"], cam["y"]
        return lambda x, y: (s * (DW / 2 + z * (x - fx)), s * (DH / 2 + z * (y - fy)))

    def _background(self, W, H):
        if (W, H) not in self._bg:
            r = np.random.default_rng(7)
            yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
            top, bot = np.array([16, 34, 48], np.float32) / 255, np.array([28, 56, 72], np.float32) / 255
            bg = np.broadcast_to(top + (bot - top) * yy, (H, W, 3)).copy()
            n = cv2.GaussianBlur(r.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.2 * W / DW)
            bg += n[..., None] * 0.012
            self._bg[(W, H)] = bg
        return self._bg[(W, H)]

    def _label(self, text, size, color=IVORY, kind="sub", tracking=0.08):
        key = (text, size, color)
        if key not in self._labels:
            self._labels[key] = _pm(text_image(text, size, kind, color, tracking, stroke=max(1, int(size / 16))))
        return self._labels[key]

    def __call__(self, frame, t, W, H, cam_unused=None):
        cam = self.cam.at(t)
        xf = self._xf(cam, W)
        s = W / DW
        z = cam["zoom"]
        frame[:] = self._background(W, H)
        SS = 2
        canvas = np.zeros((H * SS, W * SS, 3), np.uint8)

        def pts(poly):
            return (np.array([xf(*proj(*p)) for p in poly]) * SS).astype(np.int32)
        # graticule
        g = np.zeros((H, W), np.uint8)
        for lon in range(-10, 45, 10):
            cv2.polylines(g, [(np.array([xf(*proj(lon, la)) for la in range(34, 66, 2)])).astype(np.int32)], False, 255, 1,
                          cv2.LINE_AA)
        for lat in range(35, 65, 5):
            cv2.polylines(g, [(np.array([xf(*proj(lo, lat)) for lo in range(-12, 46, 2)])).astype(np.int32)], False, 255, 1,
                          cv2.LINE_AA)
        frame += (g.astype(np.float32) / 255 * 0.05)[..., None] * np.array([0.8, 0.9, 1.0], np.float32)
        land = [pts(p) for p in self.spec["land"]]
        mask = np.zeros((H * SS, W * SS), np.uint8)
        cv2.fillPoly(mask, land, 255, cv2.LINE_AA)
        landm = cv2.resize(mask, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
        shade = cv2.GaussianBlur(landm[..., 0], (0, 0), 10 * s)[..., None]
        frame[:] = frame * (1 - landm) + landm * (np.array(PARCH, np.float32) / 255 * (0.82 + 0.18 * shade))
        glow = cv2.GaussianBlur(landm[..., 0], (0, 0), 14 * s)[..., None] * (1 - landm)
        frame += glow * np.array([0.25, 0.32, 0.36], np.float32) * 0.5          # shallow-water halo
        # regions with radial reveal from an origin
        for rg in self.spec.get("regions", []):
            u = (t - rg["start"]) / rg.get("dur", 1.2)
            if u <= 0:
                continue
            m = np.zeros((H * SS, W * SS), np.uint8)
            cv2.fillPoly(m, [pts(rg["poly"])] if isinstance(rg["poly"][0][0], (int, float)) else [pts(p) for p in rg["poly"]],
                         255, cv2.LINE_AA)
            rm = cv2.resize(m, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            ox, oy = xf(*proj(*rg["origin"]))
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            rad = ease_out(u) * 900 * s * z
            rm *= np.clip((rad - np.hypot(xx - ox, yy - oy)) / (80 * s), 0, 1)
            col = np.array(rg["color"], np.float32) / 255
            a = (rm * rg.get("alpha", 0.75))[..., None]
            frame[:] = frame * (1 - a) + col * a
            if rg.get("border"):
                edge = cv2.morphologyEx((rm > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
                e = cv2.GaussianBlur(edge.astype(np.float32), (0, 0), 0.8 * s)[..., None]
                frame[:] = frame * (1 - e) + np.array(rg["border"], np.float32) / 255 * e
        # coastlines
        cv2.polylines(canvas, land, True, (255, 255, 255), max(1, int(2.2 * s * SS)), cv2.LINE_AA)
        coast = cv2.resize(canvas[..., 0], (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
        frame[:] = frame * (1 - coast * 0.85) + np.array(INK, np.float32) / 255 * coast * 0.85
        # arrows (progressive quadratic curves) and battle markers
        for ar in self.spec.get("arrows", []):
            u = (t - ar["start"]) / ar.get("dur", 0.6)
            if u <= 0:
                continue
            p0, p2 = np.array(xf(*proj(*ar["from"]))), np.array(xf(*proj(*ar["to"])))
            mid = (p0 + p2) / 2
            nrm = np.array([-(p2 - p0)[1], (p2 - p0)[0]])
            p1 = mid + nrm * ar.get("bend", 0.18)
            k = ease_out(min(1.0, u))
            ts = np.linspace(0, k, 40)[:, None]
            curve = (1 - ts) ** 2 * p0 + 2 * (1 - ts) * ts * p1 + ts ** 2 * p2
            col = ar.get("color", (178, 34, 34))
            lay = np.zeros((H * SS, W * SS), np.uint8)
            cv2.polylines(lay, [(curve * SS).astype(np.int32)], False, 255, max(2, int(7 * s * SS)), cv2.LINE_AA)
            tip, prev = curve[-1], curve[-3]
            d = (tip - prev) / (np.linalg.norm(tip - prev) + 1e-6)
            n = np.array([-d[1], d[0]])
            head = np.array([tip + d * 16 * s, tip - d * 10 * s + n * 13 * s, tip - d * 10 * s - n * 13 * s])
            cv2.fillConvexPoly(lay, (head * SS).astype(np.int32), 255, cv2.LINE_AA)
            a = cv2.resize(lay, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
            sh = cv2.GaussianBlur(a[..., 0], (0, 0), 4 * s)[..., None]
            frame *= 1 - sh * 0.35
            frame[:] = frame * (1 - a) + np.array(col, np.float32) / 255 * a
            if u >= 1:                                  # marker pops when the arrow lands
                v = min(1.0, (u - 1) * ar.get("dur", 0.6) / 0.35)
                r = (10 + 8 * (1 - ease_out(v))) * s * min(1.6, z)
                cx, cy = int(p2[0]), int(p2[1])
                cv2.circle(frame, (cx, cy), int(r + 4 * s), (0.1, 0.07, 0.05), -1, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), int(r), tuple(c / 255 for c in GOLD), -1, cv2.LINE_AA)
                for sgn in (-1, 1):                      # crossed swords
                    cv2.line(frame, (int(cx - r * 0.6), int(cy + sgn * r * 0.6)), (int(cx + r * 0.6), int(cy - sgn * r * 0.6)),
                             (0.12, 0.08, 0.06), max(1, int(2.5 * s)), cv2.LINE_AA)
                if ar.get("label"):
                    lab = self._label(ar["label"], int(27 * s))
                    dx, dy = ar.get("label_offset", (0, -34))
                    over(frame, lab, cx - lab.shape[1] / 2 + dx * s, cy - lab.shape[0] / 2 + dy * s, smooth(v * 1.5))
        for pl in self.spec.get("places", []):
            if t < pl.get("start", 0):
                continue
            v = smooth((t - pl.get("start", 0)) / 0.4)
            x, y = xf(*proj(*pl["lonlat"]))
            cv2.circle(frame, (int(x), int(y)), int(7 * s), (0.08, 0.06, 0.05), -1, cv2.LINE_AA)
            cv2.circle(frame, (int(x), int(y)), int(5 * s), tuple(c / 255 for c in IVORY), -1, cv2.LINE_AA)
            lab = self._label(pl["name"], int(pl.get("size", 30) * s), GOLD, "title", 0.12)
            dx, dy = pl.get("offset", (0, 30))
            over(frame, lab, x - lab.shape[1] / 2 + dx * s, y - lab.shape[0] / 2 + dy * s, v)


class Timeline:
    """Horizontal year scale with a moving cursor: marks = [{year, t}]; cursor eases between marks."""

    def __init__(self, y, years, start, marks, end=1e9, x0=130, x1=950):
        self.y, self.y0, self.y1, self.start, self.end, self.marks = y, years[0], years[1], start, end, marks
        self.x0, self.x1 = x0, x1
        self._lab = {}

    def _x(self, year):
        return self.x0 + (year - self.y0) / (self.y1 - self.y0) * (self.x1 - self.x0)

    def __call__(self, frame, t, W, H, cam):
        if not (self.start <= t <= self.end):
            return
        s = W / DW
        op = smooth((t - self.start) / 0.5) * min(1.0, (self.end - t) / 0.3)
        lay = frame.copy()
        grow = ease_out((t - self.start) / 0.8)
        xa, xb = self._x(self.y0), self._x(self.y0) + (self._x(self.y1) - self._x(self.y0)) * grow
        cv2.line(lay, (int(xa * s), int(self.y * s)), (int(xb * s), int(self.y * s)), tuple(c / 255 for c in IVORY),
                 max(1, int(3 * s)), cv2.LINE_AA)
        for yr in range(self.y0, self.y1 + 1):
            x = self._x(yr)
            if x > xb:
                break
            big = any(m["year"] == yr for m in self.marks)
            cv2.line(lay, (int(x * s), int((self.y - (14 if big else 8)) * s)), (int(x * s), int((self.y + (14 if big else 8)) * s)),
                     tuple(c / 255 for c in IVORY), max(1, int(2 * s)), cv2.LINE_AA)
            key = (yr, s)
            if key not in self._lab:
                self._lab[key] = _pm(text_image(str(yr), 26 * s, "sub", IVORY, 0.04, stroke=1))
            lab = self._lab[key]
            over(lay, lab, x * s - lab.shape[1] / 2, (self.y + 16) * s, 0.9)
        done = [m for m in self.marks if t >= m["t"]]
        if done:
            cur = done[-1]
            nxt = next((m for m in self.marks if m["t"] > t), None)
            yr = cur["year"]
            x = self._x(yr)
            if nxt and nxt["t"] - t < 0.35:
                x += (self._x(nxt["year"]) - x) * smooth(1 - (nxt["t"] - t) / 0.35)
            pts = np.array([[x, self.y - 16], [x + 12, self.y], [x, self.y + 16], [x - 12, self.y]]) * s
            cv2.fillConvexPoly(lay, pts.astype(np.int32), tuple(c / 255 for c in GOLD), cv2.LINE_AA)
        frame[:] = frame * (1 - op) + lay * op

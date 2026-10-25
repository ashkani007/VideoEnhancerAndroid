"""Cinematic typography for ghm4: per-letter reveals, gold rules, lower-third bars, scrims (approved in Napoleon_20s_POC).

Positions and sizes are authored in a 720x1280 design space and scaled to the output by U = OW / 720.
"""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = "/usr/share/fonts/truetype/crosextra/"
COLORS = {"ivory": (0.97, 0.93, 0.84), "gold": (0.90, 0.70, 0.36), "navy": (0.05, 0.07, 0.12),
          "blue": (0.20, 0.34, 0.68), "red": (0.74, 0.17, 0.14), "white": (1.0, 1.0, 1.0)}
NAVY = np.array(COLORS["navy"], np.float32)

# presets: font style, size, tracking, colour, stagger, rise (design units)
PRESETS = {
    "kicker": ("Bold", 34, 12, "gold", 0.045, 16),
    "title": ("Bold", 100, 12, "ivory", 0.06, 22),
    "title_m": ("Bold", 92, 10, "ivory", 0.055, 22),
    "tagline": ("Regular", 25, 5, "ivory", 0.018, 16),
    "date": ("Bold", 32, 8, "gold", 0.03, 16),
    "italic": ("Italic", 33, 1, "ivory", 0.0, 8),
    "lower_name": ("Bold", 46, 3, "ivory", 0.03, 0),
    "lower_role": ("Italic", 32, 1, "gold", 0.02, 0),
    "lower_detail": ("Italic", 25, 1, "ivory", 0.015, 0),
    "map_label": ("Bold", 27, 2, "ivory", 0.02, 8),
    "map_note": ("Italic", 25, 0, "gold", 0.0, 6),
    "ticker": ("Bold", 52, 4, "ivory", 0.0, 0),
    "legend": ("Bold", 23, 2, "ivory", 0.0, 0),
}


def ease(u):
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def easeout(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 2


def color(c):
    return np.asarray(COLORS[c] if isinstance(c, str) else c, np.float32)


@functools.lru_cache(None)
def font(style, size):
    for path in (FONTS + f"Caladea-{style}.ttf", f"C:/Windows/Fonts/georgia{'b' if style == 'Bold' else ('i' if style == 'Italic' else '')}.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Canvas:
    """Collects text/graphic masks for one frame and composites them with soft drop shadows."""

    def __init__(self, OW, OH):
        self.OW, self.OH, self.U = OW, OH, OW / 720.0
        self.items = []

    def letters(self, s, x, y, tt, preset="tagline", align="c", alpha=1.0, col=None, size=None, track=None, stagger=None,
                rise=None, dur=0.4, style=None, shadow=0.55):
        st, sz, tr, c, sg, ri = PRESETS[preset]
        U = self.U
        fnt = font(style or st, max(8, int(round((size or sz) * U))))
        tr = (tr if track is None else track) * U
        sg = sg if stagger is None else stagger
        ri = (ri if rise is None else rise) * U
        im = Image.new("L", (self.OW, self.OH), 0)
        d = ImageDraw.Draw(im)
        ws = [fnt.getlength(ch) for ch in s]
        total = sum(ws) + tr * (len(s) - 1)
        xs, ys = x * U, y * U
        xc = xs - total / 2 if align == "c" else (xs - total if align == "r" else xs)
        drawn = False
        for i, ch in enumerate(s):
            a = ease((tt - i * sg) / dur) * alpha
            if a > 0.003 and ch != " ":
                d.text((xc, ys + ri * (1 - a)), ch, font=fnt, fill=int(255 * a + 0.5), anchor="ls")
                drawn = True
            xc += ws[i] + tr
        if drawn:
            self.items.append((np.asarray(im, np.float32) / 255, color(col or c), shadow))

    def rule(self, x, y, length, p, alpha=1.0, col="gold", th=2):
        h = 0.5 * length * self.U * easeout(p)
        if h > 1 and alpha > 0:
            m = np.zeros((self.OH, self.OW), np.uint8)
            cv2.line(m, (int(x * self.U - h), int(y * self.U)), (int(x * self.U + h), int(y * self.U)), int(255 * alpha),
                     max(1, int(round(th * self.U))), cv2.LINE_AA)
            self.items.append((m.astype(np.float32) / 255, color(col), 0.3))

    def rect(self, x0, y0, x1, y1, alpha=1.0, col="gold", shadow=0.3):
        if alpha <= 0:
            return
        m = np.zeros((self.OH, self.OW), np.float32)
        U = self.U
        m[int(y0 * U):int(y1 * U), int(x0 * U):int(x1 * U)] = alpha
        self.items.append((m, color(col), shadow))

    def apply(self, img):
        for m, col, sh in self.items:
            if sh > 0:
                s = cv2.GaussianBlur(np.roll(m, int(3 * self.U), axis=0), (0, 0), 3.5 * self.U) * sh
                img = img * (1 - s[..., None]) + NAVY * s[..., None]
            img = img * (1 - m[..., None]) + col * m[..., None]
        return img


def scrim(img, y0, y1, k, top=False, U=1.0):
    OH = img.shape[0]
    yy = np.arange(OH, dtype=np.float32)[:, None] / U
    g = np.clip((y1 - yy) / (y1 - y0), 0, 1) if top else np.clip((yy - y0) / (y1 - y0), 0, 1)
    g = (g ** 1.3 * k)[..., None]
    return img * (1 - g) + NAVY * g


def draw_items(cv, items, tl):
    """Storyboard text items (shot-local times, design units).

    {"text": "NAPOLEON", "preset": "title", "x": 360, "y": 920, "at": 0.7, "out": [3.85, 4.2], "align": "c", ...}
    {"rule": 420, "x": 360, "y": 948, "at": 1.35, "dur": 0.7, "out": [...]}
    {"bar": [50, 988, 55], "height": 112, "at": 0.75, "out": [...]}            vertical bar growing upward
    """
    for it in items:
        out = it.get("out")
        alpha = 1 - ease((tl - out[0]) / max(1e-3, out[1] - out[0])) if out else 1.0
        if alpha <= 0.003:
            continue
        if "text" in it:
            cv.letters(it["text"], it.get("x", 360), it["y"], tl - it.get("at", 0), it.get("preset", "tagline"),
                       it.get("align", "c"), alpha, it.get("color"), it.get("size"), it.get("track"), it.get("stagger"),
                       it.get("rise"), it.get("dur", 0.4), it.get("style"), it.get("shadow", 0.55))
        elif "rule" in it:
            cv.rule(it.get("x", 360), it["y"], it["rule"], (tl - it.get("at", 0)) / it.get("dur", 0.7), alpha, it.get("color", "gold"))
        elif "bar" in it:
            x0, yb, x1 = it["bar"]
            h = it.get("height", 112) * easeout((tl - it.get("at", 0)) / it.get("dur", 0.5))
            if h > 1:
                cv.rect(x0, yb - h, x1, yb, alpha, it.get("color", "gold"))

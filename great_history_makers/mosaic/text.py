"""Typography overlays: subtitles, title cards, notes. Rendered with Pillow in screen space."""
import glob
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .palette import P

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(HERE, "..", "assets", "fonts"), "/usr/share/fonts", "C:/Windows/Fonts",
             os.path.expanduser("~/.fonts")]
# first match wins: drop Cinzel / EB Garamond (OFL) into assets/fonts to upgrade the look
PREFS = {
    "title": ["Cinzel*Bold*.ttf", "Cinzel*.ttf", "Caladea-Bold.ttf", "georgiab.ttf", "DejaVuSerif-Bold.ttf"],
    "sub": ["EBGaramond*SemiBold*.ttf", "EBGaramond*.ttf", "Caladea-Bold.ttf", "georgiab.ttf",
            "DejaVuSerif-Bold.ttf"],
    "note": ["EBGaramond*Italic*.ttf", "Caladea-Italic.ttf", "georgiai.ttf", "DejaVuSerif.ttf"],
}


def find_font(kind):
    for pat in PREFS[kind]:
        for d in FONT_DIRS:
            hits = sorted(glob.glob(os.path.join(d, "**", pat), recursive=True))
            if hits:
                return hits[0]
    return None


def _font(kind, size):
    path = find_font(kind)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _spaced_width(d, text, font, spacing):
    return sum(d.textlength(ch, font=font) for ch in text) + spacing * max(0, len(text) - 1)


def _draw_line(d, x_center, y, text, font, fill, spacing=0, stroke=0, stroke_fill=None):
    if spacing == 0:
        w = d.textlength(text, font=font)
        d.text((x_center - w / 2, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        return
    w = _spaced_width(d, text, font, spacing)
    x = x_center - w / 2
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += d.textlength(ch, font=font) + spacing


def _rgba(name, a=255):
    return tuple(P[name]) + (a,)


class Overlay:
    """Pre-rendered RGBA (premultiplied float) overlay with fade timing."""

    def __init__(self, img, start, end, fade=0.25):
        a = np.asarray(img).astype(np.float32) / 255.0
        a[..., :3] *= a[..., 3:4]
        self.img, self.start, self.end, self.fade = a, start, end, fade

    def opacity(self, t):
        if t < self.start or t > self.end:
            return 0.0
        return min(1.0, (t - self.start) / self.fade, (self.end - t) / self.fade)

    def apply(self, frame, t):
        o = self.opacity(t)
        if o <= 0:
            return
        f = self.img
        frame *= 1 - f[..., 3:4] * o
        frame += f[..., :3] * o


def _canvas(W, H):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _with_shadow(img, radius, strength=0.8, offset=(0, 0)):
    a = img.split()[3]
    sh = Image.new("RGBA", img.size, (12, 9, 7, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * strength)))
    if offset != (0, 0):
        sh = sh.transform(sh.size, Image.AFFINE, (1, 0, -offset[0], 0, 1, -offset[1]))
    return Image.alpha_composite(sh, img)


# Safe area for Reels / Shorts (design units, 1080x1920): keep clear of the top
# ~13% (account bar), the bottom ~22% (caption/CTA UI) and the right-hand icon rail.
SAFE = dict(top=250, bottom=1500, left=90, right=930)


def subtitle(ctx, text, start, end, y=1300, size=64):
    """Large, high-contrast caption on a soft dark plate, centred inside the safe area."""
    s = ctx.pxpd
    img, d = _canvas(ctx.W, ctx.H)
    font = _font("sub", int(size * s))
    lines = text.split("\n")
    lh = size * 1.24 * s
    cx = (SAFE["left"] + SAFE["right"]) / 2 * s
    y = min(max(y, SAFE["top"] + 60), SAFE["bottom"] - 60)
    y0 = y * s - lh * len(lines) / 2
    widths = [d.textlength(ln, font=font) for ln in lines]
    pw, ph = max(widths) + 44 * s, lh * len(lines) + 24 * s
    plate = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([cx - pw / 2, y0 - 10 * s, cx + pw / 2, y0 - 10 * s + ph],
                                            radius=int(18 * s), fill=(20, 14, 10, 150))
    plate = plate.filter(ImageFilter.GaussianBlur(3 * s))
    for i, ln in enumerate(lines):
        _draw_line(d, cx, y0 + i * lh, ln, font, (250, 244, 228, 255), stroke=max(1, int(3.6 * s)),
                   stroke_fill=_rgba("black", 240))
    return Overlay(Image.alpha_composite(plate, _with_shadow(img, 5 * s, 0.6, (0, int(2 * s)))), start, end, 0.15)


def caption(ctx, text, start, end, y=1300, size=60):
    """Mobile caption without a box: ivory text, firm dark outline and a soft shadow."""
    s = ctx.pxpd
    img, d = _canvas(ctx.W, ctx.H)
    font = _font("sub", int(size * s))
    lines = text.split("\n")
    lh = size * 1.22 * s
    cx = (SAFE["left"] + SAFE["right"]) / 2 * s
    y = min(max(y, SAFE["top"] + 80), SAFE["bottom"] - 60)
    y0 = y * s - lh * len(lines) / 2
    for i, ln in enumerate(lines):
        _draw_line(d, cx, y0 + i * lh, ln, font, (250, 245, 232, 255), stroke=max(2, int(4.2 * s)),
                   stroke_fill=(16, 11, 8, 245))
    return Overlay(_with_shadow(img, 9 * s, 0.85, (0, int(3 * s))), start, end, 0.12)


def ornament(d, cx, y, half, s, col):
    d.line([(cx - half * s, y), (cx - 18 * s, y)], fill=col, width=max(1, int(2.5 * s)))
    d.line([(cx + 18 * s, y), (cx + half * s, y)], fill=col, width=max(1, int(2.5 * s)))
    r = 9 * s
    d.polygon([(cx, y - r), (cx + r, y), (cx, y + r), (cx - r, y)], fill=col)


def title(ctx, text, sub, start, end, y=250, size=84):
    s = ctx.pxpd
    img, d = _canvas(ctx.W, ctx.H)
    f1 = _font("title", int(size * s))
    f2 = _font("title", int(size * 0.46 * s))
    _draw_line(d, ctx.W / 2, y * s, text, f1, _rgba("gold_lt"), spacing=size * 0.12 * s,
               stroke=max(1, int(2 * s)), stroke_fill=_rgba("black", 200))
    oy = (y + size * 1.25) * s
    ornament(d, ctx.W / 2, oy, 300, s, _rgba("gold"))
    if sub:
        _draw_line(d, ctx.W / 2, oy + 22 * s, sub, f2, _rgba("ivory"), spacing=size * 0.14 * s,
                   stroke=max(1, int(2.5 * s)), stroke_fill=_rgba("black", 230))
    return Overlay(_with_shadow(img, 10 * s, 0.85, (0, int(3 * s))), start, end, 0.45)


def note(ctx, text, start, end, y=205, size=30, x=None, kind="note"):
    s = ctx.pxpd
    img, d = _canvas(ctx.W, ctx.H)
    f = _font("note" if kind == "note" else "title", int(size * s))
    cx = (x if x is not None else 540) * s
    _draw_line(d, cx, y * s, text, f, _rgba("ivory" if kind == "note" else "gold_lt", 225),
               spacing=0 if kind == "note" else size * 0.12 * s, stroke=max(1, int(2.0 * s)),
               stroke_fill=_rgba("black", 200))
    return Overlay(_with_shadow(img, 5 * s, 0.6), start, end, 0.4)


def from_spec(ctx, spec):
    k = spec.get("kind", "title")
    if k in ("title", "endcard"):
        return title(ctx, spec["text"], spec.get("sub"), spec["start"], spec["end"], spec.get("y", 250),
                     spec.get("size", 84 if k == "title" else 70))
    if k == "maplabel":
        return note(ctx, spec["text"], spec["start"], spec["end"], spec.get("y", 205), spec.get("size", 40),
                    spec.get("x"), kind="label")
    return note(ctx, spec["text"], spec["start"], spec["end"], spec.get("y", 205), spec.get("size", 30), spec.get("x"))


def write_srt(cues, path):
    def ts(x):
        h, r = divmod(x, 3600)
        m, sec = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec % 1) * 1000)) % 1000:03d}"
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n\n")

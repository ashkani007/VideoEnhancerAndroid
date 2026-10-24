#!/usr/bin/env python3
"""Napoleon 20 s proof of concept: storytelling through scene variety, motion graphics and editing.

The approved illustration is the only character art, so the four compositions are:
  A  0.0-4.4   wide establishing shot of the illustration (slow pull-back, title "NAPOLEON / 1805")
  B  4.4-9.0   portrait close-up reframed from it (push-in, ONE clearly visible blink, lower third)
  C  9.0-15.0  animated campaign map drawn in the illustration palette (moving arrows, cities, date ticker)
  D 15.0-20.0  battlefield reframed from the right side (flags, marching ranks, drifting smoke, cannon puffs)
Transitions: whip-zoom (A>B), painted ink wipe (B>C), push into the Austerlitz star + flash (C>D), fade to black.
All character and battlefield motion reuses ../../Napoleon_Animation_Test/project/animate.py (no generative video).

  python render.py                 # 720x1280 preview with procedural music/SFX -> ../final/Napoleon_20s_POC_720p.mp4
  python render.py --still 7.4     # one frame -> ../qc/
  python render.py --qc            # contact sheet, blink sequence, per-shot stills -> ../qc/
"""
import argparse
import functools
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GHM = os.path.dirname(os.path.dirname(ROOT))
sys.path.insert(0, os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "project"))
sys.path.insert(0, GHM)
import animate as A  # noqa: E402

FPS, DUR = 30, 20.0
OW, OH = 720, 1280
CUT_AB, CUT_BC, CUT_CD = 4.4, 9.0, 15.0

# one longer, clearly readable blink (close 0.12 s, hold, open 0.14 s); animate.foreground looks the name up at call time
_blink = A.blink_amount
A.blink_amount = lambda t: _blink(t, 0.92, 0.30)

IVORY = np.array([0.97, 0.93, 0.84], np.float32)
GOLD = np.array([0.90, 0.70, 0.36], np.float32)
NAVY = np.array([0.05, 0.07, 0.12], np.float32)
FBLUE = (0.20, 0.34, 0.68)
CRED = (0.74, 0.17, 0.14)
FONTS = "/usr/share/fonts/truetype/crosextra/"
ease, ramp = A.ease, A.ramp


def easeout(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 2


def backout(u):
    u = min(1.0, max(0.0, u))
    return 1 + 2.2 * (u - 1) ** 3 + 1.2 * (u - 1) ** 2


@functools.lru_cache(None)
def font(style, size):
    return ImageFont.truetype(FONTS + f"Caladea-{style}.ttf", size)


# ------------------------------------------------------------------------------------------- text overlay
def letters(s, fnt, x, y, track, tt, align="c", stagger=0.045, dur=0.4, rise=16.0, alpha=1.0):
    """Per-letter reveal (fade + rise, staggered). y is the baseline. Returns a float mask (OH, OW)."""
    im = Image.new("L", (OW, OH), 0)
    d = ImageDraw.Draw(im)
    ws = [fnt.getlength(c) for c in s]
    total = sum(ws) + track * (len(s) - 1)
    xc = x - total / 2 if align == "c" else (x - total if align == "r" else x)
    for i, c in enumerate(s):
        a = ease((tt - i * stagger) / dur) * alpha
        if a > 0.003 and c != " ":
            d.text((xc, y + rise * (1 - a)), c, font=fnt, fill=int(255 * a + 0.5), anchor="ls")
        xc += ws[i] + track
    return np.asarray(im, np.float32) / 255


def rule(cx, y, length, p, alpha=1.0, th=2):
    m = np.zeros((OH, OW), np.uint8)
    h = 0.5 * length * easeout(p)
    if h > 1:
        cv2.line(m, (int(cx - h), int(y)), (int(cx + h), int(y)), int(255 * alpha), th, cv2.LINE_AA)
    return m.astype(np.float32) / 255


class Overlay:
    def __init__(self):
        self.items = []

    def add(self, m, col, shadow=0.55):
        self.items.append((m, np.asarray(col, np.float32), shadow))

    def apply(self, img):
        for m, col, sh in self.items:
            if sh > 0:
                s = cv2.GaussianBlur(np.roll(m, 3, axis=0), (0, 0), 3.5) * sh
                img = img * (1 - s[..., None]) + NAVY * s[..., None]
            img = img * (1 - m[..., None]) + col * m[..., None]
        return img


YO = np.mgrid[0:OH, 0:OW][0].astype(np.float32)
XO = np.mgrid[0:OH, 0:OW][1].astype(np.float32)


def scrim(img, y0, y1, k, top=False):
    g = np.clip((y1 - YO) / (y1 - y0), 0, 1) if top else np.clip((YO - y0) / (y1 - y0), 0, 1)
    g = (g ** 1.3 * k)[..., None]
    return img * (1 - g) + NAVY * g


VIGNETTE = (1 - 0.24 * np.clip(np.hypot((XO - OW / 2) / (OW * 0.62), (YO - OH / 2) / (OH * 0.62)) - 0.35, 0, 1) ** 1.4)[..., None]
WIPE_NOISE = cv2.resize(A.tileable_noise(160, 90, 4, 21), (OW, OH), interpolation=cv2.INTER_CUBIC)
FG_SMOKE = cv2.resize(A.tileable_noise(96, 256, 7, 33), (OW * 2, OH), interpolation=cv2.INTER_CUBIC)   # stretched: horizontal veils


def zoom_blur(img, amt, cx=OW / 2, cy=OH / 2, n=7):
    if amt < 0.004:
        return img
    acc = np.zeros_like(img)
    for i in range(n):
        s = 1 + amt * i / (n - 1)
        M = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
        acc += cv2.warpAffine(img, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return acc / n


def sharpen(img, k=0.4, sigma=1.0):
    return img + k * (img - cv2.GaussianBlur(img, (0, 0), sigma))


# ------------------------------------------------------------------------------------------- illustration shots
def comp(bg, fg, z, fx, fy, z0, par=0.55):
    """Parallax composite: the background zooms less than the foreground relative to the shot's base zoom z0."""
    zb = z0 + (z - z0) * par
    b = A.place(bg, zb, fx, fy, OW, OH, cv2.INTER_LANCZOS4)
    f = A.place(fg, z, fx, fy, OW, OH, cv2.INTER_LANCZOS4)
    a = np.clip(f[..., 3:4], 0, 1)
    return np.clip(b * (1 - a) + f[..., :3] * a, 0, 1)


def shot_a(tl, t):
    u = ramp(tl, 0, 4.4)
    z, fx, fy = 1.22 - 0.16 * u, 470.0, 705.0 + 125.0 * u
    w = min(1.0, max(0.0, (tl - 4.12) / 0.28)) ** 2                 # whip-zoom toward the face into shot B
    z *= 1 + 0.45 * w
    fx, fy = fx + (440 - fx) * w, fy + (420 - fy) * w
    img = comp(A.background(t), A.foreground(tl + 2.0), z, fx, fy, 1.22)   # tf >= 2: no blink in this shot
    img = zoom_blur(img, 0.10 * w, OW * 0.47, OH * 0.36)
    o = Overlay()
    img = scrim(img, 700, 1280, 0.68)
    out = 1 - ramp(tl, 3.85, 4.2)
    o.add(letters("1805", font("Bold", 34), OW / 2, 822, 12, tl - 0.45, alpha=out), GOLD)
    o.add(letters("NAPOLEON", font("Bold", 100), OW / 2, 920, 12, tl - 0.7, stagger=0.06, rise=22, alpha=out), IVORY)
    o.add(rule(OW / 2, 948, 420, (tl - 1.35) / 0.7, out), GOLD, 0.3)
    o.add(letters("EUROPE UNITES AGAINST ONE MAN", font("Regular", 25), OW / 2, 992, 5, tl - 1.6, stagger=0.018, alpha=out), IVORY)
    return o.apply(img)


def shot_b(tl, t):
    u = 1 - (1 - min(1.0, max(0.0, tl / 4.6))) ** 2.2
    z, fx, fy = 2.0 + 0.85 * u, 432.0 + 10.0 * u, 470.0 - 100.0 * u
    settle = 1 - ease(tl / 0.35)                                     # end of the whip-zoom
    img = comp(A.background(t), A.foreground(tl - 2.1), z * (1 + 0.10 * settle), fx, fy, 2.0)   # blink at tl 3.02 (t 7.42)
    img = zoom_blur(sharpen(img), 0.08 * settle)
    img = scrim(img, 700, 1280, 0.78)
    o = Overlay()
    out = 1 - ramp(tl, 4.05, 4.45)
    bar = np.zeros((OH, OW), np.float32)
    hb = 112 * easeout((tl - 0.75) / 0.5)
    if hb > 1:
        bar[int(988 - hb):988, 50:55] = out
    o.add(bar, GOLD, 0.3)
    o.add(letters("NAPOLEON BONAPARTE", font("Bold", 46), 72, 912, 3, tl - 0.9, align="l", stagger=0.03, rise=0, alpha=out), IVORY)
    o.add(letters("Emperor of the French", font("Italic", 32), 72, 952, 1, tl - 1.4, align="l", stagger=0.02, rise=0, alpha=out), GOLD)
    o.add(letters("crowned 2 December 1804", font("Italic", 25), 72, 984, 1, tl - 1.8, align="l", stagger=0.015, rise=0, alpha=out), IVORY)
    return o.apply(img)


SMOKE_ROI = (470, 820, 941, 1262)
_x0, _y0, _x1, _y1 = SMOKE_ROI
_SL = (slice(_y0, _y1), slice(_x0, _x1))
SMOKE_BAND_D = (A.soft_box(500, 905, 941, 1185, 70) * (1 - A.ALPHA))[_SL]
CANNON = [(0.9, 912.0, 928.0), (2.3, 640.0, 935.0), (3.6, 760.0, 915.0)]   # (shot time, source x, y): synced to the SFX


def battle_smoke(bg, t):
    """Thicker drifting powder smoke through the ranks (sub-pixel drift, posterized like the illustration)."""
    def drift(n, sx, sy):
        return cv2.remap(n, (A.XX[_SL] - sx).astype(np.float32), (A.YY[_SL] - sy).astype(np.float32), cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_WRAP)
    sm = 0.6 * drift(A.N1, 20 * t, -2.5 * t) + 0.4 * drift(A.N2, 36 * t, -4 * t)
    a = (np.clip((sm - 0.47) / 0.05, 0, 1) * 0.34 + np.clip((sm - 0.60) / 0.04, 0, 1) * 0.24) * SMOKE_BAND_D
    col = np.array([0.88, 0.79, 0.72], np.float32)
    bg[_SL] = bg[_SL] * (1 - a[..., None]) + col * a[..., None]
    return bg


PUFF_BLOBS = [(0, 0, 1.0), (0.85, 0.2, 0.78), (-0.8, 0.25, 0.72), (0.35, -0.6, 0.74), (-0.38, -0.5, 0.62), (1.45, 0.45, 0.52),
              (-1.4, 0.5, 0.5), (0.0, 0.55, 0.7)]


def cannon_puff(bg, cx, cy, dt):
    """Muzzle flash, then a billowing cluster of round puffs (lit top, shaded underside) that grows, rises and fades."""
    if dt < 0 or dt > 3.4:
        return bg
    r = 3 + 19 * min(1.0, dt / 1.1) ** 0.5
    px, py = cx + 8 * dt, cy - 7 * dt
    R = int(r * 2.6) + 24
    sl = (slice(max(0, int(py - R)), min(A.H, int(py + R))), slice(max(0, int(px - R)), min(A.W, int(px + R))))
    X, Y = A.XX[sl], A.YY[sl]
    m = np.zeros_like(X)
    for bx, by, rr in PUFF_BLOBS:
        rb = rr * r * (0.85 + 0.15 * math.sin(2.1 * dt + 3 * bx))
        m = np.maximum(m, np.clip((rb - np.hypot(X - px - bx * r, Y - py - by * r)) / 1.3, 0, 1))
    lit = np.clip(0.55 - (Y - py) / (1.7 * r) + 0.25 * (X - px) / r, 0, 1)[..., None]
    col = np.array([0.70, 0.62, 0.62], np.float32) * (1 - lit) + np.array([0.97, 0.89, 0.79], np.float32) * lit
    a = (m * 0.88 * (1 - np.clip((dt - 1.5) / 1.9, 0, 1)) * (1 - A.ALPHA[sl]))[..., None]
    bg[sl] = bg[sl] * (1 - a) + col * a
    flash = math.exp(-dt / 0.07)
    g = np.exp(-(((X - cx) / 12) ** 2 + ((Y - cy) / 8) ** 2)) * flash * 0.8
    bg[sl] += g[..., None] * np.array([1.0, 0.78, 0.42], np.float32)
    return bg


def shot_d(tl, t):
    u = ramp(tl, 0, 5.0)
    z, fx, fy = 2.22 + 0.16 * u, 688.0 + 34.0 * u, 985.0 - 25.0 * u
    z *= 1 + 0.14 * (1 - easeout(tl / 0.7))                           # cross-zoom settle after the map push
    bg = battle_smoke(A.background(t, flag_gain=2.0, bob_gain=1.7), t)
    for tc, cx, cy in CANNON:
        bg = cannon_puff(bg, cx, cy, tl - tc)
    img = sharpen(comp(np.clip(bg, 0, 1), A.foreground(tl + 5.0), z, fx, fy, 2.22, par=0.6))
    # foreground smoke wisps drifting across the lens (depth)
    off = int(40 * tl) % OW
    n = FG_SMOKE[:, off:off + OW]
    a = (np.clip((n - 0.5) / 0.3, 0, 1) * 0.14 * np.clip((YO - 420) / 500, 0, 1))[..., None]
    img = img * (1 - a) + np.array([0.86, 0.78, 0.72], np.float32) * a
    img = scrim(img, 720, 1280, 0.66)
    o = Overlay()
    o.add(letters("AUSTERLITZ", font("Bold", 92), OW / 2, 912, 10, tl - 0.55, stagger=0.055, rise=22), IVORY)
    o.add(rule(OW / 2, 942, 440, (tl - 1.1) / 0.7), GOLD, 0.3)
    sw = ramp(tl, 2.6, 2.95)
    o.add(letters("2 DECEMBER 1805", font("Bold", 32), OW / 2, 990, 8, tl - 1.2, stagger=0.03, alpha=1 - sw), GOLD)
    o.add(letters("The Battle of the Three Emperors", font("Italic", 33), OW / 2, 990, 1, tl - 2.75, stagger=0.0, rise=8), IVORY)
    return o.apply(img)


# ------------------------------------------------------------------------------------------- campaign map
PPU = 220.0
LON0, LON1, LAT0, LAT1 = -6.0, 26.0, 40.0, 58.0
KX = math.cos(math.radians(48))
CW, CH = int((LON1 - LON0) * KX * PPU), int((LAT1 - LAT0) * PPU)


def unit(lon, lat):
    return ((lon - LON0) * KX, LAT1 - lat)


def cpx(lon, lat):
    x, y = unit(lon, lat)
    return x * PPU, y * PPU


RHINE = [(9.5, 47.6), (8.6, 47.6), (7.6, 47.56), (7.75, 48.58), (8.47, 49.49), (8.27, 50.0), (7.6, 50.36), (6.96, 50.94),
         (6.77, 51.23), (5.86, 51.84), (4.3, 51.9)]
DANUBE = [(8.5, 47.95), (9.99, 48.40), (11.42, 48.76), (12.1, 49.02), (13.46, 48.57), (14.29, 48.31), (16.37, 48.21),
          (17.1, 48.14), (17.6, 47.7), (19.04, 47.5), (18.9, 46.0)]
ALPS = [(5.8, 44.6), (6.6, 45.5), (7.3, 45.95), (8.5, 46.35), (10.0, 46.55), (11.8, 46.9), (13.6, 47.15), (15.4, 47.45)]
CARPATHIANS = [(17.6, 48.9), (19.2, 49.35), (20.9, 49.3), (22.4, 49.0), (23.8, 48.1), (24.9, 47.1)]
CITIES = {"BOULOGNE": (1.61, 50.73), "STRASBOURG": (7.75, 48.58), "ULM": (9.99, 48.40), "VIENNA": (16.37, 48.21),
          "AUSTERLITZ": (16.76, 49.13), "OLMÜTZ": (17.25, 49.59)}
# French route (control points; cities are waypoints) and the converging coalition army
FR_ROUTE = [(1.61, 50.73), (3.4, 50.1), (5.7, 49.1), (7.75, 48.58), (8.9, 48.3), (9.99, 48.40), (11.5, 48.75),
            (13.1, 48.62), (14.4, 48.36), (16.37, 48.21), (16.62, 48.68), (16.76, 49.13)]
FR_WAY = [0, 3, 5, 9, 11]                                          # control-point index of each city on FR_ROUTE
CO_ROUTE = [(23.6, 50.7), (21.4, 50.15), (19.0, 49.8), (17.25, 49.59), (16.98, 49.30)]


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


FR_PATH, FR_CUM, FR_WLEN = catmull([cpx(*p) for p in FR_ROUTE])
CO_PATH, CO_CUM, CO_WLEN = catmull([cpx(*p) for p in CO_ROUTE])


def build_base():
    land = np.zeros((CH, CW), np.uint8)
    import json
    polys = json.load(open(os.path.join(GHM, "ghm2", "data", "europe_simplified.json")))["polygons"]
    cp = [np.array([cpx(lo, la) for lo, la in p], np.float64) for p in polys]
    for p in cp:
        cv2.fillPoly(land, [np.round(p * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
    lf = land.astype(np.float32) / 255
    tex_small = A.tileable_noise(400, 520, 6, 11)
    tex = cv2.resize(tex_small, (CW, CH), interpolation=cv2.INTER_CUBIC)
    fine = cv2.resize(A.tileable_noise(700, 900, 1.2, 12), (CW, CH), interpolation=cv2.INTER_LINEAR)
    yy = np.linspace(0, 1, CH, dtype=np.float32)[:, None, None]
    sea = np.array([0.09, 0.15, 0.22], np.float32) * (1 - yy) + np.array([0.13, 0.22, 0.29], np.float32) * yy
    sea = sea * (0.94 + 0.10 * tex[..., None])
    dist = cv2.distanceTransform(255 - (land > 127).astype(np.uint8) * 255, cv2.DIST_L2, 5)
    rip = sum(np.exp(-((dist - k * 22) / 1.6) ** 2) * (0.28 - 0.07 * k) for k in (1, 2, 3))
    sea = sea + rip[..., None] * np.array([0.35, 0.40, 0.42], np.float32)
    landc = np.array([0.86, 0.75, 0.56], np.float32) * (0.90 + 0.14 * tex[..., None])
    rim = lf * (1 - cv2.GaussianBlur(lf, (0, 0), 16))
    landc = landc * (1 - 0.45 * rim[..., None])
    img = sea * (1 - lf[..., None]) + landc * lf[..., None]
    img *= (0.95 + 0.07 * fine[..., None])
    del sea, landc, dist, rip, tex, fine
    base = np.clip(img * 255, 0, 255).astype(np.uint8)
    del img
    for lon in range(-4, 25, 4):                                     # faint graticule
        x = int(cpx(lon, 50)[0])
        base[:, x - 1:x + 1] = (base[:, x - 1:x + 1] * 0.86 + 255 * 0.14).astype(np.uint8)
    for lat in range(44, 56, 4):
        y = int(cpx(0, lat)[1])
        base[y - 1:y + 1] = (base[y - 1:y + 1] * 0.86 + 255 * 0.14).astype(np.uint8)
    for p in cp:
        cv2.polylines(base, [np.round(p * 4).astype(np.int32)], True, (78, 54, 34), 3, cv2.LINE_AA, shift=2)
    for ridge in (ALPS, CARPATHIANS):                                # relief: chevron hatching along the ranges
        pts = np.array([cpx(*q) for q in ridge])
        seg = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
        rng = np.random.default_rng(4)
        for dd in np.arange(0, seg[-1], 46):
            x, y = np.array([np.interp(dd, seg, pts[:, 0]), np.interp(dd, seg, pts[:, 1])]) + rng.normal(0, 16, 2)
            sz = rng.uniform(17, 27)
            ch = np.round(np.array([(x - sz, y + sz * 0.55), (x, y - sz * 0.6), (x + sz, y + sz * 0.55)]) * 4).astype(np.int32)
            cv2.polylines(base, [ch], False, (116, 86, 56), 4, cv2.LINE_AA, shift=2)
    for river in (RHINE, DANUBE):
        pts = np.round(np.array([cpx(*q) for q in river]) * 4).astype(np.int32)
        cv2.polylines(base, [pts], False, (70, 112, 136), 5, cv2.LINE_AA, shift=2)
    pil = Image.fromarray(base)
    d = ImageDraw.Draw(pil)
    for name, lon, lat, size, col in (("FRENCH EMPIRE", 2.4, 46.9, 82, (110, 78, 50)), ("BAVARIA", 11.9, 49.7, 64, (110, 78, 50)),
                                      ("AUSTRIAN EMPIRE", 15.6, 46.6, 78, (110, 78, 50)),
                                      ("GREAT BRITAIN", -1.6, 52.4, 66, (110, 78, 50)), ("NORTH SEA", 4.0, 55.6, 72, (150, 175, 185)),
                                      ("BALTIC SEA", 17.5, 55.9, 66, (150, 175, 185)), ("ADRIATIC", 15.0, 43.2, 60, (150, 175, 185)),
                                      ("Rhine", 7.0, 50.2, 54, (60, 95, 118)), ("Danube", 12.7, 48.15, 54, (60, 95, 118))):
        f = font("Italic", size)
        x, y = cpx(lon, lat)
        tr = size * 0.35
        w = sum(f.getlength(c) for c in name) + tr * (len(name) - 1)
        xc = x - w / 2
        for c in name:
            d.text((xc, y), c, font=f, fill=col, anchor="ls")
            xc += f.getlength(c) + tr
    return np.asarray(pil).copy()


BASE = None


def get_base():
    global BASE
    if BASE is None:
        BASE = build_base()
    return BASE


def partial(path, cum, L):
    if L <= 0:
        return None
    k = int(np.searchsorted(cum, L))
    if k >= len(cum):
        return path
    f = (L - cum[k - 1]) / max(1e-9, cum[k] - cum[k - 1])
    return np.vstack([path[:k], path[k - 1] + (path[k] - path[k - 1]) * f])


def draw_arrow(roi, ox, oy, path, cum, L, col, t, T=34, head=88):
    """Progressively drawn campaign arrow with a dark outline, travelling dashes and a head at the tip."""
    if L <= 4:
        return
    body = partial(path, cum, max(1.0, L - head * 0.6))
    tip = partial(path, cum, L)
    p_end, p_prev = tip[-1], tip[max(0, len(tip) - 6)]
    d = p_end - p_prev
    d = d / (np.hypot(*d) + 1e-9)
    nrm = np.array([-d[1], d[0]])
    base_c = p_end - d * head
    tri = np.array([p_end + d * 6, base_c + nrm * head * 0.55, base_c - nrm * head * 0.55])
    off = np.array([ox, oy])
    q = lambda a: np.round((a - off) * 4).astype(np.int32)        # noqa: E731
    dark = (28, 26, 34)
    sh = np.array([7.0, 9.0])
    # soft shadow (blend only inside the arrow's bounding box)
    allp = np.vstack([body, tri]) - off + sh
    bx0, by0 = np.maximum(0, allp.min(0).astype(int) - T * 2)
    bx1, by1 = allp.max(0).astype(int) + T * 2
    bx1, by1 = min(roi.shape[1], bx1), min(roi.shape[0], by1)
    if bx1 > bx0 and by1 > by0:
        m = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
        o2 = off - sh + np.array([bx0, by0])
        qq = lambda a: np.round((a - o2) * 4).astype(np.int32)    # noqa: E731
        cv2.polylines(m, [qq(body)], False, 255, T + 10, cv2.LINE_AA, shift=2)
        cv2.fillPoly(m, [qq(tri)], 255, cv2.LINE_AA, shift=2)
        m = cv2.GaussianBlur(m, (0, 0), 6).astype(np.float32)[..., None] * (0.42 / 255)
        sub = roi[by0:by1, bx0:bx1].astype(np.float32)
        roi[by0:by1, bx0:bx1] = (sub * (1 - m)).astype(np.uint8)
    c255 = tuple(int(255 * v) for v in col)
    light = tuple(int(255 * min(1.0, v * 0.45 + 0.6)) for v in col)
    cv2.polylines(roi, [q(body)], False, dark, T + 12, cv2.LINE_AA, shift=2)
    cv2.fillPoly(roi, [q(tri)], dark, cv2.LINE_AA, shift=2)
    cv2.polylines(roi, [q(tri)], True, dark, 10, cv2.LINE_AA, shift=2)
    cv2.polylines(roi, [q(body)], False, c255, T, cv2.LINE_AA, shift=2)
    cv2.fillPoly(roi, [q(tri)], c255, cv2.LINE_AA, shift=2)
    # dashes travelling along the drawn body (reads as marching movement)
    ph = (150 * t) % 110
    s0 = -110 + ph
    while s0 < L - head * 1.1:
        a, b = max(0.0, s0), min(L - head * 1.1, s0 + 42)
        if b > a + 2:
            seg = partial(path, cum, b)
            ka = int(np.searchsorted(cum, a))
            seg = seg[max(0, ka - 1):]
            cv2.polylines(roi, [q(seg)], False, light, max(3, T // 3), cv2.LINE_AA, shift=2)
        s0 += 110


def draw_dot(roi, ox, oy, lon, lat, pop, r=17):
    if pop <= 0:
        return
    x, y = cpx(lon, lat)
    c = (int((x - ox) * 4), int((y - oy) * 4))
    rr = max(1, int(r * backout(pop) * 4))
    cv2.circle(roi, c, rr + 22, (28, 26, 34), -1, cv2.LINE_AA, shift=2)
    cv2.circle(roi, c, rr, (247, 237, 214), -1, cv2.LINE_AA, shift=2)


def draw_ring(roi, ox, oy, lon, lat, p, pulse, col):
    x, y = cpx(lon, lat)
    c = (int((x - ox) * 4), int((y - oy) * 4))
    c255 = tuple(int(255 * v) for v in col)
    for a0 in range(-90, int(-90 + 360 * easeout(p)), 24):           # dashed ring drawing itself
        cv2.ellipse(roi, c, (108 * 4, 108 * 4), 0, a0, a0 + 15, c255, 10, cv2.LINE_AA, shift=2)
    if 0 < pulse < 1:
        r = int((110 + 150 * easeout(pulse)) * 4)
        sub = roi.copy()
        cv2.circle(sub, c, r, c255, 6, cv2.LINE_AA, shift=2)
        k = 1 - pulse
        roi[:] = (roi * (1 - k) + sub * k).astype(np.uint8)


def draw_star(roi, ox, oy, lon, lat, p, t):
    if p <= 0:
        return
    x, y = cpx(lon, lat)
    R = 84 * backout(p)
    ang = np.linspace(0, 2 * np.pi, 17)[:-1] + 0.25 * t
    rad = np.where(np.arange(16) % 2 == 0, R, R * 0.42)
    pts = np.stack([x - ox + rad * np.cos(ang), y - oy + rad * np.sin(ang)], 1)
    q = np.round(pts * 4).astype(np.int32)
    cv2.fillPoly(roi, [q], (28, 26, 34), cv2.LINE_AA, shift=2)
    cv2.polylines(roi, [q], True, (28, 26, 34), 12, cv2.LINE_AA, shift=2)
    cv2.fillPoly(roi, [q], (240, 186, 82), cv2.LINE_AA, shift=2)
    for k in range(2):                                               # shock rings
        u = (p * 1.6 - 0.3 * k) % 1.6
        if 0 < u < 1:
            sub = roi.copy()
            cv2.circle(sub, (int((x - ox) * 4), int((y - oy) * 4)), int((R + 160 * easeout(u)) * 4), (240, 196, 110), 7, cv2.LINE_AA,
                       shift=2)
            roi[:] = (roi * u + sub * (1 - u)).astype(np.uint8)


def hermite(keys, t):
    T = [k[0] for k in keys]
    P = [np.array(k[1:], np.float64) for k in keys]
    if t <= T[0]:
        return P[0]
    if t >= T[-1]:
        return P[-1]
    i = max(j for j in range(len(T) - 1) if T[j] <= t)
    def tan(j):
        if j == 0:
            return P[0] * 0
        if j == len(T) - 1:
            return (P[j] - P[j - 1]) / (T[j] - T[j - 1])
        return (P[j + 1] - P[j - 1]) / (T[j + 1] - T[j - 1])
    h = T[i + 1] - T[i]
    s = (t - T[i]) / h
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * P[i] + h10 * h * tan(i) + h01 * P[i + 1] + h11 * h * tan(i + 1)


MAP_CAM = [(0.0, 8.2, 9.0, math.log(9.0)), (1.9, 9.6, 9.1, math.log(9.0)), (3.3, 12.6, 9.2, math.log(9.2)),
           (4.3, 14.6, 9.0, math.log(7.4)), (6.0, 15.23, 8.87, math.log(2.0))]
# arrow legs: (start, end) in shot time, French route waypoints 0>3>5>9>11
LEGS = [(0.35, 1.25, 0, 1), (1.25, 1.95, 1, 2), (2.45, 3.4, 2, 3), (3.5, 4.2, 3, 4)]
DATES = [(0.0, "AUGUST 1805"), (1.0, "SEPTEMBER 1805"), (1.95, "20 OCTOBER 1805"), (3.2, "13 NOVEMBER 1805"), (4.2, "2 DECEMBER 1805")]


def fr_length(tl):
    L = 0.0
    for t0, t1, a, b in LEGS:
        if tl >= t0:
            la, lb = FR_WLEN[FR_WAY[a]], FR_WLEN[FR_WAY[b]]
            L = la + (lb - la) * ramp(tl, t0, t1)
    return L


def shot_c(tl, t):
    base = get_base()
    cx, cy, lw = hermite(MAP_CAM, tl)
    Wu = math.exp(lw)
    s = OW / (Wu * PPU)
    cxp, cyp = cx * PPU, cy * PPU
    hw, hh = Wu * PPU / 2, Wu * PPU / 2 * OH / OW
    x0, y0 = max(0, int(cxp - hw) - 6), max(0, int(cyp - hh) - 6)
    x1, y1 = min(CW, int(cxp + hw) + 7), min(CH, int(cyp + hh) + 7)
    roi = base[y0:y1, x0:x1].copy()
    L = fr_length(tl)
    draw_ring(roi, x0, y0, *CITIES["ULM"], ramp(tl, 1.95, 2.45), (tl - 2.2) / 0.8, CRED)
    co_L = CO_CUM[-1] * ramp(tl, 2.95, 4.15)
    draw_arrow(roi, x0, y0, CO_PATH, CO_CUM, co_L, CRED, tl, T=30, head=80)
    draw_arrow(roi, x0, y0, FR_PATH, FR_CUM, L, FBLUE, tl)
    pops = {"BOULOGNE": (tl - 0.15) / 0.35}
    for name, t0 in (("STRASBOURG", 1.2), ("ULM", 1.9), ("VIENNA", 3.35)):
        pops[name] = (tl - t0) / 0.35
    pops["OLMÜTZ"] = (tl - 4.0) / 0.35
    for name, p in pops.items():
        draw_dot(roi, x0, y0, *CITIES[name], p, r=14 if name == "OLMÜTZ" else 17)
    draw_star(roi, x0, y0, *CITIES["AUSTERLITZ"], (tl - 4.15) / 0.45, tl)
    # resample: area-average down to about the target scale, then a sub-pixel affine fit
    if s < 0.95:
        small = cv2.resize(roi, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        fx_, fy_ = small.shape[1] / roi.shape[1], small.shape[0] / roi.shape[0]
    else:
        small, fx_, fy_ = roi, 1.0, 1.0
    M = np.float32([[s / fx_, 0, OW / 2 + s * (x0 - cxp)], [0, s / fy_, OH / 2 + s * (y0 - cyp)]])
    img = cv2.warpAffine(small, M, (OW, OH), flags=cv2.INTER_CUBIC if s >= 0.95 else cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REFLECT).astype(np.float32) / 255
    proj = lambda lon, lat: (s * (cpx(lon, lat)[0] - cxp) + OW / 2, s * (cpx(lon, lat)[1] - cyp) + OH / 2)   # noqa: E731
    # Austerlitz glow
    sp = (tl - 4.15) / 0.45
    if sp > 0:
        ax, ay = proj(*CITIES["AUSTERLITZ"])
        g = np.exp(-(((XO - ax) / 90) ** 2 + ((YO - ay) / 90) ** 2)) * 0.35 * min(1.0, sp)
        img += g[..., None] * np.array([1.0, 0.72, 0.35], np.float32)
    img = scrim(img, 0, 340, 0.8, top=True)
    img = scrim(img, 900, 1280, 0.45)
    o = Overlay()
    fade = 1 - ramp(tl, 5.3, 5.7)
    # city labels (screen-constant size, pinned to the map)
    def lab(name, dx, dy, size, col, tt, align="c", style="Bold", track=2):
        x, y = proj(*CITIES[name])
        o.add(letters(name, font(style, size), x + dx, y + dy, track, tt, align=align,
                      stagger=0.02, rise=8, alpha=fade), col, 0.85)
    lab("BOULOGNE", 0, -26, 27, IVORY, tl - 0.2)
    lab("STRASBOURG", -20, 44, 27, IVORY, tl - 1.25, align="r")
    x, y = proj(*CITIES["ULM"])
    o.add(letters("ULM · 20 OCT", font("Bold", 29), x, y - 84, 2, tl - 1.95, stagger=0.02, rise=8, alpha=fade), IVORY, 0.85)
    o.add(letters("Austrian army surrenders", font("Italic", 25), x, y - 54, 0, tl - 2.25, stagger=0.0, rise=6, alpha=fade), GOLD, 0.85)
    lab("VIENNA", 0, 48, 27, IVORY, tl - 3.4)
    o.add(letters("13 NOV", font("Bold", 23), proj(*CITIES["VIENNA"])[0], proj(*CITIES["VIENNA"])[1] + 75, 2, tl - 3.55,
                  stagger=0.02, rise=6, alpha=fade), GOLD, 0.85)
    lab("OLMÜTZ", 16, -22, 23, IVORY, tl - 4.05, align="l")
    lab("AUSTERLITZ", -58, 12, 36, GOLD, tl - 4.3, align="r", track=3)
    # date ticker + kicker
    o.add(letters("THE MARCH TO AUSTERLITZ", font("Bold", 22), OW / 2, 176, 6, tl - 0.1, stagger=0.015, alpha=fade), GOLD, 0.5)
    for i, (td, txt) in enumerate(DATES):
        tn = DATES[i + 1][0] if i + 1 < len(DATES) else 99
        if td <= tl < tn:
            a_in, a_out = ease((tl - td) / 0.25), ease((tl - tn + 0.18) / 0.18)   # old date leaves before the new one rises
            a = a_in * (1 - a_out) * fade
            if a > 0.003:
                o.add(letters(txt, font("Bold", 52), OW / 2, 240 + 26 * (1 - a_in) - 26 * a_out, 4, 99, alpha=a, rise=0), IVORY, 0.6)
    # legend
    for k, (txt, col, t0) in enumerate((("FRENCH GRANDE ARMÉE", FBLUE, 0.5), ("RUSSIAN & AUSTRIAN ARMIES", CRED, 2.95))):
        a = ease((tl - t0) / 0.4) * fade
        if a > 0:
            sw = np.zeros((OH, OW), np.float32)
            yb = 968 + 38 * k
            sw[yb - 12:yb - 2, 70:112] = a
            o.add(sw, col, 0.5)
            o.add(letters(txt, font("Bold", 23), 124, yb, 2, 99, align="l", alpha=a, rise=0), IVORY, 0.6)
    return o.apply(img)


# ------------------------------------------------------------------------------------------- timeline
def render(t):
    if t < CUT_AB:
        img = shot_a(t, t)
    elif t < CUT_BC - 0.25:
        img = shot_b(t - CUT_AB, t)
    elif t < CUT_BC + 0.25:                                          # painted ink wipe B > C
        p = (t - (CUT_BC - 0.25)) / 0.5
        b, c = shot_b(t - CUT_AB, t), shot_c(t - CUT_BC, t)
        dg = (XO / OW) * 0.55 + (1 - YO / OH) * 0.45
        e = ease(p) * 1.3 - 0.15 - dg + 0.12 * (WIPE_NOISE - 0.5)
        m = np.clip(e / 0.012 + 0.5, 0, 1)[..., None]
        img = b * (1 - m) + c * m + (np.exp(-(e / 0.007) ** 2) * 0.3)[..., None] * GOLD
    elif t < CUT_CD:
        img = shot_c(t - CUT_BC, t)
        f = ramp(t, CUT_CD - 0.4, CUT_CD) ** 2 * 0.92                  # flash at the end of the push into the star
        img = img * (1 - f) + np.array([1.0, 0.93, 0.78], np.float32) * f
    else:
        img = shot_d(t - CUT_CD, t)
        f = (1 - ease((t - CUT_CD) / 0.4)) * 0.92
        img = img * (1 - f) + np.array([1.0, 0.93, 0.78], np.float32) * f
    img = img * VIGNETTE
    img = img * (1 - ramp(t, DUR - 0.65, DUR - 0.03))                 # fade to black
    g = np.random.default_rng(int(t * FPS + 0.5)).normal(0, 0.008, (OH, OW, 1)).astype(np.float32)
    return np.clip(img + g, 0, 1)


def _work(i):
    return (render(i / FPS) * 255 + 0.5).astype(np.uint8).tobytes()


AUDIO = {"duration": DUR, "audio": {
    "music": {"seed": 5, "root_hz": 110.0, "mode": "minor", "drum_from": 9.0, "drum_to": 15.0},
    "music_level": 1.0, "sfx_level": 0.8,
    "sfx": [{"type": "wind", "start": 0.0, "end": 9.3, "gain": 0.35},
            {"type": "whoosh", "start": 3.92, "gain": 0.6},
            {"type": "whoosh", "start": 8.5, "gain": 0.45},
            {"type": "drum", "start": 9.0, "end": 14.9, "period": 0.5, "gain": 0.3},
            {"type": "march", "start": 9.2, "end": 14.9, "gain": 0.25},
            {"type": "cannon", "start": 15.0, "gain": 0.8},
            {"type": "cannon", "start": 15.9, "gain": 0.5, "dist": 0.7},
            {"type": "volley", "start": 16.4, "end": 17.6, "gain": 0.28},
            {"type": "cannon", "start": 17.3, "gain": 0.45, "dist": 0.6},
            {"type": "cannon", "start": 18.6, "gain": 0.4, "dist": 0.6},
            {"type": "flutter", "start": 15.0, "end": 20.0, "gain": 0.22},
            {"type": "wind", "start": 15.0, "end": 20.0, "gain": 0.3}]}}


def save(img, path):
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255
    cv2.imwrite(path, cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))


def qc():
    q = os.path.join(ROOT, "qc")
    times = [0.5, 2.5, 4.0, 5.5, 7.0, 8.5, 9.6, 10.8, 12.0, 13.4, 14.6, 15.6, 17.0, 18.6, 19.5]
    tiles = []
    for t in times:
        im = render(t)
        th = (cv2.resize(im, (240, 427), interpolation=cv2.INTER_AREA) * 255).astype(np.uint8)
        cv2.putText(th, f"{t:.1f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(th)
    rows = [np.hstack(tiles[i:i + 5]) for i in range(0, 15, 5)]
    save(np.vstack(rows), os.path.join(q, "contact_sheet.png"))
    for name, t in (("A_wide", 2.5), ("B_portrait", 6.5), ("C_map", 12.6), ("D_battlefield", 17.0)):
        save(render(t), os.path.join(q, f"shot_{name}.png"))
    # blink: eye region at output scale, frames 7.30-7.80 s
    fr = []
    for k in range(-4, 13):
        t = 7.42 + k / FPS
        im = render(t)
        fr.append((cv2.resize(im[300:560, 180:560], (285, 195), interpolation=cv2.INTER_AREA) * 255).astype(np.uint8))
        cv2.putText(fr[-1], f"{t:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    pad = [np.zeros_like(fr[0])] * ((6 - len(fr) % 6) % 6)
    fr += pad
    save(np.vstack([np.hstack(fr[i:i + 6]) for i in range(0, len(fr), 6)]), os.path.join(q, "blink_sequence.png"))
    print("qc written to", q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=float)
    ap.add_argument("--qc", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.still is not None:
        p = os.path.join(ROOT, "qc", f"still_{a.still:.2f}.png")
        save(render(a.still), p)
        print(p)
        return
    if a.qc:
        qc()
        return
    get_base()                                                       # build once; workers share it after fork
    from mosaic.audio import build_mix
    wav = os.path.join(HERE, "mix.wav")
    build_mix(ROOT, AUDIO, wav)
    out = os.path.join(ROOT, "final", "Napoleon_20s_POC_720p.mp4")
    n = int(round(FPS * DUR))
    t0 = time.time()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
    with ctx.Pool(a.workers) as pool:
        for k, buf in enumerate(pool.imap(_work, range(n), chunksize=2)):
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"frame {k}/{n} {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print(f"wrote {out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

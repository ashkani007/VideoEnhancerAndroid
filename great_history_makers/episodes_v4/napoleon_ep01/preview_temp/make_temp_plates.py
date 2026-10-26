#!/usr/bin/env python3
"""TEMPORARY stand-in plates for the Napoleon Ep01 preview (NOT final artwork).

The cloud container cannot generate illustrations (no GPU; model hosts blocked), and only one approved illustration
exists. The beats whose ComfyUI illustration is still pending get a painted ENVIRONMENT stand-in here: light, sky,
architecture and weather only, never a code-drawn character (house rule). Each one carries a visible
"TEMP" label in the storyboard. Replace them with the picked ComfyUI plates (`python -m ghm4.episode plates`).

v2 (2026-10-26, after the visual audit): real pointed arches and rose-window tracery, irregular firelit windows,
soft snow horizon without floating props, water drawn as horizontal wave streaks (no blob noise), title-safe sky
in the closing plate. The water moves through a `wind` ripple region instead of a `smoke` band.

  python episodes_v4/napoleon_ep01/preview_temp/make_temp_plates.py     (from great_history_makers/)
"""
import json
import math
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, GHM)
from ghm4.plate import periodic_resize, tileable_noise  # noqa: E402

W, H = 1080, 1920
OUT = os.path.join(HERE, "plates")
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def noise(sigma, seed, h=240, w=135):
    return periodic_resize(tileable_noise(h, w, sigma, seed), W, H)


def streaks(seed, h=480, w=34, sigma=1.2):
    """Horizontal wave streaks: noise that is long in x and short in y (water, cloud bands)."""
    return periodic_resize(tileable_noise(h, w, sigma, seed), W, H)


def vgrad(stops):
    """stops: [(y_frac, (r, g, b)), ...] -> HxWx3 float."""
    ys = np.array([s[0] for s in stops]) * H
    cols = np.array([s[1] for s in stops], np.float32)
    col = np.stack([np.interp(np.arange(H), ys, cols[:, c]) for c in range(3)], 1)
    return np.repeat(col[:, None, :], W, 1).astype(np.float32)


def mask(pts, blur=0.0):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.array(pts) * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
    m = m.astype(np.float32) / 255
    return cv2.GaussianBlur(m, (0, 0), blur) if blur else m


def fill(img, pts, col, alpha=1.0, blur=0.0):
    m = mask(pts, blur)
    a = (m * alpha)[..., None]
    img[:] = img * (1 - a) + np.asarray(col, np.float32) * a
    return m


def blend(img, m, col, alpha=1.0):
    a = (np.clip(m, 0, 1) * alpha)[..., None]
    img[:] = img * (1 - a) + np.asarray(col, np.float32) * a


def glow(img, x, y, r, col, amp, sy=None):
    g = np.exp(-(((XX - x) / r) ** 2 + ((YY - y) / (sy or r)) ** 2)) * amp
    img += g[..., None] * np.asarray(col, np.float32)


def paint(img, seed, strength=0.04):
    """Painterly finish: brush-scale value noise and a soft edge-preserving pass (no posterize: it bands gradients)."""
    n = noise(3, seed) - 0.5
    img = img * (1 + strength * 2 * n[..., None])
    u8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    u8 = cv2.bilateralFilter(u8, 7, 30, 7)
    return np.clip(u8.astype(np.float32) / 255, 0, 1)


def save(name, img, meta):
    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(os.path.join(OUT, name + ".png"), cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    meta = dict({"ref_width": W, "temp_standin": True}, **meta)
    json.dump(meta, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(name)


def pointed_arch(cx, spring, half, n=24):
    """Outline (open at the bottom) of an equilateral pointed arch springing at y=spring, span 2*half."""
    r = 2 * half                                                  # each arc's radius = span (equilateral arch)
    apex = spring - math.sqrt(r * r - half * half)
    left, right = [], []
    for u in np.linspace(0, 1, n):
        y = spring + (apex - spring) * u
        dx = math.sqrt(max(0.0, r * r - (y - spring) ** 2))          # arc centred on the opposite springing point
        left.append((cx + half - dx, y))
        right.append((cx - half + dx, y))
    return left + right[::-1], apex


def water(img, horizon, seed, sun_x, base, glint, night=False):
    """Sea below the horizon: perspective-compressed wave streaks, a glitter path under the light source."""
    yy = np.clip((YY - horizon) / (H - horizon), 0, 1)
    depth = yy ** 0.6
    sea = np.asarray(base[0], np.float32) * (1 - depth[..., None]) + np.asarray(base[1], np.float32) * depth[..., None]
    rows = (horizon + (H - horizon) * ((np.arange(H) - horizon).clip(0) / (H - horizon)) ** 1.7).astype(np.float32)
    st = streaks(seed)
    st = cv2.remap(st, XX, np.repeat(rows[:, None], W, 1), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    wave = (st - 0.5) * (0.10 + 0.25 * depth)
    sea = sea * (1 + wave[..., None] * 1.4)
    path = np.exp(-((XX - sun_x) / (40 + 330 * depth)) ** 2)
    sparkle = np.clip((st - 0.52) / 0.08, 0, 1) * path * (0.6 + 0.4 * depth)
    sea += sparkle[..., None] * np.asarray(glint, np.float32)
    below = (YY >= horizon)[..., None]
    img[:] = np.where(below, sea, img)
    hl = np.exp(-((YY - horizon) / 3.0) ** 2) * (0.25 if not night else 0.12)     # soft horizon line
    img += hl[..., None] * np.asarray(glint, np.float32) * 0.6


# ------------------------------------------------------------------------------------------- 1. Notre-Dame nave, 1804
def coronation():
    img = vgrad([(0, (0.09, 0.06, 0.06)), (0.45, (0.20, 0.13, 0.10)), (1, (0.10, 0.06, 0.05))])
    vx, vy = W / 2, 900                                             # vanishing point (the altar)
    glow(img, vx, vy - 60, 330, (1.0, 0.76, 0.42), 0.50, 420)
    stone = np.array([0.36, 0.27, 0.21])
    # receding bays: columns (lit inner edge) and pointed arches between them
    xs = [(vx - (90 + 470 * 0.74 ** i), vx + (90 + 470 * 0.74 ** i), 0.74 ** i) for i in range(8)]
    for i in range(7, -1, -1):
        xl, xr, d = xs[i]
        top, bot = vy - 980 * d - 40, vy + 1000 * d + 30
        w = 20 + 80 * d
        shade = stone * (0.35 + 0.6 * d)
        for xc, side in ((xl, -1), (xr, 1)):
            fill(img, [(xc - w / 2, top), (xc + w / 2, top), (xc + w / 2, bot), (xc - w / 2, bot)], shade)
            edge = xc - side * w / 2                                 # edge facing the altar light
            fill(img, [(edge - side * w * 0.22, top), (edge, top), (edge, bot), (edge - side * w * 0.22, bot)],
                 np.minimum(1, shade * 1.0 + np.array([0.22, 0.15, 0.08]) * d), 0.9)
        if True:                                                     # transverse rib: pointed arch across the nave
            arch, apex = pointed_arch(vx, top, (xr - xl) / 2 - w * 0.3)
            m = np.zeros((H, W), np.uint8)
            cv2.polylines(m, [np.round(np.array(arch) * 4).astype(np.int32)], False, 255, max(2, int(6 + 30 * d)) * 4,
                          cv2.LINE_AA, shift=2)
            blend(img, m.astype(np.float32) / 255, shade * 1.1)
        if i < 7:
            xl2, xr2, d2 = xs[i + 1]
            # triforium band between the arcade and the clerestory
            fill(img, [(xl, vy - 600 * d), (xl2, vy - 600 * d2), (xl2, vy - 560 * d2), (xl, vy - 560 * d)], shade * 0.8)
            fill(img, [(xr2, vy - 600 * d2), (xr, vy - 600 * d), (xr, vy - 560 * d), (xr2, vy - 560 * d2)], shade * 0.8)
    # rose window: radial tracery, twelve lights, coloured glass, stone ring
    cx, cy, R = vx, 270, 165
    glow(img, cx, cy, R * 1.5, (0.85, 0.45, 0.35), 0.30)
    rr, ang = np.hypot(XX - cx, YY - cy), np.arctan2(YY - cy, XX - cx)
    sector = (ang + math.pi) / (2 * math.pi) * 12
    k = np.floor(sector)
    palette = np.array([[0.20, 0.30, 0.75], [0.75, 0.15, 0.18], [0.85, 0.65, 0.20], [0.20, 0.50, 0.35]], np.float32)
    glass = palette[(k.astype(int) + (rr > 0.62 * R).astype(int)) % 4]
    glass = glass * (0.75 + 0.25 * np.cos((sector - k - 0.5) * math.pi))[..., None]
    inside = (rr < R) & (rr > 26)
    img[inside] = glass[inside] * 1.05
    tracery = (np.abs(sector - np.round(sector)) < 0.035 * R / np.maximum(rr, 1) * 6) | (np.abs(rr - 0.62 * R) < 4) | (rr <= 26) | \
              ((rr > R - 9) & (rr < R + 9))
    img[tracery & (rr < R + 9)] = np.array([0.22, 0.16, 0.13], np.float32)
    # clerestory light shafts
    for sx, ang0 in ((250, 0.40), (830, -0.40), (400, 0.22), (680, -0.22)):
        d = (XX - sx) * math.cos(ang0) - (YY - 160) * math.sin(ang0)
        shaft = np.exp(-(d / 50) ** 2) * np.clip((YY - 160) / 900, 0, 1) * np.clip(1 - (YY - 1350) / 450, 0, 1)
        img += (shaft * 0.09)[..., None] * np.array([1.0, 0.86, 0.62], np.float32)
    # floor tiles in perspective, red carpet, gilded altar with cross, candles
    fl = (YY > vy + 30)
    u = (XX - vx) / np.maximum(YY - vy, 1) * 260
    vv = 4000 / np.maximum(YY - vy, 1)
    checker = ((np.floor(u / 60) + np.floor(vv / 8)) % 2)
    tile = np.array([0.30, 0.24, 0.20]) * (0.86 + 0.06 * checker[..., None])
    img[fl] = tile[fl]
    fill(img, [(vx - 40, vy + 34), (vx + 40, vy + 34), (vx + 320, H), (vx - 320, H)], (0.50, 0.08, 0.07))
    fill(img, [(vx - 30, vy + 34), (vx + 30, vy + 34), (vx + 240, H), (vx - 240, H)], (0.62, 0.12, 0.09))
    fill(img, [(vx - 150, vy - 20), (vx + 150, vy - 20), (vx + 160, vy + 36), (vx - 160, vy + 36)], (0.62, 0.46, 0.20))
    fill(img, [(vx - 150, vy - 20), (vx + 150, vy - 20), (vx + 150, vy - 8), (vx - 150, vy - 8)], (0.90, 0.74, 0.36))
    fill(img, [(vx - 9, vy - 230), (vx + 9, vy - 230), (vx + 9, vy - 20), (vx - 9, vy - 20)], (0.88, 0.70, 0.32))
    fill(img, [(vx - 55, vy - 190), (vx + 55, vy - 190), (vx + 55, vy - 172), (vx - 55, vy - 172)], (0.88, 0.70, 0.32))
    glow(img, vx, vy - 180, 60, (1.0, 0.85, 0.5), 0.25)
    candles = []
    for i, x in enumerate(np.linspace(vx - 130, vx + 130, 8)):
        if abs(x - vx) < 20:
            continue
        fill(img, [(x - 4, vy - 70), (x + 4, vy - 70), (x + 4, vy - 20), (x - 4, vy - 20)], (0.95, 0.90, 0.80))
        glow(img, x, vy - 80, 7, (1.0, 0.85, 0.45), 1.0, 11)
        candles.append({"x": float(x), "y": vy - 80, "r": 36, "amp": 0.09, "color": [1.0, 0.7, 0.35], "phase": i * 1.7})
    img = paint(img, 11)
    save("temp_b02_coronation", img, {"flicker": candles + [{"x": vx, "y": vy, "r": 280, "amp": 0.05, "color": [1.0, 0.75, 0.4]}],
                                      "particles": [{"kind": "ash", "box": [200, 120, 880, 1500], "count": 80, "size": 1.5,
                                                     "speed": 9, "seed": 4}]})


# ------------------------------------------------------------------------------------------- 2. Moscow burning, Sept 1812
def moscow():
    img = vgrad([(0, (0.05, 0.03, 0.06)), (0.28, (0.25, 0.08, 0.06)), (0.50, (0.80, 0.32, 0.11)), (0.585, (0.98, 0.58, 0.22)),
                 (0.60, (0.98, 0.58, 0.22)), (1, (0.98, 0.58, 0.22))])
    horizon = 1150
    sm = noise(12, 5)
    smoke_a = np.clip((sm - 0.40) / 0.30, 0, 1) * np.clip((horizon - YY) / 650, 0, 1) * np.clip(YY / 250, 0, 1) * 0.7
    blend(img, smoke_a, (0.17, 0.08, 0.07))
    for x, amp in ((260, 0.55), (620, 0.75), (930, 0.5)):
        glow(img, x, horizon - 30, 260, (1.0, 0.45, 0.12), amp, 170)
    sil = (0.08, 0.035, 0.035)
    rng = np.random.default_rng(8)
    city = np.zeros((H, W), np.float32)

    def add(pts):
        np.maximum(city, mask(pts), out=city)
    x = -20
    while x < W + 40:                                               # low wooden houses, gabled
        w, h = rng.uniform(46, 96), rng.uniform(38, 95)
        add([(x, horizon), (x, horizon - h), (x + w / 2, horizon - h - w * 0.32), (x + w, horizon - h), (x + w, horizon)])
        x += w * rng.uniform(0.75, 1.0)
    add([(0, horizon - 110), (600, horizon - 125), (600, horizon), (0, horizon)])            # Kremlin wall
    for b in range(0, 600, 30):                                                            # swallow-tail merlons
        add([(b, horizon - 122), (b + 16, horizon - 122), (b + 16, horizon - 142), (b + 8, horizon - 134), (b, horizon - 142)])
    for i, tx in enumerate((50, 200, 370, 545)):                                           # tented towers
        hgt = 250 + 50 * (i % 2)
        add([(tx - 34, horizon - 110), (tx - 34, horizon - hgt), (tx - 26, horizon - hgt - 20), (tx + 26, horizon - hgt - 20),
             (tx + 34, horizon - hgt), (tx + 34, horizon - 110)])
        add([(tx - 28, horizon - hgt - 20), (tx, horizon - hgt - 170), (tx + 28, horizon - hgt - 20)])
        add([(tx - 2, horizon - hgt - 170), (tx + 2, horizon - hgt - 170), (tx + 2, horizon - hgt - 200), (tx - 2, horizon - hgt - 200)])
    bx = 720                                                         # Ivan the Great bell tower: stacked octagonal tiers
    tiers = [(56, 0, 230), (48, 230, 360), (40, 360, 470), (32, 470, 560), (24, 560, 620)]
    for hw, y0, y1 in tiers:
        add([(bx - hw, horizon - y0), (bx - hw, horizon - y1), (bx + hw, horizon - y1), (bx + hw, horizon - y0)])
        add([(bx - hw - 6, horizon - y1), (bx + hw + 6, horizon - y1), (bx + hw + 6, horizon - y1 - 10), (bx - hw - 6, horizon - y1 - 10)])
    dome = [(bx + 26 * math.sin(a) * (1 - 0.25 * max(0, -math.cos(a))), horizon - 640 - 34 * (1 - math.cos(a)) * 0.9)
            for a in np.linspace(-math.pi, math.pi, 40)]
    add(dome)
    add([(bx - 3, horizon - 700), (bx + 3, horizon - 700), (bx + 3, horizon - 760), (bx - 3, horizon - 760)])
    for dx, dh, dr in ((860, 300, 40), (935, 360, 34), (1010, 290, 44), (800, 250, 30)):  # onion domes on drums
        add([(dx - dr * 0.75, horizon), (dx - dr * 0.75, horizon - dh), (dx + dr * 0.75, horizon - dh), (dx + dr * 0.75, horizon)])
        pts = []
        for t in np.linspace(0, 1, 30):                              # onion profile: bulge, then a pinched tip
            r = dr * (math.sin(math.pi * t) ** 0.8) * (1.15 - 0.6 * t)
            pts.append((dx - r, horizon - dh - t * dr * 2.4))
        add(pts + [(2 * dx - p[0], p[1]) for p in pts[::-1]])
        add([(dx - 2, horizon - dh - dr * 2.4), (dx + 2, horizon - dh - dr * 2.4), (dx + 2, horizon - dh - dr * 3.1),
             (dx - 2, horizon - dh - dr * 3.1)])
    blend(img, city, sil)
    # firelit windows: few, irregular, glowing (not a grid)
    win = np.zeros((H, W), np.float32)
    for _ in range(70):
        x, y = rng.uniform(0, W), rng.uniform(horizon - 95, horizon - 18)
        if city[int(y), int(min(W - 1, x))] > 0.5:
            cv2.ellipse(win, (int(x), int(y)), (int(rng.uniform(2, 4)), int(rng.uniform(3, 6))), 0, 0, 360, rng.uniform(0.5, 1.0), -1, cv2.LINE_AA)
    win = cv2.GaussianBlur(win, (0, 0), 1.2) + cv2.GaussianBlur(win, (0, 0), 6) * 0.8
    img += win[..., None] * np.array([1.0, 0.55, 0.18], np.float32)
    # flames licking the roofline (soft, from noise), brightest behind the silhouettes
    fl = noise(1.8, 13, 480, 270)
    roof = cv2.GaussianBlur((city > 0.5).astype(np.float32), (0, 0), 3)
    edge = np.clip(cv2.GaussianBlur(roof, (0, 0), 14) - roof, 0, 1) * 3
    flames = np.clip((fl - 0.45) / 0.2, 0, 1) * np.clip(edge, 0, 1) * (YY < horizon) * (YY > horizon - 420)
    img += flames[..., None] * np.array([1.0, 0.55, 0.16], np.float32) * 0.8
    # river Moskva: rippled, darkened reflection of the burning city
    ref = cv2.flip(img[horizon - (H - horizon):horizon], 0)
    st = streaks(31, 600, 30, 1.0)[horizon:]
    dxm = ((st - 0.5) * 30).astype(np.float32)
    yy_, xx_ = np.mgrid[0:H - horizon, 0:W].astype(np.float32)
    ref = cv2.remap(ref, xx_ + dxm, yy_, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ref = cv2.GaussianBlur(ref, (0, 0), 2.0) * (0.42 - 0.18 * (yy_ / (H - horizon)))[..., None]
    ref *= (0.8 + 0.5 * st[..., None])
    img[horizon:] = np.clip(ref, 0, 1)
    fill(img, [(0, 1700), (W, 1650), (W, H), (0, H)], (0.05, 0.03, 0.03), blur=6)       # near bank
    img = paint(img, 12)
    save("temp_b06_moscow", img, {
        "sky": {"y": 880, "drift": 2.0},
        "smoke_column": [{"x": 330, "y": 960, "sx": 80, "sy": 160}, {"x": 880, "y": 930, "sx": 90, "sy": 170}],
        "flicker": [{"x": 300, "y": 1110, "r": 260, "amp": 0.14, "color": [1.0, 0.45, 0.12]},
                    {"x": 760, "y": 1100, "r": 300, "amp": 0.16, "color": [1.0, 0.5, 0.15], "phase": 2.0}],
        "wind": [{"box": [0, horizon + 20, W, 1640], "amp": 2.5, "rate": 0.5, "feather": 30}],
        "particles": [{"kind": "embers", "box": [0, 300, W, 1180], "count": 220, "size": 2.4, "speed": 70, "seed": 2}]})


# ------------------------------------------------------------------------------------------- 3. the retreat, winter 1812
def retreat():
    img = vgrad([(0, (0.38, 0.41, 0.48)), (0.40, (0.62, 0.65, 0.70)), (0.50, (0.78, 0.79, 0.82)), (0.56, (0.84, 0.85, 0.88)),
                 (1, (0.80, 0.82, 0.87))])
    cl = noise(10, 41)
    img[:1000] *= (0.80 + 0.30 * cl[:1000, :, None])
    horizon = 1000
    rng = np.random.default_rng(5)
    for yb, sc, col, alpha in ((horizon, 0.8, (0.47, 0.50, 0.56), 0.75), (horizon + 30, 1.25, (0.30, 0.33, 0.38), 0.9)):
        forest = np.zeros((H, W), np.float32)
        x = -30
        while x < W + 30:                                            # fir forest, two depth layers, base melts into mist
            h = rng.uniform(60, 150) * sc
            w = h * 0.30
            np.maximum(forest, mask([(x - w, yb + 10), (x, yb - h), (x + w, yb + 10)]), out=forest)
            x += rng.uniform(9, 26) * sc
        forest *= np.clip((yb + 12 - YY) / 40, 0, 1)                 # fade the trunks into the ground mist
        blend(img, forest, col, alpha)
    # snowfield: gentle drifts with soft blue shadows, no hard horizon
    d1 = noise(18, 43)
    ground = np.clip((YY - (horizon - 10)) / 70, 0, 1)
    snow = np.array([0.86, 0.88, 0.93], np.float32) * (0.93 + 0.09 * d1[..., None])
    shadow = np.clip((streaks(44, 300, 20, 2.5) - 0.5) * 2.2, 0, 1) * np.clip((YY - horizon) / 500, 0, 1)
    snow = snow * (1 - 0.12 * shadow[..., None]) + np.array([0.0, 0.02, 0.06], np.float32) * shadow[..., None]
    blend(img, ground, (0, 0, 0), 0)                                 # (keep sky above)
    img[:] = img * (1 - ground[..., None]) + snow * ground[..., None]
    mist = np.exp(-((YY - (horizon + 25)) / 45) ** 2) * 0.55
    img[:] = img * (1 - mist[..., None]) + np.array([0.82, 0.84, 0.88], np.float32) * mist[..., None]
    # the road: two trampled ruts converging to the horizon, slightly darker and blue-grey
    vx = 520
    for off in (-1, 1):
        m = mask([(vx + off * 4, horizon + 30), (vx + off * 10, horizon + 30), (vx + off * 190, H), (vx + off * 110, H)], blur=5)
        blend(img, m, (0.66, 0.69, 0.76), 0.45)
    # an abandoned cannon sunk in a drift (on the ground, with a contact shadow)
    gy = 1500
    blend(img, mask([(150, gy + 30), (520, gy + 10), (560, gy + 60), (160, gy + 80)], blur=14), (0.55, 0.60, 0.70), 0.5)
    fill(img, [(190, gy - 20), (470, gy - 62), (480, gy - 40), (200, gy + 2)], (0.15, 0.13, 0.12))   # barrel
    cx, cy = 300, gy - 10
    cv2.circle(img, (cx, cy), 92, (0.15, 0.13, 0.12), 12, cv2.LINE_AA)
    for a in np.linspace(0, math.pi, 7)[:-1]:
        cv2.line(img, (int(cx - 90 * math.cos(a)), int(cy - 90 * math.sin(a))), (int(cx + 90 * math.cos(a)), int(cy + 90 * math.sin(a))),
                 (0.15, 0.13, 0.12), 7, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 18, (0.15, 0.13, 0.12), -1, cv2.LINE_AA)
    drift = mask([(60, gy + 20), (260, gy - 6), (420, gy + 4), (620, gy + 40), (620, H), (60, H)], blur=16)
    img[:] = img * (1 - drift[..., None]) + snow * drift[..., None]
    for bx, bw in ((965, 26), (1045, 34)):                           # birch trunks cropped by the frame (depth cue)
        fill(img, [(bx - bw / 2, H), (bx - bw * 0.4, -10), (bx + bw * 0.4, -10), (bx + bw / 2, H)], (0.84, 0.83, 0.80))
        fill(img, [(bx + bw * 0.15, H), (bx + bw * 0.12, -10), (bx + bw * 0.4, -10), (bx + bw / 2, H)], (0.62, 0.64, 0.70))
        yk = rng.uniform(0, 80)
        while yk < H:
            ln = rng.uniform(0.3, 0.9) * bw
            x0_ = bx - bw / 2 + rng.uniform(0, bw - ln)
            fill(img, [(x0_, yk), (x0_ + ln, yk + rng.uniform(-3, 3)), (x0_ + ln, yk + rng.uniform(3, 8)), (x0_, yk + rng.uniform(3, 7))],
                 (0.17, 0.16, 0.15))
            yk += rng.uniform(40, 130)
    img = paint(img, 13, 0.03)
    save("temp_b07_retreat", img, {
        "sky": {"y": 900, "drift": 6.0},
        "particles": [{"kind": "snow", "box": [0, 0, W, H], "count": 420, "size": 3.0, "speed": 110, "wind": 60, "seed": 7},
                      {"kind": "snow", "box": [0, 0, W, H], "count": 150, "size": 5.5, "speed": 190, "wind": 110, "seed": 8}]})


# ------------------------------------------------------------------------------------------- 4. Saint Helena at dusk / night
def island_profile(x0, x1, base, height, seed):
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6, 3)
    pts = []
    for x in np.linspace(x0, x1, 80):
        u = (x - x0) / (x1 - x0)
        h = height * math.sin(math.pi * u) ** 0.65 + 0.08 * height * math.sin(u * 21 + ph[0]) + 0.05 * height * math.sin(u * 47 + ph[1])
        h = h if 0.04 < u < 0.96 else h * min(u, 1 - u) / 0.04 * 0.95      # steep cliffs at both ends
        pts.append((x, base - max(0.0, h)))
    return [(x0, base + 4)] + pts + [(x1, base + 4)]


def helena(night=False):
    if night:
        img = vgrad([(0, (0.02, 0.03, 0.06)), (0.45, (0.07, 0.09, 0.15)), (0.60, (0.13, 0.15, 0.21))])
        horizon, sun = int(0.60 * H), (250, 330)
    else:
        img = vgrad([(0, (0.13, 0.12, 0.25)), (0.30, (0.52, 0.30, 0.33)), (0.48, (0.97, 0.62, 0.33)), (0.565, (1.0, 0.80, 0.52))])
        horizon, sun = int(0.565 * H), (760, int(0.565 * H) - 40)
    cl = streaks(51 + night, 160, 20, 2.0)                           # cloud bands, long and thin
    clouds = np.clip((cl - 0.52) / 0.18, 0, 1) * np.clip((horizon - 120 - YY) / 380, 0, 1)
    if night:
        clouds *= np.clip((YY - 820) / 200, 0, 1)                    # keep the title sky (upper half) clear
    ccol = np.array([0.10, 0.12, 0.19] if night else [0.48, 0.25, 0.30], np.float32)
    blend(img, clouds, ccol, 0.75)
    if not night:
        rim = np.clip((cl - 0.52) / 0.18, 0, 1) * np.exp(-((YY - (horizon - 260)) / 160) ** 2)
        img += (rim * 0.10)[..., None] * np.array([1.0, 0.7, 0.4], np.float32)
    glow(img, *sun, 60 if not night else 34, (1.0, 0.9, 0.7) if not night else (0.92, 0.94, 1.0), 1.0)
    glow(img, *sun, 320 if not night else 200, (1.0, 0.6, 0.3) if not night else (0.35, 0.40, 0.55), 0.35)
    if night:
        rng = np.random.default_rng(9)
        for _ in range(260):
            x, y = rng.uniform(0, W), rng.uniform(0, horizon - 200)
            cv2.circle(img, (int(x), int(y)), 1, (0.85, 0.87, 1.0), -1, cv2.LINE_AA)
    if night:
        isl = island_profile(560, 1100, horizon, 280, 3)
    else:
        isl = island_profile(-20, 760, horizon, 520, 1)
    m = mask(isl)
    body = np.array([0.10, 0.08, 0.12] if not night else [0.03, 0.03, 0.05], np.float32)
    rock = noise(4, 77)
    img[:] = img * (1 - m[..., None]) + body * (0.85 + 0.3 * rock[..., None]) * m[..., None]
    if not night:
        edge = m - cv2.erode(m, np.ones((7, 7), np.uint8))
        img += (edge * 0.35)[..., None] * np.array([1.0, 0.55, 0.3], np.float32)
    else:
        glow(img, 800, horizon - 190, 5, (1.0, 0.75, 0.4), 1.0)       # one lit window (Longwood)
    base = [(0.55, 0.36, 0.38), (0.10, 0.08, 0.14)] if not night else [(0.12, 0.14, 0.20), (0.02, 0.03, 0.05)]
    water(img, horizon, 61 + night, sun[0], base, (1.0, 0.82, 0.55) if not night else (0.75, 0.80, 0.95), night)
    img = paint(img, 14 + night, 0.03)
    meta = {"sky": {"y": horizon - 120, "drift": 2.5}, "sun": {"x": sun[0], "y": sun[1], "r": 200},
            "wind": [{"box": [0, horizon + 12, W, H], "amp": 2.2, "rate": 0.45, "feather": 24}]}
    if night:
        meta["flicker"] = [{"x": 800, "y": horizon - 190, "r": 16, "amp": 0.25, "color": [1.0, 0.7, 0.35]}]
    save("temp_b15_night_sea" if night else "temp_b13_helena", img, meta)


# ------------------------------------------------------------------------------------------- 5. legacy: Arc de Triomphe
def arc():
    img = vgrad([(0, (0.12, 0.14, 0.28)), (0.35, (0.55, 0.38, 0.45)), (0.55, (0.98, 0.68, 0.38)), (0.62, (1.0, 0.82, 0.55)), (1, (0.30, 0.20, 0.18))])
    cl = streaks(71, 160, 20, 2.0)
    clouds = np.clip((cl - 0.53) / 0.2, 0, 1) * np.clip((1000 - YY) / 500, 0, 1)
    blend(img, clouds, (0.55, 0.32, 0.36), 0.6)
    glow(img, 540, 1060, 420, (1.0, 0.7, 0.35), 0.5, 260)
    base, sil = 1420, np.array([0.17, 0.11, 0.12])
    x0, x1, top = 250, 830, 640
    fill(img, [(x0, base), (x0, top), (x1, top), (x1, base)], sil)
    for yy_, hh in ((top + 70, 22), (top - 30, 30), (top + 300, 14)):                    # cornices and frieze
        fill(img, [(x0 - 14, yy_), (x1 + 14, yy_), (x1 + 14, yy_ + hh), (x0 - 14, yy_ + hh)], sil * 1.25)
    vault = [(470, base), (470, 960)] + [(540 - 70 * math.cos(a), 960 - 130 * math.sin(a)) for a in np.linspace(0, math.pi, 30)] + \
            [(610, 960), (610, base)]
    fill(img, vault, (0.98, 0.72, 0.42))
    glow(img, 540, 1150, 90, (1.0, 0.8, 0.5), 0.45, 240)
    for px in (305, 775):                                            # relief groups catching the light
        fill(img, [(px - 34, 1010), (px + 34, 1010), (px + 34, 1270), (px - 34, 1270)], sil * 1.45)
        fill(img, [(px - 34, 1010), (px - 26, 1010), (px - 26, 1270), (px - 34, 1270)], (0.55, 0.36, 0.25))
    rng = np.random.default_rng(12)
    x = -10
    while x < W + 20:                                                # mansard roofs with chimneys
        w, h = rng.uniform(70, 130), rng.uniform(80, 170)
        if not (220 < x + w and x < 860):
            col = (0.12, 0.08, 0.09)
            fill(img, [(x, base + 20), (x, base - h), (x + w * 0.15, base - h - 34), (x + w * 0.85, base - h - 34), (x + w, base - h), (x + w, base + 20)], col)
            for cxh in (x + w * 0.3, x + w * 0.7):
                fill(img, [(cxh - 5, base - h - 34), (cxh + 5, base - h - 34), (cxh + 5, base - h - 56), (cxh - 5, base - h - 56)], col)
        x += w
    fill(img, [(0, base), (W, base), (W, H), (0, H)], (0.20, 0.13, 0.12))
    fill(img, [(500, base), (580, base), (900, H), (180, H)], (0.36, 0.24, 0.20))
    for kk in range(10):                                             # avenue trees and lamps
        u = kk / 9
        for side in (-1, 1):
            lx, ly = 540 + side * (70 + 380 * u), base + 30 + 470 * u
            r = 14 + 46 * u
            cv2.circle(img, (int(lx + side * 30 * u), int(ly - 60 - 120 * u)), int(r), (0.10, 0.08, 0.08), -1, cv2.LINE_AA)
            glow(img, lx, ly - 30 - 50 * u, 5 + 9 * u, (1.0, 0.8, 0.45), 0.9)
    img = paint(img, 15, 0.03)
    save("temp_b14_arc", img, {"sky": {"y": 760, "drift": 3.0}, "sun": {"x": 540, "y": 1060, "r": 260},
                               "flicker": [{"x": 540, "y": 1120, "r": 120, "amp": 0.05, "color": [1.0, 0.8, 0.5]}]})


if __name__ == "__main__":
    # the Arc de Triomphe plate (b13) passed the visual audit, so its committed v1 file is kept; "arc" redraws it as v2
    which = sys.argv[1:] or ["coronation", "moscow", "retreat", "helena", "night"]
    for w_ in which:
        {"coronation": coronation, "moscow": moscow, "retreat": retreat, "helena": helena, "arc": arc,
         "night": lambda: helena(night=True)}[w_]()

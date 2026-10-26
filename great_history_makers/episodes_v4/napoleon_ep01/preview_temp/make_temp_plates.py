#!/usr/bin/env python3
"""TEMPORARY stand-in plates for the Napoleon Ep01 preview (NOT final artwork).

The cloud container cannot generate illustrations (no GPU; model hosts blocked), and only one approved illustration
exists. The beats whose ComfyUI illustration is still pending get a painted ENVIRONMENT stand-in here: light, sky,
architecture and weather only, never a code-drawn character (house rule). Each one carries a visible
"TEMP" label in the storyboard. Replace them with the picked ComfyUI plates (`python -m ghm4.episode plates`).

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
from ghm4.plate import tileable_noise  # noqa: E402

W, H = 1080, 1920
OUT = os.path.join(HERE, "plates")
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def noise(sigma, seed, h=240, w=135):
    return cv2.resize(tileable_noise(h, w, sigma, seed), (W, H), interpolation=cv2.INTER_CUBIC)


def vgrad(stops):
    """stops: [(y_frac, (r, g, b)), ...] -> HxWx3 float."""
    ys = np.array([s[0] for s in stops]) * H
    cols = np.array([s[1] for s in stops], np.float32)
    col = np.stack([np.interp(np.arange(H), ys, cols[:, c]) for c in range(3)], 1)
    return np.repeat(col[:, None, :], W, 1).astype(np.float32)


def fill(img, pts, col, alpha=1.0, blur=0.0):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.array(pts) * 4).astype(np.int32)], 255, cv2.LINE_AA, shift=2)
    m = m.astype(np.float32) / 255
    if blur:
        m = cv2.GaussianBlur(m, (0, 0), blur)
    a = (m * alpha)[..., None]
    img[:] = img * (1 - a) + np.asarray(col, np.float32) * a
    return m


def glow(img, x, y, r, col, amp, sy=None):
    g = np.exp(-(((XX - x) / r) ** 2 + ((YY - y) / (sy or r)) ** 2)) * amp
    img += g[..., None] * np.asarray(col, np.float32)


def paint(img, seed, strength=0.05):
    """Painterly finish: brush-scale value noise, a soft bilateral pass and a slight posterize."""
    n = noise(3, seed) - 0.5
    img = img * (1 + strength * 2 * n[..., None])
    u8 = np.clip(img * 255, 0, 255).astype(np.uint8)
    u8 = cv2.bilateralFilter(u8, 9, 40, 9)
    img = u8.astype(np.float32) / 255
    img = np.round(img * 48) / 48 * 0.35 + img * 0.65
    return np.clip(img, 0, 1)


def save(name, img, meta):
    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(os.path.join(OUT, name + ".png"), cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    meta = dict({"ref_width": W, "temp_standin": True}, **meta)
    json.dump(meta, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(name)


def gothic_arch(cx, base, top, half):
    pts = [(cx - half, base)]
    for a in np.linspace(0, 1, 14):                                 # pointed arch: two circle arcs meeting at the apex
        pts.append((cx - half + half * math.sin(a * math.pi / 2), top + (base - top) * 0.45 * (1 - math.sin(a * math.pi / 2 + math.pi / 2) ** 1)))
    pts.append((cx, top))
    for a in np.linspace(1, 0, 14):
        pts.append((cx + half - half * math.sin(a * math.pi / 2), top + (base - top) * 0.45 * (1 - math.sin(a * math.pi / 2 + math.pi / 2) ** 1)))
    pts.append((cx + half, base))
    return pts


# ------------------------------------------------------------------------------------------- 1. Notre-Dame nave, 1804
def coronation():
    img = vgrad([(0, (0.10, 0.07, 0.07)), (0.45, (0.22, 0.14, 0.10)), (1, (0.12, 0.07, 0.06))])
    vx, vy = W / 2, 880                                             # vanishing point (the altar)
    glow(img, vx, vy, 260, (1.0, 0.78, 0.45), 0.55, 330)
    # receding columns and arches on both sides
    for i in range(7):
        d = 0.78 ** i
        for side in (-1, 1):
            x = vx + side * (120 + 430 * d)
            w = 18 + 70 * d
            col = np.array([0.30, 0.22, 0.17]) * (0.45 + 0.55 * d)
            fill(img, [(x - w / 2, vy - 820 * d - 60), (x + w / 2, vy - 820 * d - 60), (x + w / 2, vy + 900 * d + 40), (x - w / 2, vy + 900 * d + 40)], col)
            if i < 6:
                x2 = vx + side * (120 + 430 * d * 0.78)
                cx, half = (x + x2) / 2, abs(x - x2) / 2
                top = vy - 900 * d - 120
                arch = gothic_arch(cx, vy - 560 * d, top, half)
                m = np.zeros((H, W), np.uint8)
                cv2.polylines(m, [np.round(np.array(arch) * 4).astype(np.int32)], False, 255, max(2, int(16 * d)) * 4, cv2.LINE_AA, shift=2)
                a = (m.astype(np.float32) / 255)[..., None]
                img[:] = img * (1 - a) + col * 1.1 * a
    # rose window above the altar
    cx, cy, R = vx, 300, 150
    glow(img, cx, cy, R * 1.3, (0.9, 0.5, 0.3), 0.35)
    rr = np.hypot(XX - cx, YY - cy)
    ang = np.arctan2(YY - cy, XX - cx)
    petals = (0.5 + 0.5 * np.cos(12 * ang)) * (rr < R) * (rr > 30)
    cols = np.stack([0.55 + 0.4 * np.cos(ang * 3), 0.25 + 0.2 * np.sin(ang * 2), 0.6 + 0.35 * np.sin(ang * 3 + 1)], -1)
    a = np.clip(petals * 0.9, 0, 1)[..., None] * (rr < R)[..., None]
    img[:] = img * (1 - a) + cols * a
    cv2.circle(img, (int(cx), int(cy)), R, (0.18, 0.12, 0.10), 10, cv2.LINE_AA)
    # light shafts from the clerestory
    for sx, ang0 in ((260, 0.42), (820, -0.42), (420, 0.2), (660, -0.2)):
        d = (XX - sx) * math.cos(ang0) - (YY - 120) * math.sin(ang0)
        shaft = np.exp(-(d / 45) ** 2) * np.clip((YY - 120) / 900, 0, 1) * np.clip(1 - (YY - 1300) / 400, 0, 1)
        img += (shaft * 0.10)[..., None] * np.array([1.0, 0.85, 0.6], np.float32)
    # red carpet to the altar, gold altar, candles
    fill(img, [(vx - 34, vy + 40), (vx + 34, vy + 40), (vx + 300, H), (vx - 300, H)], (0.52, 0.08, 0.07))
    fill(img, [(vx - 24, vy + 40), (vx + 24, vy + 40), (vx + 210, H), (vx - 210, H)], (0.62, 0.11, 0.08))
    fill(img, [(vx - 120, vy - 40), (vx + 120, vy - 40), (vx + 130, vy + 40), (vx - 130, vy + 40)], (0.70, 0.52, 0.22))
    fill(img, [(vx - 14, vy - 190), (vx + 14, vy - 190), (vx + 14, vy - 40), (vx - 14, vy - 40)], (0.82, 0.64, 0.28))
    fill(img, [(vx - 60, vy - 150), (vx + 60, vy - 150), (vx + 60, vy - 125), (vx - 60, vy - 125)], (0.82, 0.64, 0.28))
    candles = []
    for i, x in enumerate(np.linspace(vx - 110, vx + 110, 7)):
        fill(img, [(x - 4, vy - 80), (x + 4, vy - 80), (x + 4, vy - 40), (x - 4, vy - 40)], (0.95, 0.9, 0.8))
        glow(img, x, vy - 90, 9, (1.0, 0.8, 0.4), 1.0)
        candles.append({"x": float(x), "y": vy - 90, "r": 40, "amp": 0.10, "color": [1.0, 0.7, 0.35], "phase": i * 1.7})
    # imperial bees banner suggestion on the carpet edges (gold flecks)
    rng = np.random.default_rng(3)
    for _ in range(60):
        y = rng.uniform(vy + 120, H)
        sp = (y - vy) / (H - vy)
        x = vx + rng.choice([-1, 1]) * rng.uniform(0.2, 0.9) * (34 + 266 * sp)
        cv2.circle(img, (int(x), int(y)), max(1, int(5 * sp)), (0.85, 0.68, 0.25), -1, cv2.LINE_AA)
    img = paint(img, 11)
    save("temp_b02_coronation", img, {"flicker": candles + [{"x": vx, "y": vy, "r": 260, "amp": 0.05, "color": [1.0, 0.75, 0.4]}],
                                      "particles": [{"kind": "ash", "box": [200, 100, 880, 1500], "count": 90, "size": 1.6, "speed": 10, "seed": 4}]})


# ------------------------------------------------------------------------------------------- 2. Moscow burning, Sept 1812
def moscow():
    img = vgrad([(0, (0.06, 0.04, 0.07)), (0.30, (0.30, 0.09, 0.06)), (0.52, (0.85, 0.36, 0.12)), (0.60, (0.95, 0.55, 0.20)),
                 (0.62, (0.10, 0.05, 0.05)), (1, (0.05, 0.03, 0.04))])
    sky = noise(9, 21)
    img[:1180] = img[:1180] * (0.80 + 0.35 * sky[:1180, :, None])
    horizon = 1180
    # smoke masses over the fire
    sm = noise(14, 5)
    smoke_a = np.clip((sm - 0.42) / 0.25, 0, 1) * np.clip((horizon - YY) / 700, 0, 1) * np.clip(YY / 300, 0, 1) * 0.75
    img[:] = img * (1 - smoke_a[..., None]) + np.array([0.18, 0.09, 0.08], np.float32) * smoke_a[..., None]
    for x, amp in ((300, 0.6), (640, 0.8), (900, 0.5), (140, 0.4)):
        glow(img, x, horizon - 40, 220, (1.0, 0.45, 0.12), amp, 160)
    sil = (0.07, 0.03, 0.03)
    rng = np.random.default_rng(8)
    # houses
    x = -20
    while x < W + 40:
        w = rng.uniform(40, 90)
        h = rng.uniform(40, 110)
        fill(img, [(x, horizon), (x, horizon - h), (x + w / 2, horizon - h - w * 0.35), (x + w, horizon - h), (x + w, horizon)], sil)
        x += w * rng.uniform(0.8, 1.05)
    # Kremlin wall with tented towers (left), Ivan the Great bell tower, onion domes (right)
    fill(img, [(0, horizon - 120), (620, horizon - 140), (620, horizon), (0, horizon)], sil)
    for i, tx in enumerate((40, 190, 360, 540)):
        hgt = 260 + 60 * (i % 2)
        fill(img, [(tx - 32, horizon - 120), (tx - 32, horizon - hgt), (tx, horizon - hgt - 150), (tx + 32, horizon - hgt), (tx + 32, horizon - 120)], sil)
        for b in range(0, 600, 46):
            if b < 600:
                pass
    for b in range(0, 620, 34):                                     # merlons
        fill(img, [(b, horizon - 140), (b + 18, horizon - 140), (b + 18, horizon - 162), (b, horizon - 162)], sil)
    bx = 700                                                        # Ivan the Great bell tower
    fill(img, [(bx - 46, horizon), (bx - 46, horizon - 360), (bx - 36, horizon - 360), (bx - 36, horizon - 520), (bx + 36, horizon - 520),
               (bx + 36, horizon - 360), (bx + 46, horizon - 360), (bx + 46, horizon)], sil)
    fill(img, [(bx - 30, horizon - 520), (bx - 30, horizon - 620), (bx + 30, horizon - 620), (bx + 30, horizon - 520)], sil)
    cv2.ellipse(img, (bx, horizon - 650), (40, 48), 0, 0, 360, sil, -1, cv2.LINE_AA)
    fill(img, [(bx - 6, horizon - 690), (bx, horizon - 760), (bx + 6, horizon - 690)], sil)
    for dx, dh, dr in ((850, 300, 46), (930, 360, 40), (1010, 280, 52), (790, 240, 34)):  # onion domes
        fill(img, [(dx - dr * 0.8, horizon), (dx - dr * 0.8, horizon - dh), (dx + dr * 0.8, horizon - dh), (dx + dr * 0.8, horizon)], sil)
        dome = []
        for a in np.linspace(0, 2 * math.pi, 40):
            yy_ = math.sin(a)
            r = dr * (1.0 if yy_ > 0 else (1 - 0.65 * (-yy_) ** 1.6))
            dome.append((dx + r * math.cos(a), horizon - dh - dr * 0.6 - dr * 1.3 * (-yy_ if yy_ < 0 else yy_ * 0.45)))
        fill(img, dome, sil)
        fill(img, [(dx - 4, horizon - dh - dr * 2.1), (dx, horizon - dh - dr * 2.9), (dx + 4, horizon - dh - dr * 2.1)], sil)
    # windows glowing with fire, flames along the roofline
    for _ in range(140):
        x, y = rng.uniform(0, W), rng.uniform(horizon - 100, horizon - 10)
        cv2.rectangle(img, (int(x), int(y)), (int(x + 6), int(y + 9)), (1.0, 0.55, 0.18), -1)
    fl = noise(2, 13, 480, 270)
    flames = np.clip((fl - 0.5) / 0.15, 0, 1) * np.exp(-((YY - (horizon - 70)) / 60) ** 2) * (XX < W)
    img += flames[..., None] * np.array([1.0, 0.5, 0.12], np.float32) * 0.9
    # river Moskva: dark water reflecting the fire
    refl = cv2.flip(img[horizon - 500:horizon], 0)
    water = np.clip(refl * 0.45, 0, 1)
    rip = noise(1.5, 31, 960, 135)[horizon:horizon + 500]
    water *= (0.7 + 0.6 * rip[..., None])
    img[horizon:horizon + 500] = water
    fill(img, [(0, 1680), (W, 1620), (W, H), (0, H)], (0.05, 0.03, 0.03))
    img = paint(img, 12)
    save("temp_b06_moscow", img, {
        "sky": {"y": 900, "drift": 2.0},
        "smoke": [{"box": [0, 250, W, 1050], "feather": 80, "density": 1.4, "speed": 9, "color": [0.24, 0.12, 0.10]}],
        "smoke_column": [{"x": 330, "y": 980, "sx": 80, "sy": 160}, {"x": 860, "y": 940, "sx": 90, "sy": 170}],
        "flicker": [{"x": 300, "y": 1130, "r": 260, "amp": 0.16, "color": [1.0, 0.45, 0.12]},
                    {"x": 760, "y": 1120, "r": 300, "amp": 0.18, "color": [1.0, 0.5, 0.15], "phase": 2.0}],
        "particles": [{"kind": "embers", "box": [0, 300, W, 1250], "count": 260, "size": 2.6, "speed": 70, "seed": 2}]})


# ------------------------------------------------------------------------------------------- 3. the retreat, winter 1812
def retreat():
    img = vgrad([(0, (0.42, 0.45, 0.52)), (0.45, (0.70, 0.72, 0.76)), (0.52, (0.80, 0.81, 0.83)), (1, (0.90, 0.91, 0.94))])
    cl = noise(10, 41)
    img[:1000] = img[:1000] * (0.78 + 0.32 * cl[:1000, :, None])
    horizon = 980
    rng = np.random.default_rng(5)
    for row, (yb, sc, col) in enumerate(((horizon, 1.0, (0.30, 0.33, 0.38)), (horizon + 40, 1.5, (0.20, 0.22, 0.26)))):
        x = -30
        while x < W + 30:                                           # fir forest line
            h = rng.uniform(60, 150) * sc
            w = h * 0.32
            fill(img, [(x - w, yb), (x, yb - h), (x + w, yb)], col, 0.92)
            x += rng.uniform(10, 28) * sc
    snow = noise(5, 43)
    ground = (YY > horizon + 30)
    img[ground] = (np.array([0.86, 0.88, 0.92]) * (0.92 + 0.1 * snow[ground, None]))
    # the road: trampled tracks receding to the horizon
    vx = 560
    for off, wv in ((-40, 0.62), (40, 0.62), (0, 0.72)):
        fill(img, [(vx - 6 + off * 0.1, horizon + 40), (vx + 6 + off * 0.1, horizon + 40), (vx + 140 + off * 4, H), (vx - 140 + off * 4, H)],
             (wv, wv + 0.02, wv + 0.06), 0.14, blur=14)
    # abandoned gun carriage wheel and a broken cart in the snow (objects only)
    cx, cy = 300, 1520
    cv2.circle(img, (cx, cy), 120, (0.16, 0.13, 0.12), 14, cv2.LINE_AA)
    for a in np.linspace(0, math.pi, 7)[:-1]:
        cv2.line(img, (int(cx - 118 * math.cos(a)), int(cy - 118 * math.sin(a))), (int(cx + 118 * math.cos(a)), int(cy + 118 * math.sin(a))),
                 (0.16, 0.13, 0.12), 9, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 22, (0.16, 0.13, 0.12), -1, cv2.LINE_AA)
    fill(img, [(cx - 200, cy + 60), (W, cy - 10), (W, H), (cx - 200, H)], (0.88, 0.90, 0.94), 1.0, blur=18)  # snowdrift buries it
    fill(img, [(760, 1240), (940, 1215), (950, 1245), (770, 1270)], (0.18, 0.15, 0.13))
    cv2.line(img, (760, 1255), (690, 1300), (0.18, 0.15, 0.13), 8, cv2.LINE_AA)
    fill(img, [(700, 1265), (1000, 1250), (1000, 1320), (700, 1320)], (0.88, 0.90, 0.94), 1.0, blur=10)
    img = paint(img, 13, 0.04)
    save("temp_b07_retreat", img, {
        "sky": {"y": 900, "drift": 6.0},
        "particles": [{"kind": "snow", "box": [0, 0, W, H], "count": 420, "size": 3.0, "speed": 110, "wind": 60, "seed": 7},
                      {"kind": "snow", "box": [0, 0, W, H], "count": 160, "size": 5.5, "speed": 190, "wind": 110, "seed": 8}],
        "smoke": [{"box": [0, 860, W, 1150], "feather": 90, "density": 1.0, "speed": 30, "color": [0.92, 0.93, 0.96]}]})


# ------------------------------------------------------------------------------------------- 4. Saint Helena at dusk
def helena(night=False):
    if night:
        img = vgrad([(0, (0.02, 0.03, 0.06)), (0.45, (0.08, 0.10, 0.16)), (0.56, (0.16, 0.17, 0.22)), (0.565, (0.04, 0.05, 0.08)), (1, (0.02, 0.02, 0.04))])
    else:
        img = vgrad([(0, (0.13, 0.12, 0.25)), (0.32, (0.55, 0.30, 0.32)), (0.50, (0.98, 0.62, 0.32)), (0.56, (1.0, 0.80, 0.50)),
                     (0.565, (0.20, 0.17, 0.24)), (1, (0.06, 0.06, 0.12))])
    horizon = int(0.565 * H)
    cl = noise(8, 51 + night)
    clouds = np.clip((cl - 0.5) / 0.2, 0, 1) * np.clip((horizon - 80 - YY) / 400, 0, 1)
    ccol = np.array([0.12, 0.13, 0.20] if night else [0.45, 0.24, 0.30], np.float32)
    img[:] = img * (1 - 0.8 * clouds[..., None]) + ccol * 0.8 * clouds[..., None]
    sx, sy = (760, horizon - 40) if not night else (300, 380)
    glow(img, sx, sy, 70 if not night else 40, (1.0, 0.9, 0.7) if not night else (0.9, 0.92, 1.0), 1.0)
    glow(img, sx, sy, 300, (1.0, 0.6, 0.3) if not night else (0.4, 0.45, 0.6), 0.35)
    if night:
        rng = np.random.default_rng(9)
        for _ in range(220):
            x, y = rng.uniform(0, W), rng.uniform(0, horizon - 200)
            cv2.circle(img, (int(x), int(y)), 1, (0.9, 0.9, 1.0), -1, cv2.LINE_AA)
    # the island: steep basalt cliffs rising from the sea, high central ridge
    prof = []
    for x in np.linspace(-20, 760, 60):
        u = (x + 20) / 780
        h = 520 * math.sin(math.pi * min(1, u * 1.05)) ** 0.7 + 40 * math.sin(u * 23) + 25 * math.sin(u * 51)
        prof.append((x, horizon - max(0, h)))
    isl = [(-20, horizon + 6)] + prof + [(760, horizon + 6)]
    fill(img, isl, (0.10, 0.08, 0.12) if not night else (0.03, 0.03, 0.05))
    rim = np.clip(1 - np.abs(XX - 0.5 * W) / W, 0, 1)
    if not night:
        m = fill(np.zeros_like(img), isl, (1, 1, 1))
        edge = m - cv2.erode(m, np.ones((9, 9), np.uint8))
        img += (edge * 0.35 * rim)[..., None] * np.array([1.0, 0.55, 0.3], np.float32)
    else:
        glow(img, 380, horizon - 330, 6, (1.0, 0.75, 0.4), 1.0)        # one lit window (Longwood)
    # sea: darker toward the viewer, a glitter path under the sun / moon
    sea = noise(1.2, 61, 960, 135)
    path = np.exp(-((XX - sx) / (60 + 0.35 * (YY - horizon))) ** 2) * (YY > horizon)
    gl = np.clip((sea - 0.55) / 0.1, 0, 1) * path
    img += gl[..., None] * (np.array([1.0, 0.8, 0.55]) if not night else np.array([0.7, 0.75, 0.9]))[None, None].astype(np.float32) * 0.6
    img = paint(img, 14 + night, 0.04)
    meta = {"sky": {"y": horizon - 120, "drift": 2.5},
            "smoke": [{"box": [0, horizon + 30, W, H], "feather": 60, "density": 0.6, "speed": 12,
                       "color": [0.85, 0.6, 0.45] if not night else [0.35, 0.4, 0.5]}],
            "sun": {"x": sx, "y": sy, "r": 200}}
    if night:
        meta["flicker"] = [{"x": 380, "y": horizon - 330, "r": 18, "amp": 0.25, "color": [1.0, 0.7, 0.35]}]
    save("temp_b15_night_sea" if night else "temp_b13_helena", img, meta)


# ------------------------------------------------------------------------------------------- 5. legacy: Arc de Triomphe
def arc():
    img = vgrad([(0, (0.12, 0.14, 0.28)), (0.35, (0.55, 0.38, 0.45)), (0.55, (0.98, 0.68, 0.38)), (0.62, (1.0, 0.82, 0.55)), (1, (0.30, 0.20, 0.18))])
    cl = noise(9, 71)
    clouds = np.clip((cl - 0.52) / 0.2, 0, 1) * np.clip((1000 - YY) / 500, 0, 1)
    img[:] = img * (1 - 0.6 * clouds[..., None]) + np.array([0.55, 0.32, 0.36], np.float32) * 0.6 * clouds[..., None]
    glow(img, 540, 1060, 420, (1.0, 0.7, 0.35), 0.5, 260)
    base, sil = 1420, (0.16, 0.10, 0.11)
    # the arch: massive block with a central vault and an attic storey
    x0, x1, top = 250, 830, 640
    fill(img, [(x0, base), (x0, top), (x1, top), (x1, base)], sil)
    fill(img, [(x0 - 14, top + 70), (x1 + 14, top + 70), (x1 + 14, top + 92), (x0 - 14, top + 92)], sil)
    fill(img, [(x0 - 10, top), (x1 + 10, top), (x1 + 10, top - 30), (x0 - 10, top - 30)], sil)
    vault = [(470, base)] + [(540 - 70 * math.cos(a), 960 - 120 * math.sin(a)) for a in np.linspace(0, math.pi, 30)] + [(610, base)]
    vault = [(470, base), (470, 960)] + [(540 - 70 * math.cos(a), 960 - 130 * math.sin(a)) for a in np.linspace(0, math.pi, 30)] + [(610, 960), (610, base)]
    fill(img, vault, (0.98, 0.72, 0.42))
    glow(img, 540, 1150, 90, (1.0, 0.8, 0.5), 0.5, 240)
    for px in (300, 780):                                          # relief panels catching the light
        fill(img, [(px - 30, 1000), (px + 30, 1000), (px + 30, 1260), (px - 30, 1260)], (0.24, 0.15, 0.15))
    # Paris rooftops and the avenue
    rng = np.random.default_rng(12)
    x = -10
    while x < W + 20:
        w, h = rng.uniform(60, 120), rng.uniform(80, 170)
        if not (220 < x < 860):
            fill(img, [(x, base + 20), (x, base - h), (x + w * 0.2, base - h - 30), (x + w * 0.8, base - h - 30), (x + w, base - h), (x + w, base + 20)],
                 (0.12, 0.08, 0.09))
        x += w
    fill(img, [(0, base), (W, base), (W, H), (0, H)], (0.20, 0.13, 0.12))
    fill(img, [(500, base), (580, base), (900, H), (180, H)], (0.36, 0.24, 0.20))
    for k in range(9):                                             # avenue lamps
        u = k / 8
        for side in (-1, 1):
            lx, ly = 540 + side * (60 + 330 * u), base + 30 + 470 * u
            glow(img, lx, ly - 30 - 60 * u, 6 + 10 * u, (1.0, 0.8, 0.45), 0.9)
    img = paint(img, 15, 0.04)
    save("temp_b14_arc", img, {"sky": {"y": 760, "drift": 3.0}, "sun": {"x": 540, "y": 1060, "r": 260},
                               "flicker": [{"x": 540, "y": 1120, "r": 120, "amp": 0.05, "color": [1.0, 0.8, 0.5]}]})


if __name__ == "__main__":
    coronation()
    moscow()
    retreat()
    helena()
    arc()
    helena(night=True)

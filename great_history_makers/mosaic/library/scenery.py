"""Additional environment pieces for documentary shorts: camp, market, aerial plan,
artefacts (tablet, scroll, cylinder texture), scaffolding and a simplified map.

Reconstruction notes: Babylon's plan follows the excavated layout (rectangular inner
city on both banks of the Euphrates, Ishtar Gate at the north, Etemenanki and Esagila
near the centre); proportions are simplified."""
import math
import random

import numpy as np

from ..palette import P, mix
from . import mesopotamia as M


def tent(p, x, y, w, h, col="bone", stripe="terracotta", door="umber"):
    p.poly([(x - w / 2, y), (x - w * 0.38, y - h * 0.62), (x, y - h), (x + w * 0.38, y - h * 0.62), (x + w / 2, y)], col)
    for k in (-0.25, 0.0, 0.25):
        p.line([(x + w * k * 0.5, y - h * (1 - abs(k) * 1.2)), (x + w * k * 1.6, y)], stripe, max(3, w * 0.025))
    p.poly([(x - w * 0.09, y), (x, y - h * 0.45), (x + w * 0.09, y)], door)
    p.line([(x, y - h), (x, y - h - h * 0.18)], "umber", max(3, w * 0.02))


def campfire(p, x, y, s):
    for k in range(5):
        a = math.radians(-160 + k * 35)
        p.line([(x, y), (x + math.cos(a) * 40 * s, y + 10 * s)], "umber", 9 * s)
    p.smooth([(x - 34 * s, y), (x - 10 * s, y - 70 * s), (x + 6 * s, y - 30 * s), (x + 14 * s, y - 90 * s),
              (x + 34 * s, y)], "dusk_orange", 5)
    p.smooth([(x - 18 * s, y), (x, y - 44 * s), (x + 18 * s, y)], "sun_hot", 4)


def stall(p, x, y, w, awn=("terracotta", "ivory"), goods="pots", seed=0):
    rnd = random.Random(seed)
    h = w * 0.9
    p.rect(x - w / 2, y - h * 0.38, w, h * 0.38, "umber")       # counter
    p.rect(x - w / 2 + 8, y - h * 0.38 + 8, w - 16, h * 0.38 - 16, "brick")
    p.line([(x - w / 2 + 6, y - h), (x - w / 2 + 6, y)], "umber", 8)
    p.line([(x + w / 2 - 6, y - h), (x + w / 2 - 6, y)], "umber", 8)
    n = 6
    for i in range(n):
        x0 = x - w / 2 - 20 + i * (w + 40) / n
        p.poly([(x0, y - h - 20), (x0 + (w + 40) / n, y - h - 20), (x0 + (w + 40) / n, y - h + 40), (x0, y - h + 30)],
               awn[i % 2])
    top = y - h * 0.38
    if goods == "pots":
        for i in range(4):
            cx = x - w * 0.32 + i * w * 0.21
            r = w * rnd.uniform(0.07, 0.09)
            p.ellipse(cx, top - r, r, r * 1.1, rnd.choice(["terracotta", "ochre_dk", "brick"]))
            p.rect(cx - r * 0.4, top - r * 2.4, r * 0.8, r * 0.5, "terracotta_dk")
    elif goods == "dates":
        for i in range(3):
            cx = x - w * 0.3 + i * w * 0.3
            p.ellipse(cx, top - 18, w * 0.13, 22, "ochre")
            for k in range(7):
                p.circle(cx + rnd.uniform(-w * 0.1, w * 0.1), top - 26 + rnd.uniform(-8, 6), 7, "umber")
    else:  # cloth
        for i, c in enumerate(["lapis", "crimson", "ivory", "gold"]):
            p.rect(x - w * 0.4 + i * w * 0.2, top - 50 + i * 4, w * 0.18, 50 - i * 4, c)


def houses(p, x0, x1, base, rnd, cols=("sand", "sand_dk", "bone", "ochre"), hmin=120, hmax=260, wmin=110, wmax=220):
    x = x0
    while x < x1:
        w = rnd.uniform(wmin, wmax)
        h = rnd.uniform(hmin, hmax)
        c = rnd.choice(cols)
        p.rect(x, base - h, w, h, c)
        p.rect(x, base - h, w, 10, mix(c, "umber", 0.35))
        for k in range(int(w // 60)):
            p.rect(x + 22 + k * 60, base - h * 0.62, 18, 28, "umber")
        if rnd.random() < 0.5:
            p.rect(x + w * 0.4, base - 70, w * 0.22, 70, "outline")
        x += w + rnd.uniform(-10, 12)


def city_plan(p, cx, cy, s, seed=3):
    """Top-down plan of Babylon (simplified): moat, double walls with towers, the Euphrates
    through the city, gridded blocks, Etemenanki precinct, Processional Way, Ishtar Gate."""
    rnd = random.Random(seed)
    W, H = 900 * s, 1250 * s
    x0, y0 = cx - W / 2, cy - H / 2
    p.rect(x0 - 70 * s, y0 - 70 * s, W + 140 * s, H + 140 * s, "lapis")          # moat
    p.rect(x0 - 40 * s, y0 - 40 * s, W + 80 * s, H + 80 * s, "sand_dk")          # outer wall
    p.rect(x0, y0, W, H, "ochre_dk")                                              # inner wall
    for i in range(14):                                                           # towers
        for (tx, ty) in [(x0 + W * i / 13, y0), (x0 + W * i / 13, y0 + H)]:
            p.rect(tx - 16 * s, ty - 16 * s, 32 * s, 32 * s, "sand")
    for i in range(18):
        for (tx, ty) in [(x0, y0 + H * i / 17), (x0 + W, y0 + H * i / 17)]:
            p.rect(tx - 16 * s, ty - 16 * s, 32 * s, 32 * s, "sand")
    p.rect(x0 + 22 * s, y0 + 22 * s, W - 44 * s, H - 44 * s, "sand")
    # blocks
    for r in range(13):
        for c in range(9):
            bx = x0 + 40 * s + c * (W - 80 * s) / 9
            by = y0 + 40 * s + r * (H - 80 * s) / 13
            p.rect(bx + 5 * s, by + 5 * s, (W - 80 * s) / 9 - 12 * s, (H - 80 * s) / 13 - 12 * s,
                   rnd.choice(["bone", "sand_dk", "ochre", "brick", "sand_dk"]))
    # river (north to south, slightly west of centre)
    rx = x0 + W * 0.42
    pts_l = [(rx - 40 * s + 20 * s * math.sin(k / 3), y0 - 400 * s + k * 120 * s) for k in range(int((H + 800 * s) / (120 * s)) + 1)]
    pts_r = [(x + 95 * s, y) for x, y in pts_l]
    p.poly(pts_l + pts_r[::-1], "blue_mid")
    p.poly([(x + 20 * s, y) for x, y in pts_l] + [(x - 20 * s, y) for x, y in pts_r[::-1]], "lapis")
    # Etemenanki precinct + ziggurat (square, stepped) and Esagila
    zx, zy = x0 + W * 0.66, y0 + H * 0.48
    p.rect(zx - 120 * s, zy - 120 * s, 240 * s, 240 * s, "bone")
    for k, c in enumerate(["brick", "terracotta", "brick", "terracotta", "lapis"]):
        e = (90 - k * 18) * s
        p.rect(zx - e, zy - e, 2 * e, 2 * e, c)
    p.rect(zx - 90 * s, zy + 150 * s, 180 * s, 130 * s, "gold")
    p.rect(zx - 60 * s, zy + 180 * s, 120 * s, 70 * s, "ochre_dk")
    # Processional Way to the Ishtar Gate at the north wall
    gx = x0 + W * 0.74
    p.rect(gx - 18 * s, y0 - 40 * s, 36 * s, zy - y0, "ivory")
    p.rect(gx - 45 * s, y0 - 70 * s, 90 * s, 60 * s, "lapis_dk")
    p.rect(gx - 30 * s, y0 - 60 * s, 60 * s, 40 * s, "gold_lt")
    # palace by the north wall
    p.rect(x0 + W * 0.5, y0 + 40 * s, W * 0.2, H * 0.12, "terracotta_dk")


def fields(p, x, y, w, h, seed=0):
    rnd = random.Random(seed)
    p.rect(x, y, w, h, "olive")
    for _ in range(int(w * h / 26000)):
        fx, fy = rnd.uniform(x, x + w), rnd.uniform(y, y + h)
        p.rect(fx, fy, rnd.uniform(60, 160), rnd.uniform(40, 110), rnd.choice(["green", "green_dk", "ochre", "olive", "sand"]))
    for _ in range(int(w * h / 60000)):
        M.palm(p, rnd.uniform(x, x + w), rnd.uniform(y, y + h), rnd.uniform(60, 90), seed=rnd.randint(0, 99))


def tablet(p, cx, cy, w, h, col="sand", mark="sand_dk", seed=0, rows=None):
    rnd = random.Random(seed)
    p.smooth([(cx - w / 2, cy - h / 2 + 20), (cx - w / 2 + 20, cy - h / 2), (cx + w / 2 - 20, cy - h / 2),
              (cx + w / 2, cy - h / 2 + 20), (cx + w / 2, cy + h / 2 - 20), (cx + w / 2 - 20, cy + h / 2),
              (cx - w / 2 + 20, cy + h / 2), (cx - w / 2, cy + h / 2 - 20)], col, 3)
    rows = rows or int(h / 34)
    for r in range(rows):
        y = cy - h / 2 + 30 + r * (h - 50) / rows
        p.line([(cx - w / 2 + 16, y + 14), (cx + w / 2 - 16, y + 14)], mix(col, mark, 0.5), 2)
        x = cx - w / 2 + 24
        while x < cx + w / 2 - 30:
            wedge(p, x, y, rnd.uniform(8, 13), rnd.choice([0, 0, 90, 45]), mark)
            x += rnd.uniform(14, 26)


def wedge(p, x, y, s, ang, col):
    a = math.radians(ang)
    c, si = math.cos(a), math.sin(a)
    pts = [(0, -s * 0.5), (s * 1.3, 0), (0, s * 0.5)]
    p.poly([(x + px * c - py * si, y + px * si + py * c) for px, py in pts], col)


def scroll(p, cx, cy, w, h, seed=0):
    rnd = random.Random(seed)
    p.rect(cx - w / 2, cy - h / 2, w, h, "bone")
    for k in range(int(w / 70)):
        p.line([(cx - w / 2 + k * 70, cy - h / 2), (cx - w / 2 + k * 70, cy + h / 2)], "sand", 2)
    for r in range(int((h - 60) / 30)):
        y = cy - h / 2 + 34 + r * 30
        x = cx - w / 2 + 26
        while x < cx + w / 2 - 30:
            L = rnd.uniform(16, 60)
            p.line([(x, y), (x + L, y)], "umber", 4)
            x += L + rnd.uniform(8, 16)
    for sx in (cx - w / 2, cx + w / 2):
        p.ellipse(sx, cy, 26, h / 2 + 18, "ochre_dk")
        p.ellipse(sx, cy, 14, h / 2 + 10, "sand_dk")


def scaffold(p, x0, x1, y_top, y_base):
    for x in np.linspace(x0, x1, 4):
        p.line([(x, y_top - 40), (x, y_base)], "umber", 10)
    for y in np.linspace(y_top, y_base, 4)[:-1]:
        p.line([(x0 - 20, y), (x1 + 20, y)], "umber", 9)
        p.rect(x0 - 20, y - 14, x1 - x0 + 40, 12, "ochre_dk")
    for a, b in zip(np.linspace(x0, x1, 4)[:-1], np.linspace(x0, x1, 4)[1:]):
        p.line([(a, y_base), (b, y_top)], "umber", 5)


def cuneiform_texture(w, h, seed=0, clay=(190, 150, 104)):
    """Unrolled inscription band (numpy RGB) used to colour the tiles of the rotating
    cylinder: horizontal ruled lines of wedge groups pressed into clay."""
    rnd = np.random.default_rng(seed)
    import cv2
    img = np.zeros((h, w, 3), np.float32)
    img[:] = clay
    img += rnd.normal(0, 6, (h, w, 1))
    row_h = 26
    dark = np.array(clay) * 0.55
    for y in range(18, h - 10, row_h):
        cv2.line(img, (0, y + row_h - 6), (w, y + row_h - 6), tuple(float(v) for v in np.array(clay) * 0.8), 1)
        x = 4
        while x < w - 10:
            for _ in range(rnd.integers(1, 4)):
                ang = rnd.choice([0, 0, 90, 45, -45])
                s = rnd.uniform(5, 9)
                a = math.radians(ang)
                pts = np.array([(0, -s * 0.5), (s * 1.4, 0), (0, s * 0.5)])
                R_ = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
                q = (pts @ R_.T + (x, y + row_h / 2)).astype(np.int32)
                cv2.fillPoly(img, [q], tuple(float(v) for v in dark))
                x += int(s * 1.5)
            x += int(rnd.uniform(6, 14))
    return np.clip(img, 0, 255)


# ---------------------------------------------------------------- simplified map
# Hand-simplified coastlines (lon, lat) for an artistic mosaic map, not a survey.
MED = [(26, 41), (24, 40.5), (23, 39), (24, 38), (22.5, 36.5), (26, 35.5), (28, 36.5), (30, 36.2), (32.5, 36.1),
       (35, 36.6), (36, 36.2), (35.8, 34.5), (35, 33), (34.4, 31.6), (32.5, 31.1), (29.5, 30.9), (25, 31.8),
       (20, 30.5), (18, 31)]
BLACK = [(28, 41.2), (29.2, 41.2), (31.5, 41.2), (33.5, 42), (36, 41.7), (38, 41), (40.5, 41), (41.6, 41.6),
         (41.5, 42.6), (39.5, 44), (37.5, 45), (35, 45), (33.5, 46), (30.7, 46.5), (29.5, 45), (28.6, 43.8), (27.9, 42.5)]
CASPIAN = [(49.2, 46.5), (51.3, 46.6), (53, 45.2), (51.5, 43.5), (52.5, 42), (54, 40.8), (53.8, 39), (53.9, 37.3),
           (51.5, 36.8), (49.5, 37.5), (48.8, 38.7), (49.5, 40.3), (48, 42), (47.5, 43.5)]
GULF = [(48, 30.4), (49.5, 30.1), (50.6, 29.2), (51.5, 27.9), (54, 26.7), (56.3, 27.1), (57, 25.8), (59, 25.4),
        (61.5, 25.2), (62, 22), (56.5, 22), (56.3, 24.2), (55.5, 25.4), (54, 24.2), (51.6, 24.3), (51.5, 26),
        (50.2, 26.3), (49.5, 27.2), (48.5, 28.4)]
RED = [(32.5, 30), (34.5, 28), (35, 28.1), (34.6, 29.5), (36.5, 26), (39, 22), (41, 18), (39, 18), (37, 21), (35, 24),
       (33.5, 27)]
# rivers
EUPHRATES = [(38.5, 39.5), (38.6, 38), (38.2, 36.8), (39.5, 36.0), (40.5, 35.0), (42.0, 34.4), (43.5, 33.3),
             (44.4, 32.5), (45.6, 31.5), (46.8, 31.0), (47.8, 30.5)]
TIGRIS = [(40.5, 38.3), (42.2, 37.3), (43.2, 36.3), (43.5, 35.0), (44.0, 34.2), (44.4, 33.3), (45.2, 32.6),
          (46.3, 31.8), (47.4, 31.0), (47.8, 30.5)]
# approximate regions (artistic): Persian realm c. 539 before/after Babylonia
PERSIA_539_BEFORE = [(26, 40), (27, 37.5), (30, 36.5), (33, 36.3), (36, 36.8), (38.5, 37.5), (41.5, 37.8),
                     (44, 36.5), (45.5, 34), (47, 32.5), (48.5, 30.6), (50.6, 29.2), (54, 26.8), (58, 26.4),
                     (62, 25.6), (66, 26), (69, 30), (70, 35), (69, 39), (64, 41.5), (58, 41.5), (54, 40.5),
                     (49, 40.5), (46, 41.5), (42, 41.3), (38, 41.2), (34, 42), (30, 41.4), (27, 41.2)]
BABYLONIA_EMPIRE = [(36, 36.8), (35.8, 34.5), (35, 33), (34.4, 31.6), (34.8, 29.5), (37, 29.8), (40, 30.5),
                    (44, 29.8), (47, 30.2), (48.5, 30.6), (47, 32.5), (45.5, 34), (44, 36.5), (41.5, 37.8), (38.5, 37.5)]
PLACES = {"Babylon": (44.42, 32.54), "Opis": (44.6, 33.6), "Pasargadae": (53.17, 30.2), "Ecbatana": (48.5, 34.8),
          "Sardis": (28.0, 38.5)}


def lonlat(lon, lat, ox, oy, scale):
    return ox + (lon - 24) * scale, oy + (47 - lat) * scale * 1.15


ARABIAN_SEA = [(56.3, 27.1), (57, 25.8), (59, 25.4), (61.5, 25.2), (66, 25.2), (68, 24), (76, 22), (76, 10),
               (50, 10), (51.5, 14.5), (55, 17), (58, 20), (59.8, 22.5), (58.5, 23.7), (56.5, 24.5)]
WEST_MED = [(10, 46), (13, 45.5), (19, 41.8), (23, 39), (24, 38), (22.5, 36.5), (26, 35.5), (25, 31.8), (20, 30.5),
            (10, 30)]
SEAS = (MED, BLACK, CASPIAN, GULF, RED, ARABIAN_SEA, WEST_MED)


def map_layer(p, ox, oy, scale, land="sand", sea="blue_mid", x0=-300, y0=-200, w=1700, h=2400):
    p.rect(x0, y0, w, h, land)
    for poly in SEAS:
        p.smooth([lonlat(lo, la, ox, oy, scale) for lo, la in poly], sea, 4)
    for r in (EUPHRATES, TIGRIS):
        p.curve([lonlat(lo, la, ox, oy, scale) for lo, la in r], sea, 6)


def cut_seas(p, ox, oy, scale, key=(255, 0, 255)):
    """Paint seas in the key colour so region tints never cover water."""
    for poly in SEAS:
        p.smooth([lonlat(lo, la, ox, oy, scale) for lo, la in poly], key, 4)


def region_poly(name, ox, oy, scale):
    pts = {"before": PERSIA_539_BEFORE, "babylonia": BABYLONIA_EMPIRE}[name]
    return [lonlat(lo, la, ox, oy, scale) for lo, la in pts]

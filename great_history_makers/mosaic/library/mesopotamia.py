"""Environment drawing kit for 6th-century BCE Babylon (artistic reconstruction).

Reference points: the Ishtar Gate and Processional Way of Nebuchadnezzar II
(c. 575 BCE; blue glazed brick with aurochs, mushhushshu dragons and lions),
the Etemenanki ziggurat and the double city walls along the Euphrates.
All functions draw into a Painter in design units.
"""
import math
import random

from ..palette import mix


# ------------------------------------------------------------------ sky & land
def sky(p, x, y, w, h, keys, n=None):
    """Sky laid in horizontal bands interpolated between key colours."""
    n = n or max(len(keys), int(h / 60))
    cols = []
    for i in range(n):
        f = i / (n - 1) * (len(keys) - 1)
        a = int(f)
        b = min(a + 1, len(keys) - 1)
        cols.append(mix(keys[a], keys[b], f - a))
    p.vgradient_bands(x, y, w, h, cols)


def cloud(p, cx, cy, w, h, col="bone", shade="sky_pale"):
    p.ellipse(cx, cy + h * 0.15, w * 0.5, h * 0.35, shade)
    p.ellipse(cx - w * 0.18, cy, w * 0.26, h * 0.42, col)
    p.ellipse(cx + w * 0.12, cy - h * 0.12, w * 0.24, h * 0.5, col)
    p.ellipse(cx + w * 0.32, cy + h * 0.05, w * 0.18, h * 0.32, col)


def sun(p, cx, cy, r, rings=("sun_hot", "sun", "gold")):
    for i, col in enumerate(reversed(rings)):
        rr = r * (1 + 0.35 * (len(rings) - 1 - i))
        p.circle(cx, cy, rr, col)


def palm(p, x, y, h, trunk="umber", frond="green_dk", frond2="green", lean=0.0, seed=0):
    """Date palm: ringed trunk and arching, drooping fronds with leaflets."""
    rnd = random.Random(seed)
    top = (x + lean * h, y - h)
    p.curve([(x, y), (x + lean * h * 0.35, y - h * 0.5), top], trunk, h * 0.05)
    for i in range(int(h / 34)):
        t = i / (h / 34)
        px = x + lean * h * t * (0.6 + 0.4 * t)
        p.line([(px - h * 0.024, y - h * t), (px + h * 0.024, y - h * t - h * 0.012)], "outline", h * 0.007)
    n = 11
    for k in range(n):
        a = math.radians(-180 + k * 180 / (n - 1) + rnd.uniform(-7, 7))
        L = h * rnd.uniform(0.34, 0.44)
        droop = L * (0.35 + 0.35 * abs(math.cos(a)))
        pts = []
        for s in range(9):
            u = s / 8
            pts.append((top[0] + math.cos(a) * L * u, top[1] + math.sin(a) * L * u * 0.7 + droop * u * u))
        col = frond if k % 2 else frond2
        w = h * 0.03
        left = [(px, py - w * (1 - i / 8)) for i, (px, py) in enumerate(pts)]
        right = [(px, py + w * 0.6 * (1 - i / 8)) for i, (px, py) in enumerate(pts)]
        p.poly(left + right[::-1], col)
        for i in range(1, 8):
            px, py = pts[i]
            ll = h * 0.05 * (1 - i / 9)
            p.line([(px, py), (px + ll * 0.3, py + ll)], col, h * 0.008)
    p.circle(top[0], top[1] + h * 0.02, h * 0.028, "ochre_dk")


def merlons(p, x0, x1, y, size, col, step=True):
    """Stepped Mesopotamian battlements along y (top of wall)."""
    n = max(1, int((x1 - x0) / (size * 1.6)))
    w = (x1 - x0) / n
    for i in range(n):
        cx = x0 + i * w + w / 2
        if step:
            p.rect(cx - size * 0.5, y - size * 0.55, size, size * 0.6, col)
            p.rect(cx - size * 0.3, y - size * 1.05, size * 0.6, size * 0.55, col)
        else:
            p.rect(cx - size * 0.45, y - size, size * 0.9, size, col)


def wall(p, x0, x1, top, bottom, col="sand", dark="sand_dk", merlon=26, towers=6, tower_col=None,
         courses=True):
    tower_col = tower_col or col
    p.rect(x0, top, x1 - x0, bottom - top, col)
    if courses:
        y = top + 18
        while y < bottom:
            p.line([(x0, y), (x1, y)], dark, 2.2)
            y += 26
    merlons(p, x0, x1, top, merlon, col)
    if towers:
        step = (x1 - x0) / towers
        for i in range(towers + 1):
            tx = x0 + i * step
            tw = merlon * 3.2
            p.rect(tx - tw / 2, top - merlon * 1.6, tw, bottom - top + merlon * 1.6, tower_col)
            p.rect(tx - tw / 2, top - merlon * 1.6, tw * 0.12, bottom - top + merlon * 1.6, dark)
            merlons(p, tx - tw / 2, tx + tw / 2, top - merlon * 1.6, merlon * 0.9, tower_col)


def ziggurat(p, cx, base_y, w, h, tiers=5, col="brick", dark="umber", shrine="lapis"):
    th = h / (tiers + 0.6)
    for i in range(tiers):
        tw = w * (1 - i * 0.16)
        y = base_y - th * (i + 1)
        p.rect(cx - tw / 2, y, tw, th, col if i % 2 == 0 else mix(col, "sand", 0.25))
        p.rect(cx - tw / 2, y, tw, th * 0.12, dark)
        for k in range(1, 6):
            xk = cx - tw / 2 + tw * k / 6
            p.line([(xk, y + th * 0.15), (xk, y + th)], dark, 2.5)
    tw = w * (1 - tiers * 0.16)
    p.rect(cx - tw * 0.4, base_y - th * (tiers + 0.6), tw * 0.8, th * 0.6, shrine)
    merlons(p, cx - tw * 0.4, cx + tw * 0.4, base_y - th * (tiers + 0.6), th * 0.18, "gold")
    # central stair
    p.poly([(cx - w * 0.05, base_y), (cx + w * 0.05, base_y), (cx + w * 0.03, base_y - th * 3),
            (cx - w * 0.03, base_y - th * 3)], mix(col, "sand", 0.45))


def animal(p, x, y, s, col, kind="bull", facing=1):
    """Ishtar-gate style striding animal in profile (aurochs / dragon / lion)."""
    p.push()
    p.translate(x, y)
    p.scale(s * facing, s)
    body = [(-40, -10), (-20, -22), (25, -22), (40, -14), (44, 4), (38, 12), (-36, 12), (-44, 2)]
    p.smooth(body, col, 5)
    for lx in (-32, -18, 22, 34):
        p.poly([(lx - 4, 8), (lx + 4, 8), (lx + 3, 34), (lx - 3, 34)], col)
    if kind == "bull":
        p.poly([(38, -14), (58, -18), (64, -6), (56, 4), (42, 2)], col)
        p.curve([(54, -18), (60, -34), (70, -36)], col, 4)
        p.curve([(-42, -6), (-56, 4), (-54, 24)], col, 3)
    elif kind == "dragon":
        p.poly([(36, -16), (48, -44), (62, -48), (66, -38), (52, -30), (46, -10)], col)
        p.curve([(-42, -6), (-62, -22), (-66, -40)], col, 5)
    else:  # lion
        p.ellipse(46, -18, 16, 18, col)
        p.poly([(56, -22), (70, -14), (58, -6)], col)
        p.curve([(-42, -6), (-60, -24), (-52, -38)], col, 3)
    p.pop()


def rosette_band(p, x0, x1, y, r, bg="lapis_dk", petal="white", center="gold"):
    p.rect(x0, y - r * 1.4, x1 - x0, r * 2.8, bg)
    n = int((x1 - x0) / (r * 3))
    for i in range(n):
        cx = x0 + (i + 0.5) * (x1 - x0) / n
        p.circle(cx, y, r, petal)
        p.circle(cx, y, r * 0.45, center)


HOLE = (255, 0, 255)


def ishtar_gate(p, cx, base, w, h, opening_w, opening_h, inner="blue_deep", inner_far="lapis_dk",
                hole=False):
    """Front elevation of the Ishtar Gate: glazed blue towers, animal registers, arch."""
    x0, x1, top = cx - w / 2, cx + w / 2, base - h
    p.rect(x0, top, w, h, "lapis")
    # towers
    tw = w * 0.22
    for tx in (x0 - tw * 0.15, x1 - tw * 0.85):
        p.rect(tx, top - h * 0.12, tw, h * 1.12, "lapis")
        merlons(p, tx, tx + tw, top - h * 0.12, tw * 0.17, "white")
        p.rect(tx, top - h * 0.12, tw * 0.07, h * 1.12, "lapis_dk")
    merlons(p, x0 + tw * 0.85, x1 - tw * 0.85, top, w * 0.035, "white")
    # brick courses
    y = top + 14
    while y < base:
        p.line([(x0 - tw * 0.15, y), (x1 + tw * 0.15, y)], "lapis_dk", 1.6)
        y += 22
    # animal registers alternating aurochs / dragons
    rows = 4
    for r in range(rows):
        ry = top + h * (0.14 + r * 0.2)
        kind = "bull" if r % 2 == 0 else "dragon"
        col = "gold_lt" if kind == "bull" else "white"
        n = 4
        for i in range(n):
            ax = x0 + (i + 0.5) * w / n
            if abs(ax - cx) < opening_w * 0.75 and ry > base - opening_h - 30:
                continue
            animal(p, ax, ry, w * 0.0017, col, kind, facing=1 if ax < cx else -1)
    rosette_band(p, x0 - tw * 0.15, x1 + tw * 0.15, base - 16, 9)
    # arched opening
    ow, oh = opening_w, opening_h
    p.rect(cx - ow / 2 - 14, base - oh + ow / 2, ow + 28, oh - ow / 2, "white")
    p.ellipse(cx, base - oh + ow / 2, ow / 2 + 14, ow / 2 + 14, "white", 180, 360)
    fill = HOLE if hole else inner
    p.rect(cx - ow / 2, base - oh + ow / 2, ow, oh - ow / 2 + 2, fill)
    p.ellipse(cx, base - oh + ow / 2, ow / 2, ow / 2, fill, 180, 360)
    if hole:
        return
    gate_passage(p, cx, base, ow, oh, inner, inner_far)


def gate_passage(p, cx, base, ow, oh, inner="blue_deep", inner_far="lapis_dk"):
    """Interior of the gate passage, seen through the arch (drawn behind marchers)."""
    p.rect(cx - ow / 2 - 4, base - oh + ow / 2, ow + 8, oh - ow / 2, inner)
    p.ellipse(cx, base - oh + ow / 2, ow / 2 + 4, ow / 2 + 4, inner, 180, 360)
    # glimpse of the far end of the passage
    fw = ow * 0.42
    p.rect(cx - fw / 2, base - oh * 0.62 + fw / 2, fw, oh * 0.62 - fw / 2, inner_far)
    p.ellipse(cx, base - oh * 0.62 + fw / 2, fw / 2, fw / 2, inner_far, 180, 360)
    p.rect(cx - fw * 0.35, base - oh * 0.45, fw * 0.7, oh * 0.45, "sand")


def ground(p, x, y, w, h, base="ochre", spots=("ochre_dk", "sand"), seed=0, n=60):
    rnd = random.Random(seed)
    p.rect(x, y, w, h, base)
    for _ in range(n):
        cx, cy = rnd.uniform(x, x + w), rnd.uniform(y, y + h)
        p.ellipse(cx, cy, rnd.uniform(14, 60), rnd.uniform(4, 12), rnd.choice(spots))


def paving(p, x, y, w, h, a="bone", b="sand", border="terracotta", cell=90, persp=None):
    """Courtyard floor laid like a mosaic pavement: checker of slabs with a border."""
    rows = int(h / (cell * 0.5)) + 2
    cols = int(w / cell) + 2
    for r in range(rows):
        for c in range(cols):
            p.rect(x + c * cell, y + r * cell * 0.5, cell, cell * 0.5, a if (r + c) % 2 else b)
    p.rect(x, y, w, 16, border)


def lion_frieze(p, x0, x1, y, h, bg="lapis", lion="gold_lt", border="white"):
    p.rect(x0, y, x1 - x0, h, bg)
    rosette_band(p, x0, x1, y + 10, 8, bg="lapis_dk")
    rosette_band(p, x0, x1, y + h - 10, 8, bg="lapis_dk")
    n = max(1, int((x1 - x0) / 300))
    for i in range(n):
        animal(p, x0 + (i + 0.5) * (x1 - x0) / n, y + h * 0.45, h * 0.0085, lion, "lion", facing=-1)


def reeds(p, x0, x1, y, h, seed=0, cols=("olive", "green_dk", "ochre_dk")):
    rnd = random.Random(seed)
    x = x0
    while x < x1:
        hh = h * rnd.uniform(0.5, 1.0)
        lean = rnd.uniform(-0.25, 0.25)
        p.curve([(x, y), (x + lean * hh * 0.5, y - hh * 0.6), (x + lean * hh, y - hh)], rnd.choice(cols), 5)
        if rnd.random() < 0.3:
            p.ellipse(x + lean * hh, y - hh, 5, 14, "umber")
        x += rnd.uniform(8, 20)


def river(p, x, y, w, h, bands=("blue_mid", "lapis", "blue_deep")):
    p.vgradient_bands(x, y, w, h, list(bands))

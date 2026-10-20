"""Episode 1 - Cyrus the Great: The Conquest of Babylon (539 BCE).

Four scenes built from the reusable library. Every scene is layered for parallax;
figures are cut-out rigs; water and cloth use controlled per-tile / mesh motion.
Local scene time runs from about -0.4 s to duration + 0.4 s (transition overlap).
"""
import math
import random

import numpy as np

from mosaic import fx, motion
from mosaic.geom import ease_in_out, lerp, smoothstep, wobble
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.palette import P
from mosaic.scene import FigureItem, FnItem, Layer, Scene, SpriteItem, TileAnimItem, make_sprite

BG_TILE = 8.0     # tesserae size for backgrounds (design units)
FAR_TILE = 6.0    # distant architecture needs finer tiles to read
FIG_TILE = 5.6    # figures


def _bird_sprites(ctx, name):
    def up(p):
        p.poly([(-14, 0), (-4, -8), (0, 0), (4, -8), (14, 0), (0, 3)], "outline")

    def down(p):
        p.poly([(-14, 4), (-4, 2), (0, 0), (4, 2), (14, 4), (0, 3)], "outline")
    a = make_sprite(ctx, up, (-20, -12, 40, 20), 3.0, name + "u", rows=0)
    b = make_sprite(ctx, down, (-20, -12, 40, 20), 3.0, name + "d", rows=0)
    return a, b


def birds_item(sprites, flock, speed, t_flap=0.45):
    """flock: list of (x, y, phase). Moves right->left."""
    up, down = sprites

    def fn(t):
        out = []
        from mosaic.geom import T
        for (x, y, ph) in flock:
            s = up if math.sin(2 * math.pi * (t / t_flap) + ph) > 0 else down
            dx = -speed * t
            dy = 6 * math.sin(t * 1.3 + ph)
            out.append((s.premult, T(x + dx, y + dy) @ s.pixel_to_unit(), 1.0))
        return out
    return FnItem(fn)


# =================================================================== scene 1
def scene1(ctx):
    """Cyrus and his guards look toward the walls of Babylon at dawn."""
    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -260, -200, 1600, 1350, ["blue_mid", "blue_pale", "sky_pale", "bone", "ivory", "gold_lt"]),
        M.cloud(p, 160, 380, 360, 70), M.cloud(p, 860, 300, 420, 80), M.cloud(p, 560, 560, 300, 50,
                                                                           "ivory", "bone")),
        (-260, -200, 1600, 1350), BG_TILE, "s1_sky")

    def city(p):
        M.ziggurat(p, 360, 1010, 330, 300)
        p.rect(560, 930, 120, 80, "sand_dk")
        p.rect(700, 950, 90, 60, "brick")
        p.rect(130, 960, 120, 50, "sand_dk")
        M.wall(p, -260, 1340, 990, 1100, merlon=18, towers=12, col="sand", dark="sand_dk")
        M.ishtar_gate(p, 610, 1104, 170, 120, 46, 78)
        for i, x in enumerate((-120, 40, 820, 900, 1010, 1180)):
            M.palm(p, x, 1112, 120 + (i % 3) * 18, seed=i, lean=0.08 * (-1) ** i)
    far = make_sprite(ctx, city, (-260, 700, 1600, 430), FAR_TILE, "s1_city", haze="sky_pale", haze_amt=0.32)

    def plain(p):
        M.ground(p, -300, 1090, 1700, 1100, "ochre", ("ochre_dk", "sand"), seed=4, n=70)
        for i in range(7):
            y = 1120 + i * 34
            p.poly([(-300, y), (180 - i * 30, y - 4), (220 - i * 30, y + 18), (-300, y + 24)],
                   "green" if i % 2 else "olive")
        p.poly([(-300, 1460), (-80, 1330), (260, 1210), (470, 1140), (520, 1134), (500, 1150), (300, 1236),
                (40, 1380), (-300, 1620)], "blue_mid")
        p.poly([(-300, 1500), (-60, 1360), (270, 1225), (480, 1144), (500, 1146), (290, 1236), (20, 1390),
                (-300, 1580)], "lapis")
        p.poly([(1400, 1640), (1100, 1500), (800, 1300), (640, 1110), (590, 1108), (720, 1300), (960, 1520),
                (1180, 1700)], "sand")
    def camp(p):
        # Persian camp on the plain: tents and standards (artistic reconstruction)
        rnd = random.Random(9)
        for i in range(16):
            x = rnd.uniform(-120, 520)
            y = rnd.uniform(1260, 1520)
            s = lerp(0.6, 1.25, (y - 1260) / 260)
            col = rnd.choice(["bone", "ivory", "terracotta", "sand"])
            p.poly([(x - 40 * s, y), (x, y - 46 * s), (x + 40 * s, y)], col)
            p.poly([(x - 8 * s, y), (x, y - 30 * s), (x + 8 * s, y)], "umber")
            p.line([(x, y - 46 * s), (x, y - 60 * s)], "umber", 3 * s)
        for i in range(5):
            x = 80 + i * 110
            y = 1330 + (i % 2) * 90
            p.line([(x, y), (x, y - 110)], "umber", 4)
            p.poly([(x, y - 110), (x + 44, y - 104), (x + 40, y - 80), (x, y - 84)], "crimson")
    plainspr = make_sprite(ctx, lambda p: (plain(p), camp(p)), (-300, 1080, 1700, 1120), BG_TILE, "s1_plain", haze="sky_pale",
                           haze_amt=0.12)

    minis = [F.mini_person(ctx, 0.045, FAR_TILE, variant=i, haze="sky_pale", haze_amt=0.15) for i in range(6)]

    def traffic(t):
        out = []
        for i in range(9):
            s = ((i * 0.13 + t * 0.022 + (i % 3) * 0.05) % 1.0)
            x = lerp(1050, 625, s ** 0.8) + (i % 2) * 18
            y = lerp(1560, 1108, s ** 0.8)
            k = lerp(1.5, 0.55, s)
            item = FigureItem(minis[i % 6], x, y, flip=False, scale=k,
                              pose_fn=lambda tt, i=i: {"head": (0, 0, 10 * math.sin(tt * 6 + i))})
            out += item.emit(t)
        return out

    smoke = make_sprite(ctx, lambda p: (p.ellipse(0, 0, 26, 40, "bone"), p.ellipse(10, -50, 20, 30, "sky_pale")),
                        (-40, -90, 80, 140), FAR_TILE, "s1_smoke")
    smokes = []
    for i, (x, y) in enumerate([(200, 960), (520, 940), (760, 960)]):
        def off(t, x=x, y=y, i=i):
            c = (t * 0.18 + i * 0.33) % 1.0
            return x + 30 * c + 6 * math.sin(t + i), y - 140 * c

        def op(t, i=i):
            c = (t * 0.18 + i * 0.33) % 1.0
            return 0.45 * math.sin(math.pi * c)
        smokes.append(SpriteItem(smoke, off, op))

    def ridge(p):
        p.smooth([(-300, 2150), (-300, 1900), (100, 1840), (380, 1740), (560, 1680), (760, 1650), (980, 1640),
                  (1200, 1650), (1420, 1690), (1440, 2150)], "brick", 8)
        p.smooth([(-300, 2150), (-300, 1960), (200, 1900), (520, 1790), (800, 1750), (1100, 1745), (1440, 1790),
                  (1440, 2150)], "umber", 8)
        for (a, b) in [((420, 1770), (520, 1880)), ((700, 1700), (660, 1880)), ((1000, 1690), (1100, 1900)),
                       ((100, 1880), (160, 2000))]:
            p.line([a, b], "stone_dk", 5)
        rnd = random.Random(2)
        for _ in range(26):
            x = rnd.uniform(-200, 1400)
            y = 1650 + max(0, (600 - x) * 0.2) + rnd.uniform(0, 30)
            p.poly([(x, y + 6), (x - 6, y - 22), (x + 2, y), (x + 10, y - 26), (x + 8, y + 6)], "olive")
    ridgespr = make_sprite(ctx, ridge, (-320, 1600, 1780, 560), BG_TILE, "s1_ridge")

    cyrus = F.cyrus(ctx, 0.54, FIG_TILE)
    g0 = F.persian_guard(ctx, 0.5, FIG_TILE, variant=0)
    g1 = F.persian_guard(ctx, 0.48, FIG_TILE, variant=1, haze="sky_pale", haze_amt=0.06)

    def cyrus_pose(t):
        p = motion.idle(t, 0.3, head=1.2, sway=0.35, arm=0.8, wind=1.2)
        p["head"] = (p["head"][0] + 2.0 * smoothstep(t / 4.0), 0, p["head"][2])  # gaze settles on the city
        return p

    figs = Layer(1.0, [
        FigureItem(g1, 1035, 1670, pose_fn=lambda t: motion.idle(t, 2.1, head=2.0)),
        FigureItem(g0, 915, 1680, pose_fn=lambda t: motion.idle(t, 1.2, head=2.4)),
        FigureItem(cyrus, 770, 1700, pose_fn=cyrus_pose),
    ])
    birds = birds_item(_bird_sprites(ctx, "s1b"), [(900, 720, 0), (950, 700, 1.3), (1000, 740, 2.1),
                                                    (1060, 715, 0.7)], 38)

    def cam(t):
        e = ease_in_out(t / 5.0)
        return dict(zoom=lerp(1.0, 1.085, e), ox=lerp(0, 22, e), oy=lerp(0, -12, e))

    return Scene("s1_overlook", 5.0, [
        Layer(0.05, [SpriteItem(sky)]),
        Layer(0.1, [birds]),
        Layer(0.15, [SpriteItem(far)] + smokes),
        Layer(0.32, [SpriteItem(plainspr), FnItem(traffic)]),
        Layer(1.0, [SpriteItem(ridgespr)]),
        figs,
    ], cam, fx=[
        fx.Glow((300, 880), 520, "sun_hot", 0.24, breathe=0.04, parallax=0.1),
        fx.Haze(1100, 80, "ivory", 0.12, parallax=0.2),
        fx.Shafts(-24, 0.05),
        fx.Dust(120, seed=11, strength=0.32, drift=(-10, -4), region=(0, 0.35, 1, 1)),
        fx.Grade(gain=(1.05, 1.0, 0.94), lift=(0.0, 0.0, 0.0), gamma=1.06, sat=1.08),
        fx.Vignette(0.42),
    ])


# =================================================================== scene 2
def scene2(ctx):
    """Persian soldiers pass through the Ishtar Gate while townspeople look on.
    The Nabonidus Chronicle says Cyrus's army under Ugbaru entered Babylon without battle."""
    GP = 0.6                      # parallax of the gate plane (gate, far column, onlookers)
    GX, GB, GW, GH = 400, 1330, 640, 620
    OW, OH = 270, 440

    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -400, -200, 1900, 1100, ["blue_mid", "blue_pale", "sky_pale", "bone", "ivory"]),
        M.cloud(p, 820, 260, 380, 70), M.cloud(p, 200, 420, 300, 54)),
        (-400, -200, 1900, 1100), BG_TILE, "s2_sky")

    def city_back(p):
        M.ziggurat(p, 1050, 820, 420, 380, col="brick")
        for x, h in [(-200, 120), (-60, 160), (520, 140), (700, 180), (1250, 150), (1400, 120)]:
            p.rect(x, 820 - h, 150, h + 40, "sand_dk" if x % 3 else "brick")
            M.merlons(p, x, x + 150, 820 - h, 14, "sand_dk" if x % 3 else "brick")
        for i, x in enumerate((-100, 420, 640, 1320)):
            M.palm(p, x, 860, 170, seed=10 + i)
    back = make_sprite(ctx, city_back, (-400, 380, 2200, 520), FAR_TILE, "s2_back", haze="sky_pale",
                       haze_amt=0.25)

    wallspr = make_sprite(ctx, lambda p: M.wall(p, -900, 2100, 720, 1335, merlon=30, towers=9),
                          (-920, 600, 3040, 760), BG_TILE, "s2_wall")
    passage = make_sprite(ctx, lambda p: M.gate_passage(p, GX, GB, OW, OH), (GX - 200, GB - 520, 400, 540),
                          BG_TILE, "s2_passage")
    gate = make_sprite(ctx, lambda p: M.ishtar_gate(p, GX, GB, GW, GH, OW, OH, hole=True),
                       (GX - 420, GB - 760, 840, 780), BG_TILE, "s2_gate", key_color=M.HOLE)

    def road(p):
        M.paving(p, -600, 1320, 2600, 900, a="bone", b="sand", border="lapis_dk", cell=120)
    roadspr = make_sprite(ctx, road, (-600, 1320, 2600, 900), BG_TILE, "s2_road")

    # onlookers on the wall top: some stroll along the parapet, all bob and turn
    minis = [F.mini_person(ctx, 0.05, FAR_TILE, variant=i) for i in range(8)]
    wall_top = []
    for i in range(16):
        x = 700 + i * 66 + (i % 3) * 12
        v = (8 + 6 * (i % 3)) * (-1 if i % 2 else 1) if i % 4 == 1 else 0.0
        wall_top.append(FigureItem(minis[i % 8], x, 742, flip=(i % 2 == 0),
                                   motion_fn=lambda t, v=v, i=i: (v * t, -abs(5 * math.sin(t * 5 + i)) if v else 0),
                                   pose_fn=lambda t, i=i: {"head": (12 * math.sin(t * 0.9 + i), 0,
                                                                    6 * math.sin(t * 2.1 + i * 2))}))
    # townspeople at the foot of the wall: heads follow the column, some raise an arm
    cits = [F.babylonian_citizen(ctx, 0.3, FIG_TILE, variant=i) for i in range(6)]
    onlook = []
    for i, x in enumerate([860, 960, 1060, 1170, 1270, 1380]):
        def pose(t, i=i):
            p = motion.idle(t, i * 0.7, head=1.5, arm=1.5)
            p["head"] = (p["head"][0] + 6 * math.sin(t * 0.7 + i * 0.9), 0, p["head"][2])
            if i % 2 == 0:  # raised hand, repeated gently
                wave = max(0.0, math.sin(2 * math.pi * (t / 2.4) + i)) ** 2
                p["arm"] = (p["arm"][0] - 40 * wave, 0, 0)
            p["body"] = (p["body"][0] + 1.2 * math.sin(t * 1.1 + i), 0, 0)
            return p
        onlook.append(FigureItem(cits[i % 6], x, 1318 - (i % 2) * 8, flip=False, pose_fn=pose))

    period = 1.1
    far_k, near_k = 0.29, 0.44
    stride = 2 * 2 * 430 * math.sin(math.radians(21))
    far_v, near_v = stride * far_k / period, stride * near_k / period
    far_sold = [F.persian_soldier(ctx, far_k, FIG_TILE, variant=i) for i in range(4)]
    far_std = F.persian_soldier(ctx, far_k, FIG_TILE, variant=0, standard=True)
    near_sold = [F.persian_soldier(ctx, near_k, FIG_TILE, variant=i) for i in range(4)]
    near_std = [F.persian_soldier(ctx, near_k, FIG_TILE, variant=1, standard=True),
                F.persian_soldier(ctx, near_k, FIG_TILE, variant=3, standard=True)]

    def column(figs, stds, std_at, x0, y, spacing, v, n, seed):
        items = []
        for i in range(n):
            f = stds[std_at.index(i) % len(stds)] if i in std_at else figs[(i * 3 + seed) % len(figs)]
            ph = (i * 2.3 + seed) % 6.28  # each soldier in his own step phase
            items.append(FigureItem(f, x0 + i * spacing, y + (i % 2) * 6,
                                    pose_fn=lambda t, ph=ph: motion.walk(t, period, ph),
                                    motion_fn=lambda t, v=v: (-v * t, 0)))
        return items
    far_col = column(far_sold, [far_std], [3, 11], 380, 1352, 118, far_v, 18, 1)
    near_col = column(near_sold, near_std, [2, 6], 330, 1770, 215, near_v, 12, 2)

    def near_ground(p):
        M.paving(p, -800, 1600, 3000, 600, a="sand", b="bone", border="terracotta", cell=150)
    ngr = make_sprite(ctx, near_ground, (-800, 1600, 3000, 600), BG_TILE, "s2_nground")

    def cam(t):
        e = ease_in_out(t / 5.0)
        # medium tracking shot: the camera drifts left far slower than the column marches,
        # so the soldiers visibly walk across frame and into the gate
        return dict(zoom=lerp(1.05, 1.08, e), ox=lerp(40, -110, e), oy=0)

    return Scene("s2_gate", 5.0, [
        Layer(0.05, [SpriteItem(sky)]),
        Layer(0.25, [SpriteItem(back)]),
        Layer(GP, [SpriteItem(wallspr)] + wall_top + [SpriteItem(roadspr), SpriteItem(passage)] + onlook
              + far_col + [SpriteItem(gate)]),
        Layer(1.0, [SpriteItem(ngr)] + near_col),
    ], cam, fx=[
        fx.Glow((900, 300), 700, "sun_hot", 0.18, parallax=0.05),
        fx.Dust(150, seed=5, strength=0.4, drift=(-22, -5), region=(0, 0.45, 1, 1), parallax=0.9),
        fx.Dust(90, seed=6, color="sand", strength=0.45, drift=(-60, -10), size=(1.5, 3.5),
                region=(0, 0.84, 1, 0.95), parallax=1.0),
        fx.Haze(1340, 70, "ivory", 0.08, parallax=GP),
        fx.Grade(gain=(1.04, 1.0, 0.95), gamma=1.05, sat=1.06),
        fx.Vignette(0.4),
    ])


# =================================================================== scene 3
def scene3(ctx):
    """Cyrus with Babylonian officials and townspeople in a palace courtyard.
    The meeting is an artistic reconstruction; the green branches on the ground follow
    the Nabonidus Chronicle ('green twigs were spread before him')."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -300, -200, 1700, 900, ["blue_mid", "blue_pale", "sky_pale", "bone"]),
                      (-300, -200, 1700, 900), BG_TILE, "s3_sky")

    def palace(p):
        p.rect(-300, 560, 1700, 820, "sand")
        y = 580
        while y < 1380:
            p.line([(-300, y), (1400, y)], "sand_dk", 2.2)
            y += 26
        M.merlons(p, -300, 1400, 560, 34, "sand")
        M.lion_frieze(p, -300, 1400, 880, 190)
        M.rosette_band(p, -300, 1400, 700, 14, bg="lapis")
        for x in range(-260, 1400, 120):
            p.rect(x, 590, 22, 90, "sand_dk")
        # doorway with glazed surround
        p.rect(380, 1080, 300, 300, "lapis")
        p.rect(410, 1110, 240, 270, "outline")
        p.ellipse(530, 1110, 120, 60, "outline", 180, 360)
        for x in (60, 1000):
            p.rect(x - 70, 560, 140, 820, "sand_dk")
            M.merlons(p, x - 70, x + 70, 560, 30, "sand_dk")
        M.rosette_band(p, -300, 1400, 1360, 12, bg="terracotta_dk")
    pal = make_sprite(ctx, palace, (-300, 480, 1700, 920), BG_TILE, "s3_palace")
    palms = make_sprite(ctx, lambda p: (M.palm(p, -60, 1390, 640, seed=31, lean=0.05),
                                        M.palm(p, 1160, 1390, 600, seed=32, lean=-0.06)),
                        (-400, 600, 1900, 820), BG_TILE, "s3_palms")

    cits = [F.babylonian_citizen(ctx, 0.36, FIG_TILE, variant=i, haze="bone", haze_amt=0.1) for i in range(6)]
    crowd = []
    for i, x in enumerate([-60, 60, 170, 290, 420, 640, 760, 880, 1000, 1120]):
        def pose(t, i=i):
            return motion.idle(t, i * 1.3, head=3.2, arm=1.5)
        crowd.append(FigureItem(cits[(i * 5) % 6], x, 1420 + (i % 3) * 14, flip=(x < 540), pose_fn=pose))

    def floor(p):
        M.paving(p, -400, 1390, 1900, 800, a="bone", b="sand", border="terracotta_dk", cell=110)
    fl = make_sprite(ctx, floor, (-400, 1390, 1900, 800), BG_TILE, "s3_floor")

    def twigs(p):
        rnd = random.Random(5)
        for i in range(16):
            x, y = rnd.uniform(380, 760), rnd.uniform(1690, 1800)
            a = rnd.uniform(-0.4, 0.4)
            L = rnd.uniform(60, 110)
            p.line([(x, y), (x + L, y + a * L)], "green_dk", 4)
            for k in range(4):
                px, py = x + L * (k + 1) / 5, y + a * L * (k + 1) / 5
                p.ellipse(px, py - 8, 9, 5, "green" if k % 2 else "olive")
                p.ellipse(px, py + 8, 9, 5, "green")
    tw = make_sprite(ctx, twigs, (300, 1640, 600, 220), FIG_TILE, "s3_twigs")

    cyrus = F.cyrus(ctx, 0.7, FIG_TILE)
    guard = F.persian_guard(ctx, 0.66, FIG_TILE, variant=2)
    off0 = F.babylonian_official(ctx, 0.66, FIG_TILE, variant=0)
    off1 = F.babylonian_official(ctx, 0.64, FIG_TILE, variant=2)
    off2 = F.babylonian_official(ctx, 0.62, FIG_TILE, variant=1)

    def cyrus_pose(t):
        p = motion.idle(t, 0.9, head=1.0, sway=0.3, arm=0.6, wind=0.7)
        g = motion.gesture(t, 1.1, 2.3, 3.6, 4.6, 1.0)
        p["arm"] = (p["arm"][0] + 24 * g, 0, 0)
        p["hand"] = (p["hand"][0] - 10 * g, 0, 0)
        p["head"] = (p["head"][0] + 2.5 * g, 0, p["head"][2])
        return p

    def off_pose(seed, bow_t):
        def f(t):
            p = motion.idle(t, seed, head=1.4, sway=0.35, arm=0.8)
            b = motion.gesture(t, bow_t, bow_t + 0.9, bow_t + 1.9, bow_t + 2.8, 1.0)
            p["head"] = (p["head"][0] + 7 * b, 0, p["head"][2])
            p["body"] = (p["body"][0] + 2.0 * b, 0, 0)
            return p
        return f

    def cam(t):
        e = ease_in_out(t / 5.0)
        return dict(zoom=lerp(1.03, 1.11, e), ox=lerp(-40, 30, e), oy=lerp(10, -10, e))

    return Scene("s3_court", 5.0, [
        Layer(0.05, [SpriteItem(sky)]),
        Layer(0.3, [SpriteItem(pal)]),
        Layer(0.45, [SpriteItem(palms)]),
        Layer(0.75, [SpriteItem(fl)] + crowd),
        Layer(1.0, [SpriteItem(tw),
                    FigureItem(off2, 70, 1770, flip=True, pose_fn=off_pose(2.2, 1.8)),
                    FigureItem(off1, 210, 1790, flip=True, pose_fn=off_pose(1.4, 1.4)),
                    FigureItem(off0, 360, 1800, flip=True, pose_fn=off_pose(0.6, 1.0)),
                    FigureItem(guard, 960, 1780, pose_fn=lambda t: motion.idle(t, 3.3, head=1.6)),
                    FigureItem(cyrus, 790, 1810, pose_fn=cyrus_pose)]),
    ], cam, fx=[
        fx.Glow((820, 500), 650, "sun_hot", 0.2, parallax=0.1),
        fx.Shafts(-30, 0.05, speed=6, seed=9),
        fx.Dust(110, seed=8, strength=0.3, drift=(-6, -8), region=(0, 0.3, 1, 1)),
        fx.Grade(gain=(1.04, 1.0, 0.95), gamma=1.05, sat=1.05),
        fx.Vignette(0.45),
    ])


# =================================================================== scene 4
def scene4(ctx):
    """Babylon at sunset: the Euphrates, the walls and the Etemenanki ziggurat."""
    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -400, -200, 1900, 1320, ["dusk_violet", "dusk_rose", "dusk_orange", "sun", "sun_hot"]),
        p.ellipse(200, 420, 300, 22, "dusk_rose"), p.ellipse(900, 560, 340, 18, "dusk_orange"),
        p.ellipse(420, 700, 260, 14, "sun"), M.sun(p, 826, 958, 74)),
        (-400, -200, 1900, 1320), BG_TILE, "s4_sky")

    def skyline(p):
        M.ziggurat(p, 380, 1040, 420, 420, col="brick", dark="umber", shrine="lapis_dk")
        for x, h, c in [(-300, 90, "brick"), (-120, 140, "umber"), (600, 110, "brick"), (880, 170, "umber"),
                        (1040, 120, "brick"), (1250, 90, "umber")]:
            p.rect(x, 1040 - h, 170, h + 30, c)
            M.merlons(p, x, x + 170, 1040 - h, 16, c)
        M.wall(p, -400, 1500, 1010, 1080, merlon=16, towers=14, col="brick", dark="umber", courses=False)
        for i, x in enumerate((-200, 120, 560, 660, 1000, 1300)):
            M.palm(p, x, 1085, 150 + (i % 2) * 40, trunk="black", frond="umber", frond2="umber", seed=40 + i)
    sk = make_sprite(ctx, skyline, (-400, 560, 1900, 540), FAR_TILE, "s4_skyline", haze="dusk_violet",
                     haze_amt=0.35)

    def bank(p):
        p.rect(-500, 1070, 2100, 60, "umber")
        M.merlons(p, -500, 1600, 1070, 14, "umber")
    bk = make_sprite(ctx, bank, (-500, 1040, 2100, 100), FAR_TILE, "s4_bank", haze="dusk_violet", haze_amt=0.2)

    def water(p):
        M.sky(p, -500, 1120, 2100, 840, ["dusk_orange", "dusk_rose", "dusk_violet", "lapis_dk", "blue_deep"])
        rnd = random.Random(12)
        for _ in range(170):
            y = rnd.uniform(1130, 1950)
            x = rnd.uniform(-500, 1600)
            L = rnd.uniform(40, 160) * (0.6 + (y - 1120) / 800)
            col = rnd.choice(["dusk_orange", "dusk_rose", "blue_mid", "dusk_violet", "sun"]) if y < 1500 else \
                rnd.choice(["blue_mid", "lapis", "dusk_violet", "blue_deep"])
            p.line([(x, y), (x + L, y)], col, 5 + (y - 1120) / 160)
        p.poly([(796, 1120), (856, 1120), (920, 1950), (730, 1950)], "sun")
        p.poly([(812, 1120), (840, 1120), (870, 1560), (790, 1560)], "sun_hot")
    wsp = make_sprite(ctx, water, (-500, 1120, 2100, 840), FAR_TILE, "s4_water", keep_tiles=True,
                      variation=0.05)
    base_rng = np.random.default_rng(4)

    def water_colors(tl, t):
        if "_ph" not in tl:
            tl["_ph"] = base_rng.uniform(0, 6.28, len(tl["color"])).astype(np.float32)
        col = tl["color"]
        lum = col.mean(1, keepdims=True)
        k = 0.07 + 0.12 * (lum / 255.0) ** 2
        w = np.sin(tl["_ph"] + t * 2.4 + tl["cy"] * 0.03 - tl["cx"] * 0.004)[:, None]
        glint = np.clip(np.sin(tl["_ph"] * 3 + t * 3.1), 0.85, 1.0)[:, None] - 0.85
        return np.clip(col * (1 + k * w) + glint * 4 * lum * (lum > 180), 0, 255)

    def boat(p):
        p.smooth([(-150, 0), (-120, 30), (120, 30), (160, -4), (100, 12), (-100, 12)], "umber", 6)
        p.line([(-130, 6), (140, 4)], "ochre_dk", 4)
        p.line([(30, -150), (-70, 60)], "black", 5)
        p.smooth([(10, 10), (40, 10), (50, -90), (30, -110), (0, -90)], "outline", 5)
        p.circle(32, -122, 18, "outline")
    bt = make_sprite(ctx, boat, (-170, -150, 340, 200), FAR_TILE, "s4_boat")

    def fore(p):
        M.reeds(p, -400, 260, 1990, 300, seed=1, cols=("black", "outline", "umber"))
        M.reeds(p, 900, 1500, 1990, 260, seed=2, cols=("black", "outline", "umber"))
        p.smooth([(-400, 2150), (-400, 1880), (0, 1900), (300, 1960), (500, 2150)], "black", 6)
        p.smooth([(800, 2150), (1100, 1930), (1500, 1900), (1500, 2150)], "black", 6)
        M.palm(p, -40, 1980, 980, trunk="black", frond="outline", frond2="black", seed=50, lean=0.12)
    fg = make_sprite(ctx, fore, (-450, 800, 2000, 1350), BG_TILE, "s4_fore")

    birds = birds_item(_bird_sprites(ctx, "s4b"), [(1000, 640, 0), (1050, 610, 1.1), (1100, 650, 2.0),
                                                    (1160, 630, 0.4), (1220, 660, 2.7)], 45)

    def cam(t):
        e = ease_in_out(t / 5.4)
        return dict(zoom=lerp(1.07, 1.0, e), ox=lerp(-70, 70, e), oy=lerp(-10, 0, e))

    def fade(t):
        return 1.0 - 0.75 * smoothstep((t - 4.4) / 0.6)

    return Scene("s4_sunset", 5.0, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.08, [birds]),
        Layer(0.12, [SpriteItem(sk)]),
        Layer(0.25, [SpriteItem(bk)]),
        Layer(0.45, [TileAnimItem(wsp, water_colors),
                     SpriteItem(bt, lambda t: (900 - 22 * t, 1420 + 4 * math.sin(t * 1.6)))]),
        Layer(1.0, [SpriteItem(fg)]),
    ], cam, fx=[
        fx.Glow((826, 958), 600, "sun_hot", 0.38, breathe=0.03, parallax=0.03),
        fx.Haze(1080, 50, "sun", 0.08, parallax=0.15),
        fx.Dust(90, seed=21, color="sun", strength=0.25, drift=(-8, -3), region=(0, 0.3, 1, 0.8)),
        fx.Grade(gain=(1.06, 0.98, 0.9), gamma=1.04, sat=1.08, fade=fade),
        fx.Vignette(0.5),
    ])


SCENES = [scene1, scene2, scene3, scene4]


def build(ctx):
    return [s(ctx) for s in SCENES]

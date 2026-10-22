"""Episode 02 - Napoleon: From Emperor to Exile. 17 shots, 2.5D mosaic.

Rules applied from LESSONS_LEARNED (Ep01 + experiments C/D):
* moving figures follow world-space paths with path-tangent yaw and multi-view turnaround
  bodies (mosaic.turnrig); feet planted in world space; joints projected through the camera
* profile close-ups use sculpted banded shading + self/contact/cast shadows
* every shot has its own composition, depth planes and camera intent; no reused footage
* cloth and flags move with rigid tiles; fire, water and light animate per tile in place
Builders: fn(ctx, dur) -> Scene.  SHOTS lists them in timeline order.
"""
import math
import random

import numpy as np

from mosaic import fx, motion
from mosaic.depth import Ground, depth_item
from mosaic.geom import S, T, ease_in_out, lerp, smoothstep
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.library import napoleonic as N
from mosaic.palette import P, mix
from mosaic.scene import FigureItem, FnItem, Layer, Scene, SpriteItem, TileAnimItem, TileScatterItem, make_sprite
from mosaic.shotkit import birds, burst, cam, finish, flame_colors, flash, ground_slices, puffs, shimmer_colors
from mosaic.turnrig import Path, TurnDraw, TurnSoldierAssets, TurnWalker

BG, FAR, FIG = 8.0, 6.0, 5.0
VOL = dict(mode="bands", light=(-0.6, -0.8), strength=1.2, ambient=0.3, roundness=1.0)
SH = dict(cast=0.4, contact=0.55, shx=0.6, sy=0.24, blur=2.0)
_ASSETS = {}


def assets(ctx, costume, k_ref, mips):
    key = (costume.name, k_ref, tuple(mips), ctx.W)
    if key not in _ASSETS:
        _ASSETS[key] = TurnSoldierAssets(ctx, k_ref, costume=costume, mips=mips)
    return _ASSETS[key]


def smoke_sprite(ctx, name, col="smoke_lt", col2="smoke", r=90):
    return make_sprite(ctx, lambda p: (p.ellipse(0, 0, r, r * 0.8, col2), p.ellipse(-r * 0.3, -r * 0.25, r * 0.7, r * 0.6, col),
                                       p.ellipse(r * 0.35, -r * 0.1, r * 0.55, r * 0.5, col)),
                       (-r * 1.2, -r * 1.1, r * 2.4, r * 2.1), FAR, name, rows=1)


def flash_sprite(ctx, name, r=60):
    return make_sprite(ctx, lambda p: (p.ellipse(0, 0, r, r * 0.6, "fire"), p.ellipse(-r * 0.2, 0, r * 0.6, r * 0.35, "fire_hot")),
                       (-r * 1.1, -r * 0.7, r * 2.2, r * 1.4), FAR, name, rows=0)


def column(asset_list, path, n, spacing, s_lead, period=1.0, stride=600, side=1, seed=0, **kw):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        out.append(TurnWalker(asset_list[i % len(asset_list)], path, s0=s_lead - i * spacing + rnd.uniform(-12, 12),
                              period=period * rnd.uniform(0.95, 1.06), stride=stride * rnd.uniform(0.96, 1.04),
                              side=side, seed=rnd.uniform(0, 1), **kw))
    return out


# ============================================================================ 1  Toulon, 1793
def s01_artillery(ctx, dur):
    """Young artillery officer Bonaparte directs a battery at the siege of Toulon (1793)."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1500, ["cobalt", "dusk_violet", "dusk_rose", "dusk_orange", "sun"]),
                                      M.sun(p, 260, 1030, 70, rings=("sun_hot", "sun", "amber"))),
                      (-400, -300, 1900, 1500), BG, "n1_sky")

    def harbour(p):
        M.sky(p, -400, 1060, 1900, 160, ["dusk_orange", "lapis", "lapis_dk"])
        p.smooth([(700, 1065), (820, 990), (1000, 960), (1250, 1000), (1500, 1065)], "umber", 6)      # promontory
        p.rect(930, 920, 90, 60, "stone_dk")                                                           # fort
        M.merlons(p, 930, 1020, 920, 14, "stone_dk")
        for i, x in enumerate((-120, 60, 240, 520)):                                                  # ships of the line
            s = 0.8 + 0.25 * (i % 2)
            p.smooth([(x - 70 * s, 1062), (x + 70 * s, 1062), (x + 56 * s, 1080), (x - 56 * s, 1080)], "black", 4)
            for m in (-40, 0, 40):
                p.line([(x + m * s, 1062), (x + m * s, 1062 - 120 * s)], "black", 3)
                p.poly([(x + m * s - 20 * s, 1062 - 110 * s), (x + m * s + 20 * s, 1062 - 110 * s),
                        (x + m * s + 18 * s, 1062 - 60 * s), (x + m * s - 18 * s, 1062 - 60 * s)], "outline")
    hb = make_sprite(ctx, harbour, (-400, 880, 1900, 220), FAR, "n1_harbour", haze="dusk_rose", haze_amt=0.25)
    sea = make_sprite(ctx, lambda p: M.sky(p, -400, 1080, 1900, 160, ["dusk_orange", "lapis", "lapis_dk"]),
                      (-400, 1080, 1900, 160), FAR, "n1_sea", keep_tiles=True)

    def rampart(p):
        p.smooth([(-400, 1500), (-400, 1210), (100, 1180), (600, 1200), (1000, 1190), (1500, 1220), (1500, 1500)], "ochre_dk", 6)
        p.smooth([(-400, 1500), (-400, 1270), (300, 1250), (900, 1260), (1500, 1280), (1500, 1500)], "brick", 6)
        rnd = random.Random(3)
        for _ in range(40):
            x, y = rnd.uniform(-400, 1500), rnd.uniform(1280, 1500)
            p.ellipse(x, y, rnd.uniform(16, 44), rnd.uniform(5, 10), rnd.choice(["umber", "ochre_dk", "sand_dk"]))
        p.rect(-400, 1480, 1900, 520, "umber")
        for k in range(12):                                                                            # timber platform
            p.line([(-400, 1500 + k * 44), (1500, 1500 + k * 44)], "wood", 6)
    rp = make_sprite(ctx, rampart, (-400, 1170, 1900, 840), BG, "n1_rampart")
    t_fire = 0.55
    carriage = make_sprite(ctx, lambda p: N.cannon_carriage(p), (-80, -100, 440, 260), FIG, "n1_carriage", volume=VOL,
                           outline="outline")
    barrel = make_sprite(ctx, N.cannon_barrel, (-210, -40, 490, 80), FIG, "n1_barrel", volume=VOL, outline="outline")

    def recoil(t):
        c = (t - t_fire) / 0.25
        return 0.0 if c <= 0 else 60 * (1 - math.exp(-c * 3))
    cx, cy = 300, 1520
    smk = smoke_sprite(ctx, "n1_smoke", r=110)
    fl = flash_sprite(ctx, "n1_flash", r=70)
    gun_r = N.gunner(ctx, 0.5, FIG, variant=0, tool="rammer", volume=VOL)
    gun_l = N.gunner(ctx, 0.48, FIG, variant=1, tool="linstock", volume=VOL)
    nap = N.napoleon_profile(ctx, 0.92, FIG, outfit="officer", volume=VOL)

    def nap_pose(t):
        p_ = motion.idle(t, 0.4, head=1.2, sway=0.3, arm=0.6)
        g = smoothstep((t - 0.1) / 0.6)
        p_["arm"] = (p_["arm"][0] + 58 * g - 6 * smoothstep((t - t_fire) / 0.3), 0, 0)   # points at the target
        p_["head"] = (p_["head"][0] - 3 * g, 0, p_["head"][2])
        return p_

    def gl_pose(t):
        p_ = motion.idle(t, 1.1, head=2.0, arm=1.0)
        p_["arm"] = (p_["arm"][0] - 40 * (1 - smoothstep((t - t_fire + 0.1) / 0.2)), 0, 0)  # touch-hole, then away
        p_["head"] = (p_["head"][0] - 6 * smoothstep((t - t_fire) / 0.4), 0, p_["head"][2])
        return p_

    def gr_pose(t):
        p_ = motion.idle(t, 2.2, head=1.6, arm=1.0)
        p_["body"] = (p_["body"][0] + 3 * math.sin(max(0, t - 1.2) * 3.2) * smoothstep((t - 1.2) / 0.4), 0, 0)  # rams
        return p_

    def gabions(p):
        for x, y, s in ((-140, 2010, 1.6), (90, 2040, 1.8), (1080, 2020, 1.7)):
            N.gabion(p, x, y, s)
    gb = make_sprite(ctx, gabions, (-300, 1650, 1600, 420), BG, "n1_gabions")
    return finish(Scene("n01_toulon", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.1, [TileAnimItem(sea, lambda tl, t: shimmer_colors(tl, t, 1, 0.12)), SpriteItem(hb)]),
        Layer(0.45, [SpriteItem(rp)]),
        Layer(0.75, [FigureItem(gun_l, 120, 1590, flip=True, pose_fn=gl_pose, shadow=SH),
                     SpriteItem(carriage, lambda t: (cx + recoil(t), cy)),
                     SpriteItem(barrel, lambda t: (cx + 90 + recoil(t), cy - 70)),
                     flash(fl, cx - 140, cy - 70, t_fire, 0.14, 1.3),
                     burst(smk, cx - 230, cy - 80, t_fire, 2.4, 2.6, (-160, -140), 0.85),
                     burst(smk, cx - 120, cy - 40, t_fire + 0.08, 2.6, 2.0, (-60, -90), 0.7),
                     FigureItem(gun_r, 560, 1600, pose_fn=gr_pose, shadow=SH)]),
        Layer(1.0, [FigureItem(nap, 830, 1960, pose_fn=nap_pose, shadow=SH)]),
        Layer(1.3, [SpriteItem(gb)], blur=4.0),
    ], cam(dur, z=(1.0, 1.08), ox=(-30, 20), oy=(0, -20)), fx=[
        fx.Glow((260, 1030), 520, "sun", 0.3, parallax=0.03),
        fx.Dust(90, seed=1, color="sun_hot", strength=0.3, drift=(12, -6), region=(0, 0.4, 1, 1))]), "warm")


# ============================================================================ 2  columns advance
G2 = Ground(vpx=640, horizon=880, D=330, p_ref=0.36)


def s02_advance(ctx, dur):
    """French line infantry in columns advance across open country under their eagles (c. 1805)."""
    g = G2
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1250, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                                      M.cloud(p, 200, 300, 460, 90, "ivory", "gold_lt"), M.cloud(p, 900, 460, 380, 70, "ivory", "gold_lt")),
                      (-400, -300, 1900, 1250), BG, "n2_sky")

    def hills(p):
        p.smooth([(-400, 900), (-100, 780), (300, 820), (700, 760), (1100, 800), (1500, 770), (1500, 900)], "olive", 6)
        p.smooth([(-400, 900), (0, 850), (500, 870), (1000, 840), (1500, 860), (1500, 900)], "green_dk", 6)
        rnd = random.Random(2)
        for i in range(14):
            x = rnd.uniform(-300, 1400)
            p.ellipse(x, 850 + rnd.uniform(-10, 20), 10, 40, "green_dk")
    hl = make_sprite(ctx, hills, (-400, 720, 1900, 200), FAR, "n2_hills", haze="blue_pale", haze_amt=0.35)
    smk = smoke_sprite(ctx, "n2_smoke", "smoke_lt", "stone", 70)

    def field(p):
        p.rect(-600, 870, 2400, 1250, "green")
        rnd = random.Random(5)
        for _ in range(220):
            y = rnd.uniform(890, 2100)
            q = g.q_of_y(y)
            x = rnd.uniform(-600, 1800)
            p.ellipse(x, y, 30 * q, 6 * q, rnd.choice(["olive", "green_dk", "ochre", "emerald"]))
        for k in range(-6, 8):                                                     # furrows to the vanishing point
            p.line([g.project(k * 260, 0.95), g.project(k * 260, 3.6)], mix("green", "olive", 0.5), 4)
    slices = ground_slices(ctx, g, field, (-600, 870, 2400, 1250), BG, "n2_field",
                           (900, 980, 1080, 1200, 1340, 1500, 1700, 1940, 2120))
    A = [assets(ctx, N.FrenchLine(v), 0.17, (2.6, 1.7, 1.15)) for v in range(3)]
    Astd = assets(ctx, N.FrenchLine(0, standard=True), 0.17, (2.6, 1.7, 1.15))
    walkers = []
    for c, (dx, seed) in enumerate(((0, 1), (170, 2), (340, 3))):
        pts = [(900 + dx, g.f / 0.95), (520 + dx, g.f / 1.15), (60 + dx, g.f / 1.6), (-320 + dx, g.f / 2.2), (-640 + dx, g.f / 2.7)]
        al = [A[0], A[1], Astd, A[2], A[0], A[1], A[2]] if c == 1 else [A[0], A[1], A[2]]
        walkers += column(al, Path(pts), 13, 112, 1500 + 60 * c, period=1.0, stride=600, side=1, seed=seed)
    c2 = cam(dur, z=(1.0, 1.04), ox=(30, -30), oy=(0, -10))
    draw = TurnDraw(g, walkers, c2)
    grass = make_sprite(ctx, lambda p: M.reeds(p, -300, 1400, 2000, 160, seed=4, cols=("green_dk", "olive", "emerald")),
                        (-320, 1780, 1740, 240), BG, "n2_grass")
    return finish(Scene("n02_advance", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.12, [SpriteItem(hl)] + puffs(smk, [(150, 840), (1150, 830), (520, 820)], rise=160, period=3.4, drift=50, alpha=0.5, grow=0.6)),
        *slices,
        Layer(1.0, [draw]),
        Layer(1.3, [SpriteItem(grass, lambda t: (6 * math.sin(t * 1.7), 0))], blur=3.0),
    ], c2, fx=[
        fx.Glow((900, 400), 700, "sun", 0.18, parallax=0.05),
        fx.Dust(120, seed=2, color="sand", strength=0.4, drift=(-30, -8), region=(0, 0.5, 1, 1))]), "default")


# ============================================================================ 3  coronation, 1804
def s03_coronation(ctx, dur):
    """Notre-Dame, 2 December 1804: Napoleon raises the crown above his own head (Pius VII present)."""
    VP = (540, 860)

    def back_wall(p):
        p.rect(-300, -300, 1700, 2400, "night")
        p.poly([(280, 80), (800, 80), (800, 1200), (280, 1200)], "stone_dk")
        p.circle(540, 380, 200, "lapis_dk")                                          # rose window
        for k in range(16):
            a = math.radians(k * 22.5)
            p.line([(540, 380), (540 + 200 * math.cos(a), 380 + 200 * math.sin(a))], "stone", 8)
            p.circle(540 + 130 * math.cos(a), 380 + 130 * math.sin(a), 26, ["crimson", "gold", "emerald", "lapis"][k % 4])
        p.circle(540, 380, 60, "gold")
        p.poly([(380, 1200), (700, 1200), (700, 700), (540, 580), (380, 700)], "stone")  # choir arch
        p.poly([(410, 1200), (670, 1200), (670, 720), (540, 620), (410, 720)], "night")
        for i in range(5):                                                           # golden altar candles row
            p.rect(450 + i * 40, 1040, 10, 60, "ivory")
        p.rect(420, 1100, 240, 100, "gold")
        p.rect(520, 920, 40, 120, "gold")
        p.rect(500, 950, 80, 20, "gold")
    bw = make_sprite(ctx, back_wall, (-300, -300, 1700, 2400), BG, "n3_back")
    flames = make_sprite(ctx, lambda p: [p.ellipse(455 + i * 40, 1032, 6, 12, "fire_hot") for i in range(5)],
                         (440, 1010, 200, 40), 2.6, "n3_altarflames", keep_tiles=True)

    def column_pair(q):
        def f(p):
            for side in (-1, 1):
                x = VP[0] + side * 420 * q
                w = 70 * q
                yb = VP[1] + 520 * q
                yt = VP[1] - 980 * q
                p.rect(x - w, yt, 2 * w, yb - yt, "stone")
                p.rect(x - w, yt, w * 0.5, yb - yt, mix("stone", "night", 0.45))
                p.rect(x - w * 1.3, yb - 40 * q, 2.6 * w, 40 * q, "stone_dk")
                p.rect(x - w * 1.25, yt + 100 * q, 2.5 * w, 30 * q, "gold")
                # pointed arch to the next bay
                p.curve([(x, yt + 120 * q), (x - side * 200 * q, yt - 60 * q), (VP[0], yt - 200 * q)], "stone_dk", 26 * q)
                # hangings with golden bees between columns
                hx = x - side * 150 * q
                p.rect(hx - 46 * q, VP[1] - 520 * q, 92 * q, 300 * q, "crimson")
                p.rect(hx - 46 * q, VP[1] - 232 * q, 92 * q, 12 * q, "gold")
                for by in range(3):
                    p.ellipse(hx, VP[1] - 470 * q + by * 80 * q, 8 * q, 10 * q, "gold")
        return f
    cols = []
    for q, par in ((0.75, 0.22), (1.05, 0.34), (1.5, 0.52), (2.3, 0.85)):
        cols.append((make_sprite(ctx, column_pair(q), (-600, -1700, 2300, 3400), BG, f"n3_cols{q}"), par))

    def floor(p):
        p.rect(-600, VP[1] + 300, 2300, 1300, "stone_dk")
        p.poly([(VP[0] - 120, VP[1] + 340), (VP[0] + 120, VP[1] + 340), (VP[0] + 520, 2200), (VP[0] - 520, 2200)], "crimson")
        p.poly([(VP[0] - 110, VP[1] + 340), (VP[0] - 96, VP[1] + 340), (VP[0] - 470, 2200), (VP[0] - 500, 2200)], "gold")
        p.poly([(VP[0] + 110, VP[1] + 340), (VP[0] + 96, VP[1] + 340), (VP[0] + 470, 2200), (VP[0] + 500, 2200)], "gold")
        for k in range(10):                                                          # altar steps
            y = VP[1] + 340 + k * 14
            p.line([(VP[0] - 300, y), (VP[0] + 300, y)], "stone", 3)
    fl = make_sprite(ctx, floor, (-600, VP[1] + 280, 2300, 1400), BG, "n3_floor")
    crowd = []
    for i in range(16):
        side = -1 if i % 2 == 0 else 1
        row = i // 2
        q = 0.95 + 0.06 * row
        f = N.courtier(ctx, 0.2 * q, FIG, variant=i, volume=VOL)
        x = VP[0] + side * (250 + 60 * row) * q
        crowd.append(FigureItem(f, x, VP[1] + 390 * q, flip=(side < 0),
                                pose_fn=lambda t, i=i: motion.react(t, i * 1.3, ["look", "talk", "look", "chest"][i % 4])))
    pope = N.pope_seated(ctx, 0.46, FIG, volume=VOL)
    nap = N.napoleon_profile(ctx, 0.62, FIG, outfit="coronation", volume=VOL)

    def nap_pose(t):
        p_ = motion.idle(t, 0.7, head=0.6, sway=0.2, arm=0.0, wind=0.4)
        raise_ = smoothstep((t - 0.3) / 1.6)
        p_["arm"] = (55 * (1 - raise_), 0, 0)
        p_["crown"] = (-20 * (1 - raise_), 0, 0)
        p_["head"] = (p_["head"][0] + 4 * raise_, 0, p_["head"][2])
        return p_
    throne = make_sprite(ctx, lambda p: (p.rect(730, 960, 190, 400, "crimson"), p.rect(716, 936, 218, 34, "gold"),
                                         p.rect(730, 1200, 190, 160, "crimson_dk")), (700, 920, 250, 460), FIG, "n3_throne",
                         volume=VOL)
    cand = make_sprite(ctx, lambda p: [(p.line([(x, 1200), (x, 2000)], "gold", 16), p.ellipse(x, 1190, 40, 12, "gold"),
                                        p.ellipse(x, 1166, 12, 26, "fire_hot")) for x in (-80, 1160)],
                       (-160, 1120, 1400, 900), FIG, "n3_candelabra", keep_tiles=True)
    return finish(Scene("n03_coronation", dur, [
        Layer(0.12, [SpriteItem(bw), TileAnimItem(flames, lambda tl, t: flame_colors(tl, t, 3))]),
        Layer(0.3, [SpriteItem(fl)]),
        *[Layer(par, [SpriteItem(spr)]) for spr, par in cols[:2]],
        Layer(0.42, crowd + [SpriteItem(throne), FigureItem(pope, 830, 1360, pose_fn=lambda t: motion.idle(t, 2.0, head=1.6)),
                             FigureItem(nap, 450, 1420, pose_fn=nap_pose, shadow=dict(SH, cast=0.0))]),
        *[Layer(par, [SpriteItem(spr)]) for spr, par in cols[2:]],
        Layer(1.3, [TileAnimItem(cand, lambda tl, t: flame_colors(tl, t, 4))], blur=3.0),
    ], cam(dur, z=(1.0, 1.12), oy=(30, -10)), fx=[
        fx.Shafts(-58, 0.09, speed=4, seed=3), fx.Glow((540, 380), 420, "sun", 0.25, parallax=0.12),
        fx.Dust(80, seed=3, color="sun_hot", strength=0.32, drift=(4, 6), region=(0.2, 0.15, 0.8, 0.8))], bg=(18, 20, 40)), "interior")


# ============================================================================ 4  empire map
def eu(lon, lat, ox=60, oy=470, s=19.0):
    return ox + (lon + 11) * s, oy + (63 - lat) * s * 1.36


def s04_map(ctx, dur):
    """The French Empire and dependent states at their height, c. 1811-12 (approximate)."""
    land = N.europe_land()

    def base(p):
        p.rect(-300, -200, 1700, 2400, "lapis_dk")
        rnd = random.Random(4)
        for _ in range(300):
            x, y = rnd.uniform(-100, 1200), rnd.uniform(420, 1450)
            p.line([(x - 9, y), (x, y - 4), (x + 9, y)], "lapis", 4)
        for name, poly in land.items():
            p.smooth([eu(*q) for q in poly], "sand", 3)
        for name, poly in land.items():
            from mosaic.painter import catmull_rom
            p.line(catmull_rom([eu(*q) for q in poly], 3), "navy", 5)
        p.rect(-300, -200, 1700, 560, "navy")
        p.rect(-300, 344, 1700, 14, "gold")
        p.rect(-300, 1460, 1700, 14, "gold")
        p.rect(-300, 1474, 1700, 900, "navy")
    bm = make_sprite(ctx, base, (-300, -200, 1700, 2400), FAR, "n4_base")
    KEY = M.HOLE

    def region(polys, col):
        def f(p):
            for poly in polys:
                p.smooth([eu(*q) for q in poly], col, 3)
        return f
    emp = make_sprite(ctx, region([N.EMPIRE_1812, N.ILLYRIA], "terracotta"), (-100, 300, 1300, 1300), FAR, "n4_empire",
                      keep_tiles=True)
    ally = make_sprite(ctx, region(N.ALLIED_1812, "gold"), (-100, 300, 1300, 1300), FAR, "n4_allies", keep_tiles=True)
    px, py = eu(*N.PLACES_EU["PARIS"])

    def reveal(spr, t0, t1):
        tl = spr.tiles
        ux, uy = tl["cx"] / spr.ppu + spr.x0, tl["cy"] / spr.ppu + spr.y0
        d = np.hypot(ux - px, uy - py)
        d = (d - d.min()) / (np.ptp(d) + 1e-6) + np.random.default_rng(4).uniform(0, 0.06, len(d))
        z = np.zeros(len(d))
        return lambda tl_, t: (z, z, d < (t - t0) / (t1 - t0))

    def swords(p):
        p.line([(-22, -22), (22, 22)], "white", 7)
        p.line([(-22, 22), (22, -22)], "white", 7)
        p.circle(0, 0, 8, "crimson")
    sw = make_sprite(ctx, swords, (-30, -30, 60, 60), 2.5, "n4_swords")
    battles = [((16.76, 49.13), 1.2), ((11.58, 50.93), 1.7), ((21.0, 54.45), 2.2), ((16.56, 48.3), 2.7)]
    marks = [SpriteItem(sw, lambda t, ll=ll: eu(*ll), lambda t, t0=t0: min(1.0, max(0.0, (t - t0) / 0.3)) * (0.75 + 0.25 * math.sin(t * 6)))
             for ll, t0 in battles]
    star = make_sprite(ctx, lambda p: (p.circle(0, 0, 16, "white"), p.circle(0, 0, 9, "gold")), (-20, -20, 40, 40), 2.5, "n4_paris")
    return finish(Scene("n04_map", dur, [
        Layer(1.0, [SpriteItem(bm), TileScatterItem(emp, reveal(emp, 0.1, 1.2), opacity=0.85),
                    TileScatterItem(ally, reveal(ally, 0.9, 2.2), opacity=0.55), SpriteItem(star, lambda t: (px, py))] + marks),
    ], lambda t: dict(zoom=1.0 + 0.04 * ease_in_out(t / dur), ox=10 * ease_in_out(t / dur)), fx=[]), "map")


def map4_labels():
    out = [("PARIS", *eu(*N.PLACES_EU["PARIS"]), 1.0), ("AUSTERLITZ 1805", *eu(16.76, 49.13), 1.2), ("JENA 1806", *eu(11.58, 50.93), 1.7),
           ("FRIEDLAND 1807", *eu(21.0, 54.45), 2.2), ("WAGRAM 1809", *eu(16.56, 48.3), 2.7)]
    return out


# ============================================================================ 5  the Russian plan
def s05_plan(ctx, dur):
    """Napoleon bent over a campaign map by candlelight (1812): the plan against Russia."""
    def tent(p):
        p.rect(-300, -300, 1700, 2400, "green_dk")
        for x in range(-300, 1400, 120):
            p.line([(x, -300), (x + 40, 2100)], mix("green_dk", "black", 0.3), 10)
        p.poly([(380, 300), (700, 300), (680, 760), (400, 760)], "crimson_dk")       # hanging with the imperial eagle
        p.poly([(540, 420), (440, 520), (480, 540), (520, 500), (560, 500), (600, 540), (640, 520)], "gold")
        p.circle(540, 470, 22, "gold_lt")
    tt = make_sprite(ctx, tent, (-300, -300, 1700, 2400), BG, "n5_tent", haze="night", haze_amt=0.15)

    def table(p):
        p.poly([(-200, 1500), (900, 1440), (1300, 2100), (-300, 2100)], "wood")
        p.poly([(-120, 1520), (820, 1470), (1150, 2060), (-200, 2080)], "bone")       # the map sheet
        for k in range(6):
            p.line([(-120 + k * 30, 1520 + k * 100), (820 + k * 60, 1470 + k * 100)], "sand", 2)
        p.smooth([(80, 1600), (300, 1560), (520, 1600), (700, 1700), (760, 1860), (500, 1900), (200, 1840)], "ochre", 4)  # Russia
        p.curve([(120, 1880), (360, 1760), (620, 1660)], "lapis", 8)                  # a river
        p.circle(640, 1650, 14, "crimson")                                            # Moscow
        p.circle(140, 1900, 12, "fr_blue")                                            # the Niemen crossing
    tb = make_sprite(ctx, table, (-320, 1420, 1640, 700), FIG, "n5_table", volume=dict(VOL, strength=0.6))
    candle = make_sprite(ctx, lambda p: (p.rect(940, 1380, 30, 120, "ivory"), p.ellipse(955, 1366, 14, 30, "fire_hot"),
                                         p.ellipse(955, 1376, 8, 16, "white")), (920, 1320, 70, 190), 2.6, "n5_candle", keep_tiles=True)
    nap = N.napoleon_profile(ctx, 1.25, FIG, outfit="redingote", volume=VOL)
    marshal = N.courtier(ctx, 0.62, FIG, variant=2, volume=VOL)

    def nap_pose(t):
        p_ = motion.idle(t, 0.2, head=0.8, sway=0.2, arm=0.0, wind=0.2)
        p_["body"] = (-9 + 1.2 * math.sin(t * 0.8), 0, 0)                            # leaning over the table
        p_["arm"] = (64 + 10 * math.sin(t * 1.6), 0, 0)                               # hand travels across the map
        p_["head"] = (12 - 5 * smoothstep((t - 0.6) / 0.8), 0, p_["head"][2])          # looks down, then east
        return p_
    return finish(Scene("n05_plan", dur, [
        Layer(0.2, [SpriteItem(tt)]),
        Layer(0.45, [FigureItem(marshal, 200, 1500, flip=True, pose_fn=lambda t: motion.react(t, 1.0, "talk"))], blur=4.0),
        Layer(1.0, [FigureItem(nap, 800, 2090, pose_fn=nap_pose), SpriteItem(tb)]),
        Layer(1.25, [TileAnimItem(candle, lambda tl, t: flame_colors(tl, t, 5, 0.3))], blur=lambda t: 3.0 * smoothstep(t / 1.2)),
    ], cam(dur, z=(1.04, 1.1), ox=(-30, 10), oy=(-20, 10)), fx=[
        fx.Glow((955, 1366), 520, "fire", 0.42, breathe=0.12, parallax=1.25),
        fx.Dust(50, seed=5, color="sun_hot", strength=0.25, drift=(2, -6), region=(0.4, 0.4, 1, 0.9))], bg=(14, 20, 16)), "interior")


# ============================================================================ 6  the march east
G6 = Ground(vpx=540, horizon=760, D=330, p_ref=0.36)


def s06_march(ctx, dur):
    """The multinational Grande Armée marches east along a long road (summer 1812)."""
    g = G6
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1100, ["blue_mid", "blue_pale", "gold_lt", "sun"]),
                                      M.cloud(p, 300, 260, 420, 80, "ivory", "gold_lt"), M.sun(p, 600, 720, 50)),
                      (-400, -300, 1900, 1100), BG, "n6_sky")

    def land(p):
        p.rect(-600, 750, 2400, 1400, "gold")
        rnd = random.Random(6)
        for _ in range(260):                                                          # wheat and meadow patches
            y = rnd.uniform(760, 2100)
            q = g.q_of_y(y)
            x = rnd.uniform(-600, 1800)
            p.ellipse(x, y, 40 * q, 7 * q, rnd.choice(["ochre", "amber", "olive", "gold_lt", "green"]))
        qs = np.linspace(0.8, 3.8, 30)
        xc = lambda q: -40 + 26 * (q - 1)
        left = [g.project(xc(q) - 170, q) for q in qs]
        right = [g.project(xc(q) + 170, q) for q in qs]
        p.poly(left + right[::-1], "sand")
        for q in qs[::2]:
            x, y = g.project(xc(q) + 40 * math.sin(q * 5), q)
            p.ellipse(x, y, 60 * q, 6 * q, "sand_dk")
    slices = ground_slices(ctx, g, land, (-600, 740, 2400, 1400), BG, "n6_land", (760, 820, 900, 1000, 1140, 1320, 1560, 1860, 2140))

    def poplars(q_list, side):
        def f(p):
            for q in q_list:
                x, y = g.project(-40 + 26 * (q - 1) + side * 300, q)
                h = 520 * q
                p.line([(x, y), (x, y - h * 0.3)], "umber", 10 * q)
                p.ellipse(x, y - h * 0.62, 40 * q, h * 0.4, "green_dk")
                p.ellipse(x - 10 * q, y - h * 0.68, 22 * q, h * 0.3, "green")
        return f
    trees = [(make_sprite(ctx, poplars((0.9, 1.0, 1.12, 1.26), s_), (-600, 0, 2400, 1300), BG, f"n6_poplar_far{s_}"), g.parallax(1.08))
             for s_ in (-1, 1)]
    trees += [(make_sprite(ctx, poplars((1.45, 1.75, 2.15), s_), (-900, -400, 2900, 2400), BG, f"n6_poplar_near{s_}"), g.parallax(1.8))
              for s_ in (-1, 1)]
    A = [assets(ctx, N.FrenchLine(v), 0.17, (2.4, 1.5, 0.95)) for v in range(3)]
    Astd = assets(ctx, N.FrenchLine(1, standard=True), 0.17, (2.4, 1.5, 0.95))
    xc = lambda q: -40 + 26 * (q - 1)
    pts = [(xc(q) - 60, g.f / q) for q in (3.0, 2.3, 1.7, 1.25, 0.95, 0.82)]
    pts2 = [(x + 120, z) for x, z in pts]
    w1 = column([A[0], A[1], A[2], Astd, A[0], A[2]], Path(pts), 14, 105, 980, period=1.0, stride=600, side=1, seed=6)
    w2 = column([A[1], A[2], A[0]], Path(pts2), 14, 108, 940, period=1.02, stride=600, side=-1, seed=7)
    c6 = cam(dur, z=(1.0, 1.03), ox=(0, 0), oy=(40, -40))
    draw = TurnDraw(g, w1 + w2, c6)
    dust = smoke_sprite(ctx, "n6_dust", "sand", "sand_dk", 60)
    return finish(Scene("n06_march", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        *slices[:3],
        *[Layer(p_, [SpriteItem(s_)]) for s_, p_ in trees[:2]],
        *slices[3:],
        Layer(1.0, [draw] + puffs(dust, [g.project(200, 1.5), g.project(260, 2.1)], rise=50, period=2.4, drift=-40, alpha=0.35, grow=0.8)),
        *[Layer(p_, [SpriteItem(s_)]) for s_, p_ in trees[2:]],
    ], c6, fx=[
        fx.Glow((600, 720), 600, "sun", 0.3, parallax=0.03),
        fx.Dust(120, seed=6, color="sand", strength=0.4, drift=(-8, -10), region=(0, 0.4, 1, 1))]), "warm")


# ============================================================================ 7  Moscow from the hills
G7 = Ground(vpx=540, horizon=1060, D=330, p_ref=0.36)


def moscow_skyline(p, base, glow=False):
    """Kremlin walls and towers, cathedral domes, Ivan the Great bell tower, St Basil's (all pre-1812)."""
    wall = "brick"
    p.rect(-300, base - 90, 1700, 90, wall)
    M.merlons(p, -300, 1400, base - 90, 14, wall)
    for x, h in ((60, 230), (300, 200), (720, 260), (980, 210)):
        N.kremlin_tower(p, x, base - 80, 70, h, wall, "green_dk")
    p.rect(470, base - 400, 70, 320, "ivory")                                    # Ivan the Great bell tower
    p.rect(480, base - 470, 50, 80, "ivory")
    N.onion_dome(p, 505, base - 470, 60, 80, "gold")
    for x, w, h, c in ((380, 70, 90, "gold"), (600, 60, 80, "gold"), (650, 50, 70, "gold"), (820, 90, 110, "crimson"),
                       (880, 60, 90, "emerald"), (930, 70, 100, "lapis"), (860, 50, 70, "gold")):
        p.rect(x - w * 0.42, base - 170, w * 0.84, 90, "ivory")
        N.onion_dome(p, x, base - 170, w, h, c)
    rnd = random.Random(7)
    for _ in range(40):                                                            # wooden town around
        x = rnd.uniform(-300, 1400)
        if 0 < x < 1060:
            continue
        p.rect(x, base - rnd.uniform(40, 90), rnd.uniform(40, 80), 90, rnd.choice(["wood", "umber", "sand_dk"]))


def s07_moscow(ctx, dur):
    """September 1812: the army reaches the hills before Moscow (Napoleon waited on Poklonnaya Hill)."""
    g = G7
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1400, ["cobalt", "blue_mid", "blue_pale", "gold_lt", "dusk_orange"]),
                                      M.cloud(p, 820, 380, 420, 70, "ivory", "gold_lt")), (-400, -300, 1900, 1400), BG, "n7_sky")
    city = make_sprite(ctx, lambda p: (p.rect(-300, 1060, 1700, 260, "olive"), moscow_skyline(p, 1020),
                                       M.river(p, -300, 1020, 1700, 40, ["blue_mid", "lapis"])),
                       (-300, 440, 1700, 880), FAR, "n7_city", haze="blue_pale", haze_amt=0.2)
    river = make_sprite(ctx, lambda p: M.sky(p, -300, 1020, 1700, 46, ["blue_pale", "blue_mid", "lapis"]),
                        (-300, 1015, 1700, 56), FAR, "n7_river", keep_tiles=True)

    def hill(p):
        p.smooth([(-500, 2200), (-500, 1240), (200, 1180), (700, 1200), (1200, 1160), (1600, 1220), (1600, 2200)], "olive", 8)
        p.smooth([(-500, 2200), (-500, 1400), (400, 1330), (1000, 1360), (1600, 1320), (1600, 2200)], "green_dk", 8)
        rnd = random.Random(8)
        for _ in range(90):
            x, y = rnd.uniform(-500, 1600), rnd.uniform(1260, 2150)
            p.ellipse(x, y, rnd.uniform(20, 50), rnd.uniform(5, 10), rnd.choice(["ochre", "green", "amber"]))
    hl = make_sprite(ctx, hill, (-500, 1150, 2100, 1060), BG, "n7_hill")
    A = [assets(ctx, N.FrenchLine(v), 0.17, (2.5, 1.7)) for v in range(3)]
    Astd = assets(ctx, N.FrenchLine(2, standard=True), 0.17, (2.5, 1.7))
    An = assets(ctx, N.NapoleonCostume("redingote"), 0.17, (2.5, 1.7))
    c7 = cam(dur, z=(1.0, 1.05), oy=(80, -20))
    nap = TurnWalker(An, Path([(-150, g.f / 2.6), (-150, g.f / 2.3), (-150, g.f / 2.0)]), s0=60, idle=True, side=1,
                     head_fn=lambda t: -10 * math.sin(t * 0.7))
    men = []
    for i, (X, q, a_, idle) in enumerate(((140, 2.15, A[0], True), (260, 2.3, Astd, True), (-330, 1.9, A[1], True),
                                          (400, 1.95, A[2], False), (-20, 1.8, A[1], False))):
        pth = Path([(X + 60, g.f / (q + 0.4)), (X, g.f / q), (X - 30, g.f / (q - 0.4))])
        men.append(TurnWalker(a_, pth, s0=40 if idle else 0, idle=idle, side=1 if i % 2 else -1, seed=i * 0.31,
                              head_fn=(lambda t, i=i: 8 * math.sin(t * 0.9 + i)) if idle else None))
    draw = TurnDraw(g, men + [nap], c7)
    return finish(Scene("n07_moscow", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.12, [SpriteItem(city), TileAnimItem(river, lambda tl, t: shimmer_colors(tl, t, 7, 0.15))]),
        Layer(0.75, [SpriteItem(hl)]),
        Layer(1.0, [draw]),
    ], c7, fx=[fx.Glow((300, 900), 700, "sun", 0.22, parallax=0.05), fx.Haze(1010, 60, "blue_pale", 0.08, parallax=0.12),
               fx.Dust(60, seed=7, color="sun_hot", strength=0.25, drift=(6, -4))]), "warm")


# ============================================================================ 8  Moscow burning
def s08_fire(ctx, dur):
    """Night of 15-18 September 1812: fires sweep the largely wooden city."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -300, 1900, 1500, ["night", "burgundy", "crimson_dk", "dusk_orange", "fire"]),
                      (-400, -300, 1900, 1500), BG, "n8_sky")
    dome_sil = make_sprite(ctx, lambda p: [N.onion_dome(p, x, 1000, w, h, "black") or p.rect(x - w * 0.4, 1000, w * 0.8, 300, "black")
                                           for x, w, h in ((200, 90, 120), (520, 130, 170), (640, 80, 110), (900, 100, 140))],
                           (-100, 700, 1300, 620), FAR, "n8_domes")

    def houses(p):
        rnd = random.Random(8)
        x = -300
        while x < 1400:
            w = rnd.uniform(140, 240)
            h = rnd.uniform(180, 300)
            p.rect(x, 1500 - h, w, h + 400, "wood")
            p.poly([(x - 10, 1500 - h), (x + w / 2, 1500 - h - 110), (x + w + 10, 1500 - h)], "umber")
            for k in range(int(h / 50)):
                p.line([(x, 1500 - h + 30 + k * 50), (x + w, 1500 - h + 30 + k * 50)], "umber", 5)
            p.rect(x + w * 0.35, 1500 - h * 0.6, w * 0.3, h * 0.3, "fire")
            x += w + rnd.uniform(-10, 20)
    hs = make_sprite(ctx, houses, (-300, 1000, 1700, 900), BG, "n8_houses")

    def flames(p):
        rnd = random.Random(18)
        for _ in range(26):
            x = rnd.uniform(-250, 1350)
            base = rnd.uniform(1180, 1420)
            h = rnd.uniform(200, 440)
            w = rnd.uniform(60, 120)
            p.smooth([(x - w, base), (x - w * 0.5, base - h * 0.5), (x - w * 0.2, base - h * 0.8), (x, base - h), (x + w * 0.3, base - h * 0.7),
                      (x + w * 0.6, base - h * 0.4), (x + w, base)], "fire", 6)
            p.smooth([(x - w * 0.5, base), (x - w * 0.2, base - h * 0.5), (x, base - h * 0.62), (x + w * 0.3, base - h * 0.45),
                      (x + w * 0.5, base)], "fire_hot", 5)
    fl = make_sprite(ctx, flames, (-300, 700, 1700, 760), FAR, "n8_flames", keep_tiles=True)
    smk = smoke_sprite(ctx, "n8_smoke", "smoke", "stone_dk", 140)
    ember = make_sprite(ctx, lambda p: p.ellipse(0, 0, 5, 5, "fire_hot"), (-8, -8, 16, 16), 2.0, "n8_ember", rows=0)
    rnd = np.random.default_rng(8)
    E = rnd.uniform(0, 1, (70, 4))

    def embers(t):
        out = []
        for e in E:
            c = (t * (0.2 + 0.25 * e[2]) + e[3]) % 1.0
            x = -100 + 1300 * e[0] + 60 * math.sin(t * 1.5 + e[1] * 9)
            y = 1500 - 1300 * c
            out.append((ember.premult, T(x, y) @ ember.pixel_to_unit(), 0.9 * math.sin(math.pi * c)))
        return out
    sol = [N.gunner(ctx, 0.95, FIG, variant=v, tool="linstock", volume=dict(VOL, strength=0.9), ) for v in (0, 1)]
    for f_ in sol:                                   # backlit by the fire: near-silhouettes with a warm rim
        for nm, spr in f_.sprites.items():
            pm = spr.premult.astype(np.float32)
            pm[..., :3] = pm[..., :3] * 0.22 + pm[..., 3:4] * np.array([24, 10, 8], np.float32) / 255 * 255 * 0.0
            spr.premult = pm.clip(0, 255).astype(np.uint8)
    sil = [FigureItem(sol[0], 230, 2060, flip=True, pose_fn=lambda t: motion.react(t, 0.4, "look")),
           FigureItem(sol[1], 860, 2100, pose_fn=lambda t: motion.react(t, 1.7, "point"))]
    return finish(Scene("n08_fire", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.1, puffs(smk, [(150, 900), (600, 820), (1000, 900)], rise=500, period=4.0, drift=120, alpha=0.6, grow=1.2)),
        Layer(0.14, [SpriteItem(dome_sil)]),
        Layer(0.3, [TileAnimItem(fl, lambda tl, t: flame_colors(tl, t, 8, 0.35, 9)), SpriteItem(hs)]),
        Layer(0.6, [FnItem(embers)]),
        Layer(1.0, sil),
    ], cam(dur, z=(1.0, 1.05), ox=(-30, 30)), fx=[fx.Glow((560, 1250), 900, "fire", 0.4, breathe=0.15, parallax=0.3)],
        bg=(20, 10, 14)), "night")


# ============================================================================ 9  the retreat
G9 = Ground(vpx=700, horizon=820, D=330, p_ref=0.36)


def s09_retreat(ctx, dur):
    """October-December 1812: the retreat. Hunger, typhus, exhaustion, Cossack attacks and cold."""
    g = G9
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -300, 1900, 1200, ["stone_dk", "stone", "snow_sh", "ice"]),
                      (-400, -300, 1900, 1200), BG, "n9_sky")

    def snowfield(p):
        p.rect(-600, 810, 2400, 1400, "snow")
        rnd = random.Random(9)
        for _ in range(180):
            y = rnd.uniform(820, 2150)
            q = g.q_of_y(y)
            p.ellipse(rnd.uniform(-600, 1800), y, 60 * q, 8 * q, rnd.choice(["snow_sh", "ice", "white"]))
        qs = np.linspace(0.85, 3.6, 24)
        xc = lambda q: -60 - 120 * (q - 1)
        p.poly([g.project(xc(q) - 160, q) for q in qs] + [g.project(xc(q) + 160, q) for q in qs[::-1]], "ice")
        for q in qs[::2]:
            x, y = g.project(xc(q), q)
            p.ellipse(x, y, 40 * q, 5 * q, "snow_sh")
    slices = ground_slices(ctx, g, snowfield, (-600, 800, 2400, 1400), BG, "n9_snow", (830, 900, 990, 1110, 1260, 1460, 1720, 2040, 2210))

    def birches(qs, side):
        def f(p):
            for q in qs:
                x, y = g.project(side * 520 - 60, q)
                h = 600 * q
                p.line([(x, y), (x + 10 * q, y - h)], "white", 14 * q)
                for k in range(6):
                    p.line([(x, y - h * (0.3 + 0.1 * k)), (x + 6 * q, y - h * (0.3 + 0.1 * k))], "black", 4 * q)
                for k in range(5):
                    a = -0.6 + 0.3 * k
                    p.line([(x + 5 * q, y - h * 0.8), (x + 5 * q + 120 * q * math.sin(a), y - h * 0.8 - 120 * q * math.cos(a))], "stone_dk", 4 * q)
        return f
    trees = [make_sprite(ctx, birches((1.0, 1.15, 1.35), s_), (-600, -300, 2400, 1400), BG, f"n9_birch{s_}") for s_ in (-1, 1)]

    def wreck(p):
        x, y = g.project(330, 1.9)
        N.cannon_carriage(p)
    cart = make_sprite(ctx, lambda p: (p.push(), p.translate(*g.project(380, 1.55)), p.scale(0.55), p.rotate(-14),
                                       N.cannon_carriage(p), p.pop(), p.push(), p.translate(*g.project(380, 1.55)), p.scale(0.55),
                                       p.rotate(-14), p.translate(60, -60), N.cannon_barrel(p), p.pop(),
                                       p.smooth([(g.project(330, 1.55)[0], g.project(330, 1.55)[1] + 10), (g.project(520, 1.55)[0], g.project(520, 1.5)[1] - 20),
                                                 (g.project(560, 1.55)[0], g.project(560, 1.6)[1] + 20)], "snow", 5)),
                       (300, 1100, 900, 500), FIG, "n9_cart", volume=VOL)
    A = [assets(ctx, N.Retreat(v), 0.17, (2.6, 1.7, 1.15)) for v in range(3)]
    xc = lambda q: -60 - 120 * (q - 1)
    pts = [(xc(q) + 40, g.f / q) for q in (0.85, 1.1, 1.45, 1.9, 2.4, 2.9)]
    pts2 = [(x - 110, z) for x, z in pts]
    w = column(A, Path(pts), 9, 135, 1200, period=1.35, stride=430, side=-1, seed=9, lean=10.0, arm=5.0, head_lead=40)
    w += column(A[::-1], Path(pts2), 8, 150, 1100, period=1.42, stride=420, side=-1, seed=10, lean=12.0, arm=4.0, head_lead=40)
    c9 = cam(dur, z=(1.0, 1.06), ox=(40, -40), oy=(0, -20))
    draw = TurnDraw(g, w, c9, tint=(0.7, 0.75, 0.88))
    crows = birds(ctx, "n9b", [(1100, 300, 0, 1.6), (1160, 340, 1, 1.6), (1220, 280, 2, 1.6)], 60, 0.5, "black")
    return finish(Scene("n09_retreat", dur, [
        Layer(0.03, [SpriteItem(sky), crows]),
        *slices[:4],
        Layer(g.parallax(1.15), [SpriteItem(trees[0]), SpriteItem(trees[1])]),
        *slices[4:],
        Layer(g.parallax(1.55), [SpriteItem(cart)]),
        Layer(1.0, [draw]),
    ], c9, fx=[fx.Dust(260, seed=9, color="white", strength=0.7, drift=(-90, 140), size=(1.4, 4.0), parallax=1.0),
               fx.Dust(160, seed=19, color="snow", strength=0.5, drift=(-140, 220), size=(0.8, 2.0), parallax=0.5),
               fx.Haze(830, 90, "snow", 0.2, parallax=0.15)]), "cold")


# ============================================================================ 10  the coalition
def s10_coalition(ctx, dur):
    """1813: Russia, Prussia, Austria, Britain, Sweden and others unite (Sixth Coalition)."""
    def bg(p):
        p.rect(-300, -200, 1700, 2400, "navy")
        land = N.europe_land()
        for poly in land.values():
            p.smooth([eu(*q) for q in poly], mix("navy", "stone_dk", 0.35), 3)
        p.smooth([eu(*q) for q in N.EMPIRE_1812], mix("terracotta", "navy", 0.35), 3)
    b = make_sprite(ctx, bg, (-300, -200, 1700, 2400), FAR, "n10_bg")
    kinds = ["russia", "prussia", "austria", "britain", "sweden"]
    flags = [N.flag_pole(ctx, 0.62, k, FIG, pole_h=1050, finial="spear", volume=VOL) for k in kinds]
    starts = [(-420, 1820), (1500, 1760), (-400, 1600), (1480, 1580), (540, 2600)]
    ends = [(150, 1800), (930, 1760), (330, 1620), (750, 1600), (540, 1700)]

    def mover(i):
        def m(t):
            e = smoothstep((t - 0.1 * i) / 1.3)
            return (ends[i][0] - starts[i][0]) * (e - 1), (ends[i][1] - starts[i][1]) * (e - 1)
        return m
    items = [FigureItem(flags[i], ends[i][0], ends[i][1], pose_fn=lambda t, i=i: {"_phase": i * 0.7, "_wind": 1.2},
                        motion_fn=mover(i)) for i in (2, 3, 0, 1, 4)]
    arrow = make_sprite(ctx, lambda p: p.poly([(0, -14), (180, -14), (180, -36), (240, 0), (180, 36), (180, 14), (0, 14)], "crimson"),
                        (-10, -40, 260, 80), 3.0, "n10_arrow")
    px, py = eu(*N.PLACES_EU["PARIS"])
    arrows = []
    for i, (ang, d0) in enumerate(((0, 620), (-35, 560), (32, 520), (150, 470))):
        def fn(t, ang=ang, d0=d0, i=i):
            e = smoothstep((t - 0.4 - 0.15 * i) / 1.2)
            d = d0 * (1 - 0.55 * e)
            a = math.radians(ang)
            x, y = px + d * math.cos(a), py + d * math.sin(a)
            from mosaic.geom import R
            return [(arrow.premult, T(x, y) @ R(ang + 180) @ arrow.pixel_to_unit(), min(1.0, e * 3))]
        arrows.append(FnItem(fn))
    return finish(Scene("n10_coalition", dur, [
        Layer(0.3, [SpriteItem(b)] + arrows),
        Layer(1.0, items),
    ], cam(dur, z=(1.03, 1.0)), fx=[fx.Glow((540, 900), 700, "sun", 0.14)]), "map")


def coalition_labels():
    return [("RUSSIA", 150, 1860), ("PRUSSIA", 930, 1820), ("AUSTRIA", 330, 1680), ("BRITAIN", 750, 1660), ("SWEDEN", 540, 1760)]


# ============================================================================ 11  Fontainebleau, April 1814
G11 = Ground(vpx=540, horizon=900, D=330, p_ref=0.36)


def s11_farewell(ctx, dur):
    """20 April 1814, Fontainebleau: Napoleon leaves his Old Guard for exile on Elba."""
    g = G11
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1300, ["stone_dk", "blue_pale", "sky_pale", "bone"]),
                                      M.cloud(p, 300, 300, 520, 90, "bone", "stone"), M.cloud(p, 900, 420, 420, 80, "bone", "stone")),
                      (-400, -300, 1900, 1300), BG, "n11_sky")

    def palace(p):
        p.rect(-300, 560, 1700, 360, "bone")
        for x in range(-280, 1400, 90):
            p.rect(x, 620, 40, 80, "lapis_dk")
            p.rect(x, 760, 40, 80, "lapis_dk")
        p.poly([(-300, 560), (1400, 560), (1400, 470), (-300, 470)], "lapis_dk")                  # slate roof
        for x in range(-260, 1400, 180):
            p.rect(x, 430, 30, 60, "stone")
        p.rect(400, 470, 280, 450, "bone")                                                       # central pavilion
        p.poly([(380, 470), (540, 360), (700, 470)], "lapis_dk")
        # horseshoe staircase
        for k in range(10):
            w = 260 - k * 16
            p.smooth([(540 - w, 920 - k * 14), (540 - w * 0.6, 860 - k * 14), (540, 840 - k * 14), (540 + w * 0.6, 860 - k * 14),
                      (540 + w, 920 - k * 14)], "stone" if k % 2 else "stone_dk", 4)
    pl = make_sprite(ctx, palace, (-300, 340, 1700, 600), FAR, "n11_palace", haze="sky_pale", haze_amt=0.12)

    def court(p):
        p.rect(-600, 890, 2400, 1300, "sand_dk")
        for q in np.linspace(0.95, 3.4, 14):
            p.line([g.project(-1400, q), g.project(1400, q)], "stone_dk", 3 * q)
        for X in range(-1400, 1500, 200):
            p.line([g.project(X, 0.95), g.project(X, 3.4)], "stone_dk", 3)
    slices = ground_slices(ctx, g, court, (-600, 880, 2400, 1300), BG, "n11_court", (910, 980, 1070, 1190, 1350, 1560, 1820, 2120))
    AG = [assets(ctx, N.OldGuard(v), 0.17, (2.0, 1.4)) for v in range(3)]
    An = assets(ctx, N.NapoleonCostume("redingote"), 0.17, (2.0, 1.4))
    guards = []
    for i in range(9):
        q = 1.25 + 0.09 * i
        X = 120 + 30 * i
        pth = Path([(X + 50, g.f / q), (X, g.f / q), (X - 50, g.f / q)])           # facing left, along the line
        pth = Path([(X, g.f / (q - 0.3)), (X, g.f / q), (X, g.f / (q + 0.3))])     # facing the camera
        guards.append(TurnWalker(AG[i % 3], pth, s0=40, idle=True, side=1, seed=i * 0.23,
                                 head_fn=lambda t, i=i: 6 * math.sin(t * 0.6 + i) - 12 * smoothstep((t - 1.0) / 2.0)))
    # Napoleon walks from the guard line toward the carriage, turning away from the camera
    pth = Path([(60, g.f / 1.95), (-20, g.f / 1.85), (-120, g.f / 1.6), (-200, g.f / 1.35), (-250, g.f / 1.15)])
    nap = TurnWalker(An, pth, s0=30, period=1.1, stride=520, side=1, seed=0.4, arm=6.0)

    def carriage(p):
        x, y = g.project(-330, 1.08)
        s = 1.08 * 0.17 * 1.0
        p.push()
        p.translate(x, y)
        p.scale(s * 5.4)
        p.smooth([(-60, -40), (60, -40), (70, -120), (-70, -120)], "green_dk", 4)
        p.rect(-70, -132, 140, 14, "black")
        p.rect(-40, -100, 40, 40, "sky_pale")
        for wx in (-48, 48):
            p.circle(wx, -24, 26, "black")
            p.circle(wx, -24, 18, "wood")
        p.rect(-130, -64, 70, 8, "black")
        p.pop()
    ca = make_sprite(ctx, carriage, (-100, 600, 700, 500), FIG, "n11_carriage", volume=VOL)
    horse = F.horse(ctx, 0.17 * 1.08 * 0.7, FIG, variant=2, rider=False)
    hx, hy = g.project(-470, 1.08)
    c11 = cam(dur, z=(1.0, 1.05), ox=(20, -40))
    draw = TurnDraw(g, guards + [nap], c11)
    return finish(Scene("n11_farewell", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.25, [SpriteItem(pl)]),
        *slices,
        Layer(g.parallax(1.08), [SpriteItem(ca), FigureItem(horse, hx, hy, pose_fn=lambda t: {"neck": (4 * math.sin(t * 1.3), 0, 0),
                                                                                             "tail": (0, 0, 0)})]),
        Layer(1.0, [draw]),
    ], c11, fx=[fx.Glow((300, 400), 700, "sun_hot", 0.12, parallax=0.05)]), "default", sat=1.1)


# ============================================================================ 12  return, March 1815
G12 = Ground(vpx=540, horizon=980, D=330, p_ref=0.36)


def s12_return(ctx, dur):
    """1 March 1815: Napoleon lands at Golfe-Juan with about a thousand men and marches on Paris."""
    g = G12
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1300, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                                      M.cloud(p, 250, 360, 400, 70, "ivory", "gold_lt")), (-400, -300, 1900, 1300), BG, "n12_sky")
    sea = make_sprite(ctx, lambda p: M.sky(p, -400, 980, 1900, 260, ["blue_mid", "turquoise", "lapis"]), (-400, 975, 1900, 270), FAR,
                      "n12_sea", keep_tiles=True)

    def brig(p):
        x, y = 820, 1000
        p.smooth([(x - 90, y), (x + 90, y), (x + 70, y + 26), (x - 70, y + 26)], "black", 4)
        for m in (-30, 30):
            p.line([(x + m, y), (x + m, y - 170)], "umber", 4)
            for k in range(3):
                p.poly([(x + m - 34 + k * 4, y - 160 + k * 50), (x + m + 34 - k * 4, y - 160 + k * 50),
                        (x + m + 30 - k * 4, y - 120 + k * 50), (x + m - 30 + k * 4, y - 120 + k * 50)], "bone")
    br = make_sprite(ctx, brig, (700, 800, 240, 240), FAR, "n12_brig")

    def beach(p):
        p.rect(-600, 1180, 2400, 1000, "sand")
        rnd = random.Random(12)
        for _ in range(140):
            y = rnd.uniform(1200, 2150)
            q = g.q_of_y(y)
            p.ellipse(rnd.uniform(-600, 1800), y, 40 * q, 6 * q, rnd.choice(["sand_dk", "bone", "ochre"]))
        p.smooth([(-600, 1190), (0, 1210), (500, 1196), (1000, 1214), (1800, 1196), (1800, 1240), (-600, 1240)], "white", 4)
    slices = ground_slices(ctx, g, beach, (-600, 1170, 2400, 1000), BG, "n12_beach", (1180, 1260, 1360, 1490, 1660, 1880, 2140))
    boat = make_sprite(ctx, lambda p: (p.smooth([(-150, 0), (-120, 40), (130, 40), (160, -6), (100, 14), (-100, 14)], "wood", 5),
                                       p.line([(-140, 4), (150, 2)], "umber", 5)), (-170, -30, 340, 90), FIG, "n12_boat", volume=VOL)
    bx, by = g.project(-250, 1.08)
    An = assets(ctx, N.NapoleonCostume("redingote"), 0.17, (2.6, 1.7))
    AG = [assets(ctx, N.OldGuard(v), 0.17, (2.6, 1.7)) for v in range(3)]
    Afl = assets(ctx, N.FrenchLine(0, standard=True), 0.17, (2.6, 1.7))
    Afl.costume.flag = N.flag_art("fr1812")
    # path ends at q 1.9 so his face stays above the caption band (y 1340-1480)
    pth = Path([(-120, g.f / 1.12), (-80, g.f / 1.3), (-30, g.f / 1.55), (10, g.f / 1.75), (25, g.f / 1.92)])
    nap = TurnWalker(An, pth, s0=0, period=1.05, stride=560, side=1, seed=0.2, arm=8.0)
    pth2 = Path([(x + 180, z) for x, z in pth.P[::10]])
    pth3 = Path([(x - 170, z + 30) for x, z in pth.P[::10]])
    escort = [TurnWalker(AG[0], pth2, s0=-30, period=1.0, stride=560, side=-1, seed=0.6),
              TurnWalker(Afl, pth3, s0=-50, period=1.02, stride=560, side=1, seed=0.1),
              TurnWalker(AG[1], pth2, s0=-150, period=0.98, stride=560, side=-1, seed=0.8),
              TurnWalker(AG[2], pth3, s0=-180, period=1.04, stride=560, side=1, seed=0.35)]
    c12 = cam(dur, z=(1.06, 1.0), oy=(-20, 20))
    draw = TurnDraw(g, [nap] + escort, c12)
    return finish(Scene("n12_return", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.1, [TileAnimItem(sea, lambda tl, t: shimmer_colors(tl, t, 12, 0.16)), SpriteItem(br, lambda t: (0, 3 * math.sin(t * 1.2)))]),
        *slices,
        Layer(g.parallax(1.08), [SpriteItem(boat, lambda t: (bx, by + 4 * math.sin(t * 1.6)))]),
        Layer(1.0, [draw]),
    ], c12, fx=[fx.Glow((800, 500), 700, "sun", 0.2, parallax=0.04)]), "sea")


# ============================================================================ 13  Waterloo, 18 June 1815
G13 = Ground(vpx=600, horizon=860, D=330, p_ref=0.36)


def s13_waterloo(ctx, dur):
    """Waterloo: French infantry climbs toward the Allied ridge through smoke; cuirassiers ride past."""
    g = G13
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1200, ["stone_dk", "stone", "smoke_lt", "gold_lt"]),
                                      M.cloud(p, 600, 300, 600, 110, "smoke_lt", "stone")), (-400, -300, 1900, 1200), BG, "n13_sky")

    def ridge(p):
        p.smooth([(-400, 900), (0, 820), (500, 800), (1000, 830), (1500, 810), (1500, 900)], "olive", 6)
        p.rect(880, 760, 170, 60, "bone")                                              # La Haye Sainte-style farm
        p.poly([(870, 760), (965, 715), (1060, 760)], "terracotta_dk")
    rd = make_sprite(ctx, ridge, (-400, 700, 1900, 220), FAR, "n13_ridge", haze="smoke_lt", haze_amt=0.3)

    def field(p):
        p.rect(-600, 850, 2400, 1300, "green")
        rnd = random.Random(13)
        for _ in range(200):
            y = rnd.uniform(860, 2150)
            q = g.q_of_y(y)
            p.ellipse(rnd.uniform(-600, 1800), y, 40 * q, 7 * q, rnd.choice(["olive", "green_dk", "umber", "amber"]))
    slices = ground_slices(ctx, g, field, (-600, 840, 2400, 1300), BG, "n13_field", (870, 940, 1030, 1150, 1310, 1520, 1800, 2140))
    AR = [assets(ctx, N.Redcoat(v), 0.17, (1.3, 0.9)) for v in range(2)]
    red = []
    for i in range(12):
        X, q = 200 + 34 * i, 1.0 + 0.004 * i
        red.append(TurnWalker(AR[i % 2], Path([(X, g.f / (q - 0.2)), (X, g.f / q), (X, g.f / (q + 0.2))]), s0=40, idle=True, side=1,
                              seed=i * 0.21))
    A = [assets(ctx, N.FrenchLine(v), 0.17, (2.6, 1.7, 1.2)) for v in range(3)]
    Astd = assets(ctx, N.FrenchLine(0, standard=True), 0.17, (2.6, 1.7, 1.2))
    Astd.costume.flag = N.flag_art("fr1812")
    walk = []
    for c, dx in enumerate((-160, -40, 80)):
        pts = [(dx - 160, g.f / 2.8), (dx - 60, g.f / 2.1), (dx + 40, g.f / 1.6), (dx + 140, g.f / 1.25)]
        walk += column([A[c], Astd if c == 1 else A[(c + 1) % 3], A[(c + 2) % 3]], Path(pts), 7, 120, 560, period=0.95,
                       stride=600, side=-1, seed=13 + c)
    c13 = cam(dur, z=(1.0, 1.05), ox=(-40, 40))
    draw = TurnDraw(g, walk + red, c13)
    smk = smoke_sprite(ctx, "n13_smoke", "smoke_lt", "stone", 110)
    fl = flash_sprite(ctx, "n13_flash", 34)
    bursts = []
    for i in range(10):
        x = 220 + 40 * i
        bursts += [flash(fl, x, 830, 0.3 + 0.18 * i, 0.12, 0.5), burst(smk, x, 820, 0.3 + 0.18 * i, 2.2, 1.4, (40, -40), 0.6)]
    cav = [F.horse(ctx, 0.3, FIG, variant=v) for v in (0, 1, 3)]
    cav = [N.cuirassier_horse(ctx, 0.3, FIG, variant=v, volume=VOL) for v in (0, 3)]
    gallop = [FigureItem(cav[i % 2], -300 - 260 * i, 1300 + 40 * (i % 2), flip=True, pose_fn=lambda t, i=i: motion.gallop(t, 0.6, i),
                         motion_fn=lambda t: (420 * t, 0), shadow=SH) for i in range(4)]
    dust = smoke_sprite(ctx, "n13_dust", "sand", "sand_dk", 70)
    return finish(Scene("n13_waterloo", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.12, [SpriteItem(rd)] + bursts),
        *slices,
        Layer(g.parallax(1.25), gallop + [burst(dust, -200 + 420 * k * 0.4, 1330, k * 0.4, 1.4, 1.8, (-60, -40), 0.4) for k in range(8)]),
        Layer(1.0, [draw]),
        Layer(1.2, puffs(smk, [(100, 1500), (900, 1400)], rise=120, period=3.0, drift=80, alpha=0.4, grow=1.0)),
    ], c13, fx=[fx.Haze(860, 120, "smoke_lt", 0.25, parallax=0.15),
                fx.Dust(80, seed=13, color="smoke_lt", strength=0.3, drift=(30, -10))]), "default", sat=1.12)


# ============================================================================ 14  to Saint Helena
def s14_ship(ctx, dur):
    """October 1815: HMS Northumberland brings Napoleon to Saint Helena in the South Atlantic."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1400, ["stone_dk", "blue_mid", "blue_pale", "sky_pale"]),
                                      M.cloud(p, 300, 280, 560, 100, "white", "sky_pale"), M.cloud(p, 950, 440, 420, 80, "white", "sky_pale")),
                      (-400, -300, 1900, 1400), BG, "n14_sky")

    def island(p):
        p.smooth([(560, 1060), (640, 800), (760, 700), (900, 660), (1080, 720), (1300, 820), (1500, 1060)], "umber", 8)
        p.smooth([(600, 1060), (700, 860), (820, 790), (960, 780), (1100, 860), (1500, 1060)], "brick", 8)
        p.smooth([(760, 720), (880, 690), (1000, 700), (960, 760), (820, 760)], "green_dk", 5)
        for x in range(620, 1500, 40):
            p.line([(x, 1060), (x + 30, 860 + (x % 120))], "umber", 4)
    il = make_sprite(ctx, island, (540, 620, 1000, 460), FAR, "n14_island", haze="blue_pale", haze_amt=0.35)
    sea = make_sprite(ctx, lambda p: M.sky(p, -400, 1050, 1900, 1100, ["blue_mid", "lapis", "lapis_dk", "navy"]), (-400, 1045, 1900, 1110),
                      BG, "n14_sea", keep_tiles=True)

    def hull(p):
        p.smooth([(-420, 0), (380, -10), (460, -60), (440, 40), (300, 120), (-360, 120), (-440, 40)], "black", 6)
        p.rect(-380, 30, 760, 22, "ochre")                                              # gunport strake ('Nelson chequer')
        for x in range(-340, 340, 50):
            p.rect(x, 33, 22, 16, "black")
        p.rect(-380, 70, 760, 16, "ochre")
        for x in range(-320, 320, 50):
            p.rect(x, 72, 22, 12, "black")
    hl = make_sprite(ctx, hull, (-470, -80, 950, 220), FIG, "n14_hull", volume=VOL)
    masts = make_sprite(ctx, lambda p: [p.line([(x, 0), (x, -h)], "umber", 10) for x, h in ((-220, 620), (40, 720), (280, 560))]
                        + [p.line([(380, -40), (560, -180)], "umber", 8)], (-240, -740, 820, 760), FIG, "n14_masts")

    def sail(w, h):
        def f(p):
            p.smooth([(-w / 2, 0), (w / 2, 0), (w / 2 + 20, h * 0.5), (w / 2, h), (-w / 2, h), (-w / 2 - 20, h * 0.5)], "bone", 6)
            p.line([(-w / 2, h * 0.33), (w / 2, h * 0.33)], "sand", 3)
            p.line([(-w / 2, h * 0.66), (w / 2, h * 0.66)], "sand", 3)
        return f
    sails = []
    for x, h0, w, hs in ((-220, 580, 260, 150), (-220, 410, 300, 160), (40, 680, 260, 150), (40, 510, 320, 170), (40, 330, 360, 170),
                         (280, 520, 240, 140), (280, 360, 280, 150)):
        spr = make_sprite(ctx, sail(w, hs), (-w / 2 - 40, -20, w + 80, hs + 40), FIG, f"n14_sail{x}{h0}", keep_tiles=True, volume=VOL)
        sails.append((spr, x, -h0))
    from mosaic.compositor import rigid_tile_wave
    SX, SY = 330, 1300

    def ship(t):
        bob = 8 * math.sin(t * 1.1)
        roll = 1.2 * math.sin(t * 0.9)
        from mosaic.geom import R
        base = T(SX + 22 * t, SY + bob) @ R(roll) @ S(0.62)
        out = [(masts.premult, base @ masts.pixel_to_unit(), 1.0)]
        for spr, x, y in sails:
            pm = rigid_tile_wave(spr.premult, spr.tiles, t + x * 0.01, 8 * spr.ppu, 300 * spr.ppu, 0.35, "y", 0.0, 1.0, 0.0)
            out.append((pm, base @ T(x, y) @ spr.pixel_to_unit(), 1.0))
        out.append((hl.premult, base @ hl.pixel_to_unit(), 1.0))
        return out
    ens = N.flag_pole(ctx, 0.28, "ensign", FIG, pole_h=600, finial="spear")
    wake = make_sprite(ctx, lambda p: [p.ellipse(SX - 200 - k * 70, SY + 80 + k * 6, 90 - k * 6, 8, "white") for k in range(8)],
                       (SX - 800, SY + 40, 700, 120), FAR, "n14_wake", keep_tiles=True)
    gulls = birds(ctx, "n14g", [(900, 600, 0, 1.4), (980, 640, 1.2, 1.4), (1050, 590, 2.2, 1.4)], 40, 0.5, "white")
    return finish(Scene("n14_ship", dur, [
        Layer(0.03, [SpriteItem(sky), gulls]),
        Layer(0.1, [SpriteItem(il)]),
        Layer(0.4, [TileAnimItem(sea, lambda tl, t: shimmer_colors(tl, t, 14, 0.18, 2.0)),
                    TileAnimItem(wake, lambda tl, t: shimmer_colors(tl, t, 15, 0.25, 4.0))]),
        Layer(0.6, [FnItem(ship), FigureItem(ens, SX + 300 * 0.62 + 6, SY - 20, pose_fn=lambda t: {"_wind": 1.3},
                                             motion_fn=lambda t: (22 * t, 8 * math.sin(t * 1.1)))]),
    ], cam(dur, z=(1.0, 1.04), ox=(-20, 20)), fx=[fx.Haze(1050, 80, "sky_pale", 0.15, parallax=0.1),
                                                   fx.Glow((900, 500), 700, "sun_hot", 0.15)]), "sea")


# ============================================================================ 15  alone in exile
def s15_exile(ctx, dur):
    """Longwood, Saint Helena (1815-1821): Napoleon, older and heavier, alone above the sea."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1500, ["night", "dusk_violet", "dusk_rose", "dusk_orange", "sun"]),
                                      M.sun(p, 340, 1080, 60, rings=("sun_hot", "sun", "amber"))), (-400, -300, 1900, 1500), BG, "n15_sky")
    sea = make_sprite(ctx, lambda p: M.sky(p, -400, 1100, 1900, 500, ["dusk_orange", "dusk_rose", "dusk_violet", "navy"]),
                      (-400, 1095, 1900, 510), FAR, "n15_sea", keep_tiles=True)

    def cliff(p):
        p.smooth([(300, 2200), (380, 1700), (520, 1560), (760, 1500), (1100, 1480), (1500, 1500), (1500, 2200)], "umber", 8)
        p.smooth([(420, 2200), (480, 1760), (620, 1640), (900, 1600), (1500, 1620), (1500, 2200)], "brick", 8)
        rnd = random.Random(15)
        for _ in range(30):
            x = rnd.uniform(560, 1500)
            p.poly([(x, 1560), (x - 8, 1520), (x + 4, 1550), (x + 12, 1515), (x + 10, 1560)], "olive")
    cl = make_sprite(ctx, cliff, (280, 1440, 1250, 780), BG, "n15_cliff")
    nap = N.napoleon_profile(ctx, 0.52, FIG, outfit="exile", volume=VOL)

    def pose(t):
        p_ = motion.idle(t, 0.5, head=0.6, sway=0.25, arm=0.3, wind=1.4)
        p_["head"] = (p_["head"][0] + 6 * smoothstep((t - 0.8) / 1.6), 0, p_["head"][2])     # gaze lowers to the sea
        p_["arm"] = (-25, 0, 0)                                                              # hand held behind / close
        return p_
    return finish(Scene("n15_exile", dur, [
        Layer(0.02, [SpriteItem(sky)]),
        Layer(0.08, [TileAnimItem(sea, lambda tl, t: shimmer_colors(tl, t, 15, 0.14, 1.4))]),
        Layer(0.8, [SpriteItem(cl), FigureItem(nap, 820, 1530, pose_fn=pose, shadow=dict(SH, cast=0.25))]),
    ], cam(dur, z=(1.08, 1.0), ox=(20, -10)), fx=[fx.Glow((340, 1080), 700, "sun", 0.35, parallax=0.02),
                                                   fx.Haze(1100, 60, "dusk_rose", 0.1, parallax=0.08)]), "warm", sat=1.15)


# ============================================================================ 16  legacy
G16 = Ground(vpx=540, horizon=1200, D=330, p_ref=0.36)


def s16_legacy(ctx, dur):
    """Legacy: the Arc de Triomphe (begun 1806, completed 1836) - a monument to the armies of the Empire."""
    g = G16
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -300, 1900, 1700, ["cobalt", "blue_mid", "gold_lt", "sun", "dusk_orange"]),
                                      M.cloud(p, 200, 360, 480, 90, "ivory", "gold_lt")), (-400, -300, 1900, 1700), BG, "n16_sky")

    def arc(p):
        x0, x1, top, base = 200, 880, 360, 1220
        p.rect(x0, top, x1 - x0, base - top, "bone")
        p.rect(x0, top, (x1 - x0) * 0.06, base - top, mix("bone", "stone_dk", 0.5))
        p.rect(x0 - 20, top - 30, x1 - x0 + 40, 70, "sand")
        p.rect(x0 - 20, top + 130, x1 - x0 + 40, 30, "sand_dk")
        ow, oh = 230, 560
        cx = (x0 + x1) / 2
        p.rect(cx - ow / 2, base - oh + ow / 2, ow, oh - ow / 2, "blue_pale")
        p.ellipse(cx, base - oh + ow / 2, ow / 2, ow / 2, "blue_pale", 180, 360)
        for sx in (-1, 1):                                                              # sculpture groups on the piers
            bx = cx + sx * 240
            p.rect(bx - 70, 820, 140, 280, "sand")
            p.smooth([(bx - 50, 1080), (bx - 40, 880), (bx, 840), (bx + 40, 880), (bx + 50, 1080)], "sand_dk", 5)
        for k in range(12):                                                             # frieze
            p.rect(x0 + 10 + k * 56, top + 60, 30, 50, "sand_dk")
    ar = make_sprite(ctx, arc, (160, 300, 760, 940), FAR, "n16_arc", volume=dict(VOL, strength=0.7, roundness=0.4))
    fl = N.flag_pole(ctx, 0.36, "fr1812", FIG, pole_h=900, finial="spear")

    def avenue(p):
        p.rect(-600, 1200, 2400, 1000, "stone")
        for q in np.linspace(1.0, 3.0, 12):
            p.line([g.project(-1400, q), g.project(1400, q)], "stone_dk", 3 * q)
        for X in (-500, -250, 250, 500):
            p.line([g.project(X, 1.0), g.project(X, 3.0)], "stone_dk", 5)
    slices = ground_slices(ctx, g, avenue, (-600, 1190, 2400, 1000), BG, "n16_ave", (1210, 1300, 1420, 1580, 1800, 2100))

    def trees(side):
        def f(p):
            for q in (1.2, 1.5, 1.9, 2.5):
                x, y = g.project(side * 640, q)
                p.line([(x, y), (x, y - 220 * q)], "umber", 10 * q)
                p.ellipse(x, y - 300 * q, 110 * q, 130 * q, "green_dk")
                p.ellipse(x - 20 * q, y - 330 * q, 70 * q, 80 * q, "emerald")
        return f
    tr = [make_sprite(ctx, trees(s_), (-1200, -400, 3500, 2600), BG, f"n16_trees{s_}") for s_ in (-1, 1)]
    c16 = cam(dur, z=(1.0, 1.1), oy=(40, -20))
    return finish(Scene("n16_legacy", dur, [
        Layer(0.03, [SpriteItem(sky), birds(ctx, "n16b", [(1000, 500, 0, 1.4), (1060, 470, 1, 1.4), (1120, 520, 2, 1.4)], 50)]),
        Layer(0.3, [SpriteItem(ar), FigureItem(fl, 540, 1200, pose_fn=lambda t: {"_wind": 1.1})]),
        *slices,
        Layer(0.9, [SpriteItem(tr[0]), SpriteItem(tr[1])], blur=1.5),
    ], c16, fx=[fx.Glow((540, 700), 800, "sun", 0.25, parallax=0.1),
                fx.Dust(60, seed=16, color="sun_hot", strength=0.25, drift=(6, -4))]), "warm")


# ============================================================================ 17  the hat on the rock
def s17_end(ctx, dur):
    """Closing image: a bicorne and sword left on a rock above the Atlantic at dusk (symbolic)."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -300, 1900, 1500, ["night", "navy", "dusk_violet", "burgundy", "dusk_orange"]),
                      (-400, -300, 1900, 1500), BG, "n17_sky")
    sea = make_sprite(ctx, lambda p: M.sky(p, -400, 1150, 1900, 500, ["dusk_orange", "burgundy", "dusk_violet", "navy"]),
                      (-400, 1145, 1900, 510), FAR, "n17_sea", keep_tiles=True)

    def rock(p):
        p.smooth([(-400, 2200), (-300, 1300), (100, 1200), (500, 1180), (900, 1220), (1400, 1300), (1500, 2200)], "stone_dk", 8)
        p.smooth([(-200, 1300), (200, 1230), (600, 1220), (1000, 1260), (1200, 1330), (900, 1360), (300, 1360)], "stone", 8)
        for x in range(-300, 1400, 90):
            p.line([(x, 1400), (x + 40, 2100)], "umber", 6)
    rk = make_sprite(ctx, rock, (-420, 1160, 1950, 1060), BG, "n17_rock")

    def objects(p):
        p.line([(120, 1250), (980, 1190)], "steel", 20)                                  # sabre
        p.line([(120, 1246), (980, 1186)], "white", 5)
        p.rect(950, 1166, 110, 40, "gold")
        p.line([(1000, 1150), (1000, 1226)], "gold", 12)
        p.push()
        p.translate(540, 1180)
        p.scale(2.7)
        N.bicorne(p, 180)
        p.pop()
    ob = make_sprite(ctx, objects, (80, 900, 1020, 360), FIG, "n17_objects", volume=VOL)
    return finish(Scene("n17_end", dur, [
        Layer(0.02, [SpriteItem(sky)]),
        Layer(0.08, [TileAnimItem(sea, lambda tl, t: shimmer_colors(tl, t, 17, 0.14, 1.2))]),
        Layer(0.9, [SpriteItem(rk), SpriteItem(ob)]),
    ], cam(dur, z=(1.0, 1.08), oy=(0, 30)), fx=[fx.Glow((540, 1150), 700, "dusk_orange", 0.3, parallax=0.02),
                                                fx.Dust(40, seed=17, color="sun_hot", strength=0.2, drift=(-10, -3))]), "warm",
                  fade_out=(1.2, 0.35))


SHOTS = [s01_artillery, s02_advance, s03_coronation, s04_map, s05_plan, s06_march, s07_moscow, s08_fire, s09_retreat,
         s10_coalition, s11_farewell, s12_return, s13_waterloo, s14_ship, s15_exile, s16_legacy, s17_end]


def map_labels():
    """Screen labels for map shots are configured in episode.json titles (positions from eu())."""
    return []

"""Episode 1 V3 - "Cyrus the Great: The Conquest of Babylon" - 56 s YouTube Short (final cut).

19 distinct shots cut to the ElevenLabs narration (word timestamps from forced
alignment, see audio/words_aligned.json). Every shot has its own composition and
independent animation (rigs, rigid-tile cloth, per-tile water/fire/light, tile
scatter), plus restrained camera moves. Builders take (ctx, dur) and return a Scene.
"""
import importlib.util
import math
import os
import random

import numpy as np

from mosaic import fx, motion
from mosaic.geom import T, ease_in_out, lerp, smoothstep
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.library import scenery as SC
from mosaic.palette import P
from mosaic.scene import (FigureItem, FnItem, Layer, Scene, SpriteItem, TileAnimItem, TileScatterItem,
                          make_sprite)

BG, FAR, FIG = 8.0, 6.0, 5.6
HERE = os.path.dirname(os.path.abspath(__file__))


def _ep01():
    """The approved Episode 1 scenes (gate entry, courtyard, sunset) are reused once each."""
    path = os.path.join(HERE, "..", "ep01_cyrus_babylon", "scenes.py")
    spec = importlib.util.spec_from_file_location("ep01_scenes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cam(dur, z=(1.0, 1.06), ox=(0, 0), oy=(0, 0), ease=True):
    def f(t):
        e = ease_in_out(t / dur) if ease else max(0.0, min(1.0, t / dur))
        return dict(zoom=lerp(z[0], z[1], e), ox=lerp(ox[0], ox[1], e), oy=lerp(oy[0], oy[1], e))
    return f


def grade(warm=1.0, sat=1.05, gamma=1.05):
    """Placeholder kept for V2 shot code; v3_finish() replaces it with CinematicGrade."""
    return fx.Grade(gain=(1.0 + 0.05 * warm, 1.0, 1.0 - 0.06 * warm), gamma=gamma, sat=sat)


GRADES = {  # per-shot CinematicGrade tuning (sat, vibrance, warmth, local contrast)
    "default": dict(sat=1.22, vibrance=0.3, local=0.35),
    "night": dict(sat=1.15, vibrance=0.25, local=0.3, warm=(1.05, 1.0, 0.92), cool=(0.88, 0.95, 1.14)),
    "interior": dict(sat=1.2, vibrance=0.3, local=0.4, warm=(1.09, 1.0, 0.85), cool=(0.9, 0.95, 1.12)),
    "sunset": dict(sat=1.18, vibrance=0.25, local=0.3, warm=(1.08, 0.98, 0.86), cool=(0.86, 0.92, 1.16)),
    "object": dict(sat=1.15, vibrance=0.3, local=0.5, warm=(1.08, 1.0, 0.86)),
}


def v3_finish(sc, look="default", fade=None):
    """Replace V2's washing treatments: drop haze bands and the old grade, turn white glows
    into restrained amber sunlight, keep dust light, then apply the V3 cinematic grade."""
    out = []
    for f in sc.fx:
        if isinstance(f, (fx.Haze, fx.Grade, fx.CinematicGrade)):
            continue
        if isinstance(f, fx.Glow):
            f.s *= 0.55
            f.col = np.array(P["sun"], np.float32) / 255.0
        if isinstance(f, fx.Shafts):
            f.s *= 0.6
        if isinstance(f, fx.Dust):
            f.strength *= 0.75
        if isinstance(f, fx.Vignette):
            continue
        out.append(f)
    g = dict(GRADES[look])
    out += [fx.CinematicGrade(fade=fade, **g), fx.Vignette(0.38)]
    sc.fx = out
    return sc


def birds(ctx, name, flock, speed, flap=0.42):
    def up(p):
        p.poly([(-14, 0), (-4, -8), (0, 0), (4, -8), (14, 0), (0, 3)], "outline")

    def down(p):
        p.poly([(-14, 4), (-4, 2), (0, 0), (4, 2), (14, 4), (0, 3)], "outline")
    a = make_sprite(ctx, up, (-20, -12, 40, 20), 3.0, name + "u", rows=0)
    b = make_sprite(ctx, down, (-20, -12, 40, 20), 3.0, name + "d", rows=0)

    def fn(t):
        out = []
        for (x, y, ph, s) in flock:
            spr = a if math.sin(2 * math.pi * t / flap + ph) > 0 else b
            out.append((spr.premult, T(x - speed * t, y + 6 * math.sin(t * 1.3 + ph)) @ spr.pixel_to_unit()
                        @ np.diag([s, s, 1.0]), 1.0))
        return out
    return FnItem(fn)


def puffs(sprite, sources, rise=120, period=3.0, drift=25, alpha=0.5):
    """Smoke/incense/dust puffs: each rises, drifts and fades, then restarts."""
    items = []
    for i, (x, y) in enumerate(sources):
        for j in range(2):
            ph = (i * 0.37 + j * 0.5) % 1.0

            def off(t, x=x, y=y, ph=ph):
                c = (t / period + ph) % 1.0
                return x + drift * c + 6 * math.sin(t + ph * 6), y - rise * c

            def op(t, ph=ph):
                c = (t / period + ph) % 1.0
                return alpha * math.sin(math.pi * c)
            items.append(SpriteItem(sprite, off, op))
    return items


def flame_colors(tl, t, seed=0):
    """Per-tile flicker for fire and lamps (tiles keep their place, colours dance)."""
    if "_ph" not in tl:
        tl["_ph"] = np.random.default_rng(seed).uniform(0, 6.28, len(tl["color"])).astype(np.float32)
    f = 1 + 0.22 * np.sin(tl["_ph"] + t * 11) * np.sin(tl["_ph"] * 2.3 + t * 7.3)
    return np.clip(tl["color"] * f[:, None], 0, 255)


def shimmer_colors(tl, t, seed=0, amp=0.1, speed=2.4):
    if "_ph" not in tl:
        tl["_ph"] = np.random.default_rng(seed).uniform(0, 6.28, len(tl["color"])).astype(np.float32)
    w = np.sin(tl["_ph"] + t * speed + tl["cy"] * 0.03 - tl["cx"] * 0.004)[:, None]
    return np.clip(tl["color"] * (1 + amp * w), 0, 255)


def walkers(fig_list, starts, y, v, period=1.1, flip=False, scale=1.0, seed=0):
    """A marching group: each walker gets its own step phase, cadence (+-6 %), stride and
    a slight height difference, so no two figures move in lockstep."""
    items = []
    rnd = random.Random(seed * 31 + 7)
    for i, x0 in enumerate(starts):
        ph = (i * 2.1 + seed) % 6.28
        per = period * rnd.uniform(0.94, 1.06)
        sw = rnd.uniform(18, 23)
        sc_i = scale * rnd.uniform(0.96, 1.04)
        vv = v * (per and period / per) * sc_i / scale
        items.append(FigureItem(fig_list[i % len(fig_list)], x0, y + (i % 2) * 5, flip=flip, scale=sc_i,
                                pose_fn=lambda t, ph=ph, per=per, sw=sw: motion.walk(t, per, ph, swing=sw),
                                motion_fn=lambda t, vv=vv: ((vv if flip else -vv) * t, 0)))
        items[-1].period, items[-1].phase, items[-1].vel = per, ph, (vv if flip else -vv)
    return items


_DUST = {}


def march_dust(ctx, walkers_list, foot_dx=0.0, size=1.0, alpha=0.5, life=0.7):
    """Small dust puffs kicked up at each footfall of every walker (follows their cadence)."""
    key = (ctx.W, round(size, 2))
    if key not in _DUST:
        _DUST[key] = make_sprite(ctx, lambda p: (p.ellipse(0, 0, 34 * size, 13 * size, "sand"),
                                                 p.ellipse(14 * size, -8 * size, 22 * size, 10 * size, "bone")),
                                 (-50 * size, -30 * size, 100 * size, 50 * size), FAR, f"dust{size:.2f}", rows=0)
    spr = _DUST[key]

    def fn(t):
        out = []
        for w in walkers_list:
            half = w.period / 2
            for k in range(2):
                age = ((t + w.phase / (2 * math.pi) * w.period + k * half) % w.period)
                if age > life:
                    continue
                tf = t - age
                mx, my = w.motion_fn(tf) if w.motion_fn else (0, 0)
                x = w.x + mx + (foot_dx if k == 0 else -foot_dx) * w.scale
                y = w.y + my
                g = 0.6 + 1.2 * age / life
                M_ = T(x + 18 * age * (1 if w.vel < 0 else -1), y - 26 * age * w.scale) @ np.diag([g * w.scale, g * w.scale, 1.0])
                out.append((spr.premult, M_ @ spr.pixel_to_unit(), alpha * (1 - age / life) ** 1.5))
        return out
    return FnItem(fn)


# =========================================================================== 1
def shot01_aerial(ctx, dur):
    """Bird's-eye mosaic plan of Babylon on the Euphrates."""
    land = make_sprite(ctx, lambda p: SC.fields(p, -500, -400, 2100, 2800, seed=2), (-500, -400, 2100, 2800), BG,
                       "b1_fields")
    plan = make_sprite(ctx, lambda p: SC.city_plan(p, 540, 960, 0.92), (-100, 120, 1300, 1700), FAR, "b1_plan")

    def boat(p):
        p.smooth([(-26, 0), (0, -9), (26, 0), (0, 9)], "umber", 4)
        p.line([(0, -9), (0, 9)], "bone", 3)
    bt = make_sprite(ctx, boat, (-30, -12, 60, 24), 3.0, "b1_boat", rows=0)
    rx = 540 - 0.92 * 900 / 2 + 0.92 * 900 * 0.42 + 0.92 * 8
    boats = [SpriteItem(bt, lambda t, k=k: (rx + 6 * math.sin(k), 300 + k * 330 + 38 * t * (1 if k % 2 else -1)))
             for k in range(5)]
    cloud = make_sprite(ctx, lambda p: M.cloud(p, 0, 0, 520, 150, "ivory", "bone"), (-300, -120, 600, 240), BG,
                        "b1_cloud")
    shadow = make_sprite(ctx, lambda p: M.cloud(p, 0, 0, 520, 150, "outline", "outline"), (-300, -120, 600, 240),
                         BG, "b1_cloudsh")
    clouds = [SpriteItem(cloud, lambda t, k=k: (k * 520 - 300 + 34 * t, 200 + k * 620), lambda t: 0.62)
              for k in range(3)]
    shadows = [SpriteItem(shadow, lambda t, k=k: (k * 520 - 220 + 34 * t, 300 + k * 620), lambda t: 0.16)
               for k in range(3)]
    smoke = make_sprite(ctx, lambda p: p.ellipse(0, 0, 22, 16, "bone"), (-30, -20, 60, 40), FAR, "b1_smoke")
    rnd = random.Random(4)
    smokes = puffs(smoke, [(rnd.uniform(200, 900), rnd.uniform(500, 1500)) for _ in range(6)], rise=40,
                   period=2.6, drift=50, alpha=0.45)
    return Scene("b01_aerial", dur, [
        Layer(0.35, [SpriteItem(land)]),
        Layer(0.5, [SpriteItem(plan)] + boats + smokes + shadows),
        Layer(0.7, [birds(ctx, "b1b", [(900, 700, 0, 1.6), (950, 680, 1, 1.6), (1000, 720, 2, 1.6), (870, 740, 3, 1.6)],
                          70)]),
        Layer(1.2, clouds),
    ], cam(dur, z=(1.32, 1.12), ox=(-30, 10), oy=(60, 0)), fx=[
        fx.Glow((300, 300), 900, "sun_hot", 0.18, parallax=0.0), grade(0.8), fx.Vignette(0.45)])


# =========================================================================== 2
def shot02_camp(ctx, dur):
    """Cyrus in the Persian camp turns toward the distant city."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -300, -200, 1700, 1250, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                                      M.cloud(p, 200, 330, 420, 80), M.cloud(p, 900, 220, 380, 70),
                                      M.cloud(p, 620, 560, 300, 50, "ivory", "bone")),
                      (-300, -200, 1700, 1250), BG, "b2_sky")

    def far(p):
        M.wall(p, 560, 1300, 960, 1010, merlon=12, towers=8, col="sand", dark="sand_dk", courses=False)
        M.ziggurat(p, 860, 975, 150, 150)
        M.ishtar_gate(p, 700, 1012, 70, 50, 20, 32)
    farspr = make_sprite(ctx, far, (500, 780, 900, 260), FAR, "b2_far", haze="sky_pale", haze_amt=0.35)

    def ground(p):
        M.ground(p, -300, 1000, 1700, 1200, "sand", ("sand_dk", "ochre"), seed=7, n=80)
    gr = make_sprite(ctx, ground, (-300, 1000, 1700, 1200), BG, "b2_ground")

    def tents(p):
        rnd = random.Random(3)
        for row, (y, s) in enumerate([(1080, 0.9), (1190, 1.25), (1330, 1.7)]):
            x = -260 + row * 60
            while x < 1300:
                SC.tent(p, x, y, 250 * s, 130 * s, rnd.choice(["bone", "ivory", "sand"]),
                        rnd.choice(["terracotta", "lapis", "crimson"]))
                x += rnd.uniform(270, 340) * s
    tentspr = make_sprite(ctx, tents, (-350, 700, 1750, 680), FAR, "b2_tents")
    fire = make_sprite(ctx, lambda p: SC.campfire(p, 0, 0, 1.0), (-60, -100, 120, 120), 3.5, "b2_fire",
                       keep_tiles=True)
    smoke = make_sprite(ctx, lambda p: (p.ellipse(0, 0, 30, 40, "stone"), p.ellipse(8, -40, 22, 28, "bone")),
                        (-40, -80, 80, 130), FAR, "b2_smoke")
    poles = [F.banner_pole(ctx, 0.36, FIG, variant=i) for i in range(3)]
    sentry = [F.persian_soldier(ctx, 0.26, FIG, variant=i) for i in range(2)]
    cyrus = F.cyrus(ctx, 1.25, FIG)
    guard = F.persian_guard(ctx, 1.08, FIG, variant=0)

    def cyrus_pose(t):
        p = motion.idle(t, 0.5, head=0.8, sway=0.3, arm=0.5, wind=1.3)
        g = motion.gesture(t, 0.7, 1.6, 9, 10, 1.0)
        p["head"] = (p["head"][0] - 5 * smoothstep((t - 0.2) / 1.2), 0, p["head"][2])
        p["arm"] = (p["arm"][0] + 22 * g, 0, 0)
        p["hand"] = (p["hand"][0] - 8 * g, 0, 0)
        return p
    return Scene("b02_camp", dur, [
        Layer(0.04, [SpriteItem(sky)]),
        Layer(0.1, [SpriteItem(farspr)]),
        Layer(0.35, [SpriteItem(gr), SpriteItem(tentspr)] + puffs(smoke, [(300, 1250), (760, 1200)], rise=220,
                                                                     period=3.2, alpha=0.4)),
        Layer(0.4, [TileAnimItem(fire, lambda tl, t: flame_colors(tl, t, 1)),
                    FigureItem(poles[0], 160, 1300, pose_fn=lambda t: {"_phase": 0.0}),
                    FigureItem(poles[1], 560, 1180, pose_fn=lambda t: {"_phase": 0.7}),
                    FigureItem(poles[2], 940, 1340, pose_fn=lambda t: {"_phase": 1.4})]
              + walkers(sentry, [880, 1160], 1400, 60)),
        Layer(1.0, [FigureItem(guard, 90, 2190, flip=True, pose_fn=lambda t: motion.idle(t, 2.0, head=2.0)),
                    FigureItem(cyrus, 400, 2270, flip=True, pose_fn=cyrus_pose)]),
    ], cam(dur, z=(1.0, 1.07), ox=(-20, 20), oy=(0, -20)), fx=[
        fx.Glow((820, 900), 520, "sun_hot", 0.28, parallax=0.1), fx.Shafts(-20, 0.05),
        fx.Dust(90, seed=2, strength=0.3, drift=(14, -4), region=(0, 0.5, 1, 1)), grade(1.0), fx.Vignette(0.42)])


# =========================================================================== 3
def shot03_market(ctx, dur):
    """A Babylonian street market: one of the ancient world's greatest cities."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -300, -200, 1800, 1350, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                                      M.cloud(p, 250, 250, 380, 70), M.cloud(p, 950, 380, 320, 60)),
                      (-300, -200, 1800, 1350), BG, "b3_sky")
    templ = make_sprite(ctx, lambda p: (M.ziggurat(p, 700, 960, 480, 500),
                                        M.palm(p, 160, 1000, 300, seed=5), M.palm(p, 1180, 1000, 280, seed=6)),
                        (-100, 380, 1500, 660), FAR, "b3_temple", haze="sky_pale", haze_amt=0.25)
    hs = make_sprite(ctx, lambda p: SC.houses(p, -350, 1650, 1230, random.Random(8)), (-360, 900, 2020, 340), BG,
                     "b3_houses")
    street = make_sprite(ctx, lambda p: M.paving(p, -500, 1210, 2300, 1000, "sand", "bone", "terracotta_dk", 100),
                         (-500, 1210, 2300, 1000), BG, "b3_street")

    def stalls(p):
        for i, (x, g, a) in enumerate([(-80, "pots", ("terracotta", "ivory")), (330, "dates", ("lapis", "bone")),
                                       (740, "cloth", ("ochre", "ivory")), (1150, "pots", ("crimson", "bone"))]):
            SC.stall(p, x, 1470, 330, a, g, seed=i)
    st = make_sprite(ctx, stalls, (-300, 1070, 1800, 420), BG, "b3_stalls")
    merchants = [F.townsman(ctx, 0.42, FIG, variant=i) for i in range(3)]
    walkers_m = [F.townsman(ctx, 0.52, FIG, variant=v, tool=tl) for v, tl in [(1, "basket"), (3, None), (4, "bundle")]]
    women = [F.babylonian_citizen(ctx, 0.54, FIG, variant=v) for v in (1, 3, 5)]
    donkey = F.horse(ctx, 0.34, FIG, pack=True, rider=False)

    def woman_glide(i, v, x0, flip):
        return FigureItem(women[i], x0, 1760 + i * 12, flip=flip,
                          pose_fn=lambda t: {**motion.idle(t, i, head=1.5), "body": (1.5 * math.sin(t * 5.7 + i), 0,
                                                                                     -5 * abs(math.sin(t * 5.7 + i)))},
                          motion_fn=lambda t: ((v if flip else -v) * t, 0))
    return Scene("b03_market", dur, [
        Layer(0.05, [SpriteItem(sky)]),
        Layer(0.15, [SpriteItem(templ)]),
        Layer(0.4, [SpriteItem(hs)]),
        Layer(0.6, [SpriteItem(street)]
              + [FigureItem(merchants[i], x, 1350, flip=(i % 2 == 1), pose_fn=lambda t, i=i: motion.work(t, "brick" if i == 1 else "idle", 1.6, i))
                 for i, x in enumerate([-40, 380, 790])] + [SpriteItem(st)]),
        Layer(0.85, walkers(walkers_m, [200, 900, 1300], 1720, 95, seed=1)
              + [FigureItem(donkey, 1150, 1690, flip=False, pose_fn=lambda t: motion.amble(t),
                            motion_fn=lambda t: (-62 * t, 0))]),
        Layer(1.0, [woman_glide(0, 70, -60, True), woman_glide(1, 60, 1100, False)]),
    ], cam(dur, z=(1.05, 1.1), ox=(-40, 50)), fx=[
        fx.Glow((900, 300), 700, "sun_hot", 0.16, parallax=0.05),
        fx.Dust(90, seed=3, strength=0.28, drift=(-10, -6), region=(0, 0.45, 1, 1)), grade(0.9), fx.Vignette(0.42)])


# =========================================================================== 4
def shot04_opis(ctx, dur):
    """Battle of Opis (Tigris, autumn 539 BCE) as a frieze: ranks advance, the
    Babylonian line gives way. No gore; arrows and dust only."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -200, 2000, 900, ["blue_mid", "blue_pale", "gold_lt"]),
                      (-400, -200, 2000, 900), BG, "b4_sky")

    def back(p):
        M.river(p, -400, 470, 2000, 70, ["blue_mid", "lapis"])
        M.wall(p, 880, 1220, 380, 470, merlon=10, towers=4, col="sand_dk", dark="umber", courses=False)
        for i, x in enumerate((-200, 100, 400, 700, 1300)):
            M.palm(p, x, 480, 110, seed=60 + i)
    bk = make_sprite(ctx, back, (-400, 250, 2000, 300), FAR, "b4_back", haze="sky_pale", haze_amt=0.3)
    field = make_sprite(ctx, lambda p: M.ground(p, -500, 530, 2200, 1700, "sand", ("olive", "sand_dk", "ochre", "green_dk"),
                                                seed=9, n=170), (-500, 530, 2200, 1700), BG, "b4_field")
    sold = [F.persian_soldier(ctx, kk, FIG, variant=v) for kk, v in [(0.2, 0), (0.2, 2), (0.27, 1), (0.27, 3),
                                                                     (0.34, 0), (0.34, 2)]]
    std = F.persian_soldier(ctx, 0.34, FIG, variant=0, standard=True)
    riders = [F.horse(ctx, 0.38, FIG, variant=v) for v in (0, 1, 3)]
    babs = [F.babylonian_guard(ctx, 0.22, FIG, variant=v) for v in (0, 1, 2)]
    rows = []
    rnd = random.Random(2)
    for r, (y, figs, v) in enumerate([(700, sold[:2], 70), (820, sold[:2], 72), (970, sold[2:4], 80),
                                      (1130, sold[4:], 88)]):
        xs = [-420 + i * 92 + rnd.uniform(-10, 10) for i in range(11)]
        rows += walkers(figs, xs, y, v, flip=True, seed=r)
    rows.append(FigureItem(std, -60, 1136, flip=True, pose_fn=lambda t: motion.walk(t, 1.1, 0.4),
                           motion_fn=lambda t: (85 * t, 0)))
    cav = [FigureItem(riders[i], -120 + i * 300, 1560 + (i % 2) * 50, flip=True, pose_fn=lambda t, i=i: motion.gallop(t, 0.6, i),
                      motion_fn=lambda t, i=i: (210 * t, -6 * abs(math.sin(t * 10 + i)))) for i in range(3)]
    retreat = walkers(babs, [880, 960, 1040, 1130, 1210], 760, 70, flip=True, seed=3)
    dust = make_sprite(ctx, lambda p: (p.ellipse(0, 0, 120, 50, "sand"), p.ellipse(60, -30, 80, 40, "sand_dk")),
                       (-140, -80, 300, 140), BG, "b4_dust")
    dusts = puffs(dust, [(-160, 1600), (160, 1640), (420, 1610)], rise=40, period=2.2, drift=140, alpha=0.28)

    def arrow(p):
        p.line([(-30, 0), (30, 0)], "umber", 3)
        p.poly([(30, -5), (42, 0), (30, 5)], "stone")
    ar = make_sprite(ctx, arrow, (-36, -8, 82, 16), 2.5, "b4_arrow", rows=0)

    def volley(t):
        out = []
        for k in range(14):
            ph = ((t * 0.75) + k / 14) % 1.0
            x = 100 + 700 * ph + (k % 5) * 40
            y = 760 - 380 * math.sin(math.pi * ph) + (k % 3) * 30
            ang = math.atan2(-420 * math.pi * math.cos(math.pi * ph), 700)
            c, s = math.cos(ang), math.sin(ang)
            M_ = np.array([[c, -s, x], [s, c, y], [0, 0, 1.0]])
            out.append((ar.premult, M_ @ ar.pixel_to_unit(), 0.9 if 0.05 < ph < 0.95 else 0.0))
        return out
    return Scene("b04_opis", dur, [
        Layer(0.04, [SpriteItem(sky)]),
        Layer(0.15, [SpriteItem(bk)]),
        Layer(0.5, [SpriteItem(field)] + retreat + rows + [FnItem(volley)]),
        Layer(0.9, cav + dusts),
    ], cam(dur, z=(1.02, 1.1), ox=(-30, 60)), fx=[
        fx.Dust(140, seed=4, color="sand", strength=0.45, drift=(40, -8), size=(1.2, 3.2), region=(0, 0.4, 1, 1)),
        fx.Haze(560, 120, "bone", 0.12, parallax=0.2), grade(1.1, sat=1.0), fx.Vignette(0.45)])


# =========================================================================== 5
def shot05_advance(ctx, dur):
    """The army advances through the irrigated countryside toward Babylon."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -200, 2000, 1100, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                      (-400, -200, 2000, 1100), BG, "b5_sky")

    def land(p):
        M.ground(p, -500, 820, 2300, 1400, "olive", ("green", "ochre", "green_dk"), seed=11, n=140)
        p.poly([(-500, 1900), (100, 1500), (700, 1100), (1000, 880), (1060, 880), (820, 1120), (300, 1560),
                (-200, 2000)], "sand")
        for i in range(9):
            x = 1200 + i * 30
            M.palm(p, x - i * 90, 860 + i * 40, 120 + i * 18, seed=20 + i)
        for i in range(6):
            M.palm(p, -350 + i * 110, 900 + i * 25, 130 + i * 15, seed=40 + i)
    ld = make_sprite(ctx, land, (-500, 640, 2300, 1560), BG, "b5_land")
    canal = make_sprite(ctx, lambda p: p.poly([(-500, 1300), (500, 1180), (1800, 1260), (1800, 1300), (500, 1225),
                                               (-500, 1350)], "blue_mid"), (-500, 1170, 2300, 190), FAR, "b5_canal",
                        keep_tiles=True)
    far = make_sprite(ctx, lambda p: (M.wall(p, 860, 1250, 830, 880, merlon=8, towers=5, col="sand", dark="sand_dk",
                                             courses=False), M.ziggurat(p, 1060, 850, 110, 110)),
                      (840, 700, 420, 190), FAR, "b5_far", haze="sky_pale", haze_amt=0.45)
    figs = {kk: [F.persian_soldier(ctx, kk, FIG, variant=v) for v in range(4)] for kk in (0.1, 0.16, 0.24, 0.34)}
    stdbig = F.persian_soldier(ctx, 0.95, FIG, variant=2, standard=True)

    def column(t):
        out = []
        for i in range(26):
            s = ((i / 26) + t * 0.035) % 1.0   # progress up the road
            x, y = lerp(-250, 1000, s ** 0.85), lerp(1840, 890, s ** 0.85)
            kk = 0.34 if s < 0.25 else 0.24 if s < 0.5 else 0.16 if s < 0.75 else 0.1
            f = figs[kk][i % 4]
            item = FigureItem(f, x + (i % 2) * 40 * (1 - s), y, flip=True,
                              pose_fn=lambda tt, i=i: motion.walk(tt, 1.1, i * 1.9))
            out += item.emit(t)
        return out
    dust = make_sprite(ctx, lambda p: p.ellipse(0, 0, 90, 34, "sand"), (-100, -40, 200, 80), BG, "b5_dust")
    return Scene("b05_advance", dur, [
        Layer(0.04, [SpriteItem(sky)]),
        Layer(0.1, [SpriteItem(far)]),
        Layer(0.5, [SpriteItem(ld), TileAnimItem(canal, lambda tl, t: shimmer_colors(tl, t, 5, 0.14)), FnItem(column)]
              + puffs(dust, [(0, 1700), (300, 1500), (600, 1250)], rise=50, period=2.4, drift=60, alpha=0.4)),
        Layer(1.0, [FigureItem(stdbig, 760, 2100, flip=True, pose_fn=lambda t: motion.walk(t, 1.15, 0.3),
                               motion_fn=lambda t: (60 * t, 0))]),
    ], cam(dur, z=(1.0, 1.06), ox=(-40, 40), oy=(0, -20)), fx=[
        fx.Haze(900, 90, "bone", 0.18, parallax=0.15),
        fx.Dust(110, seed=6, color="sand", strength=0.4, drift=(30, -6), region=(0, 0.55, 1, 1)), grade(0.9),
        fx.Vignette(0.42)])


# =========================================================================== 6
def shot06_walls(ctx, dur):
    """Low angle on a wall tower: Babylonian guards watch the plain."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -300, 2000, 1500, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                      (-400, -300, 2000, 1500), BG, "b6_sky")
    plain = make_sprite(ctx, lambda p: (M.ground(p, 300, 1150, 1400, 1100, "ochre", ("sand", "ochre_dk"), seed=3, n=50),
                                        M.river(p, 300, 1260, 1400, 40, ["blue_mid", "lapis"]),
                                        p.ellipse(1000, 1140, 160, 30, "bone"), p.ellipse(1080, 1130, 120, 26, "sand")),
                        (280, 1080, 1440, 1180), FAR, "b6_plain", haze="sky_pale", haze_amt=0.4)

    def tower(p):
        p.rect(-300, 640, 960, 1500, "sand")
        y = 660
        while y < 2140:
            p.line([(-300, y), (660, y)], "sand_dk", 3)
            for x in range(-300, 660, 70):
                p.line([(x + (35 if (y // 26) % 2 else 0), y), (x + (35 if (y // 26) % 2 else 0), y + 26)], "sand_dk", 2)
            y += 26
        M.lion_frieze(p, -300, 660, 1080, 230)
        p.rect(560, 640, 100, 1500, "sand_dk")
        M.merlons(p, -300, 660, 640, 70, "sand")
    tw = make_sprite(ctx, tower, (-320, 480, 1000, 1700), BG, "b6_tower")
    parapet = make_sprite(ctx, lambda p: p.rect(-300, 610, 960, 34, "sand_dk"), (-320, 600, 1000, 50), BG,
                          "b6_parapet")
    gds = [F.babylonian_guard(ctx, 0.4, FIG, variant=v) for v in range(3)]

    def gpose(i):
        def f(t):
            p = motion.idle(t, i * 1.4, head=2.5, arm=1.2)
            p["head"] = (p["head"][0] + 6 * math.sin(t * 0.8 + i * 2), 0, p["head"][2])
            if i == 1:
                p["arm"] = (p["arm"][0] + 30 * motion.gesture(t, 1.0, 1.8, 3.0, 3.8, 1.0), 0, 0)
            return p
        return f
    return Scene("b06_walls", dur, [
        Layer(0.04, [SpriteItem(sky), birds(ctx, "b6b", [(1100, 300, 0, 1.4), (1160, 340, 1.1, 1.4), (1220, 290, 2, 1.4)], 60)]),
        Layer(0.2, [SpriteItem(plain)]),
        Layer(1.0, [FigureItem(gds[i], x, 790, flip=True, pose_fn=gpose(i)) for i, x in enumerate([40, 230, 420])]
              + [SpriteItem(tw), SpriteItem(parapet)]),
    ], cam(dur, z=(1.04, 1.1), ox=(10, -10), oy=(-60, -230)), fx=[
        fx.Glow((1000, 500), 600, "sun_hot", 0.2, parallax=0.05), grade(0.9), fx.Vignette(0.42)])


# =========================================================================== 7
def shot07_sources(ctx, dur):
    """'Ancient accounts ... details differ': a Babylonian chronicle tablet and a Greek scroll."""
    def bg(p):
        p.rect(-200, -200, 1500, 2400, "outline")
        for k in range(10):
            p.rect(40 + k * 6, 520 + k * 6, 1000 - k * 12, 900 - k * 12, "umber" if k % 2 else "outline")
        p.rect(70, 550, 940, 840, "umber")
    back = make_sprite(ctx, bg, (-200, -200, 1500, 2400), BG, "b7_bg")
    tab = make_sprite(ctx, lambda p: SC.tablet(p, 0, 0, 400, 560, seed=2), (-220, -300, 440, 600), 4.0, "b7_tablet")
    scr = make_sprite(ctx, lambda p: SC.scroll(p, 0, 0, 380, 380, seed=3), (-230, -230, 460, 460), 4.0, "b7_scroll")
    return Scene("b07_sources", dur, [
        Layer(0.2, [SpriteItem(back)]),
        Layer(0.9, [SpriteItem(tab, lambda t: (300, 960 + 8 * math.sin(t * 1.8))),
                    SpriteItem(scr, lambda t: (790, 980 + 8 * math.sin(t * 1.8 + 1.5)))]),
    ], cam(dur, z=(1.0, 1.05)), fx=[
        fx.Glow((300, 700), 380, "sun_hot", 0.16), fx.Glow((790, 760), 380, "sun_hot", 0.16),
        fx.Dust(60, seed=7, strength=0.25, drift=(4, -6)), grade(0.6), fx.Vignette(0.5)])


# =========================================================================== 8
def shot08_entry(ctx, dur):
    """Persian troops pass through the Ishtar Gate (approved V2 tracking shot, used once).
    The narration says Cyrus entered Babylon; he is deliberately not shown at the gate."""
    sc = _ep01().scene2(ctx)
    base = sc.camera
    sc.camera = lambda t: base(t * 0.9 + 0.6)
    render0 = sc.render
    sc.render = lambda c, t: render0(c, t + 0.6)
    sc.duration = dur
    return sc


# =========================================================================== 9
def shot09_hall(ctx, dur):
    """Cyrus with Babylonian officials: medium shot (artistic reconstruction)."""
    sc = _ep01().scene3(ctx)
    sc.camera = cam(dur, z=(1.2, 1.27), ox=(70, 90), oy=(40, 30))
    return sc


# =========================================================================== 10
def shot10_closeup(ctx, dur):
    """Close-up: Cyrus turns his head and opens his hand."""
    def wall(p):
        p.rect(-300, -200, 1700, 2400, "lapis")
        y = -180
        while y < 2200:
            p.line([(-300, y), (1400, y)], "lapis_dk", 2.5)
            y += 34
        M.rosette_band(p, -300, 1400, 380, 26, bg="lapis_dk")
        M.lion_frieze(p, -300, 1400, 520, 300)
        M.rosette_band(p, -300, 1400, 900, 26, bg="lapis_dk")
    wl = make_sprite(ctx, wall, (-300, -200, 1700, 2400), BG, "b10_wall", haze="umber", haze_amt=0.15)
    cy = F.cyrus(ctx, 2.6, FIG)

    def pose(t):
        p = motion.idle(t, 1.7, head=0.6, sway=0.2, arm=0.4, breath=2.0, wind=0.8)
        turn = smoothstep((t - 0.1) / 0.9)
        p["head"] = (p["head"][0] - 4 * turn + 3 * motion.gesture(t, 0.9, 1.4, 9, 10, 1.0), 0, p["head"][2])
        g = motion.gesture(t, 0.4, 1.3, 9, 10, 1.0)
        p["arm"] = (p["arm"][0] + 34 * g, 0, 0)
        p["hand"] = (p["hand"][0] - 20 * g, 0, 0)
        return p
    return Scene("b10_closeup", dur, [
        Layer(0.25, [SpriteItem(wl)]),
        Layer(1.0, [FigureItem(cy, 700, 3060, pose_fn=pose)]),
    ], cam(dur, z=(1.0, 1.06), ox=(0, -20), oy=(0, -10)), fx=[
        fx.Glow((300, 500), 700, "sun_hot", 0.22), fx.Shafts(-30, 0.05, speed=5), grade(0.9), fx.Vignette(0.5)])


# =========================================================================== 11
def shot11_marduk(ctx, dur):
    """Esagila, Marduk's temple: his emblems (the marru spade and the mushhushshu dragon),
    incense and lamps, priests with raised hands. No statue is depicted: its appearance
    is not known."""
    def shrine(p):
        p.rect(-300, -200, 1700, 2400, "outline")
        p.rect(-100, 300, 1280, 1500, "lapis_dk")
        y = 300
        while y < 1800:
            p.line([(-100, y), (1180, y)], "blue_deep", 2.5)
            y += 30
        for x in range(-80, 1200, 90):
            p.circle(x, 340, 14, "gold")
            p.circle(x, 340, 6, "white")
        p.rect(300, 520, 480, 840, "blue_deep")
        p.ellipse(540, 520, 240, 160, "blue_deep", 180, 360)
        for x in (240, 840):
            p.rect(x - 40, 400, 80, 1000, "gold")
            p.rect(x - 28, 400, 56, 1000, "ochre_dk")
        p.rect(330, 1200, 420, 160, "sand_dk")       # pedestal
        p.rect(310, 1180, 460, 30, "gold")
        # marru (spade) emblem of Marduk on a pole
        p.line([(470, 760), (470, 1180)], "gold", 16)
        p.poly([(470, 640), (420, 720), (440, 780), (500, 780), (520, 720)], "gold_lt")
        # mushhushshu dragon beside it (after the Ishtar Gate reliefs)
        M.animal(p, 640, 1080, 2.4, "gold", "dragon", facing=-1)
        p.rect(-100, 1500, 1280, 500, "sand_dk")
        M.paving(p, -100, 1500, 1280, 500, "sand", "sand_dk", "gold", 90)
    sh = make_sprite(ctx, shrine, (-300, -200, 1700, 2400), BG, "b11_shrine")

    def lamp(p, x, y):
        p.rect(x - 10, y, 20, 160, "gold")
        p.ellipse(x, y, 40, 14, "ochre_dk")
        p.smooth([(x - 14, y - 4), (x, y - 50), (x + 14, y - 4)], "sun", 4)
        p.smooth([(x - 7, y - 4), (x, y - 28), (x + 7, y - 4)], "sun_hot", 4)
    lamps = make_sprite(ctx, lambda p: (lamp(p, 150, 1300), lamp(p, 930, 1300), lamp(p, 120, 900), lamp(p, 960, 900)),
                        (60, 820, 980, 660), 3.6, "b11_lamps", keep_tiles=True)
    burner = make_sprite(ctx, lambda p: (p.rect(520, 1360, 40, 150, "gold"), p.ellipse(540, 1360, 70, 22, "ochre_dk")),
                         (450, 1320, 180, 200), FIG, "b11_burner")
    smoke = make_sprite(ctx, lambda p: (p.ellipse(0, 0, 26, 36, "stone"), p.ellipse(10, -34, 20, 26, "bone")),
                        (-40, -70, 80, 110), FAR, "b11_smoke")
    pr1 = F.babylonian_official(ctx, 0.62, FIG, variant=0)
    pr2 = F.babylonian_official(ctx, 0.6, FIG, variant=2)
    return Scene("b11_marduk", dur, [
        Layer(0.3, [SpriteItem(sh)]),
        Layer(0.5, [TileAnimItem(lamps, lambda tl, t: flame_colors(tl, t, 3)), SpriteItem(burner)]
              + puffs(smoke, [(540, 1340), (530, 1330)], rise=420, period=2.6, drift=40, alpha=0.4)),
        Layer(1.0, [FigureItem(pr1, 230, 1750, flip=True, pose_fn=lambda t: motion.pray(t, 0.2, 0.4)),
                    FigureItem(pr2, 860, 1745, pose_fn=lambda t: motion.pray(t, 0.5, 1.3))]),
    ], cam(dur, z=(1.02, 1.12), oy=(20, -20)), fx=[
        fx.Glow((540, 800), 520, "sun", 0.22, breathe=0.08), grade(0.8, sat=1.05), fx.Vignette(0.55)])


# =========================================================================== 12
def shot12_cylinder(ctx, dur):
    """The Cyrus Cylinder (clay, Akkadian cuneiform, after 539 BCE; British Museum):
    a mosaic interpretation that turns on its long axis. Tiles stay fixed; their colours
    sample the unrolled inscription, so the text rolls without distorting any stone."""
    def bg(p):
        p.rect(-300, -200, 1700, 2400, "outline")
        for k in range(16):
            p.rect(-40 + k * 8, 380 + k * 8, 1160 - k * 16, 1140 - k * 16, "umber" if k % 2 else "outline")
    back = make_sprite(ctx, bg, (-300, -200, 1700, 2400), BG, "b12_bg")
    W, H, cx0, cy0 = 960, 450, 540, 960

    def barrel(p):
        pts = []
        for i in range(41):
            a = math.pi * i / 40
            pts.append((cx0 - W / 2 + 30 * math.sin(a) * 0 + (1 - math.cos(a)) * 0, 0))
        top = [(cx0 - W / 2 + W * i / 40, cy0 - H / 2 * (0.82 + 0.18 * math.sin(math.pi * i / 40))) for i in range(41)]
        bot = [(x, 2 * cy0 - y) for x, y in top]
        p.poly(top + bot[::-1], "sand")
    cyl = make_sprite(ctx, barrel, (cx0 - W / 2 - 10, cy0 - H / 2 - 10, W + 20, H + 20), 4.2, "b12_cyl",
                      keep_tiles=True, rows=1, outline="outline", outline_w=5)
    tex = SC.cuneiform_texture(430, 640, seed=5, clay=(204, 168, 120))
    ppu = cyl.ppu

    def colors(tl, t):
        ux = tl["cx"] / ppu + cyl.x0          # unit coords of tile centres
        uy = tl["cy"] / ppu + cyl.y0
        rloc = H / 2 * (0.82 + 0.18 * np.sin(np.pi * np.clip((ux - (cx0 - W / 2)) / W, 0, 1)))
        s = np.clip((uy - cy0) / rloc, -0.999, 0.999)
        th = np.arcsin(s)
        v = ((th * (H / 2) + 46 * t) * 0.5) % tex.shape[0]
        u = np.clip(((ux - (cx0 - W / 2)) / W) * (tex.shape[1] - 1), 0, tex.shape[1] - 1)
        col = tex[v.astype(int), u.astype(int)]
        shade = (0.35 + 0.65 * np.cos(th) ** 1.5) * (1 + 0.3 * np.clip(-s, 0, 1))
        sweep = np.exp(-((ux - (cx0 - W / 2) - (t / dur) * W * 1.3 + 150) / 90) ** 2) * 0.35
        return np.clip(col * shade[:, None] * (1 + sweep[:, None]), 0, 255)
    return Scene("b12_cylinder", dur, [
        Layer(0.2, [SpriteItem(back)]),
        Layer(1.0, [TileAnimItem(cyl, colors)]),
    ], cam(dur, z=(1.0, 1.08), ox=(-20, 20)), fx=[
        fx.Glow((540, 760), 520, "sun_hot", 0.1), fx.Dust(70, seed=9, strength=0.28, drift=(6, -5)), grade(0.6, sat=1.1),
        fx.Vignette(0.55)])


# =========================================================================== 13
def shot13_restoration(ctx, dur):
    """Restoring a sanctuary while displaced people return home (as the Cylinder claims)."""
    sky = make_sprite(ctx, lambda p: M.sky(p, -400, -200, 2000, 1300, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                      (-400, -200, 2000, 1300), BG, "b13_sky")

    def road(p):
        M.ground(p, -500, 1000, 2300, 400, "sand", ("sand_dk", "ochre"), seed=5, n=40)
        p.poly([(-500, 1260), (500, 1240), (500, 1270), (-500, 1300)], "bone")
        for i, x in enumerate((-300, -120, 120, 300)):
            M.palm(p, x, 1030, 240, seed=70 + i)
    rd = make_sprite(ctx, road, (-500, 700, 2300, 700), FAR, "b13_road", haze="sky_pale", haze_amt=0.2)
    travellers = [F.townsman(ctx, 0.26, FIG, variant=v, tool="bundle") for v in (0, 2, 4)]
    women = [F.babylonian_citizen(ctx, 0.26, FIG, variant=v) for v in (1, 3)]
    donkey = F.horse(ctx, 0.2, FIG, pack=True, rider=False)
    returning = walkers(travellers, [-300, -60, 200], 1240, 55, flip=True, seed=2, scale=1.4) + [
        FigureItem(women[i], x, 1104, flip=True, pose_fn=lambda t, i=i: {**motion.idle(t, i), "body": (1.0 * math.sin(t * 5 + i), 0, -4 * abs(math.sin(t * 5 + i)))},
                   motion_fn=lambda t: (50 * t, 0), scale=1.4) for i, x in enumerate([-200, 80])] + [
        FigureItem(donkey, 20, 1240, flip=True, scale=1.4, pose_fn=lambda t: motion.amble(t), motion_fn=lambda t: (52 * t, 0))]

    def temple(p):
        p.rect(420, 760, 1000, 1300, "sand")
        y = 780
        while y < 2060:
            p.line([(420, y), (1420, y)], "sand_dk", 2.5)
            y += 28
        M.rosette_band(p, 420, 1420, 1060, 16)
        p.rect(760, 1300, 300, 760, "outline")
        p.ellipse(910, 1300, 150, 90, "outline", 180, 360)
        # damaged upper course being rebuilt
        p.poly([(420, 700), (420, 800), (520, 860), (640, 800), (760, 870), (900, 790), (1420, 760), (1420, 700)],
               "sky_pale")
        for i in range(8):
            p.rect(440 + i * 50, 900 + (i % 2) * 10, 46, 24, "brick")
    tp = make_sprite(ctx, temple, (400, 680, 1040, 1400), BG, "b13_temple")
    fg = make_sprite(ctx, lambda p: M.ground(p, -500, 1300, 2000, 900, "sand", ("sand_dk", "ochre"), seed=6, n=40),
                     (-500, 1300, 2000, 900), BG, "b13_fg")
    scf = make_sprite(ctx, lambda p: SC.scaffold(p, 450, 760, 960, 1700), (410, 900, 400, 820), BG, "b13_scaffold")
    w1 = F.townsman(ctx, 0.5, FIG, variant=1, tool="brick")
    w2 = F.townsman(ctx, 0.62, FIG, variant=3, tool="hammer")
    w3 = F.townsman(ctx, 0.6, FIG, variant=0, tool="basket")
    return Scene("b13_restore", dur, [
        Layer(0.04, [SpriteItem(sky)]),
        Layer(0.3, [SpriteItem(rd)] + returning),
        Layer(1.0, [SpriteItem(fg), SpriteItem(tp), SpriteItem(scf),
                    FigureItem(w1, 600, 1222, pose_fn=lambda t: motion.work(t, "brick", 1.5, 0.2)),
                    FigureItem(w2, 1000, 1830, pose_fn=lambda t: motion.work(t, "hammer", 0.9, 1.0)),
                    FigureItem(w3, 420, 1815, pose_fn=lambda t: motion.walk(t, 1.15, 0.5),
                               motion_fn=lambda t: (-60 * t, 0))]),
    ], cam(dur, z=(1.0, 1.06), ox=(-30, 40), oy=(0, -10)), fx=[
        fx.Dust(90, seed=10, strength=0.35, drift=(-6, -10), region=(0, 0.4, 1, 1)), fx.Glow((900, 400), 700, "sun_hot", 0.18),
        grade(0.9), fx.Vignette(0.42)])


# =========================================================================== 14
def shot14_macro(ctx, dur):
    """Extreme close-up of cuneiform wedges; a band of light 'reads' along the lines."""
    def clay(p):
        p.rect(-300, -200, 1700, 2400, "sand")
        rnd = random.Random(11)
        for r in range(30):
            y = -100 + r * 80
            p.line([(-300, y + 64), (1400, y + 64)], "sand_dk", 4)
            x = -280
            while x < 1380:
                for _ in range(rnd.randint(1, 3)):
                    SC.wedge(p, x, y + 30, rnd.uniform(18, 28), rnd.choice([0, 0, 90, 45, -45]), "umber")
                    x += 34
                x += rnd.uniform(16, 40)
    cl = make_sprite(ctx, clay, (-300, -200, 1700, 2400), 7.0, "b14_clay", keep_tiles=True)
    ppu = cl.ppu

    def colors(tl, t):
        ux = tl["cx"] / ppu + cl.x0
        uy = tl["cy"] / ppu + cl.y0
        band = np.exp(-(((ux + 0.35 * (uy - 960)) - (-200 + 1500 * t / dur)) / 150) ** 2)
        dark = tl["color"].mean(1) < 140
        col = tl["color"] * (0.82 + 0.4 * band[:, None])
        col[dark] = col[dark] * (1 - band[dark, None]) + np.array(P["gold"], np.float32) * band[dark, None]
        return np.clip(col, 0, 255)
    return Scene("b14_macro", dur, [Layer(1.0, [TileAnimItem(cl, colors)])],
                 cam(dur, z=(1.08, 1.14), ox=(-40, 40), oy=(30, -30)), fx=[grade(0.5), fx.Vignette(0.6)])



# =========================================================================== 15
def shot15_scribe(ctx, dur):
    """A scribe presses wedges into clay: the Cylinder belongs to the long Mesopotamian
    tradition of royal building inscriptions - not to modern rights charters."""
    def room(p):
        p.rect(-300, -200, 1700, 2400, "umber")
        for r in range(6):
            y = 300 + r * 190
            p.rect(-200, y + 120, 760, 26, "ochre_dk")
            for k in range(14):
                x = -180 + k * 52
                p.smooth([(x, y + 120), (x + 6, y + 50), (x + 40, y + 46), (x + 44, y + 120)], ["sand", "sand_dk", "bone"][k % 3], 3)
        p.rect(600, 300, 360, 520, "outline")              # window
        p.rect(620, 320, 320, 480, "sky_pale")
        p.line([(780, 320), (780, 800)], "outline", 10)
        p.rect(-300, 1500, 1700, 700, "brick")
        M.paving(p, -300, 1500, 1700, 700, "brick", "terracotta", "umber", 110)
    rm = make_sprite(ctx, room, (-300, -200, 1700, 2400), BG, "b15_room")

    def table(p):
        p.rect(60, 1640, 960, 60, "umber")
        p.rect(60, 1700, 960, 20, "outline")
        p.rect(90, 1720, 50, 400, "umber")
        p.rect(940, 1720, 50, 400, "umber")
        for k, x in enumerate((180, 300, 860)):
            SC.tablet(p, x, 1600, 110, 70, seed=k, rows=2)
    tb = make_sprite(ctx, table, (40, 1520, 1000, 620), FIG, "b15_table")
    lamp = make_sprite(ctx, lambda p: (p.ellipse(960, 1630, 60, 18, "ochre_dk"),
                                       p.smooth([(940, 1626), (960, 1550), (980, 1626)], "sun", 4),
                                       p.smooth([(950, 1626), (960, 1586), (970, 1626)], "sun_hot", 4)),
                       (890, 1530, 140, 120), 3.2, "b15_lamp", keep_tiles=True)
    scribe = F.townsman(ctx, 1.35, FIG, variant=2, tool="stylus")
    return Scene("b15_scribe", dur, [
        Layer(0.3, [SpriteItem(rm)]),
        Layer(1.0, [FigureItem(scribe, 640, 2230, pose_fn=lambda t: motion.work(t, "stylus", 0.8, 0.3)),
                    SpriteItem(tb), TileAnimItem(lamp, lambda tl, t: flame_colors(tl, t, 6))]),
    ], cam(dur, z=(1.02, 1.08), ox=(20, -10)), fx=[
        fx.Shafts(-35, 0.09, speed=4, seed=4), fx.Glow((780, 560), 420, "sun_hot", 0.22), fx.Glow((960, 1590), 220, "sun", 0.3),
        fx.Dust(80, seed=12, strength=0.35, drift=(-4, 4), region=(0.4, 0.15, 1, 0.8)), grade(0.8), fx.Vignette(0.55)])


# =========================================================================== 16
MAP_OX, MAP_OY, MAP_S = 60, 640, 21.0


def shot16_map(ctx, dur):
    """Babylonia joins the Persian realm (approximate extent c. 539 BCE; simplified)."""
    def base(p):
        SC.map_layer(p, MAP_OX, MAP_OY, MAP_S, land="sand")
        for poly in SC.SEAS:
            pts = [SC.lonlat(lo, la, MAP_OX, MAP_OY, MAP_S) for lo, la in poly]
            from mosaic.painter import catmull_rom
            p.line(catmull_rom(pts, 4), "lapis_dk", 5)
        for y in (330, 1560):   # framing bands with a simple wave pattern
            p.rect(-300, y, 1700, 40, "lapis_dk")
            for x in range(-300, 1400, 60):
                p.circle(x, y + 20, 12, "gold")
    bm = make_sprite(ctx, base, (-300, -200, 1700, 2400), FAR, "b16_map")
    KEY = M.HOLE

    def region(name, col):
        def f(p):
            p.smooth(SC.region_poly(name, MAP_OX, MAP_OY, MAP_S), col, 3)
            SC.cut_seas(p, MAP_OX, MAP_OY, MAP_S, KEY)
        return f
    before = make_sprite(ctx, region("before", "terracotta"), (-100, 400, 1300, 1000), FAR, "b16_persia",
                         keep_tiles=True, key_color=KEY)
    babyl = make_sprite(ctx, region("babylonia", "gold"), (-100, 400, 1300, 1000), FAR, "b16_babylonia",
                        keep_tiles=True, key_color=KEY)
    ox_, oy_ = SC.lonlat(53.17, 30.2, MAP_OX, MAP_OY, MAP_S)   # Pasargadae
    bx, by = SC.lonlat(44.42, 32.54, MAP_OX, MAP_OY, MAP_S)

    def reveal(spr, cx, cy, t0, t1):
        tl = spr.tiles
        ux, uy = tl["cx"] / spr.ppu + spr.x0, tl["cy"] / spr.ppu + spr.y0
        d = np.hypot(ux - cx, uy - cy)
        d = (d - d.min()) / (np.ptp(d) + 1e-6) + np.random.default_rng(1).uniform(0, 0.08, len(d))
        zero = np.zeros(len(d))

        def fn(tl_, t):
            return zero, zero, d < (t - t0) / (t1 - t0)
        return TileScatterItem(spr, fn)
    marker = make_sprite(ctx, lambda p: (p.circle(0, 0, 16, "white"), p.circle(0, 0, 9, "crimson")), (-20, -20, 40, 40),
                         2.5, "b16_marker")
    return Scene("b16_map", dur, [
        Layer(1.0, [SpriteItem(bm), reveal(before, ox_, oy_, 0.0, 1.3), reveal(babyl, bx, by, 1.3, 2.6),
                    SpriteItem(marker, lambda t: (bx, by), lambda t: 0.6 + 0.4 * math.sin(t * 6) if t > 1.2 else 0.0)]),
    ], lambda t: dict(zoom=1.0 + 0.02 * smoothstep(t / dur)), fx=[grade(0.6, sat=1.0), fx.Vignette(0.45)])


def map_labels():
    """Screen-space labels for the map shot (positions derived from the same projection)."""
    out = []
    for name, (lo, la), dy in [("BABYLON", (44.42, 32.54), 38), ("PERSIS", (53.5, 29.6), 30),
                               ("MEDIA", (48.5, 35.5), 0), ("LYDIA", (29.0, 38.8), 0)]:
        x, y = SC.lonlat(lo, la, MAP_OX, MAP_OY, MAP_S)
        out.append((name, x, y + dy))
    return out


# =========================================================================== 17
def shot17_decay(ctx, dur):
    """Twenty-five centuries: tesserae loosen and fall from an aged glazed-brick panel."""
    def panel(p):
        p.rect(-200, -150, 1480, 2250, "lapis")
        y = -140
        while y < 2100:
            p.line([(-100, y), (1180, y)], "lapis_dk", 2)
            y += 30
        M.animal(p, 540, 640, 6.0, "gold_lt", "bull", facing=-1)
        M.animal(p, 540, 1250, 6.0, "white", "dragon", facing=1)
        M.rosette_band(p, -200, 1280, 250, 26, bg="lapis_dk")
        M.rosette_band(p, -200, 1280, 950, 26, bg="lapis_dk")
        M.rosette_band(p, -200, 1280, 1640, 26, bg="lapis_dk")
    pn = make_sprite(ctx, panel, (-200, -150, 1480, 2250), BG, "b17_panel", keep_tiles=True)
    h, w = pn.premult.shape[:2]
    plaster = np.zeros((h, w, 4), np.uint8)
    plaster[pn.premult[..., 3] > 0] = (150, 136, 118, 255)
    rng = np.random.default_rng(17)
    tl = pn.tiles
    n = len(tl["color"])
    yy = tl["cy"] / h
    crack = np.abs(np.sin(tl["cx"] / w * 7 + yy * 3)) < 0.25
    t_fall = np.where(crack, rng.uniform(0.1, 1.2, n), rng.uniform(0.9, 6.0, n))
    t_fall[rng.random(n) < 0.55] = 99      # most stones survive
    vx = rng.uniform(-30, 30, n) * pn.ppu

    def fn(tl_, t):
        dt = np.clip(t - t_fall, 0, None)
        dy = 0.5 * 2600 * pn.ppu * dt ** 2
        return vx * dt, dy, dy < h
    return Scene("b17_decay", dur, [
        Layer(1.0, [TileScatterItem(pn, fn, below=plaster)]),
    ], cam(dur, z=(1.1, 1.0), oy=(-20, 10)), fx=[
        fx.Dust(120, seed=17, color="bone", strength=0.45, drift=(3, 20), size=(1, 3)), grade(0.4, sat=0.85, gamma=1.08),
        fx.Vignette(0.55)])


# =========================================================================== 18
def shot18_portrait(ctx, dur):
    """Fragments gather into a portrait roundel of Cyrus (imagined likeness)."""
    def bg(p):
        p.rect(-300, -200, 1700, 2400, "blue_deep")
        for r in range(0, 2400, 120):
            for c in range(-300, 1700, 120):
                p.circle(c + (60 if (r // 120) % 2 else 0), r - 200, 10, "lapis")
    back = make_sprite(ctx, bg, (-300, -200, 1700, 2400), BG, "b18_bg")

    def roundel(p):
        p.circle(540, 900, 430, "gold")
        for k in range(36):
            a = 2 * math.pi * k / 36
            p.circle(540 + 395 * math.cos(a), 900 + 395 * math.sin(a), 22, "terracotta" if k % 2 else "ivory")
        p.circle(540, 900, 360, "bone")
        p.smooth([(330, 1180), (430, 1110), (700, 1110), (760, 1190), (640, 1255), (440, 1255)], "purple", 6)
        p.poly([(600, 1110), (700, 1110), (720, 1180), (620, 1200)], "crimson")
        p.push()
        p.translate(585, 640)
        p.scale(2.0)
        p.rect(-24, 150, 46, 110, "skin")
        F._hair_back(p)
        F._face(p, beard_len=1.05)
        F._crown(p)
        p.pop()
    rd = make_sprite(ctx, roundel, (100, 460, 880, 880), 5.0, "b18_roundel", keep_tiles=True)
    rng = np.random.default_rng(18)
    tl = rd.tiles
    n = len(tl["color"])
    ang = rng.uniform(0, 2 * np.pi, n)
    dist = rng.uniform(500, 1100, n) * rd.ppu
    delay = rng.uniform(0, 1.6, n) * (0.4 + 0.6 * np.hypot(tl["cx"] - rd.premult.shape[1] / 2,
                                                           tl["cy"] - rd.premult.shape[0] / 2) / (rd.premult.shape[1] / 2))

    def fn(tl_, t):
        k = np.clip((t - delay) / 0.9, 0, 1)
        e = 1 - (1 - k) ** 3
        r = dist * (1 - e)
        return np.cos(ang) * r, np.sin(ang) * r, k > 0
    return Scene("b18_portrait", dur, [
        Layer(0.2, [SpriteItem(back)]),
        Layer(1.0, [TileScatterItem(rd, fn)]),
    ], cam(dur, z=(1.0, 1.07)), fx=[fx.Glow((540, 760), 520, "sun_hot", 0.2, breathe=0.1), grade(0.7), fx.Vignette(0.5)])


# =========================================================================== 19
def shot19_finale(ctx, dur):
    """Cyrus in silhouette above Babylon at sunset; title card."""
    sc = _ep01().scene4(ctx)
    cy = F.cyrus(ctx, 1.0, FIG, haze="black", haze_amt=0.86)
    rise = make_sprite(ctx, lambda p: p.smooth([(500, 2200), (560, 1850), (760, 1760), (1000, 1740), (1300, 1780),
                                                (1400, 2200)], "black", 6), (480, 1700, 940, 520), BG, "b19_rise")

    def pose(t):
        p = motion.idle(t, 0.9, head=1.0, sway=0.3, arm=0.5, wind=1.5)
        p["head"] = (p["head"][0] + 3 * smoothstep(t / 2.5), 0, p["head"][2])
        return p
    sc.layers.append(Layer(1.0, [SpriteItem(rise), FigureItem(cy, 860, 1790, pose_fn=pose)]))
    sc.camera = cam(dur, z=(1.0, 1.06), ox=(-30, 30))
    sc.fx = [f for f in sc.fx if not isinstance(f, fx.Grade)] + [
        fx.Grade(gain=(1.06, 0.98, 0.9), gamma=1.04, sat=1.08,
                 fade=lambda t: 1.0 - 0.9 * smoothstep((t - (dur - 0.5)) / 0.5))]
    sc.duration = dur
    return sc


SHOTS = [shot01_aerial, shot02_camp, shot03_market, shot04_opis, shot05_advance, shot06_walls, shot07_sources,
         shot08_entry, shot09_hall, shot10_closeup, shot11_marduk, shot12_cylinder, shot13_restoration, shot14_macro,
         shot15_scribe, shot16_map, shot17_decay, shot18_portrait, shot19_finale]


# =========================================================================================
# V3 NEW / REBUILT SHOTS
# =========================================================================================
def v3_open(ctx, dur):
    """Opening hero: Babylon in golden morning light across the Euphrates - blue glazed
    walls, the Ishtar Gate, Etemenanki, boats and birds. Built to grab the first 2 s."""
    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -400, -200, 2000, 1350, ["cobalt", "blue_mid", "blue_pale", "gold_lt", "sun"]),
        M.cloud(p, 180, 300, 460, 90, "gold_lt", "sun"), M.cloud(p, 900, 200, 400, 80, "gold_lt", "sun"),
        M.sun(p, 880, 760, 70)), (-400, -200, 2000, 1350), BG, "v3o_sky")

    def city(p):
        M.ziggurat(p, 600, 1100, 660, 760, col="brick", dark="umber", shrine="cobalt")
        for x, h, c in [(-300, 150, "sand"), (-120, 210, "terracotta"), (880, 190, "sand"), (1060, 240, "brick"),
                        (1260, 150, "sand")]:
            p.rect(x, 1100 - h, 180, h + 40, c)
            M.merlons(p, x, x + 180, 1100 - h, 16, c)
        p.rect(-400, 1050, 2000, 130, "lapis")                     # glazed outer wall
        M.rosette_band(p, -400, 1600, 1080, 12, bg="lapis_dk")
        for i in range(14):
            x = -380 + i * 150
            p.rect(x - 40, 1000, 80, 180, "lapis")
            M.merlons(p, x - 40, x + 40, 1000, 16, "white")
        M.merlons(p, -400, 1600, 1050, 16, "white")
        M.ishtar_gate(p, 170, 1182, 380, 330, 120, 190)
        for i, x in enumerate((-260, 330, 420, 860, 1180, 1330)):
            M.palm(p, x, 1185, 200 + (i % 3) * 30, seed=80 + i)
    cty = make_sprite(ctx, city, (-400, 300, 2000, 900), FAR, "v3o_city")

    def water(p):
        M.sky(p, -500, 1175, 2100, 800, ["turquoise", "blue_mid", "lapis", "lapis_dk", "navy"])
        rnd = random.Random(3)
        for _ in range(170):
            y = rnd.uniform(1185, 1950)
            x = rnd.uniform(-500, 1600)
            L = rnd.uniform(40, 150) * (0.6 + (y - 1175) / 700)
            p.line([(x, y), (x + L, y)], rnd.choice(["blue_pale", "turquoise", "cobalt"]) if y < 1450
                   else rnd.choice(["blue_mid", "lapis", "cobalt"]), 5 + (y - 1175) / 150)
        for _ in range(70):   # broken sun glitter instead of a solid column
            y = rnd.uniform(1185, 1900)
            w = 30 + (y - 1175) * 0.18
            x = 880 + rnd.gauss(0, w * 0.6)
            p.line([(x - w * 0.4, y), (x + w * 0.4, y)], rnd.choice(["sun", "gold_lt", "sun_hot"]), 6 + (y - 1175) / 140)
    wsp = make_sprite(ctx, water, (-500, 1175, 2100, 800), FAR, "v3o_water", keep_tiles=True, variation=0.05)

    def boat(p):
        p.smooth([(-150, 0), (-120, 30), (120, 30), (160, -4), (100, 12), (-100, 12)], "umber", 6)
        p.line([(-130, 6), (140, 4)], "ochre", 4)
        p.rect(-40, -60, 90, 62, "ivory")
        p.rect(-40, -60, 90, 12, "crimson")
    bt = make_sprite(ctx, boat, (-170, -80, 340, 120), FAR, "v3o_boat")
    rower = F.townsman(ctx, 0.17, FIG, variant=0)

    def fronds(p):
        M.palm(p, -160, 2200, 1500, trunk="umber", frond="green_dk", frond2="emerald", seed=91, lean=0.2)
        M.reeds(p, 600, 1400, 1990, 280, seed=4, cols=("green_dk", "olive", "emerald"))
    fr = make_sprite(ctx, fronds, (-700, 400, 2200, 1700), BG, "v3o_fronds")
    return Scene("v3_open", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.08, [birds(ctx, "v3ob", [(1100, 640, 0, 1.6), (1160, 610, 1.1, 1.6), (1220, 660, 2.0, 1.6),
                                         (1280, 620, 0.5, 1.6), (1340, 670, 2.6, 1.6)], 70)]),
        Layer(0.15, [SpriteItem(cty)]),
        Layer(0.45, [TileAnimItem(wsp, lambda tl, t: shimmer_colors(tl, t, 11, 0.16, 3.0)),
                     SpriteItem(bt, lambda t: (300 + 40 * t, 1420 + 5 * math.sin(t * 1.7))),
                     FigureItem(rower, 320, 1420, pose_fn=lambda t: motion.work(t, "brick", 1.4, 0.0),
                                motion_fn=lambda t: (40 * t, 5 * math.sin(t * 1.7)))]),
        Layer(1.25, [SpriteItem(fr, lambda t: (-60 * ease_in_out(t / dur), 0))]),
    ], cam(dur, z=(1.14, 1.04), ox=(-30, 30), oy=(-40, 0)), fx=[
        fx.Glow((880, 760), 480, "sun", 0.3, parallax=0.03), fx.Dust(80, seed=31, color="sun_hot", strength=0.3,
                                                                   drift=(8, -4), region=(0, 0.2, 1, 0.8))])


def v3_citizens(ctx, dur):
    """Babylonians on the street and rooftops watch the change of power - varied reactions."""
    sky = make_sprite(ctx, lambda p: (M.sky(p, -400, -200, 2000, 1100, ["cobalt", "blue_mid", "blue_pale", "gold_lt"]),
                                      M.cloud(p, 300, 260, 400, 80, "ivory", "gold_lt")),
                      (-400, -200, 2000, 1100), BG, "v3c_sky")

    def far(p):
        M.wall(p, -400, 1600, 720, 820, merlon=16, towers=10, col="lapis", dark="lapis_dk", courses=False)
        M.ishtar_gate(p, 980, 822, 220, 170, 70, 110)
    farspr = make_sprite(ctx, far, (-400, 560, 2000, 300), FAR, "v3c_far", haze="blue_pale", haze_amt=0.25)
    std_far = F.banner_pole(ctx, 0.12, FIG, variant=0)

    def houses(p):
        rnd = random.Random(21)
        SC.houses(p, -450, 1700, 1180, rnd, cols=("sand", "terracotta", "ochre", "bone"), hmin=240, hmax=380,
                  wmin=180, wmax=280)
    hs = make_sprite(ctx, houses, (-460, 760, 2200, 440), BG, "v3c_houses")
    street = make_sprite(ctx, lambda p: M.paving(p, -500, 1170, 2300, 1000, "sand", "bone", "terracotta_dk", 110),
                         (-500, 1170, 2300, 1000), BG, "v3c_street")
    minis = [F.mini_person(ctx, 0.07, FAR, variant=i) for i in range(8)]
    roof = [FigureItem(minis[i % 8], x, 830 + (i % 3) * 30, flip=(i % 2 == 0),
                       pose_fn=lambda t, i=i: {"head": (10 * math.sin(t * 0.9 + i), 0, 6 * math.sin(t * 2.3 + i))})
            for i, x in enumerate(range(-300, 1500, 95))]
    mids = [F.babylonian_citizen(ctx, 0.5, FIG, variant=v) for v in range(6)] + \
           [F.townsman(ctx, 0.5, FIG, variant=v) for v in range(3)]
    kinds = ["look", "point", "talk", "chest", "look", "lift", "talk", "look", "point"]
    crowd = [FigureItem(mids[i], x, 1480 + (i % 3) * 18, flip=(i % 3 == 0),
                        pose_fn=lambda t, i=i: motion.react(t, i * 1.37, kinds[i]))
             for i, x in enumerate([-120, 20, 150, 290, 430, 600, 750, 900, 1060])]
    woman = F.babylonian_citizen(ctx, 1.0, FIG, variant=3)
    man = F.townsman(ctx, 1.02, FIG, variant=1)
    pillar = make_sprite(ctx, lambda p: (p.rect(-80, -200, 160, 2400, "lapis_dk"), p.rect(-60, -200, 120, 2400, "lapis"),
                                         M.rosette_band(p, -80, 80, 600, 12, bg="lapis_dk")), (-100, -200, 200, 2400), BG,
                         "v3c_pillar")
    return Scene("v3_citizens", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.12, [SpriteItem(farspr)] + [FigureItem(std_far, x, 760, pose_fn=lambda t, k=k: {"_phase": k},
                                                       motion_fn=lambda t: (-14 * t, 0)) for k, x in enumerate((620, 700, 790))]),
        Layer(0.4, [SpriteItem(hs)] + roof),
        Layer(0.7, [SpriteItem(street)] + crowd),
        Layer(1.0, [FigureItem(man, 160, 2050, flip=True, pose_fn=lambda t: motion.react(t, 0.3, "point")),
                    FigureItem(woman, 900, 2040, pose_fn=lambda t: motion.react(t, 2.1, "chest"))]),
        Layer(1.6, [SpriteItem(pillar, lambda t: (330 - 820 * ease_in_out(t / 1.6), 0))]),
    ], cam(dur, z=(1.03, 1.06), ox=(-60, 60)), fx=[
        fx.Glow((900, 300), 600, "sun", 0.2, parallax=0.05), fx.Dust(80, seed=14, strength=0.3, drift=(-6, -5),
                                                                    region=(0, 0.4, 1, 1))])


def v3_foundation(ctx, dur):
    """'An extraordinary artifact': the clay cylinder is set into a brick foundation niche,
    as such royal inscriptions were (reconstruction)."""
    def wall(p):
        p.rect(-300, -200, 1700, 2400, "brick")
        for r in range(-6, 60):
            y = r * 44
            off = 70 if r % 2 else 0
            p.line([(-300, y), (1400, y)], "terracotta_dk", 6)
            for x in range(-300 + off, 1400, 140):
                p.line([(x, y), (x, y + 44)], "terracotta_dk", 5)
        p.rect(240, 800, 600, 330, "outline")                       # niche
        p.rect(260, 820, 560, 290, "umber")
        p.rect(240, 1110, 600, 30, "sand_dk")
    wl = make_sprite(ctx, wall, (-300, -200, 1700, 2400), BG, "v3f_wall")

    def cyl(p):
        top = [(-260 + 520 * i / 30, -110 * (0.82 + 0.18 * math.sin(math.pi * i / 30))) for i in range(31)]
        bot = [(x, -y) for x, y in top]
        p.poly(top + bot[::-1], "sand")
        rnd = random.Random(2)
        for r in range(7):
            y = -80 + r * 26
            x = -230
            while x < 230:
                SC.wedge(p, x, y, rnd.uniform(6, 10), rnd.choice([0, 0, 90, 45]), "umber")
                x += rnd.uniform(14, 24)

    def hands(p):
        for sx in (-1, 1):
            p.smooth([(sx * 300, -60), (sx * 260, -30), (sx * 260, 60), (sx * 330, 90), (sx * 520, -400),
                      (sx * 430, -440)], "skin", 5)
            p.smooth([(sx * 520, -400), (sx * 600, -700), (sx * 450, -720), (sx * 400, -440)], "ivory", 5)
    cy = make_sprite(ctx, cyl, (-280, -140, 560, 280), 4.0, "v3f_cyl", outline="outline", outline_w=4)
    hd = make_sprite(ctx, hands, (-640, -760, 1280, 880), FIG, "v3f_hands", outline="outline")
    lamp = make_sprite(ctx, lambda p: (p.ellipse(900, 1110, 70, 22, "ochre_dk"),
                                       p.smooth([(876, 1104), (900, 1010), (924, 1104)], "sun", 4),
                                       p.smooth([(888, 1104), (900, 1050), (912, 1104)], "sun_hot", 4)),
                       (810, 990, 180, 150), 3.2, "v3f_lamp", keep_tiles=True)

    def lower(t):
        e = ease_in_out((t - 0.2) / 1.5)
        return 540, lerp(560, 1000, e)

    def hands_off(t):
        x, y = lower(t)
        back = ease_in_out((t - 1.8) / 0.7)
        return x, y - 420 * back
    return Scene("v3_foundation", dur, [
        Layer(0.6, [SpriteItem(wl), TileAnimItem(lamp, lambda tl, t: flame_colors(tl, t, 8))]),
        Layer(1.0, [SpriteItem(cy, lower), SpriteItem(hd, hands_off, lambda t: 1.0 - smoothstep((t - 2.3) / 0.3))]),
    ], cam(dur, z=(1.05, 1.16), oy=(-20, 20)), fx=[
        fx.Glow((900, 1040), 420, "sun", 0.35, breathe=0.1), fx.Dust(70, seed=41, color="sun_hot", strength=0.35,
                                                                     drift=(3, -8), region=(0.1, 0.2, 0.9, 0.8))])


def v3_centuries(ctx, dur):
    """One continuous shot for 'twenty-five centuries later ... power, conquest': glazed
    tesserae fall away from an aged panel, then fragments fly in and lock into a portrait
    roundel of Cyrus (imagined likeness)."""
    dec = shot17_decay(ctx, dur)
    por = shot18_portrait(ctx, dur)
    dec_items = dec.layers[0].items
    t_switch = 2.3
    pan_fade = lambda t: 1.0 - smoothstep((t - t_switch) / 0.8)
    for it in dec_items:
        it.opacity = pan_fade
    back = por.layers[0].items[0]
    back.opacity = lambda t: smoothstep((t - t_switch + 0.2) / 0.8)
    scat = por.layers[1].items[0]
    fn0 = scat.offset_fn
    scat.offset_fn = lambda tl, t: fn0(tl, t - t_switch)
    return Scene("v3_centuries", dur, [
        Layer(0.2, [back]),
        Layer(1.0, dec_items + [scat]),
    ], lambda t: dict(zoom=lerp(1.12, 1.0, ease_in_out(t / 3.0)) + 0.06 * smoothstep((t - 3) / (dur - 3)), oy=0),
        fx=[fx.Dust(110, seed=17, color="bone", strength=0.35, drift=(3, 16), size=(1, 3)),
            fx.Glow((540, 800), 520, "sun", 0.25, breathe=0.1)])


MAP2 = dict(ox=-400, oy=220, s=40.0)


def v3_map(ctx, dur):
    """Clearer mosaic map: deep-blue seas with wave tesserae, warm land, the two rivers,
    Zagros ranges, the Persian realm tinted (approximate, c. 539 BCE) and Babylonia
    lighting up in gold. Boundaries are deliberately soft and approximate."""
    o = MAP2

    def ll(lo, la):
        return SC.lonlat(lo, la, o["ox"], o["oy"], o["s"])

    def base(p):
        SC.map_layer(p, o["ox"], o["oy"], o["s"], land="sand", sea="lapis")
        rnd = random.Random(5)
        for _ in range(260):   # wave marks on the seas
            lo, la = rnd.uniform(30, 64), rnd.uniform(20, 46)
            if any(_inside((lo, la), poly) for poly in SC.SEAS):
                x, y = ll(lo, la)
                p.line([(x - 10, y), (x, y - 5), (x + 10, y)], "blue_mid", 4)
        for poly in SC.SEAS:
            from mosaic.painter import catmull_rom
            p.line(catmull_rom([ll(*q) for q in poly], 4), "navy", 6)
        for r in (SC.EUPHRATES, SC.TIGRIS):
            p.curve([ll(*q) for q in r], "turquoise", 9)
        for lo, la in [(46, 35), (47.5, 33.5), (49, 32), (50.5, 30.8), (52, 29.5), (45, 36.2), (48.5, 34.2), (51, 31.6)]:
            x, y = ll(lo, la)
            p.poly([(x - 22, y + 14), (x, y - 20), (x + 22, y + 14)], "sand_dk")
            p.poly([(x - 8, y - 6), (x, y - 20), (x + 8, y - 6)], "bone")
        p.rect(-300, -200, 1700, 340, "navy")             # title cartouche band
        p.rect(-300, 140, 1700, 16, "gold")
        p.rect(-300, 1500, 1700, 16, "gold")
        p.rect(-300, 1516, 1700, 900, "navy")
    bm = make_sprite(ctx, base, (-300, -200, 1700, 2400), FAR, "v3m_base")
    KEY = M.HOLE

    def region(name, col):
        def f(p):
            p.smooth(SC.region_poly(name, o["ox"], o["oy"], o["s"]), col, 3)
            SC.cut_seas(p, o["ox"], o["oy"], o["s"], KEY)
        return f
    before = make_sprite(ctx, region("before", "terracotta"), (-300, 300, 1700, 1300), FAR, "v3m_persia",
                         keep_tiles=True, key_color=KEY)
    babyl = make_sprite(ctx, region("babylonia", "gold"), (-300, 300, 1700, 1300), FAR, "v3m_babylonia",
                        keep_tiles=True, key_color=KEY)
    px, py = ll(53.17, 30.2)
    bx, by = ll(44.42, 32.54)

    def reveal(spr, cx, cy, t0, t1):
        tl = spr.tiles
        ux, uy = tl["cx"] / spr.ppu + spr.x0, tl["cy"] / spr.ppu + spr.y0
        d = np.hypot(ux - cx, uy - cy)
        d = (d - d.min()) / (np.ptp(d) + 1e-6) + np.random.default_rng(2).uniform(0, 0.06, len(d))
        z = np.zeros(len(d))
        return lambda tl_, t: (z, z, d < (t - t0) / (t1 - t0))
    marker = make_sprite(ctx, lambda p: (p.circle(0, 0, 18, "white"), p.circle(0, 0, 10, "crimson")), (-22, -22, 44, 44),
                         2.5, "v3m_marker")
    return Scene("v3_map", dur, [
        Layer(1.0, [SpriteItem(bm),
                    TileScatterItem(before, reveal(before, px, py, 0.1, 1.4), opacity=0.62),
                    TileScatterItem(babyl, reveal(babyl, bx, by, 1.4, 2.5),
                                    opacity=lambda t: 0.75 + 0.2 * math.sin(t * 4) if t > 2.5 else 0.8),
                    SpriteItem(marker, lambda t: (bx, by), lambda t: 0.65 + 0.35 * math.sin(t * 6) if t > 1.3 else 0.0)]),
    ], lambda t: dict(zoom=1.0 + 0.05 * ease_in_out(t / dur), ox=-10 * ease_in_out(t / dur), oy=0), fx=[])


def _inside(pt, poly):
    x, y = pt
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1:
            inside = not inside
    return inside


def map_labels():
    out = []
    for name, (lo, la), dx, dy in [("BABYLON", (44.42, 32.54), -10, 40), ("PERSIS", (53.4, 29.6), 0, 20),
                                   ("MEDIA", (48.6, 35.8), 0, 0), ("< TO LYDIA", (35.6, 38.9), 0, 0),
                                   ("BABYLONIA", (45.8, 30.9), 20, 30), ("PASARGADAE", (53.17, 30.2), 40, -50)]:
        x, y = SC.lonlat(lo, la, MAP2["ox"], MAP2["oy"], MAP2["s"])
        out.append((name, x + dx, y + dy))
    return out


def v3_finale(ctx, dur):
    """Cyrus in silhouette on a ridge, a crimson standard flying beside him, Babylon far
    below on the river under a deep sunset."""
    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -400, -200, 2000, 1500, ["navy", "dusk_violet", "burgundy", "dusk_rose", "dusk_orange", "sun"]),
        p.ellipse(220, 520, 360, 26, "dusk_rose"), p.ellipse(860, 680, 400, 22, "dusk_orange"),
        p.ellipse(380, 860, 300, 16, "sun"), M.sun(p, 640, 1130, 150, rings=("sun_hot", "sun", "amber"))),
        (-400, -200, 2000, 1500), BG, "v3e_sky")

    def far(p):
        M.ziggurat(p, 380, 1210, 300, 300, col="dusk_violet", dark="navy", shrine="lapis_dk")
        M.wall(p, -400, 1600, 1180, 1230, merlon=10, towers=16, col="dusk_violet", dark="navy", courses=False)
        p.rect(-400, 1230, 2000, 40, "sun")
        p.rect(-400, 1270, 2000, 20, "dusk_orange")
    fr = make_sprite(ctx, far, (-400, 860, 2000, 440), FAR, "v3e_far")

    def plain(p):
        M.sky(p, -500, 1290, 2100, 900, ["dusk_violet", "burgundy", "navy"])
    pl = make_sprite(ctx, plain, (-500, 1290, 2100, 900), BG, "v3e_plain")
    ridge = make_sprite(ctx, lambda p: p.smooth([(-500, 2300), (-500, 1700), (200, 1640), (520, 1590), (900, 1560),
                                                 (1300, 1600), (1600, 1680), (1600, 2300)], "black", 8),
                        (-520, 1520, 2140, 800), BG, "v3e_ridge")
    cyrus = F.cyrus(ctx, 1.12, FIG, haze="black", haze_amt=0.93)
    std = F.banner_pole(ctx, 1.0, FIG, variant=0, haze="burgundy", haze_amt=0.35)
    rnd = random.Random(8)

    def pose(t):
        p = motion.idle(t, 0.9, head=1.0, sway=0.3, arm=0.6, wind=1.6)
        p["head"] = (p["head"][0] - 4 * smoothstep(t / 2.0), 0, p["head"][2])
        return p
    return Scene("v3_finale", dur, [
        Layer(0.02, [SpriteItem(sky)]),
        Layer(0.06, [birds(ctx, "v3eb", [(900, 760, 0, 1.4), (950, 730, 1.0, 1.4), (1010, 770, 2.0, 1.4)], 50)]),
        Layer(0.12, [SpriteItem(fr), SpriteItem(pl)]),
        Layer(1.0, [FigureItem(std, 1060, 1610, pose_fn=lambda t: {"_phase": 0.3, "_wind": 1.4}), SpriteItem(ridge),
                    FigureItem(cyrus, 860, 1600, pose_fn=pose)]),
    ], cam(dur, z=(1.0, 1.07), ox=(-20, 20), oy=(10, -10)), fx=[
        fx.Glow((640, 1130), 640, "sun", 0.38, breathe=0.04, parallax=0.02),
        fx.Dust(70, seed=51, color="sun", strength=0.3, drift=(-10, -3), region=(0, 0.3, 1, 0.75))])


# =========================================================================================
# V2 shots: composition fixes for V3 (caption band 1340-1480 kept clear of faces, colour)
# =========================================================================================
def v3_entry(ctx, dur):
    sc = shot08_entry(ctx, dur)
    # lift the near column so faces sit above the caption band, add marching dust
    near = sc.layers[-1]
    walkers_ = []
    for it in near.items:
        if isinstance(it, FigureItem):
            it.y -= 110
            it.period, it.phase, it.scale = 1.1, 0.0, 1.0
            mf = it.motion_fn
            it.vel = mf(1.0)[0] - mf(0.0)[0]
            walkers_.append(it)
    near.items.append(march_dust(ctx, walkers_, foot_dx=12, size=0.9, alpha=0.45))
    return sc


def v3_opis(ctx, dur):
    sc = shot04_opis(ctx, dur)
    rows = [it for it in sc.layers[2].items if isinstance(it, FigureItem) and hasattr(it, "period")]
    sc.layers[2].items.append(march_dust(ctx, rows, foot_dx=10, size=0.55, alpha=0.4))
    # foreground rank passing close to camera for depth (partially cropped, out of caption band)
    big = [F.persian_soldier(ctx, 0.62, FIG, variant=v) for v in (1, 3)] + [F.persian_soldier(ctx, 0.62, FIG, variant=2, standard=True)]
    fg = walkers(big, [-500, -230, 40, 310], 2230, 120, flip=True, seed=9)
    sc.layers.append(Layer(1.15, fg + [march_dust(ctx, fg, foot_dx=14, size=1.2, alpha=0.5)]))
    return sc


SHOTS_V3 = [
    ("open", v3_open, "default"), ("camp", shot02_camp, "default"), ("market", shot03_market, "default"),
    ("opis", v3_opis, "default"), ("advance", shot05_advance, "default"), ("citizens", v3_citizens, "default"),
    ("sources", shot07_sources, "interior"), ("entry", v3_entry, "default"), ("hall", shot09_hall, "default"),
    ("closeup", shot10_closeup, "interior"), ("marduk", shot11_marduk, "interior"),
    ("cylinder", shot12_cylinder, "object"), ("restoration", shot13_restoration, "default"),
    ("foundation", v3_foundation, "interior"), ("scribe", shot15_scribe, "interior"), ("map", v3_map, "object"),
    ("centuries", v3_centuries, "default"), ("finale", v3_finale, "sunset"),
]


def _wrap(name, fn, look):
    def build(ctx, dur):
        sc = fn(ctx, dur)
        fade = None
        if name == "finale":
            fade = lambda t: 1.0 - 0.8 * smoothstep((t - (dur - 0.35)) / 0.35)
        return v3_finish(sc, look, fade)
    build.__name__ = f"v3_{name}"
    return build


SHOTS = [_wrap(n, f, lk) for n, f, lk in SHOTS_V3]

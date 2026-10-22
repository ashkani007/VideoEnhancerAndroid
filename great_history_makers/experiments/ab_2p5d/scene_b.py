"""Experiment B - 'Persian troops enter Babylon through the Ishtar Gate' in 2.5D.

Same subject, viewpoint (gate front-on, column marching into it), duration and basic
motion as shot A (ep01c v3_entry), rebuilt with:
  * one-point perspective ground plane (pinhole) and a receding Processional-Way wall
  * gate towers with real thickness, a vaulted passage receding to a sunlit far end
  * one sun (upper left): lit / shaded faces, tower shadows on the wall plane, wall shadow
    on the road, ambient occlusion in corners and along wall bases
  * figures with per-tile form shading, contact + projected cast shadows
  * planted-foot walk cycle moving through depth (scale and parallax follow depth)
  * believable scale (soldier ~1/4 of the gate height)
  * multi-plane dolly/truck with depth-correct parallax, foreground occluder, rack focus
"""
import math
import random

import numpy as np

from mosaic import fx, motion
from mosaic.depth import DepthWalkers, Ground, depth_item, perspective_paving
from mosaic.geom import ease_in_out, lerp, smoothstep
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.palette import mix
from mosaic.scene import FigureItem, Layer, Scene, SpriteItem, make_sprite, volume_shading

BG, FAR, FIG = 8.0, 6.0, 5.0
G = Ground(vpx=470, horizon=1000, D=330, p_ref=0.36)
VOL = dict(light=(-0.6, -0.8), strength=1.25, ambient=0.28, roundness=1.0)
SHADOW = dict(cast=0.42, contact=0.55, shx=0.6, sy=0.24, blur=2.0)
GATE_HALF, OPEN_HALF, GATE_H, OPEN_H, TOWER_H, Q_T = 300, 115, 620, 430, 720, 1.1


GROUND_BANDS = ((1300, 1420), (1420, 1560), (1560, 1740), (1740, 2050))  # depth slices (screen y)


def P(X, Y, q):
    return G.at_height(X, Y, q)


def arch(X0, X1, Y_spring, q, n=24, base=0.0):
    """Round-arched opening outline at depth q (spring line Y_spring)."""
    cx, r = (X0 + X1) / 2, (X1 - X0) / 2
    pts = [P(X0, base, q), P(X0, Y_spring, q)]
    for i in range(1, n):
        a = math.pi - math.pi * i / n
        pts.append(P(cx + r * math.cos(a), Y_spring + r * math.sin(a), q))
    pts += [P(X1, Y_spring, q), P(X1, base, q)]
    return pts


def courses(p, x0, x1, y0, y1, col, step=22, w=1.6):
    y = y0 + step
    while y < y1:
        p.line([(x0, y), (x1, y)], col, w)
        y += step


def build(ctx, dur=5.0):
    cam = lambda t: dict(zoom=lerp(1.0, 1.1, ease_in_out(t / dur)), ox=lerp(-50, 30, ease_in_out(t / dur)),
                         oy=lerp(0, -25, ease_in_out(t / dur)))
    # ---------------------------------------------------------------- sky / city
    sky = make_sprite(ctx, lambda p: (
        M.sky(p, -400, -300, 2000, 1400, ["cobalt", "blue_mid", "blue_pale", "gold_lt", "sun"]),
        M.cloud(p, 900, 260, 420, 80, "ivory", "gold_lt"), M.cloud(p, 180, 420, 320, 60, "ivory", "gold_lt")),
        (-400, -300, 2000, 1400), BG, "ab_sky")

    def city(p):
        M.ziggurat(p, 820, 760, 360, 420, col="brick", dark="umber", shrine="cobalt")
        for x, h, c in [(-300, 120, "sand_dk"), (-140, 170, "brick"), (1000, 150, "sand_dk"), (1180, 110, "brick")]:
            p.rect(x, 760 - h, 170, h + 60, c)
            M.merlons(p, x, x + 170, 760 - h, 14, c)
        for i, x in enumerate((-60, 140, 1080, 1300)):
            M.palm(p, x, 800, 150, seed=120 + i)
    cty = make_sprite(ctx, city, (-400, 300, 2000, 560), FAR, "ab_city", haze="blue_pale", haze_amt=0.35)

    # ---------------------------------------------------------------- passage interior
    def passage(p):
        q_back = 0.5
        far = arch(-OPEN_HALF, OPEN_HALF, OPEN_H - OPEN_HALF, q_back)
        N = 9
        for j in range(N):                        # concentric rings: near (lit) -> deep (dark)
            q = 1.0 - (1.0 - q_back) * j / N
            col = mix("lapis", "navy", min(1.0, 0.25 + j / N))
            p.poly(arch(-OPEN_HALF, OPEN_HALF, OPEN_H - OPEN_HALF, q), col)
            if j % 2 == 0:
                p.line(arch(-OPEN_HALF, OPEN_HALF, OPEN_H - OPEN_HALF, q)[1:-1], mix(col, "black", 0.3), 3 * q)
        # sunlit street beyond the far mouth
        p.poly(far, "sun")
        fx0, fy0 = P(-OPEN_HALF, 0, q_back)
        fx1, _ = P(OPEN_HALF, 0, q_back)
        p.rect(fx0, fy0 - 70, fx1 - fx0, 70, "sand")
        p.rect(fx0, fy0 - 140, (fx1 - fx0) * 0.45, 70, "terracotta")
        p.rect(fx0 + (fx1 - fx0) * 0.55, fy0 - 160, (fx1 - fx0) * 0.45, 90, "bone")
        # floor of the passage: limestone slabs fading into shadow
        for j in range(N):
            qa = 1.0 - (1.0 - q_back) * j / N
            qb = 1.0 - (1.0 - q_back) * (j + 1) / N
            col = mix("bone", "umber", min(1.0, 0.2 + 0.8 * j / N))
            p.poly([P(-OPEN_HALF, 0, qa), P(OPEN_HALF, 0, qa), P(OPEN_HALF, 0, qb), P(-OPEN_HALF, 0, qb)], col)
        # ambient occlusion where floor meets walls
        for s in (-1, 1):
            p.poly([P(s * OPEN_HALF, 0, 1.0), P(s * (OPEN_HALF - 22), 0, 1.0), P(s * (OPEN_HALF - 12), 0, q_back),
                    P(s * OPEN_HALF, 0, q_back)], "black")
    psg = make_sprite(ctx, passage, (200, 700, 560, 650), FAR, "ab_passage")

    # ---------------------------------------------------------------- gate front + towers
    def glazed(p, pts, base, x0, x1, y0, y1, animals=None):
        p.poly(pts, base)
        courses(p, x0, x1, y0, y1, mix(base, "navy", 0.45))
        if animals:
            for (ax, ay, s_, col, kind, face) in animals:
                M.animal(p, ax, ay, s_, col, kind, facing=face)

    def gate(p):
        y_top = P(0, GATE_H, 1)[1]
        y_base = P(0, 0, 1)[1]
        xl, _ = P(-GATE_HALF, 0, 1)
        xr, _ = P(GATE_HALF, 0, 1)
        # city wall continuing right (brick), lit from the left
        p.rect(xr, P(0, 470, 1)[1], 1400, y_base - P(0, 470, 1)[1], "sand")
        courses(p, xr, xr + 1400, P(0, 470, 1)[1], y_base, "sand_dk", 24, 2)
        M.merlons(p, xr, xr + 1400, P(0, 470, 1)[1], 22, "sand")
        # central gate block
        glazed(p, [(xl, y_top), (xr, y_top), (xr, y_base), (xl, y_base)], "lapis", xl, xr, y_top, y_base,
               [(xl + 130, y_top + 120, 1.2, "gold_lt", "bull", 1), (xr - 130, y_top + 120, 1.2, "gold_lt", "bull", -1),
                (xl + 130, y_top + 300, 1.2, "white", "dragon", 1), (xr - 130, y_top + 300, 1.2, "white", "dragon", -1)])
        M.merlons(p, xl, xr, y_top, 20, "white")
        # opening frame (white glazed border) - the opening itself is punched out (key colour)
        p.poly(arch(-OPEN_HALF - 16, OPEN_HALF + 16, OPEN_H - OPEN_HALF, 1.0), "white")
        p.poly(arch(-OPEN_HALF, OPEN_HALF, OPEN_H - OPEN_HALF, 1.0), M.HOLE)
        # towers: inner side faces (thickness) then front faces nearer the camera (q = Q_T)
        for s in (-1, 1):
            Xi, Xo = s * 150, s * GATE_HALF
            side = [P(Xi, 0, 1.0), P(Xi, TOWER_H, 1.0), P(Xi, TOWER_H, Q_T), P(Xi, 0, Q_T)]
            lit = s > 0                       # right tower's inner face looks toward the left sun
            p.poly(side, mix("cobalt", "sun", 0.12) if lit else mix("lapis_dk", "navy", 0.5))
            # tower shadow cast onto the gate front (sun from the left -> to the right of each tower)
            if s < 0:
                p.poly([P(Xi, 0, 1.0), P(Xi, TOWER_H - 60, 1.0), P(Xi + 48, TOWER_H - 90, 1.0), P(Xi + 48, 0, 1.0)],
                       mix("lapis", "navy", 0.6))
            else:
                p.poly([P(Xo, 0, 1.0), P(Xo, TOWER_H - 60, 1.0), P(Xo + 52, TOWER_H - 90, 1.0), P(Xo + 52, 0, 1.0)],
                       mix("sand", "umber", 0.45))
            x0, y0 = P(min(Xi, Xo), TOWER_H, Q_T)
            x1, y1 = P(max(Xi, Xo), 0, Q_T)
            glazed(p, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], mix("lapis", "sun", 0.08) if s < 0 else "lapis",
                   x0, x1, y0, y1,
                   [((x0 + x1) / 2, y0 + 140, 1.0, "gold_lt", "bull", -s), ((x0 + x1) / 2, y0 + 330, 1.0, "white", "dragon", -s),
                    ((x0 + x1) / 2, y0 + 520, 1.0, "gold_lt", "bull", -s)])
            M.merlons(p, x0, x1, y0, 22, "white")
            p.rect(x0, y1 - 40, x1 - x0, 40, M.HOLE if False else "lapis_dk")      # plinth
            M.rosette_band(p, x0, x1, y1 - 58, 8, bg="lapis_dk")
        # AO: dark seam where towers meet the gate plane
        for s in (-1, 1):
            xa, ya = P(s * 150, TOWER_H, 1.0)
            p.line([(xa, ya), P(s * 150, 0, 1.0)], "navy", 6)
    gt = make_sprite(ctx, gate, (-200, 300, 1700, 1100), BG, "ab_gate", key_color=M.HOLE)

    # ---------------------------------------------------------------- ground (sliced by depth)
    def ground(p):
        perspective_paving(p, G, -1400, 2600, 3.2, 1.0, 9, 20, "sand", "bone", "sand_dk", 2.5)
        perspective_paving(p, G, -OPEN_HALF - 25, OPEN_HALF + 25, 3.2, 1.0, 9, 3, "ivory", "bone", "sand_dk", 2.5)
        # AO along the gate base and under the tower fronts
        for q0, q1, a in ((1.0, 1.04, 0.0), (Q_T, Q_T + 0.035, 0.0)):
            p.poly([G.project(-2000, q0), G.project(2600, q0), G.project(2600, q1), G.project(-2000, q1)],
                   mix("sand", "umber", 0.55))
        # shadow of the left Processional-Way wall falling across the road (sun upper left)
        p.poly([G.project(-300, 1.12), G.project(-300, 3.2), G.project(-30, 3.0), G.project(-90, 1.12)],
               mix("sand", "blue_deep", 0.3))
    bands = []
    for y0, y1 in GROUND_BANDS:
        # slices overlap by 30 units so differential parallax never opens a seam
        spr = make_sprite(ctx, ground, (-600, 1300, 2300, 760), BG, f"ab_ground{y0}b",
                          clip=(-600, y0 - 30 if y0 > 1300 else y0, 1700, y1))
        bands.append((spr, G.parallax(G.q_of_y((y0 + y1) / 2))))

    # ---------------------------------------------------------------- left Processional-Way wall
    WALL_H = 520

    def pwall(p):
        qs = [Q_T, 1.3, 1.6, 2.0, 2.6, 3.3]
        face = [P(-GATE_HALF, 0, Q_T), P(-GATE_HALF, WALL_H, Q_T), P(-GATE_HALF, WALL_H, 3.3), P(-GATE_HALF, 0, 3.3)]
        p.poly(face, mix("lapis", "navy", 0.35))             # faces away from the sun -> cool shade
        for Y in range(40, WALL_H, 26):                      # brick courses in perspective
            p.line([P(-GATE_HALF, Y, Q_T), P(-GATE_HALF, Y, 3.3)], mix("lapis_dk", "navy", 0.5), 2)
        for Y0, Y1 in ((150, 170), (380, 400)):              # rosette bands
            p.poly([P(-GATE_HALF, Y0, Q_T), P(-GATE_HALF, Y1, Q_T), P(-GATE_HALF, Y1, 3.3), P(-GATE_HALF, Y0, 3.3)],
                   "lapis_dk")
        q = Q_T + 0.04
        while q < 3.2:                                       # glazed rosettes, foreshortened ellipses
            for Y in (160, 390):
                x, y = P(-GATE_HALF, Y, q)
                p.ellipse(x, y, 5.5 * q, 13 * q, "white")
                p.ellipse(x, y, 2.6 * q, 6 * q, "gold")
            q *= 1.06
        q = Q_T + 0.08
        while q < 3.2:                                       # lion frieze reduced to striding gold bodies
            xa, ya = P(-GATE_HALF, 250, q)
            xb, yb = P(-GATE_HALF, 300, q * 1.07)
            p.poly([(xa, ya), (xb, yb - 50 * q), (xb, yb), (xa, ya + 50 * q)], mix("gold_lt", "ochre", 0.35))
            q *= 1.16
        top = [P(-GATE_HALF, WALL_H, q_) for q_ in np.linspace(Q_T, 3.3, 30)]
        for (xa, ya), (xb, yb) in zip(top, top[1:]):         # merlons catching the sun
            p.poly([(xa, ya), (xb, yb), (xb, yb - 30 * (yb - G.h) / G.D / 3.3 - 12), (xa, ya - 12)], "white")
        p.line([P(-GATE_HALF, 0, Q_T), P(-GATE_HALF, 0, 3.3)], "black", 8)   # AO at the base
    wslices = []
    for qa, qb in ((Q_T, 1.3), (1.3, 1.6), (1.6, 2.1), (2.1, 3.4)):
        xa, _ = P(-GATE_HALF, 0, qb)
        xb, _ = P(-GATE_HALF, 0, qa)
        spr = make_sprite(ctx, pwall, (-1200, -400, 1600, 2500), BG, f"ab_pwall{qa}", clip=(xa - 2, -400, xb + 2, 2100))
        wslices.append((spr, G.parallax((qa + qb) / 2)))

    # ---------------------------------------------------------------- figures (2.5D shaded)
    with volume_shading(VOL):
        sold = [F.persian_soldier(ctx, 0.36, FIG, variant=v) for v in range(4)]
        std = F.persian_soldier(ctx, 0.36, FIG, variant=1, standard=True)
        near = [F.persian_soldier(ctx, 0.5, FIG, variant=v) for v in (2, 0, 3, 1)]
        near_std = F.persian_soldier(ctx, 0.5, FIG, variant=0, standard=True)
        cits = [F.babylonian_citizen(ctx, 0.3, FIG, variant=v) for v in range(4)]
    column = DepthWalkers(G, [sold[0], sold[1], std, sold[2], sold[3], sold[1], sold[0]],
                          [(1500, 1.5), (500, 1.3), (60, 1.12), (0, 1.0), (0, 0.55)], k_ref=0.19, n=22,
                          spacing=95, cam=cam, shadow=SHADOW, seed=3, fade_q=(0.93, 0.6))
    column.t0 = (column.s[-1] * 0.98) / column.v          # column already fills the whole route
    front = DepthWalkers(G, [near[0], near[1], near_std, near[2], near[3]], [(1500, 2.3), (-1500, 2.3)], k_ref=0.19,
                         n=14, spacing=175, cam=cam, shadow=SHADOW, seed=8)
    front.t0 = (front.s[-1] * 0.62) / front.v
    onlook = []
    kinds = ["look", "point", "talk", "chest"]
    for i, q in enumerate([1.35, 1.55, 1.8, 2.05]):
        X = -250 + 18 * (i % 2)
        x, y = G.project(X, q)
        it = FigureItem(cits[i], x, y, flip=True, scale=0.19 * 1.05 * q / cits[i].k,
                        pose_fn=lambda t, i=i: motion.react(t, i * 1.7, kinds[i]), shadow=SHADOW)
        onlook.append(depth_item(it, G, q, cam))

    def palm_fg(p):
        M.palm(p, 1180, 2300, 1900, trunk="umber", frond="green_dk", frond2="emerald", seed=7, lean=-0.06)
    fg = make_sprite(ctx, palm_fg, (500, 0, 1400, 2300), BG, "ab_palm_fg")

    rack = lambda t: smoothstep((t - 1.4) / 1.4)
    return Scene("ab_B", dur, [
        Layer(0.03, [SpriteItem(sky)]),
        Layer(0.12, [SpriteItem(cty)], blur=lambda t: 1.4 * (1 - rack(t))),
        Layer(G.p_ref, [SpriteItem(psg)], blur=lambda t: 1.0 * (1 - rack(t))),
        Layer(1.0, [type("E", (), {"emit": staticmethod(column.emitter((0, 1.0)))})()]),
        *[Layer(p_, [SpriteItem(s_)]) for s_, p_ in bands],
        Layer(G.p_ref, [SpriteItem(gt)], blur=lambda t: 1.0 * (1 - rack(t))),
        *[Layer(p_, [SpriteItem(s_)]) for s_, p_ in wslices],
        Layer(1.0, onlook + [type("E", (), {"emit": staticmethod(column.emitter((1.0, 99)))})()]),
        Layer(1.0, [type("E", (), {"emit": staticmethod(front.emitter())})()], blur=lambda t: 2.2 * rack(t)),
        Layer(1.45, [SpriteItem(fg, lambda t: (6 * math.sin(t * 0.8), 0))], blur=6.0),
    ], cam, fx=[
        fx.Shafts(-32, 0.06, speed=6, seed=5),
        fx.Dust(110, seed=33, color="sun_hot", strength=0.32, drift=(10, -5), region=(0, 0.35, 1, 0.95)),
        fx.CinematicGrade(sat=1.18, vibrance=0.3, local=0.35),
        fx.Vignette(0.38),
    ])

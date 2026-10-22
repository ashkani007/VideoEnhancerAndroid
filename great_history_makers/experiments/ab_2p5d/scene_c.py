"""Experiment C - same subject and framing as B (Persian troops before the Ishtar Gate,
gate front-on), rebuilt for volume, physical gait and a real tracking shot.

New vs B:
  * soldier_v3 rig: 15 articulated parts (torso, head, upper arm, forearm, far arm, shield,
    quiver, spear, thigh/shin/FOOT x2), banded sculptural shading baked into the tesserae,
    limb-on-body self-shadows, shield rim thickness, lit spear edge
  * gait_ik: heel strike -> foot flat -> heel-off -> toe-off -> swing, 2-bone IK from planted
    foot targets, pelvis height from leg reach, torso lean/counter-rotation, arms in
    opposition with elbow flex, wrist-stabilised spear; per-soldier cadence/stride/lift/arm
  * per-figure projected ground shadow + per-foot contact shadows that fade as the foot lifts
  * camera: lateral truck alongside the column (no zoom); ground sliced into 9 depth bands
    and every rank placed at a band centre, so feet stay locked to the paving under parallax
  * depth planes: atmosphere -> city -> gate/passage -> far column entering the gate ->
    middle rank -> near rank -> foreground glazed pillar + standard (blurred, fastest)
"""
import importlib.util
import math
import os

import numpy as np

from mosaic import fx, motion
from mosaic.depth import depth_item
from mosaic.geom import ease_in_out, lerp
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.palette import mix
from mosaic.rig3d import WalkerDraw, soldier_v3
from mosaic.scene import FigureItem, Layer, Scene, SpriteItem, make_sprite

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("scene_b_mod", os.path.join(HERE, "scene_b.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
G = B.G
EDGES = (1300, 1380, 1460, 1540, 1620, 1700, 1780, 1860, 1960, 2060)
B.GROUND_BANDS = tuple((EDGES[i] - (30 if i else 0), EDGES[i + 1]) for i in range(len(EDGES) - 1))


def band_q(i):
    return G.q_of_y((EDGES[i] + EDGES[i + 1]) / 2)


Q_NEAR, Q_MID = band_q(6), band_q(3)          # 2.48 and 1.76
K_REF = 0.17                                    # soldier ~ 1/3.6 of gate height


def build(ctx, dur=5.0):
    def cam(t):
        e = ease_in_out(t / dur)
        return dict(zoom=1.0, ox=lerp(150, -150, e), oy=lerp(10, -10, e))

    base = B.build(ctx, dur)
    keep = []
    for L in base.layers:                    # keep B's environment (sky, city, gate, ground, walls)
        if all(isinstance(it, SpriteItem) for it in L.items) and L.p < 1.4:
            keep.append(L)
    # environment layers in B's order: sky, city, passage, ground bands..., gate, wall slices...
    sky, city, passage = keep[0], keep[1], keep[2]
    gate_i = next(i for i, L in enumerate(keep) if L.p == G.p_ref and i > 2)
    bands, gate, walls = keep[3:gate_i], keep[gate_i], keep[gate_i + 1:]
    for L in (city, passage, gate):
        L.blur = None                         # gate stays crisp: it is the subject behind the march

    with __import__("mosaic.scene", fromlist=["volume_shading"]).volume_shading(None):
        near = [soldier_v3(ctx, K_REF * Q_NEAR, 5.0, variant=v) for v in (1, 2, 0, 3)]
        near_std = soldier_v3(ctx, K_REF * Q_NEAR, 5.0, variant=0, standard=True)
        mid = [soldier_v3(ctx, K_REF * Q_MID, 5.0, variant=v) for v in (3, 0, 2, 1)]
        mid_std = soldier_v3(ctx, K_REF * Q_MID, 5.0, variant=2, standard=True)
        far = [soldier_v3(ctx, K_REF * 1.25, 5.0, variant=v) for v in range(4)]

    def lateral(q, x_from, x_to):
        return [((x_from - G.vpx) / q, q), ((x_to - G.vpx) / q, q)]
    near_w = WalkerDraw(G, [near[0], near[1], near_std, near[2], near[3], near[1], near[0], near_std, near[2], near[3]],
                        lateral(Q_NEAR, 1700, -700), K_REF, 12, 150, cam, seed=21, lead=1.0)
    mid_w = WalkerDraw(G, [mid[0], mid_std, mid[1], mid[2], mid[3], mid[0], mid[2], mid_std, mid[1]],
                       lateral(Q_MID, 1500, -500), K_REF, 13, 128, cam, seed=5, lead=1.0)
    far_path = [(1500, 1.45), (500, 1.3), (60, 1.12), (0, 1.0), (0, 0.55)]
    far_back = WalkerDraw(G, far, far_path, K_REF * 0.95, 18, 95, cam, qband=(0, 1.0), seed=3, fade_q=(0.93, 0.6),
                          lead=0.98)
    far_front = WalkerDraw(G, far, far_path, K_REF * 0.95, 18, 95, cam, qband=(1.0, 1.6), seed=3, lead=0.98)

    # distant crowd at the gate base (small, individually timed reactions)
    crowd = []
    cits = [F.babylonian_citizen(ctx, 0.25, 5.0, variant=v, haze="blue_pale", haze_amt=0.15) for v in range(6)]
    for i, X in enumerate([480, 540, 600, 660, 720, 790, 850]):
        q = 1.03 + 0.012 * (i % 3)
        x, y = G.project(X, q)
        it = FigureItem(cits[i % 6], x, y, flip=False, scale=K_REF * q * 0.98 / cits[i % 6].k,
                        pose_fn=lambda t, i=i: motion.react(t, i * 1.3, ["look", "point", "talk", "look", "chest"][i % 5]))
        crowd.append(depth_item(it, G, q, cam))

    # foreground glazed pillar with sculpted (banded) cylinder shading + a hanging crimson standard
    def pillar(p):
        p.rect(-95, -300, 190, 2500, "lapis")
        for y in range(-280, 2200, 30):
            p.line([(-95, y), (95, y)], "lapis_dk", 2.5)
        for y in (240, 820, 1400):
            p.rect(-95, y - 26, 190, 52, "lapis_dk")
            for x in (-60, 0, 60):
                p.circle(x, y, 16, "white")
                p.circle(x, y, 7, "gold")
        p.rect(-112, 1850, 224, 70, "sand_dk")
    pil = make_sprite(ctx, pillar, (-130, -320, 260, 2560), 8.0, "c_pillar",
                      volume=dict(mode="bands", light=(-0.6, -0.8), strength=1.3, ambient=0.25, roundness=1.0))
    std = F.banner_pole(ctx, 0.95, 5.0, variant=0)

    rows_far = Layer(1.0, [far_back])
    rows_front = Layer(1.0, crowd + [far_front])
    layers = [sky, city, passage, rows_far, *bands, gate, *walls, rows_front,
              Layer(1.0, [mid_w]), Layer(1.0, [near_w]),
              Layer(1.55, [SpriteItem(pil, lambda t: (1010, 0)),
                           FigureItem(std, 940, 1990, pose_fn=lambda t: {"_phase": 0.4, "_wind": 1.3})], blur=3.2)]
    return Scene("ab_C", dur, layers, cam, fx=[
        fx.Haze(1000, 70, "blue_pale", 0.07, parallax=0.15),       # distant atmosphere at the horizon
        fx.Shafts(-32, 0.05, speed=6, seed=5),
        fx.Dust(120, seed=34, color="sun_hot", strength=0.3, drift=(12, -5), region=(0, 0.45, 1, 1), parallax=0.9),
        # +0.08 saturation / brighter exposure vs B: compensates the cool shadow tint of the new
        # ground and self-shadows so the shot is not less colourful or darker than B
        fx.CinematicGrade(sat=1.27, vibrance=0.32, local=0.35, exposure=1.06),
        fx.Vignette(0.34),
    ])

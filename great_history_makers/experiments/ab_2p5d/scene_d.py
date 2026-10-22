"""Experiment D - soldiers turn from the road into the Ishtar Gate and vanish inside.

Same subject and framing as B/C (gate front-on, paved Processional Way). Paths are
world-space curves on the road; each soldier's hips follow the path tangent, the torso and
head lead into the turn, the body is drawn from 9 turnaround views (side -> 3/4 -> rear
3/4 -> rear), feet are planted in world space, and every joint is projected through the
same pinhole camera as the architecture. Inside the gate, figures are clipped by the
tunnel opening at their own depth and darken with distance into the passage.
"""
import importlib.util
import math
import os

import numpy as np

from mosaic import fx, motion
from mosaic.depth import depth_item
from mosaic.geom import ease_in_out, lerp
from mosaic.library import figures as F
from mosaic.palette import P as PAL
from mosaic.scene import FigureItem, Layer, Scene, SpriteItem
from mosaic.turnrig import Path, TurnDraw, TurnSoldierAssets, TurnWalker

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("scene_b_mod_d", os.path.join(HERE, "scene_b.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
EDGES = (1300, 1380, 1460, 1540, 1620, 1700, 1780, 1860, 1960, 2060)
B.GROUND_BANDS = tuple((EDGES[i] - (30 if i else 0), EDGES[i + 1]) for i in range(len(EDGES) - 1))
G = B.G
K_REF = 0.17
Z_GATE = G.f / 1.0                  # gate plane
OPEN_HALF, OPEN_H = B.OPEN_HALF, B.OPEN_H


def Zq(q):
    return G.f / q


# world paths (X, Z). Lanes inside the arch at X = +-40 so files never collide.
PATH_R = [(470, Zq(1.68)), (300, Zq(1.66)), (150, Zq(1.5)), (60, Zq(1.27)), (40, Zq(1.1)), (40, Z_GATE),
          (40, Zq(0.86)), (40, Zq(0.76))]
PATH_L = [(-270, Zq(1.62)), (-190, Zq(1.6)), (-100, Zq(1.45)), (-50, Zq(1.25)), (-40, Zq(1.1)), (-40, Z_GATE),
          (-40, Zq(0.86)), (-40, Zq(0.76))]


def passage_clip(q):
    """Tunnel opening outline at depth q (design units) - anything outside is hidden by the walls."""
    if q >= 1.0:
        return None
    return B.arch(-OPEN_HALF, OPEN_HALF, OPEN_H - OPEN_HALF, q, n=28)


def light(q):
    """Sunlit road -> tower shadow at the gate -> darkening passage (tint toward the passage navy)."""
    if q >= 1.12:
        return 1.0, None
    if q >= 1.0:
        return 1.0 - 0.28 * (1.12 - q) / 0.12, (24, 40, 110)
    return 0.72 * math.exp(-(1.0 - q) / 0.07), (14, 24, 70)


def build(ctx, dur=8.0):
    def cam(t):
        e = ease_in_out(t / dur)
        return dict(zoom=lerp(1.0, 1.04, e), ox=lerp(25, -25, e), oy=lerp(0, -18, e))

    base = B.build(ctx, dur)
    keep = [L for L in base.layers if all(isinstance(it, SpriteItem) for it in L.items) and L.p < 1.4]
    sky, city, passage = keep[0], keep[1], keep[2]
    gate_i = next(i for i, L in enumerate(keep) if L.p == G.p_ref and i > 2)
    bands, gate, walls = keep[3:gate_i], keep[gate_i], keep[gate_i + 1:]
    for L in (city, passage, gate):
        L.blur = None

    assets = [TurnSoldierAssets(ctx, K_REF, variant=v) for v in (1, 2, 0, 3)]
    pr, pl = Path(PATH_R), Path(PATH_L)
    walkers = [
        TurnWalker(assets[0], pr, s0=150, period=1.0, stride=600, side=1, seed=0.1),        # R1: completes entry
        TurnWalker(assets[1], pl, s0=40, period=1.04, stride=590, side=-1, seed=0.55),      # L1: completes entry
        TurnWalker(assets[2], pr, s0=-150, period=0.97, stride=610, side=1, seed=0.8),      # R2: follows
        TurnWalker(assets[3], pl, s0=-230, period=1.06, stride=580, side=-1, seed=0.3),     # L2: follows
    ]
    behind = TurnDraw(G, walkers, cam, qband=(0, 1.0), clip_fn=passage_clip, light_fn=light)
    front = TurnDraw(G, walkers, cam, qband=(1.0, 99), light_fn=light)

    # townspeople watching from beside the left wall (individual reactions)
    cits = [F.babylonian_citizen(ctx, 0.25, 5.0, variant=v) for v in range(4)]
    crowd = []
    for i, (X, q) in enumerate([(-262, 1.32), (-258, 1.48), (-266, 1.7)]):
        x, y = G.project(X, q)
        it = FigureItem(cits[i], x, y, flip=True, scale=K_REF * q / cits[i].k,
                        pose_fn=lambda t, i=i: motion.react(t, i * 1.9, ["look", "point", "chest"][i]),
                        shadow=dict(cast=0.35, contact=0.5, shx=0.62, sy=0.24, blur=2.0))
        crowd.append(depth_item(it, G, q, cam))
    std = F.banner_pole(ctx, 0.95, 5.0, variant=0)
    layers = [sky, city, passage, *bands, Layer(1.0, [behind]), gate, *walls,
              Layer(1.0, crowd + [front]),
              Layer(1.25, [FigureItem(std, 1010, 1985, pose_fn=lambda t: {"_phase": 0.4, "_wind": 1.3})], blur=2.0)]
    return Scene("ab_D", dur, layers, cam, fx=[
        fx.Haze(1000, 60, "blue_pale", 0.06, parallax=0.15),
        fx.Shafts(-32, 0.05, speed=6, seed=5),
        fx.Dust(110, seed=36, color="sun_hot", strength=0.3, drift=(10, -5), region=(0, 0.45, 1, 1), parallax=0.9),
        fx.CinematicGrade(sat=1.36, vibrance=0.36, local=0.38, exposure=0.97),   # more paving in frame than C -> stronger grade
        fx.Vignette(0.34),
    ]), walkers

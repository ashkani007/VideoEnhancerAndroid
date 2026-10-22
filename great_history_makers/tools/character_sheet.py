#!/usr/bin/env python3
"""Character reference sheet: turnaround views (rig) + profile figures, rendered with the real
engine so the sheet shows exactly what animation will use.

  python tools/character_sheet.py out.png
"""
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mosaic.depth import Ground  # noqa: E402
from mosaic.library import napoleonic as N  # noqa: E402
from mosaic.scene import Ctx, FigureItem, Layer, Scene  # noqa: E402
from mosaic.turnrig import Path, TurnDraw, TurnSoldierAssets, TurnWalker  # noqa: E402

BG = (0.86, 0.78, 0.6)


def turn_row(ctx, costume, angles=(180, 135, 90, 45, 0), idle=True):
    G = Ground(vpx=540, horizon=600, D=330, p_ref=0.36)
    A = TurnSoldierAssets(ctx, 0.32, costume=costume, mips=(1.6,))
    cells = []
    for th in angles:
        psi = math.radians(th)
        d = (-math.sin(psi), math.cos(psi))
        q = 1.6
        Z = G.f / q
        p = Path([(-d[0] * 400, Z - d[1] * 400), (0, Z), (d[0] * 400, Z + d[1] * 400)])
        w = TurnWalker(A, p, s0=p.length / 2, side=1, seed=0.3, idle=idle)
        fr = np.zeros((1280, 720, 3), np.float32)
        fr[:] = BG
        TurnDraw(G, [w], lambda t: {})._draw(fr, ctx, 0.0, w, q)
        im = cv2.cvtColor((np.clip(fr, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)[130:1000, 160:560]
        im = cv2.resize(im, (300, 652))
        cv2.putText(im, f"{th} deg", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)
        cells.append(im)
    return np.hstack(cells)


def profile_row(ctx, figs):
    cells = []
    for name, fig, pose in figs:
        sc = Scene("s", 1, [Layer(1.0, [FigureItem(fig, 360, 1180, pose_fn=lambda t, p=pose: p)])], lambda t: {}, bg=(219, 199, 153))
        fr = sc.render(ctx, 0.2)
        im = cv2.cvtColor((np.clip(fr, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)[200:1200, 110:610]
        im = cv2.resize(im, (300, 600))
        cv2.putText(im, name, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2)
        cells.append(im)
    return np.hstack(cells)


def label(img, text):
    bar = np.full((44, img.shape[1], 3), (40, 30, 24), np.uint8)
    cv2.putText(bar, text, (12, 30), cv2.FONT_HERSHEY_DUPLEX, 0.8, (230, 220, 190), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def main(out):
    ctx = Ctx(720, 1280, 30)
    rows = [label(turn_row(ctx, N.NapoleonCostume("redingote")), "NAPOLEON - campaign (grey redingote, bicorne en bataille) - turnaround"),
            label(turn_row(ctx, N.NapoleonCostume("chasseur", heavy=1.0)), "NAPOLEON - exile 1815-21 (green chasseur coat, heavier) - turnaround"),
            label(turn_row(ctx, N.FrenchLine(0)), "French line infantry 1805-12 - turnaround"),
            label(turn_row(ctx, N.OldGuard(0)), "Old Guard grenadier - turnaround"),
            label(turn_row(ctx, N.Retreat(1)), "Retreat from Moscow 1812 (greatcoat, scarf) - turnaround"),
            label(turn_row(ctx, N.Redcoat(0)), "British line infantry 1815 - turnaround")]
    prof = [("1793 officer", N.napoleon_profile(ctx, 0.62, outfit="officer"), {}),
            ("1804 coronation", N.napoleon_profile(ctx, 0.62, outfit="coronation"), {}),
            ("1812 campaign", N.napoleon_profile(ctx, 0.62, outfit="redingote"), {}),
            ("1815-21 exile", N.napoleon_profile(ctx, 0.62, outfit="exile"), {}),
            ("Pius VII", N.pope_seated(ctx, 0.62), {})]
    rows.append(label(profile_row(ctx, prof), "NAPOLEON - profile figures by period (same face, hair and proportions)"))
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0)), constant_values=30) for r in rows]
    cv2.imwrite(out, np.vstack(rows))
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])

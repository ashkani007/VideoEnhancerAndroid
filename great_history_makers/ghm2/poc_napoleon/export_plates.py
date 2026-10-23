#!/usr/bin/env python3
"""Proof-of-concept only: export layered stills from existing Episode 02 shots as stand-ins for
AI-generated illustrations (background plate + transparent character/foreground layers).
In production these PNGs come from the illustration stage (local SDXL/FLUX + cut-out), not from code."""
import importlib.util
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from mosaic.compositor import composite, composite_rgba  # noqa: E402
from mosaic.scene import Ctx, layer_matrix  # noqa: E402

EP = os.path.join(ROOT, "episodes", "ep02_napoleon")
CAM = dict(zoom=1.0, ox=0.0, oy=0.0)


def render(scene, ctx, t, idxs, rgba):
    buf = np.zeros((ctx.H, ctx.W, 4 if rgba else 3), np.float32)
    if not rgba:
        buf[:] = np.array(scene.bg, np.float32) / 255.0
    for i in idxs:
        layer = scene.layers[i]
        L = layer_matrix(ctx, CAM, layer.p)
        for item in layer.items:
            for e in item.emit(t):
                if e[2] <= 0.003 or (len(e) > 3 and e[3] in ("draw", "shadow", "shadowgroup")):
                    continue
                (composite_rgba if rgba else composite)(buf, e[0], L @ e[1], e[2])
    return buf


def save(path, buf):
    if buf.shape[2] == 4:
        a = np.clip(buf[..., 3:4], 1e-6, 1)
        rgb = np.where(a > 1e-5, buf[..., :3] / a, 0)
        out = np.dstack([rgb, buf[..., 3:4]])
        cv2.imwrite(path, cv2.cvtColor((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGBA2BGRA))
    else:
        cv2.imwrite(path, cv2.cvtColor((np.clip(buf, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))


def main():
    cfg = json.load(open(os.path.join(EP, "episode.json")))
    spec = importlib.util.spec_from_file_location("ep02", os.path.join(EP, "scenes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ctx = Ctx(1350, 2400, 30)                     # 1.25x the 1080x1920 frame: headroom for camera moves
    jobs = {  # shot index, time, {plate name: (layer indices, rgba)}
        "toulon": (0, 0.0, {"bg": ([0, 1, 2, 3], False), "napoleon": ([4], True), "fg": ([5], True)}),
        "coronation": (2, 3.3, {"bg": (None, False)}),
        "plan": (4, 0.0, {"bg": ([0, 1], False), "napoleon": ([2], True), "fg": ([3], True)}),
    }
    for name, (si, t, plates) in jobs.items():
        sc = mod.SHOTS[si](ctx, cfg["scenes"][si]["duration"])
        sc = getattr(sc, "scene", sc)
        for pn, (idxs, rgba) in plates.items():
            idxs = list(range(len(sc.layers))) if idxs is None else idxs
            p = os.path.join(HERE, "plates", f"{name}_{pn}.png")
            save(p, render(sc, ctx, t, idxs, rgba))
            print(p)


if __name__ == "__main__":
    main()

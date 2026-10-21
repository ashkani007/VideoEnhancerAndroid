#!/usr/bin/env python3
"""Render a clean thumbnail from one shot (no captions) with a bold title.

  python tools/thumbnail.py episodes/ep01b_cyrus_babylon_short 10 1.4 out.png "HOW BABYLON FELL" "539 BCE"
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mosaic import text  # noqa: E402
from mosaic.episode import load_config, load_scenes_module  # noqa: E402
from mosaic.scene import Ctx  # noqa: E402


def main(ep, shot, t, out, title, sub):
    cfg = load_config(ep)
    mod = load_scenes_module(ep, cfg)
    ctx = Ctx(1080, 1920, cfg.get("fps", 30))
    entry = cfg["scenes"][int(shot) - 1]
    frame = mod.SHOTS[int(shot) - 1](ctx, entry["duration"]).render(ctx, float(t))
    ov = text.title(ctx, title, sub, 0, 10, y=120, size=78)
    ov.apply(frame, 1.0)
    img = (np.clip(frame, 0, 1) * 255).astype(np.uint8)
    cv2.imwrite(out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:7])

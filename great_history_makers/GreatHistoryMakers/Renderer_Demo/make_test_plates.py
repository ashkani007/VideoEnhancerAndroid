#!/usr/bin/env python3
"""Build the renderer demo's TEST PLATES from the approved illustration (stand-ins until ComfyUI plates exist).

Each plate is written as its own image file with its own metadata, at a different size and aspect ratio, exactly as
the renderer will receive generated plates. Their content comes from one approved image (wide, portrait reframe,
battlefield reframe), because this container cannot generate new illustrations.

  python GreatHistoryMakers/Renderer_Demo/make_test_plates.py           (from great_history_makers/)
"""
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, GHM)
from ghm4 import masks  # noqa: E402

SRC = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source")
MASTER = cv2.imread(os.path.join(SRC, "napoleon_master.png"))
META = json.load(open(os.path.join(SRC, "napoleon_master.json")))
OUT = os.path.join(HERE, "plates")
# loose outline + certain core around Napoleon, and the foreground props (draped flag, crate, map, spyglass)
HINT = {"polygon": [[0, 380], [140, 110], [620, 110], [640, 1330], [520, 1672], [0, 1672]],
        "core": [[60, 900], [300, 300], [480, 330], [430, 1200], [200, 1500], [40, 1400]],
        "include": [[[0, 1185], [470, 1250], [540, 1672], [0, 1672]]]}


def shift(meta, ox, oy, w):
    """Re-express the master metadata for a crop starting at (ox, oy), width w."""
    m = {"ref_width": w}
    bx = lambda b: [b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy]    # noqa: E731
    if "sky" in meta:
        m["sky"] = dict(meta["sky"], y=meta["sky"]["y"] - oy)
    for key in ("flags", "bob", "smoke", "wind"):
        m[key] = [dict(r, box=bx(r["box"]), **({"pole_x": r["pole_x"] - ox} if "pole_x" in r else {})) for r in meta.get(key, [])]
    m["smoke_column"] = [dict(c, x=c["x"] - ox, y=c["y"] - oy) for c in meta.get("smoke_column", [])]
    m["eyes"] = [dict(e, upper=[[x - ox, y - oy] for x, y in e["upper"]], lower=[[x - ox, y - oy] for x, y in e["lower"]],
                      close_y=e["close_y"] - oy, skin=bx(e["skin"])) for e in meta.get("eyes", [])]
    if "sun" in meta:
        m["sun"] = dict(meta["sun"], x=meta["sun"]["x"] - ox, y=meta["sun"]["y"] - oy)
    return m


def hint_for(ox, oy, inc=True):
    h = {k: [[x - ox, y - oy] for x, y in HINT[k]] for k in ("polygon", "core")}
    if inc:
        h["include"] = [[[x - ox, y - oy] for x, y in p] for p in HINT["include"]]
    return h


def write(name, img, meta, scale=1.0, matte=True):
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(os.path.join(OUT, name + ".png"), img)
    meta["_about"] = "TEST PLATE derived from the approved illustration (renderer demo); real episodes use ComfyUI plates."
    report = {"plate": name, "size": [img.shape[1], img.shape[0]]}
    if matte:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        alpha = masks.make(rgb, meta, "hybrid")
        met, probs = masks.qa(rgb, alpha)
        masks.review_sheet(rgb, alpha, os.path.join(OUT, name + "_mask_review.jpg"), f"{name}: " + ("FALLBACK" if probs else "matte ok"))
        report.update(qa=met, problems=probs)
        if probs:
            meta.pop("mask", None)                                  # QA failed: single-layer shot
        else:
            cv2.imwrite(os.path.join(OUT, name + "_mask.png"), (alpha * 255).astype(np.uint8))
            meta["mask"] = name + "_mask.png"
    json.dump(meta, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(json.dumps(report))
    return report


def main():
    os.makedirs(OUT, exist_ok=True)
    reps = []
    m1 = shift(META, 0, 0, 941)
    m1["fg_hint"] = hint_for(0, 0)
    reps.append(write("p1_wide", MASTER, m1))                                      # 941x1672 (native size)
    x0, y0, x1, y1 = 150, 100, 650, 990
    m2 = shift(META, x0, y0, x1 - x0)
    m2["fg_hint"] = hint_for(x0, y0, inc=False)
    reps.append(write("p2_portrait", MASTER[y0:y1, x0:x1], m2, scale=2.0))         # 1000x1780 (like an upscaled plate)
    x0, y0, x1, y1 = 450, 520, 941, 1360
    m4 = shift(META, x0, y0, x1 - x0)
    m4["fg_hint"] = hint_for(x0, y0, inc=False)
    reps.append(write("p4_battle", MASTER[y0:y1, x0:x1], m4, scale=1.0))           # 491x840 (not 9:16: cover fit)
    json.dump(reps, open(os.path.join(OUT, "plates_report.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

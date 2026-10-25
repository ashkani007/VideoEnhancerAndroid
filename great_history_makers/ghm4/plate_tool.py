#!/usr/bin/env python3
"""Prepare a generated plate for animation.

  python -m ghm4.plate_tool overlay plates/x.png plates/x.json        # draws eyes, flags, smoke, bob, wind boxes -> x_overlay.png
  python -m ghm4.plate_tool mask plates/x.png plates/x.json           # GrabCut foreground matte from meta "fg_hint"

"fg_hint" in plate.json: {"polygon": [[x, y], ...], "core": [[x, y], ...]}: a loose outline around the foreground figure
and an optional polygon well inside it (plate pixels at ref_width).
The matte is written next to the plate (x_mask.png) and referenced as "mask" in the meta, which turns on parallax.
"""
import json
import os
import sys

import cv2
import numpy as np


def overlay(img_path, meta_path):
    img = cv2.imread(img_path)
    meta = json.load(open(meta_path))
    k = img.shape[1] / meta.get("ref_width", img.shape[1])
    P = lambda b: tuple(int(v * k) for v in b)                       # noqa: E731
    for name, col in (("flags", (0, 0, 255)), ("smoke", (200, 200, 200)), ("bob", (0, 200, 0)), ("wind", (255, 120, 0))):
        for r in meta.get(name, []):
            x0, y0, x1, y1 = P(r["box"])
            cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
            cv2.putText(img, name, (x0 + 4, y0 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    for e in meta.get("eyes", []):
        pts = (np.array(e["upper"] + e["lower"], np.float32) * k).astype(np.int32)
        cv2.polylines(img, [pts], True, (0, 255, 255), 1)
    out = os.path.splitext(img_path)[0] + "_overlay.png"
    cv2.imwrite(out, img)
    print(out)


def mask(img_path, meta_path):
    img = cv2.imread(img_path)
    meta = json.load(open(meta_path))
    k = img.shape[1] / meta.get("ref_width", img.shape[1])
    poly = (np.array(meta["fg_hint"]["polygon"], np.float32) * k).astype(np.int32)
    gc = np.full(img.shape[:2], cv2.GC_BGD, np.uint8)
    cv2.fillPoly(gc, [poly], cv2.GC_PR_FGD)
    if meta["fg_hint"].get("core"):                                  # optional polygon that is certainly foreground
        cv2.fillPoly(gc, [(np.array(meta["fg_hint"]["core"], np.float32) * k).astype(np.int32)], cv2.GC_FGD)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    m = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    out = os.path.splitext(img_path)[0] + "_mask.png"
    cv2.imwrite(out, m)
    meta["mask"] = os.path.basename(out)
    json.dump(meta, open(meta_path, "w"), indent=1)
    print(out)


if __name__ == "__main__":
    {"overlay": overlay, "mask": mask}[sys.argv[1]](sys.argv[2], sys.argv[3])

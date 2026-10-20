#!/usr/bin/env python3
"""Convert any image (reference art, AI plate, scan) into the house mosaic style.

  python tools/mosaicify.py input.png output.png --tile 8 --colors 24

Flat illustrations work best. Photos are first posterised (mean-shift + k-means)
into flat colour regions so the tesserae can follow their contours. With
--palette the colours are snapped to the series palette for consistency.
Transparent PNGs keep their alpha, so the result can be used as a cut-out layer.
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mosaic.palette import P  # noqa: E402
from mosaic.tessellate import tessellate  # noqa: E402


def posterize(rgb, k, palette):
    sm = cv2.pyrMeanShiftFiltering(rgb, 10, 22)
    Z = sm.reshape(-1, 3).astype(np.float32)
    _, lab, cen = cv2.kmeans(Z, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3,
                             cv2.KMEANS_PP_CENTERS)
    if palette:
        pal = np.array(list(P.values()), np.float32)
        cen = pal[np.argmin(((cen[:, None] - pal[None]) ** 2).sum(-1), 1)]
    out = cen[lab.ravel()].reshape(rgb.shape).astype(np.uint8)
    return cv2.medianBlur(out, 5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--tile", type=float, default=8, help="tile size in pixels")
    ap.add_argument("--colors", type=int, default=20)
    ap.add_argument("--palette", action="store_true", help="snap colours to the series palette")
    ap.add_argument("--max-side", type=int, default=1600)
    a = ap.parse_args()
    img = cv2.imread(a.input, cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"cannot read {a.input}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    s = a.max_side / max(img.shape[:2])
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2RGB)
    flat = posterize(rgb, a.colors, a.palette)
    rgba = np.dstack([flat, np.where(img[..., 3] > 127, 255, 0).astype(np.uint8)])
    pm, _ = tessellate(rgba, a.tile, seed=1, cache=False)
    out = pm.copy()
    a8 = out[..., 3:4].astype(np.float32) / 255.0
    out[..., :3] = np.where(a8 > 0, out[..., :3] / np.maximum(a8, 1e-3), 0).astype(np.uint8)
    cv2.imwrite(a.output, cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA))
    print(a.output)


if __name__ == "__main__":
    main()

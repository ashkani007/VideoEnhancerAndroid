#!/usr/bin/env python3
"""Foreground mattes for parallax: automatic segmentation, optional hints, refinement, QA and region evaluation.

  python -m ghm4.masks make <plate.png> <plate.json> [--method birefnet|grabcut|hybrid]   # writes <plate>_mask.png, sets meta "mask"
  python -m ghm4.masks qa <plate.png> <mask.png>                                         # metrics + review sheet (no ground truth)
  python -m ghm4.masks eval                                                              # region test on the approved plate (see ghm4/tests)

Methods
- birefnet: BiRefNet-general-lite (MIT licence) through rembg + onnxruntime on the CPU, about 25 s per plate.
  The model (224 MB) is downloaded once from the rembg GitHub release into ~/.rembg.
- grabcut:  OpenCV GrabCut seeded by meta "fg_hint" {"polygon": loose outline, "core": certain interior}.
- hybrid:   birefnet, then the hint: components outside the hint polygon are dropped, "include" polygons are forced
            to foreground (props such as a draped flag), "exclude" polygons to background.
A wrong matte is worse than none: if QA fails, leave "mask" out of the plate meta and the shot renders as one layer
(camera moves still work, only the parallax is lost).
"""
import argparse
import functools
import json
import os
import sys

import cv2
import numpy as np

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(None)
def _session(name):
    from rembg import new_session
    return new_session(name)


def birefnet(img_rgb, model="birefnet-general-lite"):
    from PIL import Image
    from rembg import remove
    m = remove(Image.fromarray(img_rgb), session=_session(model), only_mask=True)
    return np.asarray(m, np.float32) / 255


def _poly(meta_pts, k, shape):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [(np.array(meta_pts, np.float32) * k).astype(np.int32)], 255)
    return m > 0


def grabcut(img_rgb, hint, k):
    gc = np.full(img_rgb.shape[:2], cv2.GC_BGD, np.uint8)
    gc[_poly(hint["polygon"], k, gc.shape)] = cv2.GC_PR_FGD
    if hint.get("core"):
        gc[_poly(hint["core"], k, gc.shape)] = cv2.GC_FGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    return ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.float32)


def refine(alpha, hint=None, k=1.0):
    """Binarise, keep the main figure, fill pin-holes, apply include/exclude hints, feather 1 px."""
    m = (alpha > 0.5).astype(np.uint8)
    H, W = m.shape
    if hint and hint.get("polygon"):
        inside = _poly(hint["polygon"], k, m.shape)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        keep = np.zeros(n, bool)
        for i in range(1, n):
            keep[i] = inside[lab == i].mean() > 0.5
        m = keep[lab].astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 1:                                                         # drop specks below 0.1 % of the frame
        small = np.where(st[:, cv2.CC_STAT_AREA] < 0.001 * H * W)[0]
        m[np.isin(lab, small)] = 0
    inv = (1 - m).astype(np.uint8)                                    # fill holes below 0.2 % of the frame
    n, lab, st, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 0.002 * H * W and x > 0 and y > 0 and x + w < W and y + h < H:
            m[lab == i] = 1
    if hint:
        for p in hint.get("include", []):
            m[_poly(p, k, m.shape)] = 1
        for p in hint.get("exclude", []):
            m[_poly(p, k, m.shape)] = 0
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.0)


def make(img_rgb, meta, method="hybrid"):
    k = img_rgb.shape[1] / meta.get("ref_width", img_rgb.shape[1])
    hint = meta.get("fg_hint")
    if method == "grabcut":
        if not hint:
            raise ValueError("grabcut needs meta fg_hint")
        return refine(grabcut(img_rgb, hint, k), None, k)
    a = birefnet(img_rgb)
    return refine(a, hint if method == "hybrid" else None, k)


def qa(img_rgb, alpha):
    """Checks that need no ground truth. Returns (metrics, problems)."""
    m = alpha > 0.5
    H, W = m.shape
    frac = float(m.mean())
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    areas = sorted(st[1:, cv2.CC_STAT_AREA], reverse=True)
    main_share = float(areas[0] / max(1, m.sum())) if areas else 0.0
    edge = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    g = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    grad = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    align = float(grad[edge].mean() / (grad.mean() + 1e-6)) if edge.any() else 0.0
    soft = float(((alpha > 0.1) & (alpha < 0.9)).mean() / max(1e-6, frac))
    met = dict(fg_fraction=round(frac, 3), components=int(n - 1), main_component_share=round(main_share, 3),
               edge_alignment=round(align, 2), soft_ratio=round(soft, 3))
    probs = []
    if not 0.03 <= frac <= 0.75:
        probs.append(f"foreground covers {frac:.0%} of the frame")
    if main_share < 0.85:
        probs.append(f"figure split into pieces (largest piece {main_share:.0%})")
    if align < 1.6:
        probs.append(f"matte edge does not follow image edges (alignment {align:.2f} < 1.6)")
    return met, probs


def review_sheet(img_rgb, alpha, path, title=""):
    """Plate | matte over a checkerboard | background layer (what parallax reveals) for a visual check."""
    H, W = alpha.shape
    cb = ((np.indices((H, W)).sum(0) // 24) % 2)[..., None] * 0.25 + 0.55
    a = alpha[..., None]
    cut = img_rgb / 255 * a + cb * (1 - a)
    over = img_rgb / 255 * 0.45 + np.array([0.1, 0.9, 0.3]) * a * 0.55
    tile = lambda x: cv2.resize((np.clip(x, 0, 1) * 255).astype(np.uint8), (360, int(360 * H / W)))   # noqa: E731
    sheet = np.hstack([tile(img_rgb / 255), tile(over), tile(cut)])
    if title:
        cv2.putText(sheet, title, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(path, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))


# ------------------------------------------------------------------------------------------- region evaluation
def evaluate(alpha, regions, ref, offset=(0, 0)):
    """regions: {"figure": {name: box}, "background": {name: box}, "props": {name: box}} in source pixels.
    figure part recall = share of (reference figure inside the box, eroded 5 px) kept in the matte;
    background leak = share of background pixels in the box that the matte wrongly takes."""
    ox, oy = offset
    H, W = alpha.shape
    m = alpha > 0.5
    core = cv2.erode(ref.astype(np.uint8), np.ones((11, 11), np.uint8)) > 0       # 5 px boundary tolerance
    bgref = cv2.erode((~ref).astype(np.uint8), np.ones((11, 11), np.uint8)) > 0
    out = {"figure": {}, "background": {}, "props": {}}

    def sl(b):
        x0, y0, x1, y1 = b
        x0, x1 = max(0, x0 - ox), min(W, x1 - ox)
        y0, y1 = max(0, y0 - oy), min(H, y1 - oy)
        return (slice(y0, y1), slice(x0, x1)) if x1 > x0 + 4 and y1 > y0 + 4 else None
    for name, b in regions["figure"].items():
        s = sl(b)
        if s is not None and core[s].sum() > 200:
            out["figure"][name] = round(float(m[s][core[s]].mean()), 3)
    for name, b in regions["background"].items():
        s = sl(b)
        if s is not None and bgref[s].sum() > 200:
            out["background"][name] = round(float(m[s][bgref[s]].mean()), 3)
    for name, b in regions.get("props", {}).items():
        s = sl(b)
        if s is not None and core[s].sum() > 200:
            out["props"][name] = round(float(m[s][core[s]].mean()), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    mk = sp.add_parser("make")
    mk.add_argument("plate")
    mk.add_argument("meta")
    mk.add_argument("--method", default="hybrid", choices=["birefnet", "grabcut", "hybrid"])
    q = sp.add_parser("qa")
    q.add_argument("plate")
    q.add_argument("mask")
    a = ap.parse_args()
    if a.cmd == "make":
        img = cv2.cvtColor(cv2.imread(a.plate), cv2.COLOR_BGR2RGB)
        meta = json.load(open(a.meta, encoding="utf-8"))
        alpha = make(img, meta, a.method)
        met, probs = qa(img, alpha)
        out = os.path.splitext(a.plate)[0] + "_mask.png"
        cv2.imwrite(out, (alpha * 255).astype(np.uint8))
        review_sheet(img, alpha, os.path.splitext(a.plate)[0] + "_mask_review.jpg", a.method)
        print(json.dumps(met), "problems:", probs or "none")
        if probs:
            print("QA failed: mask NOT added to the meta (the shot renders as one layer). Fix the hint or accept manually.")
            sys.exit(2)
        meta["mask"] = os.path.basename(out)
        json.dump(meta, open(a.meta, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(out)
    elif a.cmd == "qa":
        img = cv2.cvtColor(cv2.imread(a.plate), cv2.COLOR_BGR2RGB)
        alpha = cv2.imread(a.mask, 0).astype(np.float32) / 255
        print(qa(img, alpha))


if __name__ == "__main__":
    main()

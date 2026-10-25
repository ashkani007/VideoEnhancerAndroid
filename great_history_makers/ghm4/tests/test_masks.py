#!/usr/bin/env python3
"""Mask regression: automatic mattes must keep every figure part and leave the background alone.

  python -m ghm4.tests.test_masks [--methods hybrid,birefnet,grabcut]

Runs each method on the approved plate and on two reframed crops (portrait, battlefield), scores named figure parts
(recall) and background regions (leak) against the hand-checked reference matte, writes review sheets to
ghm4/tests/out/ and a JSON report. Pass: every figure part >= 0.95 kept, every background region <= 0.03 leaked; where the fixture allows it
("mask_or_fallback"), a QA-rejected matte (shot falls back to one layer) also passes. Only "hybrid" gates the result.
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

from ghm4 import masks

GHM = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATE = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source", "napoleon_master.png")
REF = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "project", "mask_foreground.png")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
# hints as Claude would write them after looking at the plate: loose outline + certain core (source pixels)
HINT = {"polygon": [[0, 380], [140, 110], [620, 110], [640, 1330], [520, 1672], [0, 1672]],
        "core": [[60, 900], [300, 300], [480, 330], [430, 1200], [200, 1500], [40, 1400]]}
FIG_MIN, BG_MAX = 0.95, 0.03


def shift_hint(h, ox, oy):
    return {k: [[x - ox, y - oy] for x, y in v] for k, v in h.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="hybrid,birefnet,grabcut")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    regions = json.load(open(os.path.join(HERE, "fixtures", "napoleon_master_regions.json")))
    img_full = cv2.cvtColor(cv2.imread(PLATE), cv2.COLOR_BGR2RGB)
    ref_full = cv2.imread(REF, 0) > 127
    cases = {"full": (0, 0, img_full.shape[1], img_full.shape[0])}
    cases.update({k: tuple(v) for k, v in regions["crops"].items()})
    report, ok_all = {}, True
    for method in a.methods.split(","):
        for case, (x0, y0, x1, y1) in cases.items():
            img = np.ascontiguousarray(img_full[y0:y1, x0:x1])
            ref = ref_full[y0:y1, x0:x1]
            meta = {"ref_width": img.shape[1], "fg_hint": shift_hint(HINT, x0, y0)}
            t = time.time()
            alpha = masks.make(img, meta, method)
            dt = time.time() - t
            ev = masks.evaluate(alpha, regions, ref, (x0, y0))
            met, probs = masks.qa(img, alpha)
            bad_fig = {k: v for k, v in ev["figure"].items() if v < FIG_MIN}
            bad_bg = {k: v for k, v in ev["background"].items() if v > BG_MAX}
            expect = regions["expect"][case]
            fallback = bool(probs)                      # production rule: QA failure -> no matte, single-layer shot
            if fallback:
                passed = expect == "mask_or_fallback"
            else:
                passed = not bad_fig and not bad_bg
            report[f"{method}/{case}"] = dict(passed=passed, outcome="fallback (single layer)" if fallback else "mask", seconds=round(dt, 1), figure=ev["figure"], background=ev["background"],
                                              props=ev["props"], qa=met, qa_problems=probs, failing_figure=bad_fig, failing_background=bad_bg)
            if method == "hybrid":
                ok_all &= passed
            masks.review_sheet(img, alpha, os.path.join(OUT, f"mask_{method}_{case}.jpg"), f"{method} / {case}")
            print(f"{method:8s} {case:12s} {'PASS' if passed else 'FAIL'} {'fallback' if fallback else 'mask    '} {dt:5.1f}s  min figure "
                  f"{min(ev['figure'].values(), default=1):.3f}  max bg leak {max(ev['background'].values(), default=0):.3f}"
                  + (f"  failing: {bad_fig} {bad_bg}" if not passed else ""), flush=True)
    json.dump(report, open(os.path.join(OUT, "mask_report.json"), "w"), indent=1)
    print("hybrid (production method):", "PASS" if ok_all else "FAIL")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()

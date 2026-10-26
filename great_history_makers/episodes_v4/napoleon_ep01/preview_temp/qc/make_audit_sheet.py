#!/usr/bin/env python3
"""Annotated audit contact sheet: every shot (start / middle / end + the frames around its outgoing transition)
with the defects found by eye and by `ghm4.qc`, and the root-cause category of each.

  python episodes_v4/napoleon_ep01/preview_temp/qc/make_audit_sheet.py <storyboard> <video> <findings.json> <out.jpg>
findings.json: {"<shot id>": [["<category>", "<defect>", "<fix or 'ok'>"], ...]}
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
from ghm4 import text as T  # noqa: E402

COL = {"generation": (255, 150, 90), "animation": (120, 200, 255), "compositing": (250, 205, 90), "encoding": (200, 140, 255),
       "scaling": (255, 110, 160), "ok": (140, 220, 140)}


def main(sb_path, video, findings_path, out):
    sb = json.load(open(sb_path))
    findings = json.load(open(findings_path))
    shots = sorted(sb["shots"], key=lambda s: s["start"])
    cuts = {round(t["at"], 3): t["type"] for t in sb.get("transitions", [])}
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    plan = []
    for s in shots:
        a, b = s["start"], s["end"]
        ts = [a + 0.25, (a + b) / 2, b - 0.25]
        c = round(b, 3)
        ts += [c - 0.15, c, c + 0.15] if c in cuts else []
        plan.append((s, ts))
    need = {int(round(t * fps)) for _, ts in plan for t in ts}
    frames, i = {}, 0
    while need and i <= max(need):
        ok, fr = cap.read()
        if not ok:
            break
        if i in need:
            frames[i] = fr
        i += 1
    tw, th = 160, 284
    W = tw * 6 + 700
    sheet = Image.new("RGB", (W, (th + 10) * len(plan) + 50), (16, 16, 20))
    d = ImageDraw.Draw(sheet)
    f15, f17, f22 = T.font("Regular", 15), T.font("Bold", 17), T.font("Bold", 22)
    d.text((10, 12), f"Visual audit: {os.path.basename(video)}   (colour = root cause: generation / animation / compositing / "
                     f"scaling / encoding; green = ok)", font=f22, fill=(235, 235, 240))
    for r, (s, ts) in enumerate(plan):
        y = 50 + r * (th + 10)
        labels = ["start", "mid", "end", "cut-0.15", "cut " + cuts.get(round(s["end"], 3), ""), "cut+0.15"]
        for k, t in enumerate(ts):
            fr = frames.get(int(round(t * fps)))
            im = Image.new("RGB", (tw, th), (60, 0, 0)) if fr is None else \
                Image.fromarray(cv2.cvtColor(cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
            sheet.paste(im, (k * tw, y))
            d.rectangle([k * tw, y, k * tw + tw - 1, y + 18], fill=(0, 0, 0))
            d.text((k * tw + 4, y + 1), f"{t:.2f}s {labels[k]}", font=f15, fill=(255, 230, 90))
        x = tw * 6 + 14
        items = findings.get(s["id"], [])
        bad = any(c != "ok" for c, *_ in items)
        d.text((x, y + 4), f"{s['id']}  {s['start']:.2f}-{s['end']:.2f}s  ({s['type']})", font=f17,
               fill=(255, 120, 110) if bad else (140, 220, 140))
        ty = y + 30
        for cat, defect, fix in items:
            txt = f"[{cat}] {defect}" + (f"  ->  {fix}" if fix and fix != "ok" else "")
            line = ""
            for word in txt.split():
                if d.textlength(line + " " + word, font=f15) > W - x - 12:
                    d.text((x, ty), line, font=f15, fill=COL.get(cat, (200, 200, 200)))
                    ty += 18
                    line = "    " + word
                else:
                    line = (line + " " + word).strip() if line.strip() else ("    " + word if line else word)
            d.text((x, ty), line, font=f15, fill=COL.get(cat, (200, 200, 200)))
            ty += 22
    sheet.save(out, quality=88)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:5])

#!/usr/bin/env python3
"""Visual quality control for a rendered v4 video: flags suspicious shots before a human looks at them.

  python -m ghm4.qc <storyboard.json> <video.mp4> [--out <dir>]

Writes <dir>/qc_report.json and <dir>/qc_contact.jpg (one row per shot: start / middle / end, then the frames
around the outgoing transition; flags printed on the row). Exit code 1 if any shot has an ERROR flag.

Checks
- integrity: the file decodes, frame count = duration x fps, size and fps match the storyboard target
- per frame: black (mean luma), frozen stretches (no pixel change for >= 1 s), flicker (luma jumps outside transitions)
- per shot: sharpness (Laplacian, relative to the episode median), motion (camera / effects actually move)
- per plate shot, from the source image and the camera: upscale factor at the tightest zoom (soft image if > 1.6x),
  visible fraction of the plate, aspect ratio of the source, matte file present
- text items: wider than the frame or crossing its edge, inside the caption band while captions are on screen,
  low contrast against the rendered background
- transitions: washed-out stretches (flash / fade frames with almost no detail for >= 0.2 s)
- maps: labels cut by the frame edge, labels overlapping each other (sampled through the shot)
- captions: background too bright behind the subtitle band
Thresholds are deliberately conservative: a flag means "look at this shot", not "this shot is broken".
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import text as T

CAPTION_BAND = (860, 990)          # design units (720x1280): titles must stay above y 840 (ghm4.narrate check)
FORMATS = {"portrait": dict(dw=720, dh=1280, band=CAPTION_BAND, cap_rows=(880 / 1280, 1000 / 1280)),
           "landscape": dict(dw=1280, dh=720, band=(600, 700), cap_rows=(0.84, 0.97))}


def fmt(sb):
    return FORMATS["landscape" if sb.get("format") == "landscape" else "portrait"]
LIMITS = {"washout_frames": 6, "washout_std": 0.07, "caption_bg_luma": 0.70, "text_contrast": 1.6, "black_luma": 0.035, "frozen_s": 1.0, "frozen_diff": 0.0008, "flicker_jump": 0.06, "rel_sharp": 0.40,
          "upscale_warn": 1.6, "upscale_error": 2.4, "min_motion": 0.0015}


def text_extent(it):
    """Left/right x of a text item in design units (letter tracking included)."""
    st, sz, tr, *_ = T.PRESETS[it.get("preset", "tagline")]
    f = T.font(it.get("style") or st, int(round(it.get("size") or sz)))
    s = it["text"]
    tr = tr if it.get("track") is None else it["track"]
    w = sum(f.getlength(ch) for ch in s) + tr * (len(s) - 1)
    x = it.get("x", 360)
    al = it.get("align", "c")
    x0 = x - w / 2 if al == "c" else (x - w if al == "r" else x)
    return x0, x0 + w


def source_detail(path, cam, OW, OH):
    """Laplacian variance of the plate itself at the shot's mid zoom (same half-resolution measure as the frames),
    so 'soft' can be split into: the render lost detail vs. the source simply has little detail."""
    src = cv2.imread(path)
    if src is None:
        return None
    z = (cam.get("from", {}).get("zoom", 1.0) + cam.get("to", cam.get("from", {})).get("zoom", 1.0)) / 2
    H0, W0 = src.shape[:2]
    sc = max(OW / W0, OH / H0) * z / 2
    im = cv2.resize(src, (max(8, int(W0 * sc)), max(8, int(H0 * sc))), interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_LANCZOS4)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    h, w = g.shape                                                # the visible window (centre), then the same rows
    fh, fw = min(h, OH // 2), min(w, OW // 2)                     # as the frame measure: 10-68 % (above the captions)
    win = g[(h - fh) // 2:(h - fh) // 2 + fh, (w - fw) // 2:(w - fw) // 2 + fw]
    return float(cv2.Laplacian(win[int(0.1 * fh):int(0.68 * fh)], cv2.CV_32F).var())


def static_checks(sb, sb_dir, OW, OH):
    """Problems visible from the storyboard and the source images alone (no decoding)."""
    F = fmt(sb)
    out = {}
    caps = sb.get("captions")
    for sh in sb["shots"]:
        fl = []
        if sh["type"] == "plate":
            path = os.path.join(sb_dir, sh["plate"])
            im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if im is None:
                fl.append(("ERROR", f"plate missing: {sh['plate']}"))
                out[sh["id"]] = fl
                continue
            H0, W0 = im.shape[:2]
            meta = {}
            if sh.get("meta") and os.path.exists(os.path.join(sb_dir, sh["meta"])):
                meta = json.load(open(os.path.join(sb_dir, sh["meta"])))
                if meta.get("mask") and not os.path.exists(os.path.join(os.path.dirname(os.path.join(sb_dir, sh["meta"])), meta["mask"])):
                    fl.append(("ERROR", f"matte {meta['mask']} missing (renders as one layer)"))
            cam = sh.get("camera", {})
            zmax = max(cam.get("from", {}).get("zoom", 1.0), cam.get("to", {}).get("zoom", 1.0))
            up = max(OW / W0, OH / H0) * zmax
            if up > LIMITS["upscale_error"]:
                fl.append(("ERROR", f"source {W0}x{H0} enlarged {up:.2f}x at zoom {zmax} (blurry)"))
            elif up > LIMITS["upscale_warn"]:
                fl.append(("WARN", f"source {W0}x{H0} enlarged {up:.2f}x at zoom {zmax} (soft)"))
            vis = (OW / OH) / (W0 / H0)
            vis = min(vis, 1 / vis) / zmax ** 2
            target = OW / OH
            if abs(W0 / H0 - target) > 0.08 * target:
                fl.append(("WARN", f"source aspect {W0 / H0:.2f} differs from the frame ({target:.2f}); only {vis * 100:.0f}% of the image is ever visible"))
            if meta.get("temp_standin"):
                fl.append(("INFO", "temporary stand-in plate"))
        for it in sh.get("text", []):
            if "text" not in it:
                continue
            x0, x1 = text_extent(it)
            if x0 < 8 or x1 > F["dw"] - 8:
                fl.append(("ERROR", f"text '{it['text']}' spans x {x0:.0f}-{x1:.0f} (frame 0-{F['dw']}): clipped"))
            y = it.get("y", 0)
            if caps and F["band"][0] - 20 < y <= F["band"][1] + 40:
                fl.append(("WARN", f"text '{it['text']}' at y {y} sits in the caption band"))
        out[sh["id"]] = fl
    return out


def map_checks(sb, sb_dir, OW, OH):
    """Clipped and overlapping map labels, sampled every 0.25 s."""
    from . import mapshot
    F = fmt(sb)
    out = {}
    for sh in sb["shots"]:
        if sh["type"] != "map":
            continue
        m = mapshot.MapShot(os.path.join(sb_dir, sh["map"]), OW, OH)
        clipped, overl, under = {}, {}, {}
        for tl in np.arange(0.0, sh["end"] - sh["start"], 0.25):
            boxes = [b for b in m.layout(float(tl)) if b[5] > 0.35]
            for txt, x0, x1, y, sz, a, kind in boxes:
                if (x0 < 4 or x1 > F["dw"] - 4) and y > 0 and y < F["dh"]:
                    clipped.setdefault(txt, round(sh["start"] + tl, 2))
                if sb.get("captions") and F["band"][0] - 10 < y < F["band"][1] + 30 and x1 > F["dw"] / 6 and x0 < F["dw"] * 5 / 6:
                    under.setdefault(txt, round(sh["start"] + tl, 2))
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    A, B = boxes[i], boxes[j]
                    if A[6] == "region" and B[6] == "region":
                        continue
                    ox = min(A[2], B[2]) - max(A[1], B[1])
                    oy = min(A[3], B[3]) - max(A[3] - A[4] * 0.8, B[3] - B[4] * 0.8)
                    if ox > -12 and oy > -8:                         # touching labels read as one word
                        overl.setdefault(f"{A[0]} / {B[0]}", round(sh["start"] + tl, 2))
        fl = [("WARN", f"map label '{k}' cut by the frame edge at {v}s") for k, v in clipped.items()]
        fl += [("WARN", f"map labels overlap or touch: {k} at {v}s") for k, v in overl.items()]
        fl += [("WARN", f"map label '{k}' under the subtitle band at {v}s") for k, v in under.items()]
        out[sh["id"]] = fl
    return out


def text_contrast(sb, frames_at, fps):
    """Luma contrast between each title and the rendered background behind it (frame where the title is fully in)."""
    out = {}
    for sh in sb["shots"]:
        fl = []
        for it in sh.get("text", []):
            if "text" not in it or str(it["text"]).startswith("TEMP"):
                continue
            t = sh["start"] + it.get("at", 0) + 0.9
            if it.get("out"):
                t = min(t, sh["start"] + it["out"][0] - 0.05)
            fr = frames_at(int(round(t * fps)))
            if fr is None:
                continue
            Hh, Ww = fr.shape[:2]
            U = Ww / fmt(sb)["dw"]
            st, sz, *_ = T.PRESETS[it.get("preset", "tagline")]
            size = it.get("size") or sz
            x0, x1 = text_extent(it)
            y1, y0 = it["y"], it["y"] - size * 0.75
            box = fr[max(0, int(y0 * U)):int(y1 * U), max(0, int(x0 * U)):min(Ww, int(x1 * U))]
            if box.size == 0:
                continue
            g = cv2.cvtColor(box, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
            lo, hi = np.percentile(g, 15), np.percentile(g, 95)
            if (hi + 0.05) / (lo + 0.05) < LIMITS["text_contrast"]:
                fl.append(("WARN", f"text '{it['text']}' low contrast at {t:.2f}s (ratio {(hi + 0.05) / (lo + 0.05):.2f})"))
        out[sh["id"]] = fl
    return out


def analyse(sb_path, video, out_dir):
    sb = json.load(open(sb_path, encoding="utf-8"))
    sb_dir = os.path.dirname(os.path.abspath(sb_path))
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or sb.get("fps", 30)
    OW, OH = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    shots = sorted(sb["shots"], key=lambda s: s["start"])
    cuts = sorted({round(t["at"], 3) for t in sb.get("transitions", [])})
    want = {}                                                     # frame index -> label for the contact sheet
    for sh in shots:
        a, b = sh["start"], sh["end"]
        for lab, t in (("start", a + 0.25), ("mid", (a + b) / 2), ("end", b - 0.25)):
            want[int(round(t * fps))] = (sh["id"], lab)
    for c in cuts:
        for lab, dt in (("cut-0.2", -0.2), ("cut", 0.0), ("cut+0.2", 0.2)):
            want.setdefault(int(round((c + dt) * fps)), (None, lab))
    for sh in shots:                                              # frames for the text-contrast check
        for it in sh.get("text", []):
            if "text" in it:
                t = sh["start"] + it.get("at", 0) + 0.9
                if it.get("out"):
                    t = min(t, sh["start"] + it["out"][0] - 0.05)
                want.setdefault(int(round(t * fps)), (sh["id"], "text"))
    luma, diff, sharp, frames, lstd, capl = [], [], [], {}, [], []
    prev = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(fr, (OW // 2, OH // 2), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        luma.append(float(g.mean()))
        lstd.append(float(g.std()))
        r0, r1 = fmt(sb)["cap_rows"]
        capl.append(float(g[int(g.shape[0] * r0):int(g.shape[0] * r1), int(g.shape[1] * 0.15):int(g.shape[1] * 0.85)].mean()))
        sharp.append(float(cv2.Laplacian(g[int(0.1 * g.shape[0]):int(0.68 * g.shape[0])], cv2.CV_32F).var()))  # above the captions
        diff.append(float(np.abs(g - prev).mean()) if prev is not None else 0.0)
        prev = g
        i = len(luma) - 1
        if i in want:
            frames[i] = fr
    cap.release()
    n = len(luma)
    expect = int(round(sb["duration"] * sb.get("fps", 30)))
    report = {"video": video, "size": [OW, OH], "fps": fps, "frames": n, "expected_frames": expect, "shots": [], "global": []}
    if n != expect:
        report["global"].append(("ERROR", f"{n} frames decoded, {expect} expected"))
    want = 16 / 9 if sb.get("format") == "landscape" else 9 / 16
    if abs(OW / OH - want) > 0.01:
        report["global"].append(("ERROR", f"output aspect {OW}x{OH} is not {'16:9' if want > 1 else '9:16'}"))
    luma, diff, sharp, lstd, capl = map(np.array, (luma, diff, sharp, lstd, capl))
    mapq = map_checks(sb, sb_dir, OW, OH)
    txtq = text_contrast(sb, frames.get, fps)
    cap_on = np.zeros(n, bool)
    if sb.get("captions"):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from mosaic import captions as C
            cs = sb["captions"]
            tr = open(os.path.join(sb_dir, cs["transcript"]), encoding="utf-8").read().strip()
            words = C.map_words(tr, json.load(open(os.path.join(sb_dir, cs["words"]))), cs.get("spoken"))
            for w in words:
                cap_on[int(w["start"] * fps):min(n, int(w["end"] * fps) + 1)] = True
        except Exception as e:                                    # noqa: BLE001 (QC must not crash on caption data)
            report["global"].append(("INFO", f"caption timing not available: {e}"))
    near_cut = np.zeros(n, bool)
    for c in cuts + [sb["duration"] - sb.get("fade_out", 0.65)]:
        near_cut[max(0, int((c - 0.5) * fps)):min(n, int((c + 0.5) * fps))] = True
    near_cut[-int(sb.get("fade_out", 0.65) * fps) - 2:] = True
    static = static_checks(sb, sb_dir, OW, OH)
    med_sharp = float(np.median(sharp)) if n else 0.0
    for sh in shots:
        a, b = int(sh["start"] * fps), min(n, int(sh["end"] * fps))
        fl = list(static.get(sh["id"], [])) + mapq.get(sh["id"], []) + txtq.get(sh["id"], [])
        seg = slice(a, b)
        wo = (lstd < LIMITS["washout_std"]) & (luma > 0.55)
        run, worst, at = 0, 0, a
        for k in range(max(0, a - 15), min(n, b + 15)):
            run = run + 1 if wo[k] else 0
            if run > worst:
                worst, at = run, k - run + 1
        if worst >= LIMITS["washout_frames"]:
            fl.append(("WARN", f"washed-out frames: {worst} in a row from {at / fps:.2f}s (transition too strong?)"))
        bright = cap_on[a:b] & (capl[a:b] > LIMITS["caption_bg_luma"])
        if bright.sum() > 0.25 * fps:
            fl.append(("WARN", f"subtitle background bright for {bright.sum() / fps:.1f}s (mean luma up to {capl[a:b].max():.2f})"))
        blk = np.where(luma[seg] < LIMITS["black_luma"])[0]
        blk = blk[~near_cut[a:b][blk]]
        if len(blk):
            fl.append(("ERROR", f"{len(blk)} black frames from {(a + blk[0]) / fps:.2f}s"))
        run, worst, at = 0, 0, a
        for k in range(a + 1, b):
            run = run + 1 if diff[k] < LIMITS["frozen_diff"] else 0
            if run > worst:
                worst, at = run, k - run
        if worst / fps >= LIMITS["frozen_s"]:
            fl.append(("ERROR", f"frozen for {worst / fps:.1f}s from {at / fps:.2f}s"))
        jumps = np.where((np.abs(np.diff(luma[seg])) > LIMITS["flicker_jump"]) & ~near_cut[a + 1:b])[0]
        if len(jumps):
            fl.append(("WARN", f"{len(jumps)} luma jumps (flicker) e.g. {(a + jumps[0] + 1) / fps:.2f}s"))
        ms = float(np.median(sharp[seg])) if b > a else 0.0
        if ms < LIMITS["rel_sharp"] * med_sharp:
            sd = source_detail(os.path.join(sb_dir, sh["plate"]), sh.get("camera", {}), OW, OH) if sh["type"] == "plate" else None
            if sd and ms >= 0.8 * sd:
                fl.append(("INFO", f"low detail ({ms / max(med_sharp, 1e-9):.2f}x the episode median) comes from the source "
                                   f"image, not the render (render/source detail {ms / sd:.1f}x)"))
            else:
                fl.append(("WARN", f"soft: sharpness {ms / max(med_sharp, 1e-9):.2f}x the episode median"
                                   + (f", render/source detail {ms / sd:.2f}x (render loses detail)" if sd else "")))
        mm = float(np.median(diff[a + 1:b])) if b > a + 1 else 0.0
        if mm < LIMITS["min_motion"]:
            fl.append(("WARN", f"little motion (median frame change {mm:.4f})"))
        report["shots"].append({"id": sh["id"], "type": sh["type"], "start": sh["start"], "end": sh["end"],
                                "sharpness_rel": round(ms / max(med_sharp, 1e-9), 3), "motion": round(mm, 5),
                                "luma": round(float(np.mean(luma[seg])), 3) if b > a else None, "flags": fl})
    report["errors"] = sum(1 for s in report["shots"] for f in s["flags"] if f[0] == "ERROR") + \
        sum(1 for f in report["global"] if f[0] == "ERROR")
    report["warnings"] = sum(1 for s in report["shots"] for f in s["flags"] if f[0] == "WARN")
    json.dump(report, open(os.path.join(out_dir, "qc_report.json"), "w"), indent=1)
    contact(report, frames, fps, cuts, os.path.join(out_dir, "qc_contact.jpg"))
    return report


def contact(report, frames, fps, cuts, path, tw=None):
    fw, fh = report["size"]
    tw = tw or (150 if fh > fw else 300)                          # thumbnails keep the frame's aspect (9:16 or 16:9)
    th = int(round(tw * fh / fw))
    rows = report["shots"]
    W = tw * 6 + 520
    sheet = Image.new("RGB", (W, (th + 8) * len(rows)), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    fnt = T.font("Regular", 15)
    fb = T.font("Bold", 17)

    def thumb(i):
        fr = frames.get(i)
        if fr is None:
            return Image.new("RGB", (tw, th), (60, 0, 0))
        return Image.fromarray(cv2.cvtColor(cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
    for r, sh in enumerate(rows):
        y = r * (th + 8)
        a, b = sh["start"], sh["end"]
        idx = [int(round(t * fps)) for t in (a + 0.25, (a + b) / 2, b - 0.25)]
        nxt = min([c for c in cuts if abs(c - b) < 0.02] or [None], key=lambda c: 0 if c is None else c)
        if nxt is not None:
            idx += [int(round((nxt + dt) * fps)) for dt in (-0.2, 0.0, 0.2)]
        labels = ["start", "mid", "end", "cut-0.2", "cut", "cut+0.2"]
        for k, i in enumerate(idx):
            sheet.paste(thumb(i), (k * tw, y))
            d.text((k * tw + 4, y + 3), f"{i / fps:.2f}s {labels[k]}", font=fnt, fill=(255, 230, 90))
        x = tw * 6 + 12
        worst = max([{"ERROR": 2, "WARN": 1}.get(f[0], 0) for f in sh["flags"]] + [0])
        col = [(140, 220, 140), (250, 200, 80), (255, 90, 80)][worst]
        d.text((x, y + 6), f"{sh['id']}  {a:.2f}-{b:.2f}s  ({sh['type']})", font=fb, fill=col)
        ty = y + 30
        for lvl, msg in sh["flags"]:
            for line in [msg[i:i + 58] for i in range(0, len(msg), 58)]:
                d.text((x, ty), ("" if line != msg[:58] else f"{lvl}: ") + line, font=fnt,
                       fill={"ERROR": (255, 110, 100), "WARN": (250, 205, 90)}.get(lvl, (170, 170, 180)))
                ty += 18
        d.text((x, y + th - 20), f"sharp {sh['sharpness_rel']}x  motion {sh['motion']}  luma {sh['luma']}", font=fnt, fill=(150, 150, 160))
    sheet.save(path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("video")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.video)), "qc")
    r = analyse(a.storyboard, a.video, out)
    for f in r["global"]:
        print(*f)
    for s in r["shots"]:
        for lvl, msg in s["flags"]:
            if lvl != "INFO":
                print(f"{lvl:5} {s['id']:16} {msg}")
    print(f"{r['frames']} frames, {r['errors']} errors, {r['warnings']} warnings -> {out}/qc_report.json, qc_contact.jpg")
    sys.exit(1 if r["errors"] else 0)


if __name__ == "__main__":
    main()

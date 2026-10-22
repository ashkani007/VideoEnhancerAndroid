#!/usr/bin/env python3
"""Render Version C and compare with B on identical timestamps.

Writes AB_C_720x1280.mp4, AB_C_Comparison.mp4 (B | C, labelled), AB_C_ContactSheet.png and
metrics.json (per-region motion = measured parallax, frame-difference stats, duplicates)."""
import importlib.util
import json
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from mosaic.scene import Ctx  # noqa: E402

OUT = os.path.join(ROOT, "output", "experiments", "ab_2p5d")
AUDIO = os.path.join(ROOT, "output", "ep01c_cyrus_v3", "deliverables", "Cyrus_Babylon_V3_Final_1080x1920.mp4")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "experiments", "ab_2p5d", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def encode(frames, W, H, out, fps=30, dur=5.0):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-ss", "19.6", "-t", str(dur), "-i", AUDIO, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
           "-crf", "17", "-tune", "animation", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-af", f"afade=t=in:d=0.2,afade=t=out:st={dur - 0.3}:d=0.3", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def decode(path, W, H):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    return list(np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3))


def region_motion(frames, box):
    """Median horizontal shift (px/frame) of a region via phase correlation."""
    x0, y0, x1, y1 = box
    sh = []
    for a, b in zip(frames[:-1:3], frames[3::3]):
        ga = cv2.cvtColor(a[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        gb = cv2.cvtColor(b[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
        sh.append(dx / 3)
    return float(np.median(sh))


def main():
    W, H, fps, dur = 720, 1280, 30, 5.0
    ctx = Ctx(W, H, fps)
    C = load("scene_c")
    sc = C.build(ctx, dur)
    fC = []
    for i in range(int(dur * fps)):
        f = sc.render(ctx, i / fps)
        fC.append(cv2.cvtColor((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    encode(fC, W, H, os.path.join(OUT, "AB_C_720x1280.mp4"))
    fB = decode(os.path.join(OUT, "AB_B_720x1280.mp4"), W, H)[:len(fC)]

    def sbs():
        for b, c in zip(fB, fC):
            img = np.hstack([b, np.zeros((H, 8, 3), np.uint8), c])
            for x0, txt in ((0, "B  previous 2.5D"), (W + 8, "C  volume + IK gait + tracking")):
                cv2.rectangle(img, (x0 + 14, 14), (x0 + 14 + int(W * 0.62), 14 + 44), (20, 14, 10), -1)
                cv2.putText(img, txt, (x0 + 24, 46), cv2.FONT_HERSHEY_DUPLEX, 0.72, (230, 240, 250), 1, cv2.LINE_AA)
            yield img
    encode(sbs(), 2 * W + 8, H, os.path.join(OUT, "AB_C_Comparison.mp4"))
    # contact sheet: B (top) vs C (bottom) at identical timestamps + C crops at 1:1
    ts = [0.3, 1.5, 2.7, 3.9, 4.8]
    top = np.hstack([cv2.resize(fB[int(t * fps)], (W // 3, H // 3)) for t in ts])
    bot = np.hstack([cv2.resize(fC[int(t * fps)], (W // 3, H // 3)) for t in ts])
    crops = np.hstack([fC[int(2.0 * fps) + k * 4][700:1220, 40:400] for k in range(4)])
    crops = cv2.resize(crops, (top.shape[1], int(crops.shape[0] * top.shape[1] / crops.shape[1])))
    lab = lambda img, txt: cv2.putText(img, txt, (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    lab(top, "B  t = " + "  ".join(f"{t}s" for t in ts))
    lab(bot, "C  same timestamps")
    lab(crops, "C  near rank 1:1 crops, every 4th frame from 2.0 s")
    cv2.imwrite(os.path.join(OUT, "AB_C_ContactSheet.png"), np.vstack([top, bot, crops]))
    # metrics
    regions = {"sky (far)": (40, 30, 680, 200), "gate (mid-far)": (200, 330, 520, 560),
               "near ground (near)": (60, 1180, 660, 1270), "fg pillar zone (right)": (520, 200, 720, 900)}
    m = {}
    for tag, fr in (("B", fB), ("C", fC)):
        g = np.array([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in fr]).astype(np.float32)
        d = np.abs(np.diff(g, axis=0)).mean((1, 2))
        m[tag] = dict(region_dx_px_per_frame={k: round(region_motion(fr, b), 3) for k, b in regions.items()},
                      frame_diff_mean=round(float(d.mean()), 3), frame_diff_min=round(float(d.min()), 3),
                      frame_diff_max=round(float(d.max()), 3), frozen_frames=int((d < 0.05).sum()),
                      mean_saturation=round(float(np.mean([cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 1].mean() / 255 for f in fr[::10]])), 3))
    json.dump(m, open(os.path.join(OUT, "AB_C_metrics.json"), "w"), indent=1)
    print(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()

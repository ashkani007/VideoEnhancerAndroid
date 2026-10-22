#!/usr/bin/env python3
"""Render Version D (gate entry with turning soldiers), the C-vs-D comparison and motion metrics."""
import importlib.util
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from mosaic.scene import Ctx, layer_matrix  # noqa: E402

OUT = os.path.join(ROOT, "output", "experiments", "ab_2p5d")
AUDIO = os.path.join(ROOT, "output", "ep01c_cyrus_v3", "deliverables", "Cyrus_Babylon_V3_Final_1080x1920.mp4")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "experiments", "ab_2p5d", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def encode(frames, W, H, out, dur, fps=30):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-ss", "19.2", "-t", str(dur), "-i", AUDIO, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
           "-crf", "17", "-tune", "animation", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-af", f"afade=t=in:d=0.2,afade=t=out:st={dur - 0.4}:d=0.4", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def to8(f):
    return cv2.cvtColor((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)


def main():
    W, H, fps, dur = 720, 1280, 30, 8.0
    n = int(dur * fps)
    ctx = Ctx(W, H, fps)
    D = load("scene_d")
    scD, walkers = D.build(ctx, dur)
    fD = [to8(scD.render(ctx, i / fps)) for i in range(n)]
    encode(fD, W, H, os.path.join(OUT, "AB_D_Gate_Entry_720x1280.mp4"), dur)
    C = load("scene_c")
    scC = C.build(ctx, dur)
    fC = [to8(scC.render(ctx, i / fps)) for i in range(n)]

    def sbs():
        for c, d in zip(fC, fD):
            img = np.hstack([c, np.zeros((H, 8, 3), np.uint8), d])
            for x0, txt in ((0, "C  sideways march (no turning)"), (W + 8, "D  path-following turn into gate")):
                cv2.rectangle(img, (x0 + 14, 14), (x0 + 14 + int(W * 0.7), 58), (20, 14, 10), -1)
                cv2.putText(img, txt, (x0 + 24, 46), cv2.FONT_HERSHEY_DUPLEX, 0.66, (230, 240, 250), 1, cv2.LINE_AA)
            yield img
    encode(sbs(), 2 * W + 8, H, os.path.join(OUT, "AB_C_vs_D_Comparison.mp4"), dur)

    # ---------------- motion metrics
    G = D.G
    met = {"walkers": []}
    names = ["R1 (from right)", "L1 (from left)", "R2 (from right)", "L2 (from left)"]
    for name, w in zip(names, walkers):
        rec = {"name": name}
        ts = np.arange(0, dur, 1 / fps)
        psi = [w.psi_hip(t) for t in ts]
        vis = [i for i, t in enumerate(ts) if 0 < w.s_at(t) < w.path.length]
        rec["heading_first_visible_deg"] = round(psi[vis[0]], 1) if vis else None
        rec["heading_last_visible_deg"] = round(psi[vis[-1]], 1) if vis else None
        # body yaw vs actual direction of travel (finite difference of root positions)
        errs, head_leads = [], []
        for t in ts[1:-1]:
            x0, z0 = w.path.at(w.s_at(t - 0.02))
            x1, z1 = w.path.at(w.s_at(t + 0.02))
            if 0 < w.s_at(t) < w.path.length:
                travel = math.degrees(math.atan2(-(x1 - x0), (z1 - z0)))
                errs.append(abs(((w.psi_hip(t) - travel) + 180) % 360 - 180))
                head_leads.append(w.pose3d(t)["psi_h"] - w.psi_hip(t))
        rec["max_body_vs_travel_error_deg"] = round(max(errs), 2) if errs else None
        rec["head_lead_range_deg"] = [round(min(head_leads), 1), round(max(head_leads), 1)] if head_leads else None
        # planted foot drift in world units during flat stance (consecutive frames)
        drift = 0.0
        for leg in ("n", "f"):
            prev = None
            for t in ts:
                if not (0 < w.s_at(t) < w.path.length):
                    prev = None
                    continue
                (X, Z, Y), pitch, up, stance = w.foot(t, leg)
                if stance and abs(pitch) < 1e-6:
                    if prev is not None:
                        drift = max(drift, math.hypot(X - prev[0], Z - prev[1]))
                    prev = (X, Z)
                else:
                    prev = None
        rec["max_planted_ankle_drift_world_units_per_frame"] = round(drift, 4)
        # entry timing
        cross = [t for t in ts if 0 < w.s_at(t) < w.path.length and G.f / w.path.at(w.s_at(t))[1] < 1.0]
        rec["passes_gate_plane_at_s"] = round(cross[0], 2) if cross else None
        dark = [t for t in ts if 0 < w.s_at(t) < w.path.length and D.light(G.f / w.path.at(w.s_at(t))[1])[0] < 0.12]
        rec["fully_in_passage_darkness_at_s"] = round(dark[0], 2) if dark else None
        met["walkers"].append(rec)
    for tag, fr in (("C", fC), ("D", fD)):
        g = np.array([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in fr]).astype(np.float32)
        d = np.abs(np.diff(g, axis=0)).mean((1, 2))
        met[tag] = dict(frame_diff_min=round(float(d.min()), 3), frame_diff_max=round(float(d.max()), 3),
                        frozen_frames=int((d < 0.05).sum()),
                        saturation=round(float(np.mean([cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 1].mean() / 255 for f in fr[::10]])), 3),
                        luma=round(float(g.mean()), 1))
    json.dump(met, open(os.path.join(OUT, "AB_D_metrics.json"), "w"), indent=1)
    # ---------------- frame-by-frame strip: gate region every 0.5 s
    strip = []
    for t in np.arange(0.0, dur, 0.5):
        f = fD[int(t * fps)][520:1160, 120:600].copy()
        cv2.putText(f, f"{t:.1f}s", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        strip.append(cv2.resize(f, (240, 320)))
    rows = [np.hstack(strip[i:i + 8]) for i in range(0, len(strip), 8)]
    cv2.imwrite(os.path.join(OUT, "AB_D_FrameStrip.png"), np.vstack(rows))
    print(json.dumps(met, indent=1))


if __name__ == "__main__":
    main()

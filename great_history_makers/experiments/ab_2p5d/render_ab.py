#!/usr/bin/env python3
"""Render the A/B style comparison: A = current flat shot (ep01c v3 entry), B = 2.5D rebuild.
Both: 720x1280 (or --final 1080x1920), 30 fps, 5.0 s, same grade family, same audio
excerpt (V3 mix 19.6-24.6 s), no captions. Also writes a labelled side-by-side clip and
a still comparison sheet."""
import importlib.util
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from mosaic.scene import Ctx  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def encode(frames_iter, W, H, fps, out, audio, a_ss, dur):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", "-ss", str(a_ss), "-t", str(dur), "-i", audio, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "animation", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-af", "afade=t=in:d=0.2,afade=t=out:st=%.2f:d=0.3" % (dur - 0.3),
           "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames_iter:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def main():
    final = "--final" in sys.argv
    W, H = (1080, 1920) if final else (720, 1280)
    fps, dur = 30, 5.0
    ctx = Ctx(W, H, fps)
    out = os.path.join(ROOT, "output", "experiments", "ab_2p5d")
    os.makedirs(out, exist_ok=True)
    ep = load(os.path.join(ROOT, "episodes", "ep01c_cyrus_v3", "scenes.py"), "ep01c")
    B = load(os.path.join(ROOT, "experiments", "ab_2p5d", "scene_b.py"), "scene_b")
    names = [s.__name__ for s in ep.SHOTS]
    scA = ep.SHOTS[names.index("v3_entry")](ctx, dur)
    scB = B.build(ctx, dur)
    audio = os.path.join(ROOT, "output", "ep01c_cyrus_v3", "deliverables", "Cyrus_Babylon_V3_Final_1080x1920.mp4")
    n = int(dur * fps)
    frames = {}
    for tag, sc in (("A", scA), ("B", scB)):
        fr = []
        for i in range(n):
            f = sc.render(ctx, i / fps)
            fr.append(cv2.cvtColor((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
        frames[tag] = fr
        encode(iter(fr), W, H, fps, os.path.join(out, f"AB_{tag}_{W}x{H}.mp4"), audio, 19.6, dur)
        print("wrote", tag)
    # side by side with labels
    def sbs():
        for a, b in zip(frames["A"], frames["B"]):
            img = np.hstack([a, np.zeros((H, 8, 3), np.uint8), b])
            for x0, txt in ((0, "A  current (flat)"), (W + 8, "B  2.5D mosaic")):
                cv2.rectangle(img, (x0 + 16, 16), (x0 + 16 + int(W * 0.48), 16 + int(H * 0.04)), (20, 14, 10), -1)
                cv2.putText(img, txt, (x0 + 28, 16 + int(H * 0.03)), cv2.FONT_HERSHEY_DUPLEX, W / 900, (230, 240, 250),
                            1, cv2.LINE_AA)
            yield img
    encode(sbs(), 2 * W + 8, H, fps, os.path.join(out, f"AB_side_by_side_{W}x{H}.mp4"), audio, 19.6, dur)
    rows = []
    for t in (0.5, 2.5, 4.5):
        i = int(t * fps)
        rows.append(np.hstack([cv2.resize(frames["A"][i], (W // 2, H // 2)), cv2.resize(frames["B"][i], (W // 2, H // 2))]))
    cv2.imwrite(os.path.join(out, "AB_stills.png"), np.vstack(rows))
    print("done")


if __name__ == "__main__":
    main()

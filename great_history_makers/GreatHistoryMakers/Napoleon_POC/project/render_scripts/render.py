#!/usr/bin/env python3
"""Render the Napoleon 2D animation POC (no narration).

  python render.py --preview            # 540x960 low-res preview
  python render.py                      # 1080x1920 final -> ../../final/Napoleon_2D_Animation_POC.mp4
  python render.py --still 2.6          # one PNG frame
Windows: identical; uses h264_nvenc automatically if FFmpeg has it, else libx264.
"""
import argparse
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "animation_source")
sys.path.insert(0, SRC)
import scenes  # noqa: E402
from anim import ease  # noqa: E402
from gfx import to_numpy  # noqa: E402

FPS, DUR = 30, 12.0
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def draw_scene(W, H, t):
    s = W / 1080.0
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color(0, 0, 0))
    c.save()
    if t < 4.0:
        z, (fx, fy) = scenes.cam1(t)
        c.translate(W / 2, H / 2)
        c.scale(z * s, z * s)
        c.translate(-fx, -fy)
        scenes.scene1(c, t)
    elif t < 8.0:
        z, (fx, fy) = scenes.cam2(t)
        c.translate(W / 2, H / 2)
        c.scale(z * s, z * s)
        c.translate(-fx, -fy)
        scenes.scene2(c, t)
    else:
        z, (fx, fy), dx = scenes.cam3(t)
        c.translate(W / 2, H / 2)
        c.scale(z * s, z * s)
        c.translate(-fx, -fy)
        scenes.scene3(c, t, dx)
    c.restore()
    return to_numpy(surf).astype(np.float32) / 255.0


_VIG = {}


def finish(f):
    H, W = f.shape[:2]
    if (W, H) not in _VIG:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.hypot((xx - W / 2) / (W / 2), (yy - H * 0.48) / (H / 2))
        _VIG[(W, H)] = (1 - 0.28 * np.clip(d - 0.45, 0, 1) ** 1.5)[..., None]
    return f * _VIG[(W, H)]


def frame(W, H, t):
    # whip-pan 7.85-8.15 s in the pointing direction (motivated by the gesture)
    if 7.85 <= t < 8.15:
        u = ease((t - 7.85) / 0.3, "io")
        a = draw_scene(W, H, min(t, 7.999))
        b = draw_scene(W, H, max(t, 8.0))
        sh = int(W * u)
        img = np.concatenate([a[:, sh:], b[:, :sh]], axis=1) if sh else a
        k = max(1, int(W * 0.18 * math.sin(math.pi * u)))
        import cv2
        img = cv2.blur(img, (k, 1))
    else:
        img = draw_scene(W, H, t)
    return finish(img)


def _work(args):
    W, H, i = args
    return (np.clip(frame(W, H, i / FPS), 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()


def encoder():
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1", "-c:v",
                            "h264_nvenc", "-f", "null", "-"], capture_output=True, timeout=20)
        if r.returncode == 0:
            return ["-c:v", "h264_nvenc", "-preset", "p7", "-cq", "18", "-b:v", "0", "-profile:v", "high"]
    except Exception:
        pass
    return ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-tune", "animation"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--still", type=float)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    W, H = (540, 960) if a.preview else (1080, 1920)
    if a.still is not None:
        import cv2
        out = os.path.join(ROOT, "project", "previews")
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, f"still_{a.still:05.2f}_{W}.png")
        cv2.imwrite(p, cv2.cvtColor((np.clip(frame(W, H, a.still), 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(p)
        return
    out = os.path.join(ROOT, "final", "Napoleon_2D_Animation_POC.mp4") if not a.preview else \
        os.path.join(ROOT, "project", "previews", "Napoleon_POC_preview_540x960.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = int(round(DUR * FPS))
    t0 = time.time()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
                           str(FPS), "-i", "-"] + encoder() + ["-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    with mp.get_context("spawn" if os.name == "nt" else "fork").Pool(a.workers) as pool:
        for k, buf in enumerate(pool.imap(_work, [(W, H, i) for i in range(n)], chunksize=3)):
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"frame {k}/{n}  {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"wrote {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

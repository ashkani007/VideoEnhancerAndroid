#!/usr/bin/env python3
"""Render the Cinematic Living Illustration proof of concept (two connected shots).

  python -m ghm3.render_poc                 # 540x960 preview
  python -m ghm3.render_poc --final         # 1080x1920
"""
import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mosaic import audio, captions, qc, text  # noqa: E402
from mosaic.render import encoder_args, mux, pick_encoder  # noqa: E402
from mosaic.scene import Ctx  # noqa: E402

from ghm2.anim import smooth  # noqa: E402
from ghm3.paint import fbm  # noqa: E402
from ghm3.shots import shot_a, shot_b  # noqa: E402

EP = os.path.join(ROOT, "ghm3", "poc_napoleon")
CFG = json.load(open(os.path.join(EP, "poc.json")))
_W = _H = None
_CAPS = []


def _init(W, H):
    global _W, _H, _CAPS
    _W, _H = W, H
    cc = CFG["captions"]
    cues = captions.build_groups(cc["groups"], os.path.join(EP, cc["transcript"]), os.path.join(EP, cc["words"]))
    _CAPS = [text.caption(Ctx(W, H, 30), c["text"], c["start"], c["end"], y=cc["y"], size=cc["size"]) for c in cues]


def frame(t):
    tr = CFG["transitions"][0]
    a0, a1 = tr["at"] - tr["dur"] / 2, tr["at"] + tr["dur"] / 2
    if t < a0:
        f = shot_a(_W, _H, t)
    elif t > a1:
        f = shot_b(_W, _H, t)
    else:                                    # dissolve through drifting smoke: noise-keyed reveal
        A, B = shot_a(_W, _H, t), shot_b(_W, _H, t)
        u = smooth((t - a0) / (a1 - a0))
        n = fbm(_H, _W, _W / 1080, 77)
        n = (n - n.min()) / (np.ptp(n) + 1e-6)
        k = np.clip((u * 1.4 - n * 0.4 - 0.2) / 0.25, 0, 1)[..., None]
        haze = np.sin(np.pi * u) * 0.25
        f = A * (1 - k) + B * k
        f = f * (1 - haze) + np.array([0.55, 0.48, 0.44]) * haze
    f = f.astype(np.float32)
    for c in _CAPS:
        c.apply(f, t)
    return f


def _work(i):
    return (np.clip(frame(i / CFG["fps"]), 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    W, H = (1080, 1920) if a.final else (540, 960)
    out = os.path.join(ROOT, "output", "v3", "poc_napoleon")
    os.makedirs(out, exist_ok=True)
    q = "final" if a.final else "preview"
    tag = f"ghm3_poc_{q}_{W}x{H}"
    t0 = time.time()
    wav = os.path.join(out, "ghm3_poc_mix.wav")
    audio.build_mix(EP, CFG, wav)
    enc = pick_encoder(True)
    silent = os.path.join(out, tag + "_video.mp4")
    n = int(round(CFG["duration"] * CFG["fps"]))
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
                           str(CFG["fps"]), "-i", "-"] + encoder_args(enc, q) + ["-pix_fmt", "yuv420p", silent],
                          stdin=subprocess.PIPE)
    with mp.get_context("fork").Pool(a.workers, _init, (W, H)) as pool:
        for k, buf in enumerate(pool.imap(_work, range(n), chunksize=2)):
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"[v3] frame {k}/{n} {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    final = os.path.join(out, tag + ".mp4")
    mux(silent, wav, final, CFG["audio"]["loudness_lufs"])
    os.remove(silent)
    cc = CFG["captions"]
    text.write_srt(captions.build_groups(cc["groups"], os.path.join(EP, cc["transcript"]), os.path.join(EP, cc["words"])),
                   os.path.join(out, "ghm3_poc.en.srt"))
    rep = qc.run(final, CFG, os.path.join(out, tag), W, H)
    rep.update(encoder=enc, render_seconds=round(time.time() - t0))
    json.dump(rep, open(os.path.join(out, tag + "_qc.json"), "w"), indent=2)
    print(json.dumps(rep["checks"]))
    print("[qc] PASSED" if rep["passed"] else "[qc] ISSUES FOUND", final, f"({rep['render_seconds']}s)")


if __name__ == "__main__":
    main()

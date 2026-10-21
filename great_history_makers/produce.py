#!/usr/bin/env python3
"""Great History Makers - one-command episode production.

  python produce.py episodes/ep01_cyrus_babylon                     # 720p preview
  python produce.py episodes/ep01_cyrus_babylon --quality final     # 1080x1920 master
  python produce.py episodes/ep01_cyrus_babylon --still 12.5        # single frame PNG
  python produce.py episodes/ep01_cyrus_babylon --frames 0 120      # partial render test

Steps: scene build (tessellation cached) -> audio mix -> parallel frame render ->
FFmpeg encode -> mux + loudness normalisation -> SRT -> automatic QC report.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mosaic import audio, qc, render, text  # noqa: E402
from mosaic.episode import load_config, make_ctx  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--quality", choices=["draft", "preview", "final"], default="preview")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--frames", type=int, nargs=2, default=None)
    ap.add_argument("--still", type=float, default=None)
    ap.add_argument("--no-burn-subs", action="store_true")
    ap.add_argument("--cpu-encode", action="store_true", help="skip NVENC probe")
    ap.add_argument("--out", default=None)
    ap.add_argument("--scene", type=int, default=None, help="render one scene (1-based) as a standalone clip")
    a = ap.parse_args()

    ep = os.path.abspath(a.episode)
    cfg = load_config(ep)
    name = os.path.basename(ep.rstrip("/\\"))
    out_dir = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", name)
    os.makedirs(out_dir, exist_ok=True)

    if a.still is not None:
        p = os.path.join(out_dir, f"still_{a.still:05.2f}.png")
        render.still(ep, a.still, p, a.quality)
        print(p)
        return

    ctx = make_ctx(cfg, a.quality)
    tag = f"{name}_{a.quality}_{ctx.W}x{ctx.H}"
    solo, trim = None, None
    if a.scene is not None:
        solo = a.scene - 1
        sc = cfg["scenes"][solo]
        a.frames = (int(round(sc["start"] * ctx.fps)), int(round((sc["start"] + sc["duration"]) * ctx.fps)))
        trim = (sc["start"], sc["duration"])
        tag = f"{name}_scene{a.scene}_{a.quality}_{ctx.W}x{ctx.H}"
    t0 = time.time()
    wav = os.path.join(out_dir, f"{name}_mix.wav")
    voice = audio.build_mix(ep, cfg, wav)
    print(f"[audio] mix written ({'with narration' if voice else 'NO narration file - music & SFX only'})")
    silent = os.path.join(out_dir, f"{tag}_video.mp4")
    enc = render.render_video(ep, silent, a.quality, a.workers, a.frames, not a.no_burn_subs,
                              prefer_gpu=not a.cpu_encode, solo=solo)
    final = os.path.join(out_dir, f"{tag}.mp4")
    render.mux(silent, wav, final, cfg.get("audio", {}).get("loudness_lufs", -15), trim)
    os.remove(silent)
    cues = cfg.get("subtitles", [])
    if cfg.get("captions"):
        from mosaic import captions
        cc = cfg["captions"]
        cues = captions.build_groups(cc["groups"], os.path.join(ep, cc["transcript"]), os.path.join(ep, cc["words"]))
    text.write_srt(cues, os.path.join(out_dir, f"{name}.en.srt"))
    if a.frames is None:
        rep = qc.run(final, cfg, os.path.join(out_dir, tag), ctx.W, ctx.H)
        rep.update(encoder=enc, narration=voice, render_seconds=round(time.time() - t0))
        with open(os.path.join(out_dir, f"{tag}_qc.json"), "w") as f:
            json.dump(rep, f, indent=2)
        print(json.dumps(rep["checks"], indent=1))
        print("[qc] PASSED" if rep["passed"] else "[qc] ISSUES FOUND - see report")
    print(f"[done] {final}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

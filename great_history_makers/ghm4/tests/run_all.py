#!/usr/bin/env python3
"""ghm4 regression suite.

  python -m ghm4.tests.run_all                 # everything (about 4-6 min on 4 CPUs; first run downloads the matte model)
  python -m ghm4.tests.run_all --quick         # skip the matte model and the worker test
  python -m ghm4.tests.run_all --update-golden # re-bless the golden frames after an approved visual change

Tests
  golden        approved POC port + renderer demo: key frames must match the blessed frames (PSNR >= 40 dB)
  plate_sizes   SDXL-native, hires, 2x-upscaled, landscape and very tall plates: cover fit, no border, timing
  robustness    metadata regions outside the plate, missing matte, eyes outside the frame
  transitions   whip / ink / flash / dissolve / cut: no NaN, only intended jumps, both shots visible mid-wipe
  narrate       retime to aligned words, caption-band collision check, excerpt duration
  masks         region-scored automatic mattes (ghm4/tests/test_masks.py)
  worker        ComfyUI worker plumbing (comfyui/worker/test_worker.py)
  episode       automated episode pipeline end to end with stand-in results (ghm4/tests/test_episode.py)
Writes ghm4/tests/out/test_report.json.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import traceback

import cv2
import numpy as np

from ghm4.render import Renderer

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
GOLD = os.path.join(HERE, "golden")
PORT = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_20s_POC", "ghm4_port", "storyboard.json")
DEMO = os.path.join(GHM, "GreatHistoryMakers", "Renderer_Demo", "storyboard.timed.json")
MASTER = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source", "napoleon_master.png")
MASTER_META = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source", "napoleon_master.json")
GOLDEN_TIMES = {"port": [1.5, 4.3, 7.49, 9.0, 12.6, 15.1, 17.0], "demo": [2.0, 7.55, 10.25, 12.5, 14.6, 16.6]}


def psnr(a, b):
    mse = np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2)
    return 99.0 if mse < 1e-6 else 10 * math.log10(255 ** 2 / mse)


def small(img):
    return cv2.resize((np.clip(img, 0, 1) * 255).astype(np.uint8), (240, 427), interpolation=cv2.INTER_AREA)


def test_golden(update):
    res = {}
    for name, sb in (("port", PORT), ("demo", DEMO)):
        R = Renderer(sb, 720, 1280)
        for t in GOLDEN_TIMES[name]:
            im = small(R.frame(t))
            p = os.path.join(GOLD, f"{name}_{t:.2f}.png")
            if update or not os.path.exists(p):
                cv2.imwrite(p, cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
                res[f"{name}@{t}"] = "blessed"
                continue
            g = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
            v = psnr(im, g)
            res[f"{name}@{t}"] = round(v, 1)
            assert v >= 40, f"{name} frame {t}s differs from golden (PSNR {v:.1f} dB)"
    return res


def plate_storyboard(d, plate, meta=None, zooms=(1.0, 1.3), dur=2.0):
    sb = {"id": "t", "duration": dur, "fade_out": 0.05, "grain": 0.0,
          "shots": [{"type": "plate", "start": 0, "end": dur, "plate": plate, **({"meta": meta} if meta else {}),
                     "camera": {"from": {"zoom": zooms[0]}, "to": {"zoom": zooms[1]}}}]}
    p = os.path.join(d, "sb.json")
    json.dump(sb, open(p, "w"))
    return p


def test_plate_sizes():
    src = cv2.imread(MASTER)
    res = {}
    with tempfile.TemporaryDirectory() as d:
        for name, (w, h) in {"sdxl_native_768x1344": (768, 1344), "hires_1152x2016": (1152, 2016), "upscaled_2304x4032": (2304, 4032),
                             "landscape_1920x1080": (1920, 1080), "very_tall_600x1600": (600, 1600)}.items():
            img = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA if w < 941 else cv2.INTER_LANCZOS4)
            cv2.imwrite(os.path.join(d, name + ".png"), img)
            R = Renderer(plate_storyboard(d, name + ".png"), 1080, 1920)
            R.frame(0.0)                                                # load + cache
            t0 = time.time()
            frames = [R.frame(t) for t in (0.0, 1.0, 1.9)]
            dt = (time.time() - t0) / 3
            for f in frames:
                assert np.isfinite(f).all() and f.shape == (1920, 1080, 3)
                # cover fit: every edge row/column carries picture, not a reflected seam or a flat border
                for edge in (f[0], f[-1], f[:, 0], f[:, -1]):
                    assert edge.std() > 0.01, f"{name}: flat border"
            P = R.plate_for(R.shots[0])
            res[name] = dict(work_size=[P.W, P.H], seconds_per_1080p_frame=round(dt, 2))
            if w >= 2304:
                assert P.W < w, "large plates must be rendered at the needed working resolution"
    return res


def test_robustness():
    meta = json.load(open(MASTER_META))
    with tempfile.TemporaryDirectory() as d:
        crop = cv2.imread(MASTER)[900:1500, 600:941]                   # 341 px wide: the eye (x 425-455) and most regions fall outside
        cv2.imwrite(os.path.join(d, "c.png"), crop)
        m = {k: v for k, v in meta.items() if k not in ("mask", "background")}
        m["ref_width"] = crop.shape[1]                                   # coordinates are crop pixels
        m["mask"] = "missing_mask.png"                                   # missing file must not crash: ignored -> one layer
        json.dump(m, open(os.path.join(d, "c.json"), "w"))
        try:
            R = Renderer(plate_storyboard(d, "c.png", "c.json"), 720, 1280)
            R.frame(0.5)
            missing_ok = "ignored"
        except Exception as e:                                           # noqa: BLE001
            missing_ok = f"crash: {e}"
        m.pop("mask")
        json.dump(m, open(os.path.join(d, "c.json"), "w"))
        R = Renderer(plate_storyboard(d, "c.png", "c.json"), 720, 1280)
        f = R.frame(0.5)
        assert np.isfinite(f).all()
        P = R.plate_for(R.shots[0])
        res = dict(flags_kept=len(P.flags), eyes_kept=len(P.eyes), winds_kept=len(P.winds), missing_mask=missing_ok)
        assert len(P.eyes) == 0, "eyes outside the plate must be skipped"
        assert missing_ok == "ignored", missing_ok
    return res


def test_transitions():
    res = {}
    with tempfile.TemporaryDirectory() as d:
        src = cv2.imread(MASTER)
        cv2.imwrite(os.path.join(d, "a.png"), src)
        cv2.imwrite(os.path.join(d, "b.png"), cv2.flip(src, 1)[:, :, ::-1])   # visibly different second plate
        for kind in ("whip", "ink", "flash", "dissolve", "cut"):
            sb = {"id": "t", "duration": 3.0, "fade_out": 0.1, "grain": 0.0,
                  "shots": [{"type": "plate", "start": 0, "end": 1.5, "plate": "a.png", "camera": {"from": {"zoom": 1.1}, "to": {"zoom": 1.2}}},
                            {"type": "plate", "start": 1.5, "end": 3.0, "plate": "b.png", "camera": {"from": {"zoom": 1.1}, "to": {"zoom": 1.2}}}],
                  "transitions": [{"at": 1.5, "type": kind}]}
            p = os.path.join(d, f"{kind}.json")
            json.dump(sb, open(p, "w"))
            R = Renderer(p, 360, 640)
            fr = [R.frame(i / 30) for i in range(30, 61)]
            assert all(np.isfinite(f).all() for f in fr)
            diffs = [float(np.abs(fr[i + 1] - fr[i]).mean()) for i in range(len(fr) - 1)]
            big = [round(1.0 + (i + 1) / 30, 3) for i, v in enumerate(diffs) if v > 0.06]    # time of each large change
            res[kind] = dict(max_step=round(max(diffs), 3), large_changes_at=big)
            window = {"whip": (1.2, 1.86), "ink": (1.24, 1.76), "flash": (1.09, 1.91), "dissolve": (1.19, 1.81), "cut": (1.49, 1.51)}[kind]
            outside = [t for t in big if not window[0] <= t <= window[1]]
            assert not outside, f"{kind}: large frame changes outside the transition window at {outside}"
            if kind == "cut":
                assert len(big) == 1, f"cut should change hard exactly once, got {big}"
            if kind == "ink":                                            # mid-wipe frame contains both plates
                mid = R.frame(1.5)
                a, b = R.render_shot(R.shots[0], 1.5), R.render_shot(R.shots[1], 1.5)
                near_a = (np.abs(mid - a).mean(-1) < 0.05).mean()
                near_b = (np.abs(mid - b).mean(-1) < 0.05).mean()
                res[kind].update(share_a=round(float(near_a), 2), share_b=round(float(near_b), 2))
                assert near_a > 0.15 and near_b > 0.15, "ink wipe should show both shots"
    return res


def test_narrate():
    from ghm4 import narrate
    sb, d = narrate.load(os.path.join(GHM, "GreatHistoryMakers", "Renderer_Demo", "storyboard.json"))
    with tempfile.TemporaryDirectory() as tmp:
        import shutil
        p = os.path.join(os.path.dirname(DEMO), "_t_storyboard.json")
        json.dump(sb, open(p, "w"))
        try:
            subprocess.run([sys.executable, "-m", "ghm4.narrate", p, "retime"], cwd=GHM, check=True, capture_output=True)
            timed = json.load(open(p.replace(".json", ".timed.json")))
        finally:
            for f in (p, p.replace(".json", ".timed.json")):
                if os.path.exists(f):
                    os.remove(f)
        del shutil
    starts = [s["start"] for s in timed["shots"]]
    assert starts == [0.0, 4.95, 10.25, 15.74], starts
    assert timed["duration"] == 18.2
    cues = narrate.cues_for(sb, d)
    demo_conf = narrate.text_conflicts(timed, [c for c in cues if c["start"] < 18.2])
    port, pd = narrate.load(PORT)
    port = dict(port, captions=sb["captions"])
    port_conf = narrate.text_conflicts(port, cues)
    assert not demo_conf, demo_conf
    assert port_conf, "the POC titles sit in the caption band and must be reported"
    return dict(shot_starts=starts, demo_conflicts=0, port_conflicts_detected=len(port_conf))


def run_script(args):
    t = time.time()
    r = subprocess.run([sys.executable, *args], cwd=GHM, capture_output=True, text=True)
    tail = [ln for ln in r.stdout.strip().splitlines() if "Warning" not in ln][-12:]
    assert r.returncode == 0, "\n".join(tail) + r.stderr[-800:]
    return dict(seconds=round(time.time() - t, 1), output=tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--update-golden", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(GOLD, exist_ok=True)
    tests = [("golden", lambda: test_golden(a.update_golden)), ("plate_sizes", test_plate_sizes), ("robustness", test_robustness),
             ("transitions", test_transitions), ("narrate", test_narrate)]
    if not a.quick:
        tests += [("masks", lambda: run_script(["-m", "ghm4.tests.test_masks", "--methods", "hybrid"])),
                  ("worker", lambda: run_script(["comfyui/worker/test_worker.py"])),
                  ("episode", lambda: run_script(["-m", "ghm4.tests.test_episode"]))]
    report, failed = {}, 0
    for name, fn in tests:
        t = time.time()
        try:
            detail = fn()
            report[name] = dict(passed=True, seconds=round(time.time() - t, 1), detail=detail)
            print(f"PASS {name:12s} {time.time() - t:6.1f}s", flush=True)
        except Exception as e:                                           # noqa: BLE001
            failed += 1
            report[name] = dict(passed=False, seconds=round(time.time() - t, 1), error=str(e)[:2000], trace=traceback.format_exc()[-1500:])
            print(f"FAIL {name:12s} {time.time() - t:6.1f}s  {str(e)[:300]}", flush=True)
    json.dump(report, open(os.path.join(OUT, "test_report.json"), "w"), indent=1)
    print(f"{len(tests) - failed}/{len(tests)} passed -> ghm4/tests/out/test_report.json")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

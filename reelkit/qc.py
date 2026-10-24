"""Automated quality control on a rendered Short."""

from __future__ import annotations

import re
from pathlib import Path

from .util import ffprobe, run


def loudness(path: Path) -> dict:
    err = run(["ffmpeg", "-v", "info", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
               "-f", "null", "-"]).stderr
    tail = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return {"integrated_lufs": float(i.group(1)) if i else None,
            "true_peak_dbfs": float(tp.group(1)) if tp else None}


def black_frames(path: Path) -> list[tuple[float, float]]:
    err = run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "blackdetect=d=0.25:pix_th=0.08",
               "-an", "-f", "null", "-"]).stderr
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]


def run_qc(out: Path, story: dict, lines: list[dict], timeline: list[dict], analysis: dict,
           render_info: dict, profile: str, min_final_height: int) -> dict:
    info = ffprobe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    checks = []

    def check(name, ok, detail, level="fail"):
        checks.append({"check": name, "status": "pass" if ok else level, "detail": detail})

    check("duration 45-60 s", 45 <= dur <= 60.5, f"{dur:.2f} s")
    check("resolution", (int(v["width"]), int(v["height"])) == (render_info["width"], render_info["height"]),
          f"{v['width']}x{v['height']}")
    hook_end = lines[0]["end"]
    check("hook line lands inside 3 s", hook_end <= 3.0, f"first line ends at {hook_end:.2f} s")
    for b in story["beats"]:
        ls = [ln for ln in lines if ln["beat"] == b["name"]]
        if ls:
            s, e = ls[0]["start"], ls[-1]["end"]
            ok = s >= b["target"][0] - 2.5 and e <= b["target"][1] + 2.5
            check(f"beat '{b['name']}' timing", ok,
                  f"{s:.1f}-{e:.1f} s (target {b['target'][0]}-{b['target'][1]} s)", "warn")
    words = sum(len(ln["text"].split()) for ln in lines)
    speech = sum(ln["end"] - ln["start"] for ln in lines)
    wps = words / speech
    check("narration pace 2.2-3.3 words/s", 2.2 <= wps <= 3.3, f"{words} words, {wps:.2f} words/s", "warn")
    durs = [s["dur"] for s in timeline]
    check("shot lengths", min(durs) >= 0.35 and max(durs) <= 4.5,
          f"{len(durs)} cuts, min {min(durs):.2f} s, max {max(durs):.2f} s, mean {sum(durs)/len(durs):.2f} s", "warn")
    over = [s["shot"] for s in timeline if s["overruns_shot"]]
    check("no clip runs past its source cut", not over, f"overruns: {over}" if over else "none", "warn")
    ranges = sorted((s["src_in"], s["src_out"]) for s in timeline)
    dup = [(a, b) for (a, b), (c, d) in zip(ranges, ranges[1:]) if c < b - 0.05]
    check("no repeated footage", not dup, f"overlapping ranges: {dup}" if dup else "none", "warn")
    blacks = black_frames(out)
    check("no black gaps", not blacks, f"{blacks}" if blacks else "none", "warn")
    lo = loudness(out)
    ok = lo["integrated_lufs"] is not None and abs(lo["integrated_lufs"] + 14) <= 1.5
    check("loudness ~ -14 LUFS", ok, f"{lo}", "warn")
    up = render_info["height"] * 1.0 / analysis["height"]
    fg_up = render_info["width"] / min(analysis["width"], analysis["height"])
    check("source resolution", profile == "preview" or analysis["height"] >= min_final_height,
          f"source {analysis['width']}x{analysis['height']}, foreground upscale x{fg_up:.2f}",
          "warn" if profile == "preview" else "fail")
    lic = story["source"].get("license", "")
    check("licence + credit recorded", bool(lic and story["source"].get("credit")), f"{lic}")
    status = "fail" if any(c["status"] == "fail" for c in checks) else (
        "warn" if any(c["status"] == "warn" for c in checks) else "pass")
    return {"status": status, "duration": dur, "checks": checks, "encoder": render_info["encoder"]}

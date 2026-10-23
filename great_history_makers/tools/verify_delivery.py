#!/usr/bin/env python3
"""Verify a branded delivery: narration audible and in sync, burned captions on the aligned
cues, the original Great History Makers logo present (watermark + end card).

  python tools/verify_delivery.py video.mp4 episodes/<id> [--report out.json]

Exit code 0 only when every check passes. All measurements are objective (no eyeballing):
- narration: cross-correlation of the delivered audio with the source take (lag and r), and the
  RMS level of the delivered track while words are spoken
- captions: SRT cues rebuilt from words_aligned.json; for each cue the caption band must contain
  ivory text pixels with a dark outline at the cue midpoint, and much less in pauses between cues
- logo: masked normalised correlation of the frame against the original logo PNG at the
  watermark position (and against nearby off-positions as a baseline), and at the end card
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mosaic import captions  # noqa: E402

LOGO = os.path.join(ROOT, "assets", "brand", "Great_History_Makers_Logo_Transparent.png")
IVORY = np.array([242, 230, 200], np.float32)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels:format=duration",
                          "-of", "json", path], capture_output=True, text=True).stdout
    return json.loads(out)


def pcm(path, sr=8000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def frame(path, t, W, H):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3)


def check_narration(video, narr, words):
    sr = 8000
    v, m = pcm(narr, sr), pcm(video, sr)
    n = min(len(v), len(m)) - 2 * sr
    best = (-1.0, 0)
    for lag in range(-sr // 2, sr // 2 + 1, 4):            # +-0.5 s search
        a = m[max(0, lag):max(0, lag) + n]
        b = v[max(0, -lag):max(0, -lag) + n]
        r = float(np.corrcoef(a, b)[0, 1])
        if r > best[0]:
            best = (r, lag)
    speech = np.zeros(len(m), bool)
    for w in words:
        speech[int(w["start"] * sr):int(w["end"] * sr)] = True
    rms = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)  # noqa: E731
    res = dict(corr=round(best[0], 3), offset_ms=round(best[1] / sr * 1000, 1),
               speech_rms_dbfs=round(float(rms(m[speech[:len(m)]])), 1),
               pause_rms_dbfs=round(float(rms(m[~speech[:len(m)]])), 1))
    res["ok"] = res["corr"] > 0.8 and abs(res["offset_ms"]) <= 20 and res["speech_rms_dbfs"] > -30
    return res


def caption_score(img, H, W):
    """Fraction of band pixels that are ivory text sitting next to a dark outline."""
    y0, y1 = int(H * 1300 / 1920), int(H * 1530 / 1920)
    band = img[y0:y1, int(W * 0.06):int(W * 0.94)].astype(np.float32)
    ivory = np.linalg.norm(band - IVORY, axis=2) < 38
    dark = band.mean(2) < 55
    near_dark = cv2.dilate(dark.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return float((ivory & near_dark).mean())


def check_captions(video, cues, W, H, dur):
    rows, hits = [], 0
    gaps = []
    for i, c in enumerate(cues):
        mid = (c["start"] + c["end"]) / 2
        s = caption_score(frame(video, mid, W, H), H, W)
        hits += s > 0.004
        rows.append(dict(start=c["start"], end=c["end"], score=round(s, 4)))
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else dur
        if nxt - c["end"] >= 0.25:
            gaps.append(round(caption_score(frame(video, (c["end"] + nxt) / 2, W, H), H, W), 4))
    on = float(np.median([r["score"] for r in rows]))
    off = float(np.median(gaps)) if gaps else 0.0
    res = dict(cues=len(cues), cues_with_text=hits, median_on=round(on, 4), median_in_pauses=round(off, 4),
               pauses_checked=len(gaps))
    res["ok"] = hits == len(cues) and on > 4 * max(off, 1e-4)
    return res, rows


def masked_ncc(patch, tmpl, mask):
    p, t = patch[mask], tmpl[mask]
    p, t = p - p.mean(), t - t.mean()
    return float((p * t).sum() / (np.sqrt((p * p).sum() * (t * t).sum()) + 1e-9))


def logo_gray(width):
    logo = cv2.imread(LOGO, cv2.IMREAD_UNCHANGED)
    h = int(round(logo.shape[0] * width / logo.shape[1]))
    L = cv2.resize(logo, (width, h), interpolation=cv2.INTER_AREA).astype(np.float32)
    return cv2.cvtColor(L[..., :3], cv2.COLOR_BGR2GRAY), L[..., 3] > 200


def check_logo(video, W, H, dur):
    sc = W / 1080
    wm_w, x, y = int(round(155 * sc)), int(round(55 * sc)), int(round(100 * sc))
    g, m = logo_gray(wm_w)
    scores, base = [], []
    for t in np.linspace(1.0, dur - 4.0, 6):
        f = cv2.cvtColor(frame(video, t, W, H), cv2.COLOR_RGB2GRAY).astype(np.float32)
        scores.append(masked_ncc(f[y:y + g.shape[0], x:x + g.shape[1]], g, m))
        for dx, dy in ((W // 2, 0), (0, H // 3)):
            base.append(masked_ncc(f[y + dy:y + dy + g.shape[0], x + dx:x + dx + g.shape[1]], g, m))
    f = cv2.cvtColor(frame(video, dur - 0.3, W, H), cv2.COLOR_RGB2GRAY).astype(np.float32)
    end_best = -1.0
    for s in (0.97, 0.98, 0.99, 1.0):
        ew = int(round(760 * sc * s / 2) * 2)
        ge, me = logo_gray(ew)
        cy = int(round(840 * sc))
        x0, y0 = (W - ge.shape[1]) // 2, cy - ge.shape[0] // 2
        end_best = max(end_best, masked_ncc(f[y0:y0 + ge.shape[0], x0:x0 + ge.shape[1]], ge, me))
    res = dict(watermark_ncc_min=round(min(scores), 3), watermark_ncc_mean=round(float(np.mean(scores)), 3),
               offposition_ncc_max=round(max(base), 3), endcard_ncc=round(end_best, 3))
    res["ok"] = res["watermark_ncc_min"] > 0.5 and res["watermark_ncc_min"] > res["offposition_ncc_max"] + 0.2 \
        and res["endcard_ncc"] > 0.8
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("episode")
    ap.add_argument("--report")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.episode, "episode.json"), encoding="utf-8"))
    cc = cfg["captions"]
    tr = open(os.path.join(a.episode, cc["transcript"]), encoding="utf-8").read().strip()
    wpath = os.path.join(a.episode, cc["words"])
    words = captions.map_words(tr, json.load(open(wpath)))
    cues = captions.build_groups(cc["groups"], os.path.join(a.episode, cc["transcript"]), wpath)
    p = probe(a.video)
    vs = [s for s in p["streams"] if s["codec_type"] == "video"][0]
    au = [s for s in p["streams"] if s["codec_type"] == "audio"]
    W, H, dur = vs["width"], vs["height"], float(p["format"]["duration"])
    rep = dict(file=os.path.abspath(a.video),
               container=dict(width=W, height=H, fps=vs["r_frame_rate"], video=vs["codec_name"],
                              audio=au[0]["codec_name"] if au else None,
                              sample_rate=au[0].get("sample_rate") if au else None, duration=round(dur, 2)))
    rep["container"]["ok"] = bool(au) and vs["codec_name"] == "h264" and vs["r_frame_rate"] == "30/1" and W * 16 == H * 9
    narr = os.path.join(a.episode, cfg["audio"]["narration_file"])
    rep["narration"] = check_narration(a.video, narr, words) if au else dict(ok=False, error="no audio stream")
    rep["captions"], rows = check_captions(a.video, cues, W, H, dur)
    first = []
    i = 0
    for g in cc["groups"]:
        first.append(words[i]["start"])
        i += len(g.replace("/", " ").split())
    rep["captions"]["cue_start_vs_first_word_max_ms"] = round(1000 * max(abs(c["start"] - f) for c, f in zip(cues, first)), 1)
    rep["captions"]["wording_matches_transcript"] = " ".join(c["text"].replace("\n", " ") for c in cues).split() == tr.split()
    rep["captions"]["ok"] = rep["captions"]["ok"] and rep["captions"]["wording_matches_transcript"] \
        and rep["captions"]["cue_start_vs_first_word_max_ms"] <= 10
    rep["logo"] = check_logo(a.video, W, H, dur)
    rep["passed"] = all(rep[k]["ok"] for k in ("container", "narration", "captions", "logo"))
    rep["caption_rows"] = rows
    print(json.dumps({k: v for k, v in rep.items() if k != "caption_rows"}, indent=1))
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=1)
    sys.exit(0 if rep["passed"] else 1)


if __name__ == "__main__":
    main()

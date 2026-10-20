"""Automatic quality control on the rendered file: format checks, contact sheet,
temporal stability (flicker / pops), black frames and loudness."""
import json
import re
import subprocess

import numpy as np

from .render import ffmpeg_bin


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def decode_small(path, w=135, h=240):
    cmd = [ffmpeg_bin(), "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def contact_sheet(path, out_png, times, cols=4, w=270):
    import cv2
    tiles = []
    h = int(w * 16 / 9)
    for t in times:
        cmd = [ffmpeg_bin(), "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:{h}",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        img = np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()
        cv2.putText(img, f"{t:.1f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(img)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(out_png, np.vstack(rows))


def loudness(path):
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return (float(m[-1]) if m else None), (float(p[-1]) if p else None)


def run(path, cfg, out_prefix, expect_w, expect_h):
    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    fps = eval(v["r_frame_rate"])
    dur = float(info["format"]["duration"])
    frames = decode_small(path)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    trans = [tr["at"] for tr in cfg.get("transitions", [])]
    # intentional changes (transitions, opening fade-in, closing fade) are not flicker
    def intentional(ts):
        return any(abs(ts - t) <= 0.6 for t in trans) or ts < 0.5 or ts > cfg["duration"] - 0.7
    steady = [i for i in range(len(diffs)) if not intentional((i + 1) / fps)]
    sd = diffs[steady] if steady else diffs
    med = float(np.median(sd))
    spikes = [round((i + 1) / fps, 2) for i in steady if diffs[i] > max(6.0, med * 5)]
    means = frames.mean(axis=(1, 2))
    black = [round(i / fps, 2) for i, m in enumerate(means) if m < 12 and i / fps > 0.5]
    lufs, peak = loudness(path) if a else (None, None)
    checks = {
        "resolution": (int(v["width"]), int(v["height"])) == (expect_w, expect_h),
        "codec_h264": v["codec_name"] == "h264",
        "pix_fmt_yuv420p": v.get("pix_fmt") == "yuv420p",
        "fps": abs(fps - cfg["fps"]) < 0.01,
        "duration": abs(dur - cfg["duration"]) < 0.15,
        "has_audio": bool(a),
        "no_flicker_spikes": not spikes,
        "no_black_frames": not black,
    }
    report = dict(file=path, width=v["width"], height=v["height"], fps=fps, duration=dur,
                  video_codec=v["codec_name"], audio_codec=a[0]["codec_name"] if a else None,
                  bitrate_kbps=round(int(info["format"].get("bit_rate", 0)) / 1000),
                  mean_frame_diff=round(med, 3), max_frame_diff=round(float(sd.max()), 3),
                  flicker_spikes_s=spikes, black_frames_s=black, loudness_lufs=lufs, true_peak_dbfs=peak,
                  checks=checks, passed=all(checks.values()))
    with open(out_prefix + "_qc.json", "w") as f:
        json.dump(report, f, indent=2)
    contact_sheet(path, out_prefix + "_contact.png", [0.6, 2.5, 4.6, 5.0, 6.5, 8.5, 10.0, 11.5, 13.0, 15.0,
                                                      16.5, 19.0])
    return report

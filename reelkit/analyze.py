"""Footage analysis: shot boundaries, per-shot visual features, saliency for
reframing, keyframes and labelled contact sheets for captioning.

Everything is computed from one low-resolution decode pass (no ML models) and
cached by the source file's sha256, so a film is analysed once no matter how
many Shorts are cut from it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .util import Cache, Config, ffprobe, run, sha256_file, write_json, read_json

AW = 192  # analysis width (px)


def _video_stream(info: dict) -> dict:
    return next(s for s in info["streams"] if s["codec_type"] == "video")


def _decode_gray(path: Path, w: int, h: int, fps: float):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}:flags=area",
           "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = w * h
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w)
    finally:
        proc.stdout.close()
        proc.wait()


def _frame_stats(path: Path, fps: float, aw: int, ah: int):
    hists, bright, motion, cols = [], [], [], []
    prev = None
    for g in _decode_gray(path, aw, ah, fps):
        f = g.astype(np.float32)
        hists.append(np.histogram(g, bins=32, range=(0, 256))[0] / g.size)
        bright.append(f.mean())
        if prev is None:
            m = np.zeros_like(f)
        else:
            m = np.abs(f - prev)
        motion.append(m.mean())
        gx = np.abs(np.diff(f, axis=1, prepend=f[:, :1]))
        gy = np.abs(np.diff(f, axis=0, prepend=f[:1, :]))
        # saliency proxy: edges + motion, weighted toward vertical centre band
        sal = (gx + gy) + 2.0 * m
        cols.append(sal.sum(axis=0))
        prev = f
    return np.array(hists), np.array(bright), np.array(motion), np.array(cols)


def detect_shots(hists: np.ndarray, motion: np.ndarray, fps: float, min_len: float = 0.4) -> list[int]:
    """Cut detector: histogram distance OR pixel-difference spike, each against
    a local adaptive threshold (catches cuts between similarly-lit shots)."""
    d = np.zeros(len(hists))
    d[1:] = 0.5 * np.abs(np.diff(hists, axis=0)).sum(axis=1)
    win = int(fps * 2)
    cuts = [0]
    for i in range(1, len(d)):
        lo, hi = max(0, i - win), min(len(d), i + win)
        hist_cut = d[i] > max(0.16, 3.0 * np.median(d[lo:hi]))
        neigh = np.concatenate([motion[lo:i], motion[i + 1:hi]])
        pix_cut = motion[i] > max(14.0, 4.0 * (np.median(neigh) if len(neigh) else 0) + 4.0)
        if (hist_cut or pix_cut) and (i - cuts[-1]) >= min_len * fps:
            cuts.append(i)
    return cuts


def analyze_source(cfg: Config, src: Path, force: bool = False) -> dict:
    cache = Cache(cfg.cache_dir)
    digest = sha256_file(src)
    cached = cache.get("analysis", digest)
    out_dir = cfg.cache_dir / "analysis" / digest[:16]
    if cached and not force and (out_dir / "shots.json").exists():
        return read_json(out_dir / "shots.json")

    info = ffprobe(src)
    vs = _video_stream(info)
    W, H = int(vs["width"]), int(vs["height"])
    num, den = vs["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    ah = int(round(AW * H / W / 2) * 2)

    hists, bright, motion, cols = _frame_stats(src, fps, AW, ah)
    cuts = detect_shots(hists, motion, fps)
    bounds = cuts + [len(hists)]

    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a < 2:
            continue
        colprof = cols[a:b].mean(axis=0)
        x = np.arange(len(colprof))
        w = colprof / (colprof.sum() + 1e-6)
        cx = float((x * w).sum() / len(colprof))
        spread = float(np.sqrt(((x / len(colprof) - cx) ** 2 * w).sum()))
        # horizontal saliency track (per ~0.5s) for moving crops
        step = max(1, int(fps / 2))
        track = []
        for j in range(a, b, step):
            cp = cols[j:min(b, j + step)].mean(axis=0)
            cw = cp / (cp.sum() + 1e-6)
            track.append(round(float((x * cw).sum() / len(cp)), 3))
        br = float(bright[a:b].mean())
        shots.append({
            "id": len(shots),
            "start": round(a / fps, 3),
            "end": round(b / fps, 3),
            "duration": round((b - a) / fps, 3),
            "brightness": round(br, 1),
            "motion": round(float(motion[a + 1:b].mean()) if b - a > 1 else 0.0, 2),
            "contrast": round(float(hists[a:b].mean(axis=0).std() * 100), 3),
            "saliency_x": round(cx, 3),
            "saliency_spread": round(spread, 3),
            "saliency_track": track,
            "is_black": br < 12,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    _keyframes(src, shots, out_dir / "keyframes")
    sheets = _contact_sheets(shots, out_dir / "keyframes", out_dir / "sheets")
    result = {
        "source": str(src), "sha256": digest, "width": W, "height": H, "fps": fps,
        "duration": float(info["format"]["duration"]), "shots": shots,
        "keyframes_dir": str(out_dir / "keyframes"), "contact_sheets": sheets,
    }
    write_json(out_dir / "shots.json", result)
    cache.put("analysis", digest, {"dir": str(out_dir)})
    return result


def _keyframes(src: Path, shots: list[dict], kdir: Path) -> None:
    kdir.mkdir(parents=True, exist_ok=True)
    # one seek-accurate frame per shot; batched through a select filter so the
    # file is decoded once
    times = [(s["start"] + s["end"]) / 2 for s in shots]
    for s, t in zip(shots, times):
        p = kdir / f"shot_{s['id']:04d}.jpg"
        if not p.exists():
            run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
                 "-q:v", "3", str(p), "-y"])


def _contact_sheets(shots: list[dict], kdir: Path, sdir: Path, per_sheet: int = 24,
                    cols: int = 4) -> list[str]:
    sdir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    out = []
    for k in range(0, len(shots), per_sheet):
        group = shots[k:k + per_sheet]
        thumbs = [Image.open(kdir / f"shot_{s['id']:04d}.jpg").convert("RGB") for s in group]
        tw = 320
        th = int(thumbs[0].height * tw / thumbs[0].width)
        rows = (len(group) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + 20)), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for i, (s, im) in enumerate(zip(group, thumbs)):
            x, y = (i % cols) * tw, (i // cols) * (th + 20)
            sheet.paste(im.resize((tw, th)), (x, y + 20))
            mm, ss = divmod(s["start"], 60)
            d.text((x + 4, y + 2), f"#{s['id']}  {int(mm):02d}:{ss:05.2f}  {s['duration']:.1f}s",
                   fill=(255, 220, 0), font=font)
        p = sdir / f"sheet_{k // per_sheet:03d}.jpg"
        sheet.save(p, quality=85)
        out.append(str(p))
    return out

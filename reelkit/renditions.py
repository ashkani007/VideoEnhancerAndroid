"""Multiple encodes of the same film ("renditions") behind one analysed timeline.

The story and timeline always speak in *master* time (the analysed file).
Other authorised copies — a sharper partial clip, or the official 1080p/4K
download — are registered here, aligned to master time automatically by
cross-correlating per-frame brightness, and the renderer picks the copy with
the most real pixels that covers each clip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .util import Config, ffprobe, read_json, sha256_file, write_json

FPS = 8  # alignment sampling rate


def _registry(cfg: Config) -> Path:
    return cfg.sources_dir / "renditions.json"


def _signature(path: Path) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={FPS},scale=32:18,format=gray",
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 18 * 32).astype(np.float32)
    s = frames.mean(axis=1)
    return (s - s.mean()) / (s.std() + 1e-6)


def _video_dims(path: Path) -> tuple[int, int, float]:
    info = ffprobe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return int(v["width"]), int(v["height"]), float(info["format"]["duration"])


def register(cfg: Config, master: Path, rendition: Path, license: str, url: str) -> dict:
    """Align `rendition` against `master` and record it."""
    sm, sr = _signature(master), _signature(rendition)
    n = len(sm) + len(sr)
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(sm, size) * np.conj(np.fft.rfft(sr, size)), size)
    lag = int(np.argmax(corr[: len(sm)]))           # rendition frame 0 == master frame `lag`
    overlap = min(len(sr), len(sm) - lag)
    score = float(np.dot(sm[lag:lag + overlap], sr[:overlap]) / overlap)
    w, h, dur = _video_dims(rendition)
    offset = lag / FPS
    entry = {"file": str(rendition), "sha256": sha256_file(rendition), "width": w, "height": h,
             "offset": round(offset, 3), "covers": [round(offset, 3), round(offset + dur, 3)],
             "match_score": round(score, 3), "license": license, "url": url}
    if score < 0.6:
        raise SystemExit(f"rendition does not match the master (score {score:.2f}); not registered")
    reg = read_json(_registry(cfg)) if _registry(cfg).exists() else {}
    key = sha256_file(master)
    reg.setdefault(key, [])
    reg[key] = [e for e in reg[key] if e["sha256"] != entry["sha256"]] + [entry]
    write_json(_registry(cfg), reg)
    return entry


def choose(cfg: Config, master: Path, analysis: dict, src_in: float, src_out: float) -> dict:
    """Best copy for one clip: most horizontal pixels, must fully cover the clip."""
    best = {"file": str(master), "width": analysis["width"], "height": analysis["height"],
            "offset": 0.0, "master": True}
    if not _registry(cfg).exists():
        return best
    for e in read_json(_registry(cfg)).get(analysis["sha256"], []):
        if e["covers"][0] + 0.1 <= src_in and src_out <= e["covers"][1] - 0.1 and e["width"] > best["width"]:
            best = e | {"master": False}
    return best

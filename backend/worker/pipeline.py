"""FFmpeg decode -> AI super resolution -> FFmpeg encode, with audio copied from the source.

Frames are decoded without auto-rotation (coded orientation, like the Android pipeline) and
the source display rotation is written to the output. The output frame rate is the source's
average frame rate, so total duration and audio sync are preserved; sources whose nominal and
average frame rates differ by more than 1% (true variable frame rate) are rejected upstream.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.media import ProbeResult
from .sr import Engine, upscale_frame


class Cancelled(Exception):
    pass


@dataclass
class EncodeSettings:
    codec: str = "libx265"
    preset: str = "slow"
    crf: int = 18


def _fps_arg(p: ProbeResult) -> str:
    raw = p.raw["video"].get("avg_frame_rate") or p.raw["video"].get("r_frame_rate") or "30/1"
    return raw if raw and raw != "0/0" else "30/1"


def process(
    src: str,
    out: str,
    probe: ProbeResult,
    engine: Engine,
    layout: str,
    out_w: int,
    out_h: int,
    start_ms: int,
    duration_ms: int | None,
    sharpen_amount: float,
    enc: EncodeSettings,
    on_progress: Callable[[int, int], None],
    should_cancel: Callable[[], bool],
) -> dict:
    w, h = probe.width, probe.height
    seg_ms = (probe.duration_ms - start_ms) if duration_ms is None else min(duration_ms, probe.duration_ms - start_ms)
    if seg_ms <= 0:
        raise ValueError("Empty segment")
    fps = _fps_arg(probe)
    expected = max(1, round(seg_ms / 1000 * float(eval_fraction(fps))))

    seek = ["-ss", f"{start_ms / 1000:.3f}"] if start_ms > 0 else []
    limit = ["-t", f"{seg_ms / 1000:.3f}"] if duration_ms is not None else []
    dec_cmd = ["ffmpeg", "-v", "error", "-noautorotate", *seek, "-i", src, *limit, "-map", "0:v:0",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-fps_mode", "passthrough", "-"]

    vf = []
    if sharpen_amount > 0:
        # Conventional unsharp mask on luma only (not AI), conservative amount.
        vf = ["-vf", f"unsharp=lx=5:ly=5:la={min(sharpen_amount, 1.0) * 1.0:.2f}:cx=5:cy=5:ca=0"]
    rot = ["-display_rotation", str(probe.rotation)] if probe.rotation else []
    audio_in = [*seek, "-i", src, *limit] if probe.audio_codec else []
    audio_map = ["-map", "1:a:0", "-c:a", "copy" if probe.audio_codec == "aac" else "aac"] if probe.audio_codec else []
    codec_args = ["-c:v", enc.codec, "-preset", enc.preset, "-crf", str(enc.crf), "-pix_fmt", "yuv420p"]
    if enc.codec == "libx265":
        codec_args += ["-tag:v", "hvc1", "-x265-params", "log-level=error"]
    enc_cmd = ["ffmpeg", "-v", "error", "-y",
               *rot, "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{out_w}x{out_h}", "-framerate", fps, "-i", "-",
               *audio_in, "-map", "0:v:0", *audio_map, *vf, *codec_args,
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-movflags", "+faststart", out]

    frame_bytes = w * h * 3
    t0 = time.monotonic()
    n = 0
    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    encp = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            if should_cancel():
                raise Cancelled()
            buf = dec.stdout.read(frame_bytes)
            if not buf:
                break
            if len(buf) != frame_bytes:
                raise RuntimeError("Truncated frame from decoder")
            frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
            try:
                encp.stdin.write(upscale_frame(engine, frame, layout, out_w, out_h).tobytes())
            except BrokenPipeError:
                encp.wait()
                raise RuntimeError("Encoder exited: " + encp.stderr.read().decode(errors="replace")[-600:]) from None
            n += 1
            on_progress(n, expected)
        encp.stdin.close()
        if encp.wait() != 0:
            raise RuntimeError("Encoder failed: " + encp.stderr.read().decode(errors="replace")[-400:])
        if dec.wait() != 0:
            raise RuntimeError("Decoder failed: " + dec.stderr.read().decode(errors="replace")[-400:])
    except BaseException:
        for p in (dec, encp):
            if p.poll() is None:
                p.kill()
        raise
    elapsed = time.monotonic() - t0
    if n == 0:
        raise RuntimeError("No frames decoded")
    return {"frames": n, "expected_frames": expected, "elapsed_s": round(elapsed, 2),
            "s_per_frame": round(elapsed / n, 3), "fps": fps, "audio": probe.audio_codec}


def eval_fraction(v: str) -> float:
    num, _, den = v.partition("/")
    return float(num) / float(den or 1)

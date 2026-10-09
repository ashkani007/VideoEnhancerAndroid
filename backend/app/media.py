"""ffprobe-based validation of uploaded sources and produced outputs."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction

from .config import Settings


class MediaError(Exception):
    pass


@dataclass
class ProbeResult:
    container: str
    video_codec: str
    width: int
    height: int
    fps: float
    avg_fps: float
    duration_ms: int
    frame_count: int | None
    pix_fmt: str | None
    audio_codec: str | None
    rotation: int
    raw: dict

    @property
    def variable_frame_rate(self) -> bool:
        return self.fps > 0 and self.avg_fps > 0 and abs(self.fps - self.avg_fps) / self.fps > 0.01


def _fraction(v: str | None) -> float:
    try:
        f = Fraction(v or "0")
        return float(f) if f.denominator else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str, count_frames: bool = False) -> ProbeResult:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
    if count_frames:
        cmd += ["-count_packets"]
    cmd.append(path)
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, timeout=120).stdout
    except subprocess.CalledProcessError as e:
        raise MediaError(f"Not a readable media file: {e.stderr.decode(errors='replace').strip()[:200]}") from None
    except subprocess.TimeoutExpired:
        raise MediaError("Timed out reading the file") from None
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise MediaError("No video stream found")
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    duration = float(video.get("duration") or fmt.get("duration") or 0)
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    frames = video.get("nb_read_packets") or video.get("nb_frames")
    return ProbeResult(
        container=fmt.get("format_name", ""),
        video_codec=video.get("codec_name", ""),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=_fraction(video.get("r_frame_rate")),
        avg_fps=_fraction(video.get("avg_frame_rate")),
        duration_ms=int(duration * 1000),
        frame_count=int(frames) if frames else None,
        pix_fmt=video.get("pix_fmt"),
        audio_codec=audio.get("codec_name") if audio else None,
        rotation=rotation,
        raw={"format": fmt.get("format_name"), "video": {k: video.get(k) for k in ("codec_name", "width", "height", "r_frame_rate", "avg_frame_rate", "pix_fmt")}},
    )


def validate_source(p: ProbeResult, s: Settings) -> None:
    codecs = {c.strip() for c in s.allowed_video_codecs.split(",")}
    containers = {c.strip() for c in s.allowed_containers.split(",")}
    if p.video_codec not in codecs:
        raise MediaError(f"Video codec {p.video_codec} is not accepted")
    if not set(p.container.split(",")) & containers:
        raise MediaError(f"Container {p.container} is not accepted")
    if p.width <= 0 or p.height <= 0 or p.width * p.height > s.max_source_pixels:
        raise MediaError(f"Source size {p.width}x{p.height} is outside the server limits")
    if p.duration_ms <= 0 or p.duration_ms > s.max_duration_ms:
        raise MediaError("Video duration is outside the server limits")
    if p.fps <= 0:
        raise MediaError("Frame rate could not be determined")


def validate_output(path: str, width: int, height: int, expected_frames: int, expect_audio: bool) -> dict:
    p = probe(path, count_frames=True)
    problems = []
    if (p.width, p.height) != (width, height):
        problems.append(f"resolution {p.width}x{p.height}, expected {width}x{height}")
    if p.frame_count is not None and p.frame_count != expected_frames:
        problems.append(f"{p.frame_count} frames, expected {expected_frames}")
    if expect_audio and not p.audio_codec:
        problems.append("audio missing")
    return {"ok": not problems, "problems": problems, "width": p.width, "height": p.height,
            "frames": p.frame_count, "duration_ms": p.duration_ms, "video_codec": p.video_codec, "audio_codec": p.audio_codec}

"""Parallel frame rendering piped into FFmpeg (NVENC when available, else libx264)."""
import multiprocessing as mp
import os
import shutil
import subprocess
import time

_EP = None


def ffmpeg_bin():
    return os.environ.get("FFMPEG", shutil.which("ffmpeg") or "ffmpeg")


def pick_encoder(prefer_gpu=True):
    """Probe NVENC with a tiny real encode; fall back to libx264."""
    if prefer_gpu:
        try:
            r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                "color=c=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"],
                               capture_output=True, timeout=30)
            if r.returncode == 0:
                return "h264_nvenc"
        except Exception:
            pass
    return "libx264"


def encoder_args(enc, quality):
    if enc == "h264_nvenc":
        cq = "17" if quality == "final" else "21"
        return ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", cq, "-b:v", "0",
                "-profile:v", "high"]
    crf = "16" if quality == "final" else "20"
    return ["-c:v", "libx264", "-preset", "slow" if quality == "final" else "medium", "-crf", crf,
            "-profile:v", "high", "-tune", "animation"]


def _init(ep_dir, quality, burn, only):
    global _EP
    from .episode import Episode, load_config, make_ctx
    _EP = Episode(ep_dir, make_ctx(load_config(ep_dir), quality), burn_subtitles=burn, only_scenes=only)


def _frame(i):
    return i, _EP.frame(i / _EP.ctx.fps).tobytes()


def render_video(ep_dir, out_path, quality="preview", workers=None, frames=None, burn=True, prefer_gpu=True,
                 log=print):
    from .episode import load_config, make_ctx
    cfg = load_config(ep_dir)
    ctx = make_ctx(cfg, quality)
    n_total = int(round(cfg["duration"] * ctx.fps))
    f0, f1 = frames or (0, n_total)
    enc = pick_encoder(prefer_gpu)
    log(f"[render] {ctx.W}x{ctx.H} @ {ctx.fps}fps, frames {f0}-{f1}, encoder {enc}")
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{ctx.W}x{ctx.H}", "-r", str(ctx.fps), "-i", "-"] + encoder_args(enc, quality) + \
          ["-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    workers = workers or max(1, min(os.cpu_count() or 2, 6) - 0)
    t0 = time.time()
    mpctx = mp.get_context("spawn")
    with mpctx.Pool(workers, initializer=_init, initargs=(ep_dir, quality, burn, None)) as pool:
        for k, (i, buf) in enumerate(pool.imap(_frame, range(f0, f1), chunksize=2)):
            proc.stdin.write(buf)
            if k % 24 == 0:
                el = time.time() - t0
                log(f"[render] frame {i}/{f1}  {el:.0f}s elapsed")
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    log(f"[render] video done in {time.time() - t0:.0f}s -> {out_path}")
    return enc


def mux(video, audio, out_path, lufs=-15):
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-i", audio, "-map", "0:v",
           "-map", "1:a", "-c:v", "copy", "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11", "-ar", "48000",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)


def still(ep_dir, t, out_png, quality="preview"):
    import cv2
    from .episode import Episode, load_config, make_ctx
    cfg = load_config(ep_dir)
    ctx = make_ctx(cfg, quality)
    idx = None
    for i, s in enumerate(cfg["scenes"]):
        if s["start"] - 0.5 <= t <= s["start"] + s["duration"] + 0.5:
            idx = set(idx or ()) | {i}
    ep = Episode(ep_dir, ctx, only_scenes=idx)
    cv2.imwrite(out_png, cv2.cvtColor(ep.frame(t), cv2.COLOR_RGB2BGR))

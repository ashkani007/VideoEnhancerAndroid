#!/usr/bin/env python3
"""Add Great History Makers branding to a finished video without touching anything else.

  python tools/brand.py master.mp4 audio_source.mp4 out.mp4 endcard.png

- permanent watermark: upper-left, 155 px wide, 60 % opacity, 55 px / 100 px margins
- end signature over the final 3 s: centred logo fades in with a very slow scale,
  soft radial shade behind it, channel handle below; the watermark fades out as it enters
- video frames are composited from the master; the audio stream is copied bit-for-bit
"""
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mosaic.text import find_font  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "..", "assets", "brand", "Great_History_Makers_Logo_Transparent.png")
W, H, FPS = 1080, 1920, 30
WM_W, WM_X, WM_Y, WM_OP = 155, 55, 100, 0.60
END_LEN, END_W, END_CY = 3.0, 760, 840
HANDLE = "@great_history_makers_en"


def premul(rgba):
    f = rgba.astype(np.float32) / 255.0
    f[..., :3] *= f[..., 3:4]
    return f


def scaled(logo, width):
    h = int(round(logo.shape[0] * width / logo.shape[1]))
    return cv2.resize(logo, (width, h), interpolation=cv2.INTER_AREA)


def over(frame, layer_pm, x, y, op):
    h, w = layer_pm.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0 or op <= 0:
        return
    L = layer_pm[y0 - y:y1 - y, x0 - x:x1 - x] * op
    roi = frame[y0:y1, x0:x1]
    roi *= 1 - L[..., 3:4]
    roi += L[..., :3]


def handle_layer():
    img = Image.new("RGBA", (W, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    path = find_font("sub")
    f = ImageFont.truetype(path, 46) if path else ImageFont.load_default()
    sp = 2.5
    widths = [d.textlength(ch, font=f) for ch in HANDLE]
    x = W / 2 - (sum(widths) + sp * (len(HANDLE) - 1)) / 2
    for ch, w in zip(HANDLE, widths):
        d.text((x, 40), ch, font=f, fill=(246, 232, 196, 255), stroke_width=2, stroke_fill=(20, 14, 10, 230))
        x += w + sp
    a = img.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.8))
    sh = Image.new("RGBA", img.size, (10, 7, 5, 0))
    sh.putalpha(a)
    return premul(np.array(Image.alpha_composite(sh, img)))


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def main(master, audio_src, out, endcard_png, bitrate="12.8M"):
    logo = cv2.cvtColor(cv2.imread(LOGO, cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    wm = premul(scaled(logo, WM_W))
    hd = handle_layer()
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                master], capture_output=True, text=True).stdout)
    n = int(round(dur * FPS))
    t_end = dur - END_LEN
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    shade = np.exp(-(((xx - W / 2) / 520) ** 2 + ((yy - END_CY - 60) / 470) ** 2) * 1.6)[..., None]
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", master, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    raw_out = out + ".video.mkv"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "12",
                            "-pix_fmt", "yuv420p", raw_out], stdin=subprocess.PIPE)
    cache = {}
    for i in range(n):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        t = i / FPS
        f = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32) / 255.0
        p = smooth((t - t_end) / 1.0)                         # end-card fade-in over 1 s
        over(f, wm, WM_X, WM_Y, WM_OP * (1 - p))
        if p > 0:
            f *= 1 - 0.38 * p * shade                          # restrained shade behind the emblem only
            s = 0.94 + 0.06 * smooth((t - t_end) / END_LEN)   # very slow settle 94 % -> 100 %
            wpx = int(round(END_W * s / 2) * 2)
            if wpx not in cache:
                cache[wpx] = premul(scaled(logo, wpx))
            L = cache[wpx]
            over(f, L, (W - L.shape[1]) // 2, END_CY - L.shape[0] // 2, p)
            ph = smooth((t - t_end - 0.6) / 0.8)
            over(f, hd, 0, END_CY + int(END_W * 0.642 / 2) + 30, ph)
        if abs(t - (dur - 0.8)) < 0.5 / FPS:
            cv2.imwrite(endcard_png, cv2.cvtColor((np.clip(f, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        enc.stdin.write((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    dec.wait()
    log = out + ".2pass"
    common = ["-c:v", "libx264", "-preset", "slow", "-b:v", bitrate, "-maxrate", "20M", "-bufsize", "30M",
              "-tune", "animation", "-profile:v", "high", "-pix_fmt", "yuv420p", "-passlogfile", log]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw_out] + common + ["-pass", "1", "-an", "-f", "null", "-"],
                   check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw_out, "-i", audio_src, "-map", "0:v", "-map", "1:a"]
                   + common + ["-pass", "2", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    import glob
    for f_ in [raw_out] + glob.glob(log + "*"):   # intermediate master and 2-pass logs
        os.remove(f_)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:5])

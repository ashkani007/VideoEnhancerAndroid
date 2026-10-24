#!/usr/bin/env python3
"""Napoleon image-to-animation test: a 5 s 2.5D shot built from the approved illustration (no generative video).

Layers: foreground (Napoleon, rocks, draped flag; GrabCut matte) over an inpainted background plate.
Every motion is a controlled local warp or repaint of the original pixels, so the design is preserved:
  eyes: gaze drift + one blink (painted lid) | brows lower/knit, mouth sets | head + hat soft-masked turn
  coat flaps, draped flag, hair: wind ripples | flags: travelling wave pinned at the pole
  soldiers: staggered marching bob | smoke: stylized drifting layers + billowing column | clouds drift
  light: warm sweep across the face | camera: slow drift, then a parallax push-in (fg zooms more than bg)

  python animate.py --preview     # 540x960 -> ../qc/preview_540x960.mp4
  python animate.py               # 1080x1920 -> ../final/Napoleon_Animation_Test.mp4
  python animate.py --still 2.0   # one frame
"""
import argparse
import math
import multiprocessing as mp
import os
import subprocess
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FPS, DUR = 30, 5.0

IMG = cv2.cvtColor(cv2.imread(os.path.join(ROOT, "source", "napoleon_master.png")), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
PLATE = cv2.cvtColor(cv2.imread(os.path.join(HERE, "background_plate.png")), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
H, W = IMG.shape[:2]
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
_m = cv2.imread(os.path.join(HERE, "mask_foreground.png"), 0).astype(np.float32) / 255
ALPHA = cv2.GaussianBlur(_m, (0, 0), 0.9)


# ------------------------------------------------------------------------------------------- helpers
def ease(u):
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def ramp(t, t0, t1):
    return ease((t - t0) / (t1 - t0))


def soft_box(x0, y0, x1, y1, f):
    """1 inside the box, smooth falloff of width f outside."""
    dx = np.maximum(np.maximum(x0 - XX, XX - x1), 0)
    dy = np.maximum(np.maximum(y0 - YY, YY - y1), 0)
    return np.clip(1 - np.hypot(dx, dy) / f, 0, 1) ** 2


def gauss(cx, cy, sx, sy):
    return np.exp(-(((XX - cx) / sx) ** 2 + ((YY - cy) / sy) ** 2))


def warp(img, dx, dy, roi):
    """Inverse warp inside roi=(x0,y0,x1,y1): output(x) = img(x - d). img may have any channel count."""
    x0, y0, x1, y1 = roi
    sl = (slice(y0, y1), slice(x0, x1))
    mx = (XX[sl] - dx[sl]).astype(np.float32)
    my = (YY[sl] - dy[sl]).astype(np.float32)
    out = img.copy()
    out[sl] = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)   # maps index the full image
    return out


def tileable_noise(h, w, sigma, seed):
    r = np.random.default_rng(seed)
    F = np.fft.rfft2(r.normal(0, 1, (h, w)))
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.rfftfreq(w)[None, :]
    F *= np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    n = np.fft.irfft2(F, s=(h, w)).astype(np.float32)
    return (n - n.min()) / (np.ptp(n) + 1e-6)


# precomputed masks / textures
SKY = np.clip((660 - YY) / 80, 0, 1)
FLAG_BIG = soft_box(772, 950, 888, 1100, 6)
FLAG_A = soft_box(517, 1006, 566, 1080, 5)
FLAG_B = soft_box(570, 1006, 646, 1086, 5)
_hsv = cv2.cvtColor((IMG * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
CLOTH = cv2.GaussianBlur(((_hsv[..., 1] > 90) | (_hsv[..., 2] > 225)).astype(np.float32), (0, 0), 2.0)
SOLDIERS = soft_box(540, 1110, 941, 1330, 30) * (1 - ALPHA)
RIDER = soft_box(625, 1045, 800, 1300, 20) * (1 - ALPHA)
SMOKE_BAND = soft_box(505, 925, 941, 1070, 45) * (1 - ALPHA)
SMOKE_COL = gauss(830, 665, 50, 40)
N1 = tileable_noise(H, W, 26, 3)
N2 = tileable_noise(H, W, 11, 7)
HEAD = np.clip(soft_box(165, 132, 600, 345, 28) + soft_box(245, 280, 505, 440, 30), 0, 1) * np.clip((470 - YY) / 40, 0, 1)
HAIR = soft_box(255, 300, 330, 385, 14)
COAT_L = soft_box(0, 850, 175, 1185, 30) * np.clip((175 - XX) / 175, 0, 1) ** 0.7
COAT_R = soft_box(455, 950, 585, 1340, 20) * np.clip((XX - 455) / 130, 0, 1)
FLAG_FG = np.clip(soft_box(0, 1175, 520, 1290, 30) + soft_box(482, 1345, 560, 1672, 8), 0, 1)   # fabric only: not the map, spyglass or crate
FACE = soft_box(380, 285, 505, 445, 25) * ALPHA

# eye geometry (source pixels)
EYE_UP = np.array([(425, 307), (430, 305.5), (437, 305), (444, 305), (450, 305.5), (454, 307)], np.float32)
EYE_LO = np.array([(455, 309), (454, 315), (451, 319.5), (446, 319), (440, 317.5), (434, 314.5), (428, 310)], np.float32)
LID_SKIN = IMG[300:303, 432:446].reshape(-1, 3).mean(0)
LASH = np.array([0.06, 0.04, 0.05], np.float32)


def eye_mask():
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.vstack([EYE_UP, EYE_LO]).astype(np.int32)], 255)
    return cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 0.7)


EYE = eye_mask()


def blink_amount(t, t0=0.92, dur=0.2):
    u = (t - t0) / dur
    if u < 0 or u > 1:
        return 0.0
    return u / 0.4 if u < 0.4 else (1.0 if u < 0.55 else 1 - (u - 0.55) / 0.45)


# ------------------------------------------------------------------------------------------- layers
def background(t):
    bg = PLATE.copy()
    # clouds drift (upper sky moves more)
    dx = (3.0 * t / DUR) * SKY * (1.2 - YY / 700)
    bg = warp(bg, dx, np.zeros_like(dx), (0, 0, W, 700))
    # billowing smoke column by the town
    ph = 2 * math.pi * t
    dxc = SMOKE_COL * (2.0 * np.sin(YY / 11 + ph * 0.6))
    dyc = SMOKE_COL * (1.5 * np.sin(XX / 14 + ph * 0.45) - 1.2 * (t / DUR))
    bg = warp(bg, dxc, dyc, (740, 600, 920, 740))
    # flags: travelling wave pinned at the pole
    for mask, pole, length, amp, freq, k in ((FLAG_BIG, 772, 112, 4.2, 1.25, 68), (FLAG_A, 518, 48, 2.2, 1.45, 40),
                                             (FLAG_B, 571, 75, 2.6, 1.35, 52)):
        u = np.clip((XX - pole) / length, 0, 1)
        wv = np.sin(2 * math.pi * ((XX - pole) / k - freq * t))
        w = mask * np.maximum(CLOTH, 0.25) * u
        bg = warp(bg, 0.35 * amp * w * np.cos(2 * math.pi * ((XX - pole) / k - freq * t)), amp * w * wv,
                  (pole - 4, 940, pole + length + 12, 1110))
    # soldiers: staggered marching bob (about one step every 0.55 s), rider bobs more slowly
    step = np.sin(2 * math.pi * (1.8 * t) + XX / 36.0 * 2.3 + 0.7 * np.sin(XX / 13.0))
    bg = warp(bg, np.zeros_like(XX), 1.3 * SOLDIERS * step, (530, 1040, W, 1345))
    bg = warp(bg, np.zeros_like(XX), 0.9 * RIDER * np.sin(2 * math.pi * 0.9 * t), (620, 1040, 805, 1305))
    # drifting battlefield smoke: two stylized layers (flat, posterized edges like the illustration)
    s1 = np.roll(N1, int(14 * t), axis=1)
    s2 = np.roll(N2, int(26 * t), axis=1)
    sm = 0.6 * s1 + 0.4 * s2
    a = (np.clip((sm - 0.52) / 0.06, 0, 1) * 0.30 + np.clip((sm - 0.62) / 0.05, 0, 1) * 0.22) * SMOKE_BAND
    col = np.array([0.86, 0.76, 0.70], np.float32) * (0.92 + 0.12 * np.clip((1060 - YY) / 140, 0, 1))[..., None]
    bg = bg * (1 - a[..., None]) + col * a[..., None]
    # sun breathes a little warmer toward the end
    sun = gauss(905, 590, 160, 140) * 0.06 * ramp(t, 3.3, 5.0)
    bg += sun[..., None] * np.array([1.0, 0.75, 0.45], np.float32)
    return bg


def foreground(t):
    fg = np.dstack([IMG, ALPHA])
    # --- eyes: gaze drifts to the horizon (iris starts slightly inward)
    g = -2.6 * (1 - ramp(t, 0.15, 1.25))
    wiris = EYE * gauss(447, 311, 7, 6)
    fg = warp(fg, g * wiris, 0.5 * (g / -2.6) * wiris, (420, 298, 460, 322))
    # --- blink: skin lid descends over the opening, lash line rides its edge
    b = blink_amount(t)
    if b > 0:
        top = EYE_UP[:, 1].min()
        edge = top + (320.0 - top) * b
        lid = EYE * (YY <= edge) * soft_box(424, 303, 456, 321, 1.5)
        fg[..., :3] = fg[..., :3] * (1 - lid[..., None]) + LID_SKIN * lid[..., None]
        lash = np.exp(-((YY - edge) / 1.1) ** 2) * soft_box(425, 303, 456, 321, 1.0) * (EYE > 0.05) * b
        fg[..., :3] = fg[..., :3] * (1 - lash[..., None]) + LASH * lash[..., None]
    # --- expression sets: brows lower and knit, mouth corner tightens
    d = ramp(t, 0.95, 1.55)
    wb = soft_box(418, 282, 482, 307, 7)
    knit = np.clip((XX - 440) / 40, 0, 1)
    fg = warp(fg, -0.8 * d * wb * knit, d * wb * (0.9 + 1.4 * knit), (410, 275, 492, 314))
    wm = gauss(444, 384.5, 6, 3.5)
    fg = warp(fg, 0.9 * d * wm, 0.35 * d * wm, (432, 376, 460, 394))
    # --- head + hat turn toward the horizon (soft mask into the neck), hair sways
    h = ramp(t, 1.5, 3.4)
    ang = math.radians(-1.3 * h)
    px, py = 430.0, 452.0
    rx = (XX - px) * math.cos(ang) - (YY - py) * math.sin(ang) + px - XX
    ry = (XX - px) * math.sin(ang) + (YY - py) * math.cos(ang) + py - YY
    fg = warp(fg, (rx + 2.6 * h) * HEAD, (ry - 0.6 * h) * HEAD, (140, 110, 620, 480))
    fg = warp(fg, 1.4 * HAIR * math.sin(2 * math.pi * 0.7 * t + 0.6), 0.4 * HAIR * math.sin(2 * math.pi * 0.7 * t),
              (240, 290, 345, 400))
    # --- wind: coat flaps and the draped flag ripple (gentle, increasing toward free edges)
    wind = 0.6 + 0.4 * math.sin(2 * math.pi * 0.23 * t)
    fg = warp(fg, wind * 3.2 * COAT_L * np.sin(2 * math.pi * 0.62 * t + YY / 55), wind * 1.2 * COAT_L * np.sin(2 * math.pi * 0.62 * t + YY / 70 + 1),
              (0, 820, 210, 1215))
    fg = warp(fg, wind * 2.2 * COAT_R * np.sin(2 * math.pi * 0.7 * t + YY / 75), np.zeros_like(XX), (440, 930, 600, 1350))
    fg = warp(fg, wind * 1.2 * FLAG_FG * np.sin(2 * math.pi * 0.5 * t - XX / 90 + YY / 130),
              wind * 2.6 * FLAG_FG * np.sin(2 * math.pi * 0.5 * t - XX / 85 + YY / 110), (0, 1150, 580, H))
    # --- warm light sweep across the face (rim strengthens, colour warms)
    lsw = ramp(t, 3.4, 5.0)
    band = np.clip(1 - np.abs((XX - (520 - 120 * lsw))) / 90, 0, 1)
    k = FACE * (0.05 + 0.10 * band) * lsw
    fg[..., :3] *= 1 + k[..., None] * np.array([0.9, 0.45, 0.05], np.float32)
    return fg


def camera(t):
    """Explicit, always-valid framings: a barely perceptible drift, then an eased push toward the face.
    (Start and end crops lie inside the image, so the clamp never engages and the move has no jolt.)"""
    u = ramp(t, 3.4, 5.0)
    z = 1.0 + 0.02 * ramp(t, 0.0, 3.4) + 0.065 * u
    fx = 470.0 + (447.0 - 470.0) * u
    fy = 836.0 + (792.0 - 836.0) * u
    return z, fx, fy


def place(layer, z, fx, fy, OW, OH, interp):
    s = OW / W * z
    hw, hh = W / (2 * z), H / (2 * z)
    fx, fy = min(max(fx, hw), W - hw), min(max(fy, hh), H - hh)
    M = np.float32([[s, 0, OW / 2 - fx * s], [0, s, OH / 2 - fy * s]])
    return cv2.warpAffine(layer, M, (OW, OH), flags=interp, borderMode=cv2.BORDER_REFLECT)


def frame(t, OW, OH):
    z, fx, fy = camera(t)
    zb = 1 + (z - 1) * 0.55                                   # parallax: background zooms less
    bg = place(background(t), zb, fx, fy, OW, OH, cv2.INTER_LANCZOS4)
    fg = place(foreground(t), z, fx, fy, OW, OH, cv2.INTER_LANCZOS4)
    a = np.clip(fg[..., 3:4], 0, 1)
    out = bg * (1 - a) + fg[..., :3] * a
    if OW >= 1000:                                            # gentle sharpening after the upscale
        blur = cv2.GaussianBlur(out, (0, 0), 1.2)
        out = out + 0.35 * (out - blur)
    return np.clip(out, 0, 1)


def _work(args):
    i, OW, OH = args
    return (frame(i / FPS, OW, OH) * 255 + 0.5).astype(np.uint8).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--still", type=float)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    OW, OH = (540, 960) if a.preview else (1080, 1920)
    if a.still is not None:
        p = os.path.join(ROOT, "qc", f"still_{a.still:.2f}_{OW}.png")
        cv2.imwrite(p, cv2.cvtColor((frame(a.still, OW, OH) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(p)
        return
    out = os.path.join(ROOT, "qc", "preview_540x960.mp4") if a.preview else os.path.join(ROOT, "final", "Napoleon_Animation_Test.mp4")
    n = int(round(FPS * DUR))
    t0 = time.time()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
    with ctx.Pool(a.workers) as pool:
        for k, buf in enumerate(pool.imap(_work, [(i, OW, OH) for i in range(n)], chunksize=2)):
            ff.stdin.write(buf)
            if k % 30 == 0:
                print(f"frame {k}/{n} {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"wrote {out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

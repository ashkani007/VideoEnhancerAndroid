"""Shot-type presets and automatic plate metadata (cuts the per-plate manual work).

Automatic: sky line (cloud drift), French tricolour flags (pole on the left), battle smoke band and cannon puffs,
marching-rank bob, cloth wind under the figure, matte hint, camera move, transitions, default sound design.
Manual (one annotation per close-up): the eye outline for the blink and the pivot box for hand motion; until they are
annotated, a shot simply renders without blink / hand motion.
"""
import cv2
import numpy as np


# ------------------------------------------------------------------------------------------- detectors
def sky_line(img_rgb):
    """Row (plate px) where the calm sky ends, or None when the top of the frame is busy (no cloud drift then)."""
    H, W = img_rgb.shape[:2]
    g = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    tex = np.abs(cv2.Sobel(cv2.GaussianBlur(g, (0, 0), 2), cv2.CV_32F, 0, 1)).mean(1)
    tex = np.convolve(tex, np.ones(15) / 15, mode="same")
    top = tex[: int(0.12 * H)].mean()
    if top > 6.0:                                                     # textured top (hat, foliage...): no drift
        return None
    busy = np.where(tex > max(2.2 * top, 4.0))[0]
    busy = busy[busy > int(0.12 * H)]
    if not len(busy):
        return None
    y = int(busy[0])
    return y if 0.15 * H <= y <= 0.65 * H else None


def tricolour_flags(img_rgb, min_area_frac=0.0002, exclude=None):
    """French tricolours (blue | white | red, left to right). Returns [{"box", "pole_x"}] in plate px."""
    H, W = img_rgb.shape[:2]
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    blue = ((h >= 95) & (h <= 130) & (s > 80) & (v > 45)).astype(np.uint8)
    red = (((h <= 10) | (h >= 150)) & (s > 110) & (v > 70)).astype(np.uint8)
    white = ((v > 195) & ((s < 60) | ((h <= 35) & (s < 150)))).astype(np.uint8)      # warm whites under golden light
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(blue, 8)
    out = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if a < min_area_frac * H * W or w < 6 or hh < 8 or hh > 4 * w or w > 3 * hh:
            continue
        ys = slice(y + hh // 5, y + hh - hh // 5)
        wz = white[ys, x + w: min(W, x + 2 * w)]
        rz = red[ys, min(W, x + int(1.6 * w)): min(W, x + 3 * w)]
        if wz.size == 0 or rz.size == 0:
            continue
        if exclude is not None and exclude[y:y + hh, x:x + 3 * w].mean() > 0.2:
            continue                                                  # inside the foreground figure (uniforms are tricolour too)
        if a > 0.01 * H * W:
            continue
        if wz.mean() > 0.35 and rz.mean() > 0.25 and blue[ys, x:x + w].mean() > 0.5:
            out.append({"box": [int(x - 2), int(y - 4), int(min(W, x + 3 * w + 4)), int(min(H, y + hh + 6))], "pole_x": int(x)})
    return out


def figure_box(alpha):
    m = alpha > 0.5
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


# ------------------------------------------------------------------------------------------- presets
def default_hint(kind, W, H):
    """Loose outline + core for the matte when the beat gives none (subject placement per shot type)."""
    if kind == "portrait":
        return {"polygon": [[0.02 * W, 0.08 * H], [0.98 * W, 0.08 * H], [0.98 * W, H], [0.02 * W, H]],
                "core": [[0.35 * W, 0.35 * H], [0.65 * W, 0.35 * H], [0.65 * W, 0.8 * H], [0.35 * W, 0.8 * H]]}
    if kind == "hero_wide":
        return {"polygon": [[0.0, 0.1 * H], [0.75 * W, 0.1 * H], [0.75 * W, H], [0.0, H]],
                "core": [[0.2 * W, 0.4 * H], [0.5 * W, 0.4 * H], [0.5 * W, 0.8 * H], [0.2 * W, 0.8 * H]]}
    return None                                                       # battle / landscape: no foreground layer


def auto_meta(kind, img_rgb, alpha=None, seed=0):
    """Metadata in plate pixels (ref_width = plate width)."""
    H, W = img_rgb.shape[:2]
    k = W / 941.0                                                     # amplitudes were tuned on a 941 px plate
    meta = {"ref_width": W, "auto": True}
    sy = sky_line(img_rgb)
    if sy and (alpha is not None or kind in ("battle", "landscape")):
        meta["sky"] = {"y": sy, "drift": 3.0 * k}
    flags = tricolour_flags(img_rgb, exclude=None if alpha is None else alpha > 0.5)
    if flags:
        meta["flags"] = [dict(f, amp=3.2 * k * (f["box"][3] - f["box"][1]) / (150 * k), freq=1.3, k=60 * k) for f in flags[:6]]
    if kind == "battle":
        hz = sy or int(0.45 * H)
        meta["smoke"] = [{"box": [0, hz, W, min(H, hz + int(0.18 * H))], "feather": 45 * k, "density": 1.0, "speed": 14 * k},
                         {"box": [0, hz, W, min(H, hz + int(0.32 * H))], "feather": 70 * k, "density": 2.0, "speed": 20 * k,
                          "gain_key": "battle", "default_gain": 0}]
        meta["bob"] = [{"box": [0, int(0.62 * H), W, H], "amp": 1.1 * k, "rate": 1.8, "feather": 30 * k}]
        rng = np.random.default_rng(seed)
        meta["puff_points"] = [[int(rng.uniform(0.15, 0.85) * W), int(hz + rng.uniform(0.0, 0.06) * H)] for _ in range(3)]
    if alpha is not None and kind in ("portrait", "hero_wide"):
        fb = figure_box(alpha)
        if fb:
            x0, y0, x1, y1 = fb
            meta["wind"] = [{"box": [x0, int(y1 - 0.3 * (y1 - y0)), x1, y1], "amp": 2.0 * k, "rate": 0.55, "feather": 30 * k}]
    return meta


CAMERA = {   # zoom 1 = cover; focus as fractions of the plate (x, y)
    "portrait": {"from": (1.0, (0.5, 0.45)), "to": (1.3, (0.5, 0.33)), "ease": "out"},
    "hero_wide": {"from": (1.18, (0.5, 0.42)), "to": (1.04, (0.5, 0.5)), "ease": "inout"},
    "battle": {"from": (1.04, (0.48, 0.55)), "to": (1.16, (0.55, 0.5)), "ease": "inout"},
    "landscape": {"from": (1.0, (0.5, 0.5)), "to": (1.12, (0.5, 0.45)), "ease": "inout"},
}


def camera(kind, W, H, face=None):
    c = CAMERA[kind]
    (z0, (fx0, fy0)), (z1, (fx1, fy1)) = c["from"], c["to"]
    to = [fx1 * W, fy1 * H] if face is None else [face[0], face[1] + 0.06 * H]
    return {"from": {"zoom": z0, "focus": [fx0 * W, fy0 * H]}, "to": {"zoom": z1, "focus": to}, "ease": c["ease"], "parallax": 0.55}


def transition(prev_kind, kind):
    """plate -> map: painted ink wipe; map -> plate: flash; plate -> plate: whip-zoom."""
    if kind == "map":
        return "ink"
    if prev_kind == "map":
        return "flash"
    return "whip"


def sound(beats_timed, duration):
    """Default sound design from the shot types (procedural, royalty-free: mosaic.audio)."""
    sfx = []
    for b in beats_timed:
        t0, t1, kind = b["start"], b["end"], b["type"]
        if t0 > 0.3:
            sfx.append({"type": "whoosh", "start": max(0.0, t0 - 0.48), "gain": 0.5})
        if kind == "battle":
            sfx += [{"type": "cannon", "start": t0, "gain": 0.6}, {"type": "flutter", "start": t0, "end": t1, "gain": 0.2},
                    {"type": "volley", "start": t0 + 0.6, "end": min(t1, t0 + 1.8), "gain": 0.22}]
        elif kind == "map":
            sfx.append({"type": "drum", "start": t0, "end": t1 - 0.1, "period": 0.5, "gain": 0.25})
        else:
            sfx.append({"type": "wind", "start": t0, "end": t1, "gain": 0.28})
    return {"music": {"seed": 7, "root_hz": 110.0, "mode": "minor", "drum_from": duration + 1, "drum_to": duration + 1},
            "music_level": 1.0, "sfx_level": 0.8, "sfx": sfx}

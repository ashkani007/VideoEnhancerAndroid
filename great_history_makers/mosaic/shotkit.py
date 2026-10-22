"""Reusable shot helpers (episode-independent): camera curves, birds, smoke/dust puffs,
scaling bursts, per-tile fire/water colour animation, ground slicing for depth scenes,
waving standards, and the house grade."""
import math

import numpy as np

from . import fx
from .geom import S, T, ease_in_out, lerp
from .scene import FnItem, Layer, SpriteItem, make_sprite


def cam(dur, z=(1.0, 1.06), ox=(0, 0), oy=(0, 0), ease=True):
    def f(t):
        e = ease_in_out(t / dur) if ease else max(0.0, min(1.0, t / dur))
        return dict(zoom=lerp(z[0], z[1], e), ox=lerp(ox[0], ox[1], e), oy=lerp(oy[0], oy[1], e))
    return f


def birds(ctx, name, flock, speed, flap=0.42, col="outline"):
    def up(p):
        p.poly([(-14, 0), (-4, -8), (0, 0), (4, -8), (14, 0), (0, 3)], col)

    def down(p):
        p.poly([(-14, 4), (-4, 2), (0, 0), (4, 2), (14, 4), (0, 3)], col)
    a = make_sprite(ctx, up, (-20, -12, 40, 20), 3.0, name + "u", rows=0)
    b = make_sprite(ctx, down, (-20, -12, 40, 20), 3.0, name + "d", rows=0)

    def fn(t):
        out = []
        for (x, y, ph, s) in flock:
            spr = a if math.sin(2 * math.pi * t / flap + ph) > 0 else b
            out.append((spr.premult, T(x - speed * t, y + 6 * math.sin(t * 1.3 + ph)) @ S(s) @ spr.pixel_to_unit(), 1.0))
        return out
    return FnItem(fn)


def puffs(sprite, sources, rise=120, period=3.0, drift=25, alpha=0.5, grow=0.0):
    items = []
    for i, (x, y) in enumerate(sources):
        for j in range(2):
            ph = (i * 0.37 + j * 0.5) % 1.0

            def fn(t, x=x, y=y, ph=ph):
                c = (t / period + ph) % 1.0
                g = 1 + grow * c
                cx, cy = x + drift * c + 6 * math.sin(t + ph * 6), y - rise * c
                return [(sprite.premult, T(cx, cy) @ S(g) @ sprite.pixel_to_unit(), alpha * math.sin(math.pi * c))]
            items.append(FnItem(fn))
    return items


def burst(sprite, x, y, t0, dur=1.6, grow=2.2, drift=(30, -60), alpha=0.85, cx=0.0, cy=0.0):
    """One expanding, fading cloud (cannon / musket smoke) starting at t0."""
    def fn(t):
        c = (t - t0) / dur
        if c <= 0 or c >= 1:
            return []
        g = 0.35 + grow * (1 - (1 - c) ** 2)
        px, py = x + drift[0] * c, y + drift[1] * c
        return [(sprite.premult, T(px, py) @ S(g) @ T(-cx, -cy) @ sprite.pixel_to_unit(), alpha * (1 - c) ** 1.2)]
    return FnItem(fn)


def flash(sprite, x, y, t0, dur=0.12, s=1.0):
    def fn(t):
        c = (t - t0) / dur
        if c <= 0 or c >= 1:
            return []
        return [(sprite.premult, T(x, y) @ S(s * (0.8 + 0.4 * c)) @ sprite.pixel_to_unit(), 1 - c)]
    return FnItem(fn)


def flame_colors(tl, t, seed=0, amp=0.25, speed=11):
    if "_ph" not in tl:
        tl["_ph"] = np.random.default_rng(seed).uniform(0, 6.28, len(tl["color"])).astype(np.float32)
    f = 1 + amp * np.sin(tl["_ph"] + t * speed) * np.sin(tl["_ph"] * 2.3 + t * speed * 0.66)
    return np.clip(tl["color"] * f[:, None], 0, 255)


def shimmer_colors(tl, t, seed=0, amp=0.1, speed=2.4, kx=0.004, ky=0.03):
    if "_ph" not in tl:
        tl["_ph"] = np.random.default_rng(seed).uniform(0, 6.28, len(tl["color"])).astype(np.float32)
    w = np.sin(tl["_ph"] + t * speed + tl["cy"] * ky - tl["cx"] * kx)[:, None]
    return np.clip(tl["color"] * (1 + amp * w), 0, 255)


def ground_slices(ctx, g, draw, rect, tile, name, edges, overlap=30):
    """Slice one ground drawing by screen-y bands; each band gets the parallax of its centre depth."""
    layers = []
    x0, y0, w, h = rect
    for i in range(len(edges) - 1):
        ya = edges[i] - (overlap if i else 0)
        spr = make_sprite(ctx, draw, rect, tile, f"{name}_g{edges[i]}", clip=(x0, ya, x0 + w, edges[i + 1]))
        if spr is not None:
            layers.append(Layer(g.parallax(g.q_of_y((edges[i] + edges[i + 1]) / 2)), [SpriteItem(spr)]))
    return layers


def finish(sc, look="default", fade_in=0.0, fade_out=None, vignette=0.36, **kw):
    looks = {
        "default": dict(sat=1.24, vibrance=0.3, local=0.36),
        "warm": dict(sat=1.24, vibrance=0.3, local=0.36, warm=(1.09, 1.0, 0.86), cool=(0.9, 0.95, 1.1)),
        "interior": dict(sat=1.2, vibrance=0.3, local=0.42, warm=(1.1, 1.0, 0.84), cool=(0.88, 0.94, 1.12)),
        "cold": dict(sat=0.95, vibrance=0.2, local=0.4, warm=(1.0, 1.0, 1.02), cool=(0.84, 0.92, 1.16)),
        "night": dict(sat=1.18, vibrance=0.3, local=0.4, warm=(1.12, 0.98, 0.82), cool=(0.84, 0.9, 1.18)),
        "sea": dict(sat=1.15, vibrance=0.3, local=0.34, warm=(1.04, 1.0, 0.94), cool=(0.86, 0.94, 1.14)),
        "map": dict(sat=1.12, vibrance=0.25, local=0.3),
    }
    g = dict(looks[look])
    g.update(kw)
    fade = None
    if fade_out is not None:
        dur = sc.duration
        fade = lambda t: 1.0 - fade_out[1] * max(0.0, min(1.0, (t - (dur - fade_out[0])) / fade_out[0]))
    sc.fx = list(sc.fx) + [fx.CinematicGrade(fade=fade, **g), fx.Vignette(vignette)]
    return sc

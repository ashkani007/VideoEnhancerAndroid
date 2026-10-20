"""Reusable motion recipes for cut-out figures (angles in degrees, units in figure space).

Everything is built from smooth periodic functions so motion is calm and
loop-free of jitter. Amplitudes are deliberately small: the brief is an ancient
mosaic that has *subtly* come alive."""
import math

from .geom import smoothstep, wobble


def idle(t, seed=0.0, head=1.6, sway=0.45, arm=1.2, breath=3.0, wind=1.0):
    return {
        "body": (wobble(t, 0.11, seed, sway), 0.0, 0.0),
        "head": (wobble(t, 0.16, seed + 1, head), 0.0, breath * math.sin(t * 1.3 + seed)),
        "arm": (wobble(t, 0.14, seed + 2, arm), 0.0, 0.0),
        "hand": (wobble(t, 0.2, seed + 3, arm * 1.5), 0.0, 0.0),
        "_wind": wind,
    }


def walk(t, period=1.1, seed=0.0, swing=17.0, bob=7.0, arm=5.0):
    """Two-step walk cycle with knee bend and body bob (facing -x)."""
    ph = 2 * math.pi * (t / period) + seed
    s = math.sin(ph)
    knee_f = 22 * max(0.0, -math.cos(ph))      # bend while the leg swings through
    knee_b = 22 * max(0.0, math.cos(ph))
    return {
        "thigh_f": (swing * s, 0, 0),
        "shin_f": (-knee_f, 0, 0),
        "thigh_b": (-swing * s, 0, 0),
        "shin_b": (-knee_b, 0, 0),
        "body": (1.5 + 0.8 * math.sin(2 * ph), 0, -bob * abs(math.cos(ph))),
        "head": (1.2 * math.sin(ph * 0.5 + seed), 0, 0),
        "arm": (arm * -s * 0.4, 0, 0),
        "spear": (0, 0, 0),
        "_wind": 1.3,
    }


def gesture(t, t0, t1, t2, t3, angle):
    """0 -> angle between t0..t1, hold, back to 0 between t2..t3 (eased)."""
    if t < t1:
        return angle * smoothstep((t - t0) / max(1e-3, t1 - t0))
    return angle * (1 - smoothstep((t - t2) / max(1e-3, t3 - t2)))


def merge(*poses):
    out = {}
    for p in poses:
        for k, v in p.items():
            if k.startswith("_") or k not in out:
                out[k] = v
            else:
                a = out[k]
                out[k] = (a[0] + v[0], a[1] + v[1], a[2] + v[2])
    return out

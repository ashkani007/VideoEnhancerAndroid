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


def walk(t, period=1.1, seed=0.0, swing=21.0, bob=9.0, arm=9.0):
    """Two-step walk cycle (facing -x): alternating thighs, knee bend during the swing
    phase, body bob at double support, swinging spear arm with a counter-swaying spear,
    shield bounce and a small head nod. All limbs move on their own pivots."""
    ph = 2 * math.pi * (t / period) + seed
    s, c = math.sin(ph), math.cos(ph)
    return {
        "thigh_f": (swing * s, 0, 0),
        "shin_f": (-30 * max(0.0, c) ** 1.5, 0, 0),      # front leg swings forward when cos > 0
        "thigh_b": (-swing * s, 0, 0),
        "shin_b": (-30 * max(0.0, -c) ** 1.5, 0, 0),
        "body": (2.0 + 1.0 * math.sin(2 * ph), 0, -bob * abs(c)),
        "head": (2.2 * math.sin(2 * ph + 0.6), 0, 2.5 * math.sin(2 * ph)),
        "arm": (-arm * s, 0, 0),
        "hand": (3.0 * math.sin(ph + 0.4), 0, 0),
        "spear": (arm * s * 0.75 + 1.8 * math.sin(2 * ph + 0.9), 0, 0),
        "shield": (2.5 * math.sin(2 * ph + 1.2), 0, 4 * math.sin(2 * ph + 0.8)),
        "banner": (0, 0, 0),
        "_wind": 1.0,
        "_phase": seed * 0.3,
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


def gallop(t, period=0.62, seed=0.0, amp=26.0):
    """Four-beat-ish gallop: diagonal leg pairs, body pitch and bob, nodding neck,
    rider sways with the horse."""
    ph = 2 * math.pi * (t / period) + seed
    s = math.sin(ph)
    return {
        "leg_ff": (amp * s, 0, 0), "leg_hb": (amp * 0.9 * s, 0, 0),
        "leg_fb": (-amp * math.sin(ph + 0.6), 0, 0), "leg_hf": (-amp * 0.9 * math.sin(ph + 0.6), 0, 0),
        "body": (2.5 * math.sin(ph + 1.0), 0, -14 * abs(math.cos(ph))),
        "neck": (6 * math.sin(ph + 0.4), 0, 0),
        "rider": (-2.5 * math.sin(ph + 1.0), 0, 0),
        "rhead": (2 * math.sin(2 * ph), 0, 0),
        "rarm": (3 * math.sin(ph), 0, 0),
        "_wind": 1.4,
    }


def amble(t, period=1.3, seed=0.0):
    """Slow donkey/horse walk."""
    p = gallop(t, period, seed, amp=14.0)
    p["body"] = (0.8 * math.sin(2 * math.pi * t / period * 2 + seed), 0, -4 * abs(math.cos(2 * math.pi * t / period + seed)))
    p["_wind"] = 0.6
    return p


def work(t, kind, period=1.1, seed=0.0):
    """Small repeated labour actions on the 'arm' part: hammer strikes, placing bricks,
    pressing a stylus into clay. Sharp downbeat, slow recovery."""
    ph = ((t / period) + seed / 6.283) % 1.0
    if kind == "hammer":
        a = -55 * (1 - ph) ** 3 + 0 if ph < 0.35 else -55 * smoothstep((ph - 0.35) / 0.65)
        a = 10 + a
    elif kind == "brick":
        a = -38 * math.sin(math.pi * ph) ** 2
    elif kind == "stylus":
        a = -6 * abs(math.sin(2 * math.pi * ph * 2))
    else:
        a = 4 * math.sin(2 * math.pi * ph)
    base = idle(t, seed, head=1.6, sway=0.6, arm=0.0)
    base["arm"] = (a, 0, 0)
    base["head"] = (base["head"][0] + (4 if kind in ("hammer", "stylus") else 0), 0, base["head"][2])
    return base


def pray(t, t0=0.4, seed=0.0):
    """Mesopotamian gesture of greeting/prayer: one hand raised before the face."""
    p = idle(t, seed, head=1.0, arm=0.8)
    p["arm"] = (p["arm"][0] - 62 * smoothstep((t - t0) / 0.9), 0, 0)
    return p

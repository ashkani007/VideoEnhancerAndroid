"""Keyframe animation: eased tracks with holds, anticipation/overshoot helpers and a damped spring
for secondary motion (coat tails, fringe, plume) driven by the primary motion."""
import math


def ease(u, kind="io"):
    u = min(1.0, max(0.0, u))
    if kind == "lin":
        return u
    if kind == "in":
        return u * u * u
    if kind == "out":
        return 1 - (1 - u) ** 3
    if kind == "back":                         # overshoot then settle (snappy gestures)
        s = 1.70158 * 1.2
        v = u - 1
        return 1 + v * v * ((s + 1) * v + s)
    return u * u * (3 - 2 * u) if kind == "smooth" else (0.5 - 0.5 * math.cos(math.pi * u))


class Track:
    """Keys [(t, value, ease_into_this_key)]; values may be numbers or tuples."""

    def __init__(self, keys):
        self.k = sorted(keys, key=lambda x: x[0])

    def __call__(self, t):
        k = self.k
        if t <= k[0][0]:
            return k[0][1]
        for a, b in zip(k, k[1:]):
            if t <= b[0]:
                u = ease((t - a[0]) / max(1e-6, b[0] - a[0]), b[2] if len(b) > 2 else "io")
                if isinstance(a[1], tuple):
                    return tuple(x + (y - x) * u for x, y in zip(a[1], b[1]))
                return a[1] + (b[1] - a[1]) * u
        return k[-1][1]


def spring(signal, t, k=60.0, c=7.0, dt=1 / 120.0, t0=0.0):
    """Damped spring following signal(t) from t0: returns the lagging value at t (deterministic)."""
    x, v = signal(t0), 0.0
    s = t0
    while s < t:
        a = k * (signal(s) - x) - c * v
        v += a * dt
        x += v * dt
        s += dt
    return x


def blink(t, times, dur=0.16):
    for b in times:
        u = (t - b) / dur
        if 0 <= u <= 1:
            return u / 0.4 if u < 0.4 else (1.0 if u < 0.55 else 1 - (u - 0.55) / 0.45)
    return 0.0

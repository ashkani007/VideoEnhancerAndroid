import math

import numpy as np


def T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1.0]])


def S(sx, sy=None):
    sy = sx if sy is None else sy
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1.0]])


def R(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def about(px, py, M):
    return T(px, py) @ M @ T(-px, -py)


# ---- easing / timing helpers ----
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_in_out(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def lerp(a, b, t):
    return a + (b - a) * t


def wobble(t, freq, seed=0.0, amp=1.0):
    """Smooth pseudo-random motion: sum of incommensurate sines (no jitter)."""
    return amp * (0.6 * math.sin(2 * math.pi * freq * t + seed * 1.7)
                  + 0.3 * math.sin(2 * math.pi * freq * 1.618 * t + seed * 3.1)
                  + 0.1 * math.sin(2 * math.pi * freq * 2.71 * t + seed * 5.3))

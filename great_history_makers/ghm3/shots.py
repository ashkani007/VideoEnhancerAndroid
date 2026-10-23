"""Proof-of-concept shots for Cinematic Living Illustration (Napoleon, Italy 1796).

Shot A (close-up, night tent): the young general studies the campaign map by candlelight,
  scans it, then lifts his eyes as he makes the decision; brows set, jaw tightens.
Shot B (wide, dawn): what he has decided: his columns advance through smoke under wind-torn
  banners while he watches from the ridge in the foreground; the light dims as smoke rolls in.
All acting is keyed to absolute shot time; the camera is a slow motivated push or truck."""
import math

import cv2
import numpy as np

from ghm2.anim import keys, smooth
from .character import Bonaparte
from .paint import Canvas, bloom, catmull, fbm, noise, paint_finish, ramp, scroll, soft

CANDLE = (905, 1385)


def flicker(t, seed=0.0):
    return 0.86 + 0.07 * math.sin(t * 11.3 + seed) + 0.05 * math.sin(t * 6.7 + 1.3 + seed) + 0.03 * math.sin(t * 23.1)


# =============================================================================== shot A
def acting_a(t):
    """Keyframed performance (seconds). The eyes lead, the head follows, then the face sets."""
    p = dict(
        gy=keys([[0, 0.85], [2.25, 0.85], [2.6, -0.05], [5.5, -0.1]], t),
        gx=keys([[0, -0.15], [0.7, -0.15], [0.8, 0.25], [1.5, 0.25], [1.6, -0.05], [2.25, 0.0], [2.6, 0.35], [4.0, 0.3],
                 [4.1, 0.38], [5.5, 0.36]], t),
        lid=keys([[0, 0.78], [2.3, 0.78], [2.75, 0.97], [3.6, 0.88], [5.5, 0.86]], t),
        pitch=keys([[0, -9.0], [2.4, -9.0], [3.15, 0.5], [5.5, 1.2]], t),
        yaw=keys([[0, -2.0], [2.4, -2.0], [3.2, 2.5], [5.5, 3.0]], t),
        roll=keys([[0, 1.5], [2.4, 1.5], [3.2, -0.5], [5.5, -0.8]], t),
        knit=keys([[0, 0.25], [2.5, 0.25], [3.0, 1.0], [5.5, 1.0]], t),
        raise_=0.0,
        tense=keys([[0, 0.1], [2.8, 0.1], [3.3, 1.0], [5.5, 1.0]], t),
        breath=math.sin(2 * math.pi * t / 3.9) * (1 - 0.6 * smooth((t - 2.3) / 0.6)) + 1.4 * smooth((t - 2.35) / 0.35) * (1 - smooth((t - 3.4) / 1.2)),
    )
    p["raise"] = p.pop("raise_")
    for b in (1.15, 4.35):                                   # blinks: one while reading, one after the decision
        u = (t - b) / 0.17
        if 0 <= u <= 1:
            p["blink"] = min(1.0, u / 0.35) if u < 0.35 else (1.0 if u < 0.5 else 1 - (u - 0.5) / 0.5)
    p["flicker"] = flicker(t)
    return p


def tent(cv, t, f):
    """Canvas wall with soft vertical folds lit by the candle; deep falloff into darkness."""
    X, Y = cv.X, cv.Y
    folds = 0.5 + 0.5 * np.sin(X / 58 + 0.8 * np.sin(Y / 300)) * 0.6 + 0.25 * np.sin(X / 23 + 1.7)
    d = np.hypot(X - CANDLE[0], (Y - CANDLE[1]) * 0.8)
    light = (0.06 + 0.9 * np.exp(-d / 520) * f) * (0.75 + 0.25 * folds)
    cv.rgb[:] = ramp(light, [(0, (6, 4, 6)), (0.25, (30, 16, 14)), (0.55, (92, 48, 28)), (0.9, (176, 102, 52))])
    # tent pole, out of focus, left
    pole = (X > 120) & (X < 150)
    cv.rgb[pole] *= 0.35
    cv.rgb[:] = cv2.GaussianBlur(cv.rgb, (0, 0), 6 * cv.k)


def table(cv, t, f):
    """Campaign map on the table, foreground, under the candle (slightly soft focus)."""
    poly = np.array([(-60, 1530), (1140, 1470), (1140, 2000), (-60, 2000)])
    sl = cv.roi_of(poly, pad=10)
    if sl is None:
        return
    d = cv.sdf(poly, sl)
    a = soft(d, 2.0)
    X, Y = cv.X[sl], cv.Y[sl]
    dist = np.hypot(X - CANDLE[0], Y - (CANDLE[1] + 160))
    v = 0.1 + 0.95 * np.exp(-dist / 560) * f
    paper = ramp(v * (1 + 0.06 * noise(X.shape, 6 * cv.k, 21)), [(0, (16, 10, 8)), (0.4, (96, 70, 44)), (0.8, (214, 176, 120)), (1.1, (250, 224, 170))])
    ink = np.zeros(X.shape, np.float32)
    off = (sl[1].start, sl[0].start)
    def line(pts, w, c=1.0):
        q = np.array([cv.px(*p) for p in pts]) - off
        cv2.polylines(ink, [(q * 4).astype(np.int32)], False, c, max(1, int(w * cv.k)), cv2.LINE_AA, shift=2)
    line(catmull([(40, 1640), (260, 1600), (420, 1660), (600, 1620), (820, 1700), (1100, 1660)], False), 6)   # the river
    line(catmull([(120, 1900), (300, 1760), (430, 1680)], False), 3)
    for x, y in ((520, 1700), (640, 1690), (700, 1760)):                                                     # Austrian blocks
        cv2.rectangle(ink, tuple((np.array(cv.px(x, y)) - off).astype(int)), tuple((np.array(cv.px(x + 46, y + 18)) - off).astype(int)), 0.7, -1)
    paper = paper * (1 - ink[..., None] * 0.75) + ink[..., None] * np.array([0.08, 0.05, 0.04])
    blue = np.zeros_like(ink)
    for x, y in ((300, 1780), (360, 1800)):
        cv2.rectangle(blue, tuple((np.array(cv.px(x, y)) - off).astype(int)), tuple((np.array(cv.px(x + 46, y + 18)) - off).astype(int)), 1.0, -1)
    paper = paper * (1 - blue[..., None] * 0.8) + blue[..., None] * np.array([0.12, 0.18, 0.42]) * (v[..., None] * 1.2)
    cv.over(sl, paper, a)
    cv.rgb[sl] = cv.rgb[sl] * (1 - a[..., None]) + cv2.GaussianBlur(cv.rgb[sl], (0, 0), 2.5 * cv.k) * a[..., None]


def candle(cv, t, f):
    x, y = CANDLE
    wax = np.array([(x - 26, y + 6), (x + 26, y + 4), (x + 28, y + 230), (x - 28, y + 232)])
    sl = cv.roi_of(wax, 30)
    if sl is not None:
        d = cv.sdf(wax, sl)
        X = cv.X[sl]
        v = 0.35 + 0.55 * np.clip(1 - np.abs(X - x) / 30, 0, 1) * f
        cv.over(sl, ramp(v, [(0, (60, 40, 30)), (0.6, (230, 200, 160)), (1, (255, 244, 220))]), soft(d, 2.5))
    sway = 3 * math.sin(t * 2.3) + 2 * math.sin(t * 5.1)
    hgt = 52 * f
    flame = catmull([(x, y - hgt), (x + 12 + sway * 0.3, y - hgt * 0.45), (x + 9, y - 6), (x, y + 2), (x - 9, y - 6),
                     (x - 12 + sway * 0.3, y - hgt * 0.45)], n=10)
    flame[:, 0] += sway * np.clip((y - flame[:, 1]) / hgt, 0, 1) ** 2
    sl = cv.roi_of(flame, 40)
    if sl is not None:
        d = cv.sdf(flame, sl, ss=3)
        cv.over(sl, (1.0, 0.55, 0.18), soft(d + 2, 3.0))
        cv.over(sl, (1.0, 0.85, 0.5), soft(d + 6, 3.0))
        cv.over(sl, (1.0, 0.98, 0.9), soft(d + 10, 2.5))
    # warm glow around the flame
    g = np.exp(-((cv.X - x) ** 2 + (cv.Y - (y - 26)) ** 2) / (2 * 90 ** 2)) * 0.55 * f
    cv.rgb += g[..., None] * np.array([1.0, 0.62, 0.28], np.float32)


def smoke_wisp(cv, t):
    """A thin wisp rising from the flame and curling in the tent air."""
    x, y = CANDLE
    pts = []
    for i in range(40):
        u = i / 39
        yy = y - 70 - u * 700
        xx = x + 30 * math.sin(u * 7 - t * 1.6) * u + 60 * u * math.sin(t * 0.4 + u * 3)
        pts.append((xx, yy))
    pts = np.array(pts)
    sl = cv.roi_of(pts, 60)
    if sl is None:
        return
    m = np.zeros((sl[0].stop - sl[0].start, sl[1].stop - sl[1].start), np.float32)
    q = np.array([cv.px(*p) for p in pts]) - (sl[1].start, sl[0].start)
    for i in range(len(q) - 1):
        cv2.line(m, tuple((q[i] * 4).astype(int)), tuple((q[i + 1] * 4).astype(int)), float(0.5 * (1 - i / 40)),
                 max(1, int((3 + i * 0.6) * 1.5 * cv.k)), cv2.LINE_AA, shift=2)
    m = cv2.GaussianBlur(m, (0, 0), 6 * cv.k)
    cv.rgb[sl] += m[..., None] * np.array([0.34, 0.26, 0.2], np.float32)


def shot_a(W, H, t, dur=5.6):
    z = 1.0 + 0.075 * smooth(t / dur)
    cv = Canvas(W, H, zoom=z, focus=(560 + 10 * smooth(t / dur), 930 - 20 * smooth(t / dur)))
    f = flicker(t)
    tent(cv, t, f)
    hero = Bonaparte(center=(470, 900), scale=600, light=(CANDLE[0], CANDLE[1] - 30))
    hero.draw(cv, acting_a(t))
    table(cv, t, f)
    candle(cv, t, f)
    smoke_wisp(cv, t)
    # dust motes drifting through the candle light
    r = np.random.default_rng(5)
    P0 = r.uniform([0, 400], [1080, 1700], (40, 2))
    m = np.zeros((H, W), np.float32)
    for (px, py), ph in zip(P0, r.uniform(0, 6.28, 40)):
        X, Y = cv.px(px + 20 * math.sin(t * 0.3 + ph), py - 12 * t)
        cv2.circle(m, (int(X), int(Y)), max(1, int(2 * cv.k)), float(0.5 + 0.5 * math.sin(t + ph)), -1, cv2.LINE_AA)
    lightmap = np.exp(-np.hypot(cv.X - CANDLE[0], cv.Y - CANDLE[1]) / 600)
    cv.rgb += (cv2.GaussianBlur(m, (0, 0), 1.2 * cv.k) * lightmap)[..., None] * np.array([0.6, 0.42, 0.25]) * 0.6
    return finish(cv, warm=True)


def finish(cv, warm=True):
    rgb = cv.rgb
    bloom(rgb, 0.7, 26, 0.45, cv.s)
    paint_finish(rgb, cv.s)
    H, W = rgb.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1 - 0.55 * np.clip(np.hypot((xx - W / 2) / (W / 2), (yy - H * 0.47) / (H / 2)) / 1.25, 0, 1) ** 2
    rgb *= vig[..., None]
    # filmic toe/shoulder + split tone (warm highlights, cool shadows)
    L = rgb.mean(2, keepdims=True)
    rgb[:] = rgb + (1 - np.clip(L, 0, 1)) ** 3 * np.array([-0.004, 0.0, 0.025]) + np.clip(L, 0, 1) ** 2 * np.array([0.03, 0.01, -0.03])
    rgb[:] = rgb / (1 + 0.25 * rgb)
    rgb *= 1.18
    return np.clip(rgb, 0, 1)


# =============================================================================== shot B
SUN = (770, 985)


def _mix(a, b, u):
    return np.asarray(a, np.float32) * (1 - u) + np.asarray(b, np.float32) * u


def sky(cv, t, dim):
    X, Y = cv.X, cv.Y
    v = np.clip((Y - 200) / 820, 0, 1)
    top, mid, hor = np.array([34, 40, 62]) / 255, np.array([116, 92, 96]) / 255, np.array([238, 156, 92]) / 255
    col = np.where(v[..., None] < 0.6, top + (mid - top) * (v[..., None] / 0.6), mid + (hor - mid) * ((v[..., None] - 0.6) / 0.4))
    d = np.hypot(X - SUN[0], Y - SUN[1])
    col = col + (np.exp(-d / 260) * 0.9 + np.exp(-d / 40) * 1.6)[..., None] * np.array([1.0, 0.72, 0.42]) * dim
    cv.rgb[:] = col


def hills(cv, t, cam):
    for depth, base, amp, col, seed in ((0.15, 1000, 40, (120, 96, 104), 1), (0.3, 1050, 55, (84, 70, 78), 2)):
        xs = np.linspace(-200, 1300, 60)
        r = np.random.default_rng(seed)
        ys = base - amp * (0.6 * np.sin(xs / 210 + seed) + 0.4 * np.sin(xs / 90 + 2 * seed)) - r.uniform(0, 8, len(xs))
        pts = np.vstack([np.stack([xs - cam * depth, ys], 1), [(1300, 1500), (-200, 1500)]])
        sl = cv.roi_of(pts, 5)
        a = soft(cv.sdf(pts, sl), 3.0)
        cv.over(sl, np.asarray(col, np.float32) / 255, a)
    # valley floor: muted fields receding into haze
    sl = cv.roi(-50, 1040, 1130, 1600)
    Y = cv.Y[sl]
    X = cv.X[sl]
    haze = np.clip((1260 - Y) / 220, 0, 1)
    fields = 0.5 + 0.5 * np.sin((X - cam * 0.5) / 70 + Y / 40) * np.clip((Y - 1060) / 300, 0, 1)
    floor = _mix((58, 56, 40), (82, 74, 46), fields[..., None] * 0.5) / 255
    floor = floor * (1 - haze[..., None]) + np.array([150, 112, 100]) / 255 * haze[..., None]
    a = np.clip((Y - 1062) / 6, 0, 1)
    cv.over(sl, floor, a)


def smoke(cv, t, cam, density, front=False):
    H, W = cv.H, cv.W
    s = cv.s
    n1 = scroll(fbm(H, W, s, 41 if not front else 47), (-28 * t - cam * (0.5 if not front else 0.9)) * cv.k, -3 * t * cv.k)
    n2 = scroll(fbm(H, W, s, 43 if not front else 49, scales=(140, 60, 24)), (-45 * t - cam * 0.6) * cv.k, -6 * t * cv.k)
    n = 0.65 * n1 + 0.35 * n2
    Y, X = cv.Y, cv.X
    band = np.exp(-((Y - (1180 if not front else 1430)) / (190 if not front else 160)) ** 2)
    a = np.clip((n * 0.9 + 0.35 + density * 0.5) * band * (0.9 + density), 0, 1) * (0.75 if not front else 0.55)
    d = np.hypot(X - SUN[0], Y - SUN[1])
    lit = np.exp(-d / 420) * (1.2 - density * 0.6)
    col = _mix((92, 86, 92), (178, 150, 130), np.clip(n * 0.4 + 0.5, 0, 1)[..., None]) / 255
    col = col + lit[..., None] * np.array([0.9, 0.55, 0.28])
    cv.rgb[:] = cv.rgb * (1 - a[..., None]) + col * a[..., None]


def soldier(m, rim, cv, x, y, h, phase, carry_flag=False):
    """A marching 1796 fusilier silhouette (bicorne, musket with bayonet on the shoulder)."""
    k = cv.k
    P = lambda dx, dy: (int((cv.px(x + dx * h, y + dy * h)[0]) * 4), int((cv.px(x + dx * h, y + dy * h)[1]) * 4))
    sw = math.sin(phase)
    bob = abs(math.cos(phase)) * 0.015
    w = max(1, int(0.09 * h * k))
    cv2.line(m, P(0, -0.48 + bob), P(-0.10 * sw, 0), 1.0, w, cv2.LINE_AA, shift=2)           # legs
    cv2.line(m, P(0, -0.48 + bob), P(0.10 * sw, 0), 1.0, w, cv2.LINE_AA, shift=2)
    body = np.array([P(-0.13, -0.50 + bob), P(0.12, -0.50 + bob), P(0.11, -0.86 + bob), P(-0.10, -0.88 + bob)], np.int32)
    cv2.fillConvexPoly(m, body, 1.0, cv2.LINE_AA, shift=2)
    cv2.circle(m, P(0, -0.94 + bob), max(1, int(0.075 * h * k)), 1.0, -1, cv2.LINE_AA, shift=2)       # head
    hat = np.array([P(-0.17, -0.99 + bob), P(0.17, -0.99 + bob), P(0.0, -1.10 + bob)], np.int32)      # bicorne
    cv2.fillConvexPoly(m, hat, 1.0, cv2.LINE_AA, shift=2)
    cv2.line(m, P(-0.06, -0.80 + bob), P(-0.30, -1.32 + bob), 1.0, max(1, int(0.03 * h * k)), cv2.LINE_AA, shift=2)  # musket
    cv2.line(rim, P(-0.30, -1.32 + bob), P(-0.36, -1.46 + bob), 1.0, max(1, int(0.015 * h * k)), cv2.LINE_AA, shift=2)  # bayonet glint
    cv2.line(rim, P(0.11, -0.86 + bob), P(0.10, -0.52 + bob), 1.0, max(1, int(0.03 * h * k)), cv2.LINE_AA, shift=2)    # sunlit edge


def flag(cv, x, y, h, t, seed, haze):
    """Tricolour on a pole, cloth waving left with the wind, glowing when backlit."""
    pole_top = (x, y - 2.2 * h)
    sl = cv.roi(x - 2.2 * h, y - 2.4 * h, x + 0.1 * h, y + 5)
    if sl is None:
        return
    m = np.zeros((sl[0].stop - sl[0].start, sl[1].stop - sl[1].start, 3), np.float32)
    a = np.zeros(m.shape[:2], np.float32)
    ox, oy = sl[1].start, sl[0].start
    p0, p1 = cv.px(x, y), cv.px(*pole_top)
    cv2.line(a, (int((p0[0] - ox) * 4), int((p0[1] - oy) * 4)), (int((p1[0] - ox) * 4), int((p1[1] - oy) * 4)), 1.0,
             max(1, int(0.04 * h * cv.k)), cv2.LINE_AA, shift=2)
    fw, fh = 1.3 * h, 0.8 * h
    cols = [(0.16, 0.24, 0.62), (0.95, 0.92, 0.86), (0.78, 0.12, 0.12)]
    N = 24
    for i in range(N):
        u0, u1 = i / N, (i + 1) / N
        wav = lambda u: (math.sin(u * 7 - t * 7 + seed) * 0.12 + math.sin(u * 3 - t * 4) * 0.06) * fh * u
        qs = [(pole_top[0] - u0 * fw, pole_top[1] + wav(u0)), (pole_top[0] - u1 * fw, pole_top[1] + wav(u1)),
              (pole_top[0] - u1 * fw, pole_top[1] + fh + wav(u1)), (pole_top[0] - u0 * fw, pole_top[1] + fh + wav(u0))]
        q = np.array([[(cv.px(*p)[0] - ox) * 4, (cv.px(*p)[1] - oy) * 4] for p in qs], np.int32)
        band = cols[min(2, int((1 - (u0 + u1) / 2) * 3))]
        shade = 0.75 + 0.35 * math.cos(u0 * 7 - t * 7 + seed)
        poly = np.zeros_like(a)
        cv2.fillConvexPoly(poly, q, 1.0, cv2.LINE_AA, shift=2)
        m = m * (1 - poly[..., None]) + np.array(band) * shade * poly[..., None]
        a = np.maximum(a, poly)
    m = m * (1 - haze) + np.array([0.75, 0.6, 0.55]) * haze
    cv.over(sl, m, a)


def troops(cv, t, cam, dim):
    H, W = cv.H, cv.W
    m = np.zeros((H, W), np.float32)
    rim = np.zeros((H, W), np.float32)
    flags = []
    for col, (x0, y0, rows, depth) in enumerate(((760, 1250, 6, 0.55), (1010, 1330, 7, 0.7))):
        for r in range(rows):
            for f in range(8):
                y = y0 + r * 14 + f * 3
                q = 0.55 + (y - 1150) / 320                         # perspective size
                h = 62 * q
                x = x0 + f * 15 * q - r * 9 - 26 * t - cam * depth + (r % 2) * 6
                ph = t * 6.2 + r * 0.9 + f * 0.37 + col
                soldier(m, rim, cv, x, y, h, ph)
            if r == 1:
                flags.append((x0 - r * 9 - 26 * t - cam * depth + 40, y0 + 20, 62 * (0.55 + (y0 + 20 - 1150) / 320), col))
    m = cv2.GaussianBlur(m, (0, 0), 0.6 * cv.k)
    rim = cv2.GaussianBlur(rim, (0, 0), 0.6 * cv.k)
    haze = np.clip((1330 - cv.Y) / 260, 0, 0.55)[..., None]
    silcol = np.array([0.08, 0.07, 0.09]) * (1 - haze) + np.array([0.42, 0.34, 0.34]) * haze
    cv.rgb[:] = cv.rgb * (1 - m[..., None]) + silcol * m[..., None]
    cv.rgb += rim[..., None] * np.array([1.0, 0.7, 0.4]) * 0.9 * dim
    for x, y, h, col in flags:
        flag(cv, x, y, h, t, col * 1.7, 0.2)


def cannon_flashes(cv, t, cam):
    for t0, x, y in ((6.2, 380, 1090), (7.4, 180, 1110), (9.1, 520, 1080), (10.6, 290, 1100)):
        u = t - t0
        if 0 <= u < 1.2:
            f = math.exp(-u * 9) * 1.6
            d = np.hypot(cv.X - (x - cam * 0.35), cv.Y - y)
            cv.rgb += (np.exp(-d / 45) * f + np.exp(-d / 180) * f * 0.25)[..., None] * np.array([1.0, 0.62, 0.3])


GEN_BODY = [(178, 1232), (132, 1246), (108, 1272), (100, 1330), (114, 1470), (150, 1560), (128, 1700), (96, 1930),
            (486, 1930), (452, 1700), (418, 1560), (440, 1430), (452, 1300), (430, 1258), (392, 1236)]
GEN_ARM = [(424, 1262), (462, 1296), (472, 1430), (446, 1500), (366, 1532), (334, 1516), (350, 1488), (422, 1456), (428, 1330)]


def general(cv, t, cam, dim):
    """The young general from behind, foreground left: rim-lit by the sun; hair, coat skirts and
    plume move in the wind; head turns slowly to follow the columns, shoulders breathe."""
    dx = -cam * 1.25
    turn = keys([[5.6, -0.4], [8.5, 0.6], [12.5, 1.0]], t)               # head follows the advance
    breath = math.sin(2 * math.pi * (t - 5.6) / 3.6) * 3
    wind = math.sin(t * 2.1) * 0.6 + math.sin(t * 5.3) * 0.4

    def body_pt(x, y):
        lift = breath * (1.0 if y < 1320 else 0.3)
        flut = (10 * wind * ((y - 1600) / 330)) if y > 1600 else 0.0      # skirts stream left in the wind
        return (x + dx - flut, y - lift)
    body = catmull([body_pt(x, y) for x, y in GEN_BODY], n=8)
    arm = catmull([body_pt(x, y) for x, y in GEN_ARM], n=8)
    hx, hy = 286 + dx + 12 * turn, 1150 - breath * 0.7
    head = catmull([(hx - 58, hy - 26), (hx - 18, hy - 74), (hx + 40, hy - 72), (hx + 66, hy - 16), (hx + 58, hy + 56),
                    (hx + 18, hy + 88), (hx - 38, hy + 86), (hx - 64, hy + 36)])
    hair = catmull([(hx - 64, hy - 20), (hx + 64, hy - 20), (hx + 74, hy + 96 + 6 * wind), (hx + 34, hy + 124),
                    (hx - 44, hy + 124 - 8 * wind), (hx - 82 - 10 * wind, hy + 96)])
    w = 1 + 0.12 * turn
    hat = catmull([(hx - 142 * w, hy - 58), (hx - 70 * w, hy - 70), (hx - 8, hy - 128), (hx + 60 * w, hy - 74),
                   (hx + 138 * w, hy - 62), (hx + 60 * w, hy - 46), (hx, hy - 44), (hx - 70 * w, hy - 46)], n=8)
    plume = catmull([(hx - 8, hy - 122), (hx - 26 - 12 * wind, hy - 168), (hx + 4 - 16 * wind, hy - 196), (hx + 18, hy - 132)], n=8)
    ep = (446 + dx, 1270 - breath)
    for poly, edge in ((body, 1.5), (arm, 1.5), (hair, 2.5), (head, 1.5), (hat, 1.2)):
        sl = cv.roi_of(poly, 20)
        if sl is None:
            continue
        d = cv.sdf(poly, sl)
        a = soft(d, edge)
        X, Y = cv.X[sl], cv.Y[sl]
        folds = 0.025 * np.sin((X - dx) / 18 + Y / 160) * np.clip((Y - 1500) / 300, 0, 1)
        core = np.array([0.04, 0.04, 0.058]) + (0.02 * noise(X.shape, 5 * cv.k, 7) + folds)[..., None]
        dl = cv.sdf(poly + [-10, 5], sl)
        rimm = np.clip(dl / 10, 0, 1) * a * dim
        col = core + rimm[..., None] * np.array([1.0, 0.62, 0.32]) * 0.95
        cv.over(sl, col, a)
    # gold epaulette catching the sun, fringe swinging
    eps = catmull([(ep[0] - 38, ep[1] + 2), (ep[0], ep[1] - 16), (ep[0] + 36, ep[1] + 4), (ep[0], ep[1] + 16)], n=8)
    sl = cv.roi_of(eps, 40)
    cv.over(sl, np.array([0.36, 0.25, 0.1]) + np.array([0.5, 0.36, 0.14]) * dim, soft(cv.sdf(eps, sl), 1.5))
    m = np.zeros((sl[0].stop - sl[0].start, sl[1].stop - sl[1].start), np.float32)
    for k in range(9):
        x = ep[0] - 30 + k * 7.5
        a0, b0 = cv.px(x, ep[1] + 10), cv.px(x - 3 * wind, ep[1] + 40)
        cv2.line(m, (int((a0[0] - sl[1].start) * 4), int((a0[1] - sl[0].start) * 4)),
                 (int((b0[0] - sl[1].start) * 4), int((b0[1] - sl[0].start) * 4)), 1.0, max(1, int(2.5 * cv.k)), cv2.LINE_AA, shift=2)
    cv.over(sl, np.array([0.3, 0.2, 0.08]) + np.array([0.6, 0.42, 0.18]) * dim, cv2.GaussianBlur(m, (0, 0), 0.6))
    sl = cv.roi_of(plume, 20)
    cv.over(sl, np.array([0.62, 0.14, 0.12]) * (0.6 + 0.4 * dim), soft(cv.sdf(plume, sl), 2.5) * 0.9)


def ridge(cv, t, cam):
    xs = np.linspace(-200, 1300, 80)
    ys = 1560 + 30 * np.sin(xs / 160) + 18 * np.sin(xs / 47)
    pts = np.vstack([np.stack([xs - cam * 1.25, ys], 1), [(1300, 1990), (-200, 1990)]])
    sl = cv.roi_of(pts, 5)
    cv.over(sl, (0.05, 0.045, 0.04), soft(cv.sdf(pts, sl), 2.0))
    m = np.zeros((cv.H, cv.W), np.float32)
    r = np.random.default_rng(9)
    for x in r.uniform(-200, 1300, 260):
        y0 = 1560 + 30 * math.sin(x / 160) + 18 * math.sin(x / 47) + r.uniform(0, 20)
        L = r.uniform(18, 55)
        lean = math.sin(t * 2.3 + x * 0.05) * 6 - 6
        a, b = cv.px(x - cam * 1.25, y0), cv.px(x - cam * 1.25 + lean, y0 - L)
        cv2.line(m, (int(a[0] * 4), int(a[1] * 4)), (int(b[0] * 4), int(b[1] * 4)), 1.0, max(1, int(3.0 * cv.k)),
                 cv2.LINE_AA, shift=2)
    m = cv2.GaussianBlur(m, (0, 0), 0.7 * cv.k)
    cv.rgb[:] = cv.rgb * (1 - m[..., None]) + np.array([0.06, 0.05, 0.04]) * m[..., None]
    cv.rgb += m[..., None] * np.exp(-np.hypot(cv.X - SUN[0], cv.Y - 1560) / 500)[..., None] * np.array([0.25, 0.15, 0.08])


def shot_b(W, H, t, t0=5.6, dur=7.0):
    u = (t - t0) / dur
    cam = 70 * u                                       # slow truck following the advance
    dim = 1.0 - 0.45 * smooth((t - (t0 + 4.4)) / 2.2)  # smoke rolls in: the light fails
    cv = Canvas(W, H, zoom=1.0 + 0.03 * u, focus=(560, 1000))
    sky(cv, t, dim)
    hills(cv, t, cam)
    density = 0.15 + 0.5 * smooth((t - (t0 + 4.0)) / 2.5)
    smoke(cv, t, cam, density)
    cannon_flashes(cv, t, cam)
    troops(cv, t, cam, dim)
    smoke(cv, t, cam, density, front=True)
    # god rays through the smoke
    X, Y = cv.X, cv.Y
    ang = np.arctan2(Y - SUN[1], X - SUN[0])
    rays = (0.5 + 0.5 * np.sin(ang * 17 + 0.3 * math.sin(t * 0.4))) * (0.5 + 0.5 * np.sin(ang * 41 + 1.3)) * np.exp(-np.hypot(X - SUN[0], Y - SUN[1]) / 600)
    cv.rgb += cv2.GaussianBlur(rays.astype(np.float32), (0, 0), 8 * cv.k)[..., None] * np.array([0.5, 0.33, 0.18]) * 0.16 * dim
    ridge(cv, t, cam)
    general(cv, t, cam, dim)
    # drifting ash
    r = np.random.default_rng(12)
    P0 = r.uniform([0, 300], [1080, 1900], (70, 2))
    m = np.zeros((H, W), np.float32)
    for (px, py), ph in zip(P0, r.uniform(0, 6.28, 70)):
        x, y = cv.px((px - 40 * t - cam) % 1200 - 60, py + 10 * math.sin(t + ph))
        cv2.circle(m, (int(x), int(y)), max(1, int(1.6 * cv.k)), float(0.4 + 0.4 * math.sin(t * 2 + ph)), -1, cv2.LINE_AA)
    cv.rgb += cv2.GaussianBlur(m, (0, 0), 1.0 * cv.k)[..., None] * np.array([0.7, 0.55, 0.45]) * 0.5
    # the mood turns: cooler, flatter as the smoke takes the sun
    cool = 1 - dim
    cv.rgb[:] = cv.rgb * (1 - 0.5 * cool) + cv.rgb.mean(2, keepdims=True) * np.array([0.8, 0.86, 1.0]) * 0.5 * cool
    return finish(cv)

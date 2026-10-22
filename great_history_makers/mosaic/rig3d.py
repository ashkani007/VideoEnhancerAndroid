"""Sculptural 2.5D figures: banded form shading, an articulated soldier rig, IK gait and a
self-shadowing walker renderer. Reusable for any episode (see PROMPT_LIBRARY/README.md).

* sculpt_bands(): quantises a lit 'inflated' volume of each part into 5 tone bands BEFORE
  tessellation, so tesserae rows follow the form (opus vermiculatum) - stones stay flat-coloured.
* soldier_v3(): Persian infantryman after Persepolis / Herodotus 7.61 (felt tiara, sleeved tunic
  over scale corselet, trousers, wicker spara, spear with pomegranate butt). Parts: torso, head,
  near upper arm, near forearm+hand, spear, far arm, shield, quiver, thigh/shin/foot x2.
* gait_ik(): heel strike -> flat foot -> heel-off -> toe-off -> swing arc, solved with 2-bone IK
  from planted foot targets. Pelvis height follows leg reach (natural bob), torso lean and
  counter-rotation, arms in opposition, spear stabilised by the wrist.
* WalkerDraw: renders each figure into its own buffer, applies limb-on-body shadows, projects the
  whole silhouette as a ground shadow plus per-foot contact shadows, then composites it.
"""
import math

import cv2
import numpy as np

from .compositor import _warp_roi
from .geom import R, S, T, about
from .library.figures import _face, _hand, mix_dark
from .palette import P, mix
from .scene import Figure, PartSpec, layer_matrix, world_of

L1, L2 = 205.0, 185.0        # thigh (hip 575 -> knee 780), shin (knee -> ankle 965)
HIP, KNEE, ANKLE = (0.0, 575.0), (0.0, 780.0), (0.0, 965.0)
HEEL, TOE = (24.0, 1000.0), (-74.0, 1000.0)


# ----------------------------------------------------------------------------- sculpting
def sculpt_bands(arr, vol):
    """arr: RGBA flat art of ONE part. Returns art with 5 discrete light/shade bands."""
    lx, ly = vol.get("light", (-0.6, -0.8))
    a = (arr[..., 3] > 127).astype(np.uint8)
    if not a.any():
        return arr
    d = cv2.distanceTransform(a, cv2.DIST_L2, 5)
    Rr = max(2.0, float(d.max()) * vol.get("roundness", 1.0))
    u = np.clip(d / Rr, 0, 1)
    h = np.sqrt(np.clip(1 - (1 - u) ** 2, 0, 1)) * Rr
    h = cv2.GaussianBlur(h, (0, 0), max(1.0, Rr * 0.3))
    gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    Lv = np.array([-lx, -ly, 0.85], np.float32)
    Lv /= np.linalg.norm(Lv)
    diff = np.clip((-gx * Lv[0] - gy * Lv[1] + Lv[2]) / np.sqrt(gx * gx + gy * gy + 1), 0, 1)
    amb, st = vol.get("ambient", 0.3), vol.get("strength", 1.2)
    shade = (amb + st * diff) / (amb + st * Lv[2])
    edges = np.array(vol.get("edges", (0.62, 0.82, 1.0, 1.1)))
    levels = np.array(vol.get("levels", (0.56, 0.74, 0.9, 1.04, 1.2)))
    idx = np.digitize(shade, edges).astype(np.uint8)
    idx = cv2.medianBlur(idx, 5)                       # clean band edges -> tidy tile rows
    lv = levels[idx][..., None]
    warm = np.array(vol.get("warm", (1.06, 1.0, 0.9)), np.float32)
    cool = np.array(vol.get("cool", (0.86, 0.93, 1.1)), np.float32)
    tint = np.where(lv >= 1.0, 1 + (lv - 1) * 4 * (warm - 1), 1 - (1 - lv) * 2.2 * (1 - cool))
    out = arr.copy()
    rgb = arr[..., :3].astype(np.float32) * lv * tint
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[a == 0] = arr[a == 0]
    return out


# ----------------------------------------------------------------------------- soldier rig
def soldier_v3(ctx, k, tile=5.0, variant=0, standard=False, haze=None, haze_amt=0.0, sculpt=None):
    tunics = [("terracotta", "terracotta_dk", "lapis", "sand"), ("ochre", "ochre_dk", "terracotta", "bone"),
              ("lapis", "lapis_dk", "sand", "ochre"), ("emerald", "green_dk", "ochre", "sand")]
    tun, tun_dk, trous, hood = tunics[variant % len(tunics)]
    far_t = mix_dark(trous) if trous in ("lapis", "terracotta", "sand", "ochre") else trous

    def thigh(col):
        def f(p):
            p.smooth([(-36, 556), (36, 556), (30, 700), (24, 790), (-22, 790), (-30, 700)], col, 5)
        return f

    def shin(col):
        def f(p):
            p.smooth([(-24, 772), (24, 772), (20, 880), (18, 960), (-18, 960), (-22, 880)], col, 5)
            p.smooth([(-22, 905), (22, 905), (24, 968), (-24, 968)], "umber", 3)      # boot top
        return f

    def foot(p):
        p.smooth([(-20, 940), (24, 940), (30, 1000), (-74, 1000), (-78, 986), (-40, 960)], "umber", 5)
        p.poly([(-78, 990), (30, 990), (30, 1002), (-78, 1002)], "black")             # sole edge

    def torso(p):
        p.rect(-22, 150, 44, 110, "skin")
        p.smooth([(-50, 244), (-72, 320), (-66, 470), (-84, 770), (82, 770), (64, 470), (68, 300), (50, 244)], tun, 7)
        # scale corselet (Herodotus 7.61: 'iron scales like those of a fish')
        for r, y in enumerate(range(270, 470, 22)):
            for x in range(-60, 62, 20):
                xx = x + (10 if r % 2 else 0)
                if -66 < xx < 64:
                    p.ellipse(xx, y + 8, 10, 12, "gold" if r % 3 else "ochre_dk", 0, 180)
        p.rect(-68, 464, 134, 20, "umber")
        p.circle(-2, 474, 9, "gold")
        for x in (-44, -6, 32):
            p.line([(x * 0.8, 500), (x * 1.25, 752)], tun_dk, 6)
        p.poly([(-86, 748), (84, 748), (82, 772), (-84, 772)], hood)

    def quiver(p):
        p.smooth([(40, 262), (86, 248), (118, 560), (78, 574)], "umber", 4)
        p.poly([(44, 270), (84, 258), (92, 330), (54, 342)], "gold")

    def shield(p):
        # wicker spara with a visible rim THICKNESS on its edge (darker side band)
        p.smooth([(-6, 292), (160, 284), (176, 520), (160, 790), (6, 800), (-8, 540)], "umber", 6)
        p.smooth([(-6, 292), (150, 284), (166, 520), (150, 788), (6, 800), (-8, 540)], "brick", 6)
        p.smooth([(8, 306), (142, 300), (156, 520), (142, 774), (16, 784), (4, 540)], "ochre", 6)
        for y in range(322, 774, 30):
            p.line([(12, y), (148, y - 4)], "ochre_dk", 6)
        for x in range(30, 150, 28):
            p.line([(x, 312), (x + 2, 776)], "sand", 3)

    def far_arm(p):
        c = mix_dark(tun) if tun in ("terracotta", "ochre", "lapis") else "green_dk"
        p.smooth([(-26, 256), (24, 256), (20, 420), (-14, 470), (-70, 492), (-74, 460), (-18, 420)], c, 6)
        p.ellipse(-82, 474, 16, 13, "skin_sh")

    def upper_arm(p):
        p.smooth([(-30, 248), (28, 248), (26, 330), (20, 424), (-18, 424), (-26, 330)], tun, 6)
        p.line([(-4, 300), (-2, 410)], tun_dk, 5)

    def fore_arm(p):
        p.smooth([(-20, 404), (22, 404), (14, 440), (-70, 486), (-80, 458)], tun, 6)
        _hand(p, x=-90, y=470, holding=True)

    def spear(p):
        if standard:
            p.line([(-90, -400), (-90, 990)], "umber", 11)
            p.line([(-94, -400), (-94, 990)], "ochre_dk", 3)                           # lit edge
            p.poly([(-90, -470), (-190, -520), (-150, -440), (-102, -420), (-78, -420), (-30, -440), (10, -520)], "gold")
            p.circle(-90, -480, 20, "gold_lt")
        else:
            p.line([(-90, -150), (-90, 990)], "umber", 11)
            p.line([(-94, -150), (-94, 990)], "ochre_dk", 3)
            p.poly([(-90, -230), (-104, -164), (-90, -140), (-76, -164)], "stone")
            p.line([(-92, -222), (-92, -150)], "white", 3)
            p.circle(-90, 990, 16, "gold")

    def head(p):
        p.smooth([(-40, 60), (-10, 0), (40, 18), (62, 90), (62, 196), (34, 228), (-10, 232), (-20, 170), (10, 120)], hood, 5)
        _face(p, beard="umber", curls="hair_lt", beard_len=0.6, ear=False)
        p.smooth([(-54, 76), (-50, 26), (-12, -6), (40, 14), (52, 70), (18, 70), (-12, 80)], hood, 5)   # rounded tiara
        p.curve([(-46, 62), (-12, 38), (30, 44)], mix(hood, "umber", 0.5), 6)

    parts = [
        PartSpec("quiver", quiver, pivot=(60, 262), parent="torso", z=0),
        PartSpec("shield", shield, pivot=(70, 300), parent="farm", z=0.5),
        PartSpec("farm", far_arm, pivot=(2, 262), parent="torso", z=0.3),
        PartSpec("thigh_b", thigh(far_t), pivot=HIP, parent="torso", z=0.8),
        PartSpec("shin_b", shin(far_t), pivot=KNEE, parent="thigh_b", z=0.8),
        PartSpec("foot_b", foot, pivot=ANKLE, parent="shin_b", z=0.85),
        PartSpec("torso", torso, pivot=(0, 600), z=2),
        PartSpec("thigh_f", thigh(trous), pivot=HIP, parent="torso", z=2.2),
        PartSpec("shin_f", shin(trous), pivot=KNEE, parent="thigh_f", z=2.2),
        PartSpec("foot_f", foot, pivot=ANKLE, parent="shin_f", z=2.25),
        PartSpec("head", head, pivot=(0, 210), parent="torso", z=3, tile_mul=0.62),
        PartSpec("spear", spear, pivot=(-90, 470), parent="farm_f", z=3.5),
        PartSpec("farm_u", upper_arm, pivot=(0, 262), parent="torso", z=4),
        PartSpec("farm_f", fore_arm, pivot=(-2, 412), parent="farm_u", z=4.2),
    ]
    if standard:
        def banner(p):
            p.poly([(-86, -390), (200, -378), (220, -150), (-86, -160)], "crimson")
            p.poly([(-86, -390), (200, -378), (202, -352), (-86, -362)], "gold")
            p.poly([(-86, -186), (216, -176), (220, -150), (-86, -160)], "gold")
            p.circle(60, -270, 34, "gold")
            p.circle(60, -270, 16, "crimson_dk")
            for x in range(-70, 210, 28):
                p.line([(x, -152), (x + 2, -126)], "gold", 6)
        parts.append(PartSpec("banner", banner, pivot=(-90, -270), parent="spear", z=3.4,
                              deform=dict(amp=22, wl=230, speed=0.85, axis="x", anchor=0.0, power=1.1)))
    # parts that cast shadows onto the parts drawn before them (self-shadowing)
    drop = {"torso", "thigh_f", "shin_f", "head", "farm_u", "farm_f", "spear"}
    fig = Figure(ctx, f"soldier3d{variant}{'s' if standard else ''}", parts, k, tile, haze, haze_amt,
                 volume=dict(sculpt or SCULPT, mode="bands"))
    fig.drop = drop
    return fig


SCULPT = dict(light=(-0.6, -0.8), strength=1.2, ambient=0.3, roundness=1.0)


# ----------------------------------------------------------------------------- gait
def _ik(H, A):
    dx, dy = A[0] - H[0], A[1] - H[1]
    d = min(math.hypot(dx, dy), L1 + L2 - 0.5)
    phi = math.atan2(-dx, dy)
    a = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    th = phi + a                                       # knee bends forward (facing -x)
    K = (H[0] - L1 * math.sin(th), H[1] + L1 * math.cos(th))
    sh = math.atan2(-(A[0] - K[0]), A[1] - K[1])
    return math.degrees(th), math.degrees(sh)


def _rot(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c * v[0] - s * v[1], s * v[0] + c * v[1])


def _ankle_target(u, Sx, lift):
    """Ankle position (relative to hip x=0) and absolute foot angle for one leg at phase u."""
    st = 0.6
    if u < st:
        pr = u / st
        xc = -0.3 * Sx + 0.6 * Sx * pr                    # contact point slides back at body speed
        if pr < 0.14:                                     # heel strike: toes still up, roll on heel
            th = 16 * (1 - pr / 0.14)
            heel = (xc + HEEL[0], HEEL[1])
            v = _rot((ANKLE[0] - HEEL[0], ANKLE[1] - HEEL[1]), th)
            return (heel[0] + v[0], heel[1] + v[1]), th, 0.0
        if pr > 0.68:                                     # heel-off / toe-off: roll over the toes
            th = -38 * ((pr - 0.68) / 0.32)
            toe = (xc + TOE[0], TOE[1])
            v = _rot((ANKLE[0] - TOE[0], ANKLE[1] - TOE[1]), th)
            return (toe[0] + v[0], toe[1] + v[1]), th, 0.0
        return (xc, ANKLE[1]), 0.0, 0.0
    v = (u - st) / (1 - st)
    a0, t0, _ = _ankle_target(st - 1e-6, Sx, lift)
    a1, t1, _ = _ankle_target(0.0, Sx, lift)
    e = v * v * (3 - 2 * v)
    up = lift * math.sin(math.pi * v) ** 1.2
    th = t0 + (t1 - t0) * (v ** 0.7)
    return (a0[0] + (a1[0] - a0[0]) * e, a0[1] + (a1[1] - a0[1]) * e - up), th, up


def gait_ik(t, period=1.1, stride=425.0, phase=0.0, lift=32.0, arm=13.0, lean=3.5):
    """Returns (pose dict, feet info). stride = body travel per cycle (figure units)."""
    u = (t / period + phase) % 1.0
    feet = {}
    for leg, uu in (("f", u), ("b", (u + 0.5) % 1.0)):
        A, th, up = _ankle_target(uu, stride, lift)
        feet[leg] = (A, th, up, uu < 0.6)
    # pelvis height: as high as the stance legs can reach (natural bob, never floating)
    Lmax = (L1 + L2) * 0.985

    def hip_at(uu):
        hy = HIP[1]
        for leg, off in (("f", 0.0), ("b", 0.5)):
            w = (uu + off) % 1.0
            if w < 0.6:
                A, _, _ = _ankle_target(w, stride, lift)
                hy = max(hy, A[1] - math.sqrt(max(1.0, Lmax * Lmax - A[0] * A[0])))
        return hy
    hy = (hip_at(u) * 2 + hip_at((u + 0.02) % 1) + hip_at((u - 0.02) % 1)) / 4
    dy = hy - HIP[1]
    ph = 2 * math.pi * u
    lam = lean + 0.9 * math.sin(2 * ph)                         # forward lean + push-off surge
    Mb = T(0, dy) @ about(0, 600, R(lam))
    Hw = (Mb @ np.array([HIP[0], HIP[1], 1.0]))[:2]
    pose = {"torso": (lam, 1.5 * math.sin(2 * ph - 0.5), dy)}
    for leg in ("f", "b"):
        A, th, up, stance = feet[leg]
        tha, sha = _ik(Hw, A)
        pose["thigh_" + leg] = (tha - lam, 0, 0)
        pose["shin_" + leg] = (sha - tha, 0, 0)
        pose["foot_" + leg] = (th - sha, 0, 0)
    sw = math.cos(ph - 0.3)                                     # +1 when near leg is forward
    au = -arm * sw
    af = 6 + 8 * max(0.0, -sw)                                  # elbow flexes on the back-swing
    pose["farm_u"] = (au, -5 * sw, 0)                           # shoulder twist with the arm
    pose["farm_f"] = (af, 0, 0)
    pose["spear"] = (-(lam + au + af) * 0.88 + 1.2 * math.sin(2 * ph + 0.8), 0, 0)
    pose["farm"] = (arm * 0.7 * sw, 4 * sw, 0)
    pose["shield"] = (1.5 * math.sin(2 * ph + 1.0), 0, 3 * math.sin(2 * ph + 0.7))
    pose["head"] = (-lam * 0.7 + 1.2 * math.sin(2 * ph + 0.5), 0, 0)
    pose["banner"] = (0, 0, 0)
    pose["_wind"] = 1.0
    return pose, feet


def gait_speed(k, period=1.1, stride=500.0):
    return k * stride / period


# ----------------------------------------------------------------------------- renderer
_CS = {}


def _contact():
    if "c" not in _CS:
        h, w = 40, 120
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        a = np.exp(-(((xx - w / 2) / (w * 0.3)) ** 2 + ((yy - h / 2) / (h * 0.28)) ** 2) * 1.5)
        _CS["c"] = a.astype(np.float32)
    return _CS["c"]


class WalkerDraw:
    """Walkers moving along a ground path (list of (X, q)), each rendered with self-shadowing,
    a projected ground shadow and contact shadows. Emits 'draw' entries (see Scene.render)."""

    def __init__(self, ground, figs, path, k_ref, n, spacing, cam, qband=(0, 99), seed=0, fade_q=None,
                 sun=(0.62, 0.24), lead=0.95, tint=(0.58, 0.64, 0.82)):
        self.g, self.figs, self.k_ref, self.n, self.spacing = ground, figs, k_ref, n, spacing
        self.cam, self.qband, self.fade_q, self.sun, self.tint = cam, qband, fade_q, sun, np.array(tint, np.float32)
        pts = []
        for (Xa, qa), (Xb, qb) in zip(path, path[1:]):
            for i in range(40):
                w = i / 40
                X, q = Xa + (Xb - Xa) * w, qa + (qb - qa) * w
                pts.append((X, ground.depth(q), q))
        pts.append((path[-1][0], ground.depth(path[-1][1]), path[-1][1]))
        self.P = np.array(pts)
        self.s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(self.P[:, 0]), np.diff(self.P[:, 1])))])
        rnd = np.random.default_rng(seed)
        self.var = [dict(period=rnd.uniform(1.02, 1.18), stride=rnd.uniform(400, 450), phase=rnd.uniform(0, 1),
                         lift=rnd.uniform(26, 36), arm=rnd.uniform(10, 16), size=rnd.uniform(0.96, 1.04),
                         lean=rnd.uniform(2.5, 4.5)) for _ in range(n)]
        v0 = gait_speed(k_ref, 1.1, 425)
        self.t0 = self.s[-1] * lead / v0

    def _state(self, s):
        return np.interp(s, self.s, self.P[:, 0]), np.interp(s, self.s, self.P[:, 2])

    def emit(self, t):
        rows = []
        for i in range(self.n):
            vv = self.var[i]
            v = gait_speed(self.k_ref * vv["size"], vv["period"], vv["stride"])
            s = (t + self.t0) * v - i * self.spacing
            if 0 <= s <= self.s[-1]:
                X, q = self._state(s)
                if self.qband[0] <= q < self.qband[1]:
                    rows.append((q, i, X))
        rows.sort()
        return [((lambda fr, ctx, cam, q=q, i=i, X=X: self._draw(fr, ctx, t, q, i, X)), None, 1.0, "draw")
                for q, i, X in rows]

    def _draw(self, frame, ctx, t, q, i, X):
        vv = self.var[i]
        fig = self.figs[i % len(self.figs)]
        op = 1.0
        if self.fade_q and q < self.fade_q[0]:
            op = max(0.0, (q - self.fade_q[1]) / (self.fade_q[0] - self.fade_q[1]))
        if op <= 0.01:
            return
        cam = self.cam(t)
        L = layer_matrix(ctx, cam, self.g.parallax(q))
        x, y = self.g.project(X, q)
        k = self.k_ref * vv["size"] * q
        pose, feet = gait_ik(t, vv["period"], vv["stride"], vv["phase"], vv["lift"], vv["arm"], vv["lean"])
        root = T(x, y) @ S(k, k) @ T(0, -1000)
        world = {}
        for p in fig.parts:
            world_of(p, fig, root, pose, world)
        H, W = frame.shape[:2]
        items = []
        for p in fig.parts:
            spr = fig.sprites[p.name]
            if spr is None:
                continue
            pm = spr.premult
            if p.deform:
                from .compositor import rigid_tile_wave
                d = p.deform
                pm = rigid_tile_wave(pm, spr.tiles, t + vv["phase"], d["amp"] * spr.ppu, d["wl"] * spr.ppu,
                                     d.get("speed", 0.5), d.get("axis", "y"), 0.0, d.get("power", 1.4), d.get("anchor", 0.0))
            items.append((p.name, pm, L @ world[p.name] @ spr.pixel_to_unit()))
        # figure bounding box in pixels
        boxes = []
        for _, pm, M in items:
            h, w = pm.shape[:2]
            c = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float) @ M.T
            boxes.append((c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()))
        pad = 8
        x0 = int(max(0, min(b[0] for b in boxes) - pad))
        y0 = int(max(0, min(b[1] for b in boxes) - pad))
        x1 = int(min(W, max(b[2] for b in boxes) + pad))
        y1 = int(min(H, max(b[3] for b in boxes) + pad))
        if x1 <= x0 or y1 <= y0:
            return
        buf = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
        off = T(-x0, -y0)
        sdx, sdy = 7 * k * ctx.pxpd, 9 * k * ctx.pxpd      # self-shadow offset (sun upper left)
        for name, pm, M in items:
            Mo = off @ M
            if name in fig.drop:
                r = _warp_roi(pm, T(sdx, sdy) @ Mo, buf.shape[1], buf.shape[0])
                if r is not None:
                    w_, a0, b0, a1, b1 = r
                    a = cv2.GaussianBlur(w_[..., 3].astype(np.float32) / 255.0, (0, 0), max(0.6, 3 * k * ctx.pxpd))
                    sub = buf[b0:b1, a0:a1]
                    sub[..., :3] *= (1 - 0.45 * a[..., None] * (1 - self.tint))
            r = _warp_roi(pm, Mo, buf.shape[1], buf.shape[0])
            if r is None:
                continue
            w_, a0, b0, a1, b1 = r
            f = w_.astype(np.float32) / 255.0
            sub = buf[b0:b1, a0:a1]
            sub *= 1 - f[..., 3:4]
            sub += f
        # ground plane foot line in pixels
        fx, fy = (L @ np.array([x, y, 1.0]))[:2]
        fy_b = fy - y0
        alpha = buf[..., 3]
        shx, sy = self.sun
        Pm = np.array([[1, -shx, shx * fy_b], [0, sy, (1 - sy) * fy_b]], np.float32)
        Hh, Ww = alpha.shape
        ext = int(Hh * shx) + 20
        cast = cv2.warpAffine(alpha, Pm, (Ww + ext, Hh), flags=cv2.INTER_LINEAR)
        cast = cv2.GaussianBlur(cast, (0, 0), max(0.8, 2.5 * k * ctx.pxpd)) * 0.42 * op
        # contact shadows under each foot (fade with foot height)
        cs = _contact()
        for leg in ("f", "b"):
            A, th, up, stance = feet[leg]
            ax = (root @ np.array([A[0] - 20, 1000.0, 1.0]))[0]
            px_ = (L @ np.array([ax, y, 1.0]))[0] - x0
            w = 150 * k * ctx.pxpd
            hgt = w * 0.24
            sc = cv2.resize(cs, (max(2, int(w)), max(2, int(hgt))))
            o = max(0.0, 1 - up / 45) * 0.6 * op
            xa, ya = int(px_ - w / 2), int(fy_b - hgt / 2)
            xb, yb = xa + sc.shape[1], ya + sc.shape[0]
            if xb > 0 and yb > 0 and xa < cast.shape[1] and ya < cast.shape[0]:
                ca, cb = max(0, xa), max(0, ya)
                cast[cb:min(cast.shape[0], yb), ca:min(cast.shape[1], xb)] = np.maximum(
                    cast[cb:min(cast.shape[0], yb), ca:min(cast.shape[1], xb)],
                    sc[cb - ya:min(cast.shape[0], yb) - ya, ca - xa:min(cast.shape[1], xb) - xa] * o)
        X1 = min(W, x0 + cast.shape[1])
        roi = frame[y0:y1, x0:X1]
        roi *= 1 - cast[:, :X1 - x0, None] * (1 - self.tint)
        buf *= op
        roi2 = frame[y0:y1, x0:x1]
        roi2 *= 1 - buf[..., 3:4]
        roi2 += buf[..., :3]

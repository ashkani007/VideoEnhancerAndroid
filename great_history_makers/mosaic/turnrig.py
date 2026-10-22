"""Turning 2.5D soldiers: path-following walkers with multi-view mosaic bodies.

Design (reusable for any episode where figures change direction):
* Body joints live in 3D. Body frame: a = forward, b = right, c = up (figure units, height
  1000, ground c = 0). Yaw psi: 0 = walking away from the camera, +90 = facing screen-left.
  World offset: X = -a sin(psi) + b cos(psi),  Z = a cos(psi) + b sin(psi)  (times k_ref),
  then every joint is projected through the scene's pinhole Ground, so size, foot placement
  and vanishing point are exact.
* Heading comes from the walking path tangent; hips follow the path, the torso leads a
  little, the head leads most (it starts looking toward the destination first).
* Turnaround drawings: torso, head, shield, quiver and boots are drawn and tessellated at
  9 yaw views (0-90 deg, 11.25 deg steps) and at 3 depth scales (mip levels), mirrored for
  soldiers approaching from the other side. Limbs (thigh, shin, arms, spear) are cylinders,
  placed between projected joints; small foreshortening is taken from 3 pre-drawn lengths
  so tesserae are never visibly squashed.
* Feet are planted in WORLD space: each stance has a fixed ground point (computed from the
  path at mid-stance); swing interpolates between consecutive plants with a lift arc. Legs
  are solved with 2-bone IK toward the planted ankle. Hip height follows leg reach.
* Rendering: per-figure buffer with limb self-shadows, then a projected ground shadow and
  per-foot contact shadows, then lighting by location (sun, gate shadow, passage darkness)
  and an optional clip polygon (the tunnel opening at the figure's depth).
"""
import math

import cv2
import numpy as np

from .compositor import _warp_roi
from .geom import R, S, T
from .library.figures import _face, _hand, _hood, _hood_back, mix_dark
from .painter import catmull_rom
from .palette import P, mix
from .rig3d import _ankle_target
from .scene import layer_matrix, make_sprite

VIEWS = [i * 11.25 for i in range(9)]           # 0 (rear) ... 90 (side, facing left)
L1, L2, ANK_C = 205.0, 185.0, 35.0              # thigh, shin, ankle height
HIP_C, SH_C, NECK_C = 425.0, 738.0, 790.0
HIP_B, SH_B = 40.0, 64.0
UA, FA = 165.0, 150.0                           # upper arm, forearm (to hand centre)
SCULPT = dict(mode="bands", light=(-0.6, -0.8), strength=1.2, ambient=0.3, roundness=1.0)
TUNICS = [("terracotta", "terracotta_dk", "lapis", "sand"), ("ochre", "ochre_dk", "terracotta", "bone"),
          ("lapis", "lapis_dk", "sand", "ochre"), ("emerald", "green_dk", "ochre", "sand")]


def _ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# =================================================================== drawings (fig units)
def draw_torso(p, th, tun, tun_dk, hood):
    """Torso at view th (deg). Local origin = pelvis centre (c=425), y down, x = screen."""
    s, r = math.sin(math.radians(th)), math.cos(math.radians(th))
    sh, wa, he = 50 * s + 82 * r, 44 * s + 62 * r, 70 * s + 80 * r
    front = -1 if th > 5 else 0
    bul = 10 * s
    y_sh, y_be, y_he = -(SH_C - HIP_C) - 14, -45, 205
    pts = [(-sh - bul * 0.5, y_sh + 10), (-sh - bul, y_sh + 80), (-wa - bul * 0.6, y_be), (-he, y_he),
           (he, y_he), (wa, y_be), (sh, y_sh + 60), (sh * 0.8, y_sh + 6)]
    p.smooth(pts, tun, 7)
    # scale corselet (front, sides and back - Herodotus 7.61)
    for row, y in enumerate(range(int(y_sh + 30), int(y_be - 6), 22)):
        w = sh - (sh - wa) * (y - y_sh) / (y_be - y_sh)
        x = -w + 6 + (10 if row % 2 else 0)
        while x < w - 6:
            p.ellipse(x, y + 8, 10, 12, "gold" if row % 3 else "ochre_dk", 0, 180)
            x += 20
    p.rect(-wa - bul * 0.6, y_be - 10, 2 * wa + bul * 0.6, 20, "umber")
    if th > 30:
        p.circle(-wa * s - bul * 0.6 + 8, y_be, 9, "gold")            # buckle on the front side
    for k in (-0.55, 0.0, 0.55):                                       # skirt folds
        x0 = k * wa
        p.line([(x0, y_be + 20), (x0 * 1.3, y_he - 14)], tun_dk, 6)
    if th < 30:                                                        # back seam
        p.line([(0, y_sh + 20), (0, y_be - 12)], tun_dk, 5)
    p.poly([(-he, y_he - 22), (he, y_he - 22), (he, y_he), (-he, y_he)], hood)
    p.rect(-20, y_sh - 46, 40, 56, "skin" if th > 40 else hood)       # neck / hood flap


def draw_head(p, th, hood):
    """Head at view th, figure coords (neck pivot at (0, 210))."""
    if th >= 56:                                    # profile -> near-profile (face narrows)
        sx = 0.7 + 0.3 * (th - 56) / 34
        p.push()
        p.translate(6 * (1 - sx) * 10, 0)
        p.scale(sx, 1)
        _hood_back(p, hood)
        _face(p, beard="umber", curls="hair_lt", beard_len=0.6, ear=False)
        _hood(p, hood, "umber")
        p.pop()
        return
    vis = (th - 8) / 48 if th > 8 else 0.0          # how much face still shows (rear 3/4)
    # hood dome + neck flap seen from behind
    p.smooth([(-52, 70), (-46, 18), (-8, -8), (36, 4), (58, 60), (62, 170), (44, 226), (0, 238), (-44, 226),
              (-60, 170)], hood, 6)
    p.curve([(-40, 70), (0, 52), (40, 66)], mix(hood, "umber", 0.45), 6)
    p.curve([(-30, 150), (0, 166), (30, 150)], mix(hood, "umber", 0.3), 4)
    if vis > 0:
        w = 34 * vis
        p.smooth([(-58, 96), (-58 + w, 92), (-58 + w * 0.8, 150), (-60, 196), (-66, 150)], "skin_sh", 4)  # cheek
        p.smooth([(-62, 150), (-60 + w * 0.9, 146), (-56 + w * 0.6, 230), (-66, 228)], "umber", 4)        # beard
        if vis > 0.55:
            p.circle(-58 + w * 0.6, 108, 5, "black")                                                       # eye corner


def draw_shield(p, th):
    """Wicker spara on the far arm. Face width ~ sin(th), rim/edge thickness ~ cos(th)."""
    s, r = math.sin(math.radians(th)), math.cos(math.radians(th))
    wf, we = 166 * s, 26 * r + 6
    x0 = -wf / 2
    if wf > 6:
        p.smooth([(x0, -250), (x0 + wf, -256), (x0 + wf + 8 * s, -10), (x0 + wf, 250), (x0, 256), (x0 - 8 * s, 0)], "brick", 6)
        p.smooth([(x0 + 10 * s, -236), (x0 + wf - 10 * s, -240), (x0 + wf - 4 * s, -10), (x0 + wf - 10 * s, 236),
                  (x0 + 10 * s, 240), (x0 + 4 * s, 0)], "ochre", 6)
        for y in range(-226, 236, 30):
            p.line([(x0 + 12 * s, y), (x0 + wf - 12 * s, y - 4 * s)], "ochre_dk", 6)
        for x in np.arange(x0 + 26 * s, x0 + wf - 20 * s, max(8, 28 * s)):
            p.line([(x, -230), (x + 2, 232)], "sand", 3)
    # edge band (thickness) on the side facing the camera when turned away
    xe = x0 + wf
    p.smooth([(xe, -252), (xe + we, -246), (xe + we, 246), (xe, 252)], "umber", 3)
    p.line([(xe + we * 0.5, -240), (xe + we * 0.5, 240)], "ochre_dk", 3)


def draw_quiver(p, th):
    if th > 50:
        p.smooth([(-14, -150), (30, -164), (58, 150), (18, 164)], "umber", 4)
        p.poly([(-10, -140), (28, -152), (36, -80), (-2, -68)], "gold")
    else:
        p.smooth([(-26, -160), (26, -160), (24, 160), (-24, 160)], "umber", 4)
        p.rect(-26, -150, 52, 46, "gold")
        for x in (-14, 0, 14):                                          # fletchings
            p.poly([(x - 6, -160), (x, -196), (x + 6, -160)], "bone")


def draw_boot(p, th):
    """Foot from the ankle (0,0); profile shortens to a heel oval as the view turns away."""
    s = math.sin(math.radians(th))
    ln = 22 + 78 * s
    p.smooth([(-22, -28), (24, -28), (28, 32), (-ln, 32), (-ln - 4, 18), (-ln * 0.55, -6)], "umber", 5)
    p.poly([(-ln - 4, 24), (28, 24), (28, 36), (-ln - 4, 36)], "black")


def draw_tube(p, length, w0, w1, col, boot=False, hand=False, dark=None, boot_col="umber", cuff=None):
    p.smooth([(-w0, -6), (w0, -6), (w1, length * 0.5), (w1 * 0.9, length + 4), (-w1 * 0.9, length + 4),
              (-w1, length * 0.5)], col, 5)
    if dark:
        p.line([(-w0 * 0.2, 10), (-w1 * 0.2, length - 10)], dark, 5)
    if boot:
        p.smooth([(-w1 - 2, length - 60), (w1 + 2, length - 60), (w1 + 3, length + 6), (-w1 - 3, length + 6)], boot_col, 3)
    if cuff:
        p.rect(-w1 - 2, length - 36, 2 * w1 + 4, 26, cuff)
    if hand:
        p.ellipse(0, length, 20, 16, "skin")
        p.ellipse(-10, length - 6, 9, 8, "skin")


def draw_spear(p):
    p.line([(0, -1150), (0, 320)], "umber", 11)
    p.line([(-4, -1150), (-4, 320)], "ochre_dk", 3)
    p.poly([(0, -1230), (-14, -1164), (0, -1140), (14, -1164)], "stone")
    p.line([(-2, -1222), (-2, -1150)], "white", 3)
    p.circle(0, 320, 16, "gold")


# =================================================================== asset set
class PersianCostume:
    """Episode-1 costume (default) - wraps the original drawing functions."""
    front = False
    arm_mode = "weapon"
    torso_rect = (-140, -420, 280, 660)

    def __init__(self, variant=0):
        self.tun, self.tun_dk, self.trous, self.hood = TUNICS[variant % len(TUNICS)]
        self.far_t = mix_dark(self.trous) if self.trous in ("lapis", "terracotta", "sand", "ochre") else self.trous
        self.name = f"persian{variant}"
        self.tubes = dict(thigh_n=(self.trous, None), thigh_f=(self.far_t, None), shin_n=(self.trous, True),
                          shin_f=(self.far_t, True), uarm_n=(self.tun, self.tun_dk), uarm_f=(self.tun_dk, None),
                          farm_n=(self.tun, None), farm_f=(self.tun_dk, None))

    def torso(self, p, th):
        draw_torso(p, th, self.tun, self.tun_dk, self.hood)

    def head(self, p, th):
        draw_head(p, th, self.hood)

    def shield(self, p, th):
        draw_shield(p, th)

    def pack(self, p, th):
        draw_quiver(p, th)

    def boot(self, p, th):
        draw_boot(p, th)

    def weapon(self, p):
        draw_spear(p)

    flag = None


def _views(front):
    return [i * 11.25 for i in range(17 if front else 9)]


class TurnSoldierAssets:
    """All view/mip sprites for one costume. costume: PersianCostume (default) or any object with
    torso/head/boot(p, th), optional shield/pack(p, th), weapon(p), flag(p, th), tubes dict and front flag."""

    MIPS = (1.6, 1.15, 0.8)

    def __init__(self, ctx, k_ref, variant=0, tile=5.0, costume=None, mips=None):
        self.k_ref = k_ref
        self.costume = cs = costume or PersianCostume(variant)
        self.MIPS = tuple(mips or self.MIPS)
        self.views = _views(cs.front)
        self.sets = {}
        tag = cs.name
        for q in self.MIPS:
            k = k_ref * q
            mk = lambda draw, rect, name, mul=1.0, keep=False: make_sprite(
                ctx, draw, rect, tile * mul, f"tr_{tag}_{name}_{q}", unit_scale=k, volume=SCULPT, outline="outline",
                keep_tiles=keep)
            d = {"torso": {}, "head": {}, "shield": {}, "quiver": {}, "boot": {}, "flag": {}}
            for th in self.views:
                d["torso"][th] = mk(lambda p, th=th: cs.torso(p, th), cs.torso_rect, f"torso{th}")
                d["head"][th] = mk(lambda p, th=th: cs.head(p, th), (-200, -300, 400, 560), f"head{th}", 0.62)
                if getattr(cs, "shield", None):
                    d["shield"][th] = mk(lambda p, th=th: cs.shield(p, th), (-130, -280, 260, 560), f"shield{th}")
                if getattr(cs, "pack", None):
                    d["quiver"][th] = mk(lambda p, th=th: cs.pack(p, th), (-110, -230, 220, 440), f"pack{th}")
                d["boot"][th] = mk(lambda p, th=th: cs.boot(p, th), (-130, -50, 190, 100), f"boot{th}")
            if getattr(cs, "flag", None):
                for th in (0, 45, 90, 135, 180):
                    d["flag"][th] = mk(lambda p, th=th: cs.flag(p, th), (-20, -20, 480, 380), f"flag{th}", 1.0, True)
            T_ = cs.tubes
            for lf in (1.0, 0.86, 0.72):
                for key, base, w0, w1, rect in (("thigh", L1, 34, 26, (-60, -30, 120, 280)), ("shin", L2, 25, 19, (-50, -30, 100, 260)),
                                                ("uarm", UA, 28, 22, (-50, -30, 100, 240)), ("farm", FA, 21, 16, (-50, -30, 100, 230))):
                    for side_ in ("n", "f"):
                        col, extra = T_[f"{key}_{side_}"]
                        kw = {}
                        if key == "shin":
                            kw["boot"] = bool(extra)
                            if isinstance(extra, str):
                                kw["boot_col"] = extra
                        elif key == "farm":
                            kw["hand"] = True
                            if extra:
                                kw["cuff"] = extra
                        elif extra:
                            kw["dark"] = extra
                        d[(f"{key}_{side_}", lf)] = mk(lambda p, lf=lf, base=base, w0=w0, w1=w1, col=col, kw=kw:
                                                       draw_tube(p, base * lf, w0, w1, col, **kw), rect, f"{key}{side_}{lf}")
            if getattr(cs, "weapon", None):
                d["spear"] = mk(cs.weapon, (-60, -1300, 120, 1700), "weapon")
            self.sets[q] = d

    def level(self, q):
        cands = [m for m in self.MIPS if m >= q * 0.92]
        return min(cands) if cands else max(self.MIPS)


# =================================================================== path
class Path:
    def __init__(self, pts, samples=24):
        P_ = catmull_rom(pts, samples, closed=False)
        self.P = np.array(P_, float)
        d = np.hypot(*np.diff(self.P, axis=0).T)
        self.s = np.concatenate([[0], np.cumsum(d)])
        self.length = self.s[-1]

    def at(self, s):
        s = min(max(s, 0.0), self.length)
        return np.interp(s, self.s, self.P[:, 0]), np.interp(s, self.s, self.P[:, 1])

    def heading(self, s, ds=14.0):
        x0, z0 = self.at(s - ds)
        x1, z1 = self.at(s + ds)
        return math.degrees(math.atan2(-(x1 - x0), (z1 - z0)))     # psi


# =================================================================== walker
class TurnWalker:
    def __init__(self, assets, path, s0, period=1.0, stride=600.0, lift=30.0, arm=14.0, side=1, seed=0.0,
                 head_lead=70.0, torso_lead=28.0, lean=3.0, idle=False, head_fn=None, arm_fn=None, wind=1.0):
        self.A, self.path, self.s0 = assets, path, s0
        self.lean0, self.idle, self.head_fn, self.arm_fn, self.wind = lean, idle, head_fn, arm_fn, wind
        if idle:
            stride = 0.0
        self.period, self.stride, self.lift, self.arm, self.side, self.ph = period, stride, lift, arm, side, seed
        self.v = assets.k_ref * stride / period                            # world units / s
        self.head_lead, self.torso_lead = head_lead, torso_lead
        self.kr = assets.k_ref

    # --- timing helpers
    def s_at(self, t):
        return self.s0 + self.v * t

    def u_at(self, t):
        return (t / self.period + self.ph) % 1.0

    def psi_hip(self, t):
        return self.path.heading(self.s_at(t))

    def world(self, t, a, b, c, psi):
        X0, Z0 = self.path.at(self.s_at(t))
        sp, cp = math.sin(math.radians(psi)), math.cos(math.radians(psi))
        b = b * self.side
        return X0 + self.kr * (-a * sp + b * cp), Z0 + self.kr * (a * cp + b * sp), self.kr * c

    def plant(self, t_stance_mid, leg_b):
        """World ground point of a stance foot (fixed for the whole stance)."""
        X, Z, _ = self.world(t_stance_mid, 0.0, leg_b, 0.0, self.psi_hip(t_stance_mid))
        return X, Z

    def foot(self, t, leg):
        """World ankle (X, Z, height), pitch (deg), lift height, stance flag."""
        off = 0.0 if leg == "n" else 0.5
        b = -HIP_B if leg == "n" else HIP_B                    # near leg on the spear (left) side
        if self.idle:                                          # standing: both feet planted, slight stagger
            X, Z, _ = self.world(0.0, 18.0 if leg == "n" else -14.0, b * 1.15, 0.0, self.psi_hip(0.0))
            return (X, Z, self.kr * ANK_C), 0.0, 0.0, True
        u = (self.u_at(t) + off) % 1.0
        st = 0.6
        cyc0 = t - u * self.period                             # time of this cycle's heel strike
        A, pitch, up = _ankle_target(u, self.stride, self.lift)
        if u < st:
            Xp, Zp = self.plant(cyc0 + st * self.period * 0.5, b)
            xc = -0.3 * self.stride + 0.6 * self.stride * (u / st)
            da = -(A[0] - xc)
            dc = 1000.0 - A[1]
            psi = self.psi_hip(t)
            sp, cp = math.sin(math.radians(psi)), math.cos(math.radians(psi))
            return (Xp + self.kr * (-da * sp), Zp + self.kr * (da * cp), self.kr * dc), pitch, 0.0, True
        v = (u - st) / (1 - st)
        e = v * v * (3 - 2 * v)
        Xa, Za = self.plant(cyc0 + st * self.period * 0.5, b)
        Xb, Zb = self.plant(cyc0 + self.period + st * self.period * 0.5, b)
        h = ANK_C + self.lift * math.sin(math.pi * v) ** 1.2
        return (Xa + (Xb - Xa) * e, Za + (Zb - Za) * e, self.kr * h), pitch, up, False

    def to_body(self, t, X, Z, psi):
        X0, Z0 = self.path.at(self.s_at(t))
        dx, dz = (X - X0) / self.kr, (Z - Z0) / self.kr
        sp, cp = math.sin(math.radians(psi)), math.cos(math.radians(psi))
        return -dx * sp + dz * cp, (dx * cp + dz * sp) * self.side     # a, b

    def pose3d(self, t):
        """All joints as body-frame (a, b, c) + yaws. Returns dict."""
        psi = self.psi_hip(t)
        s = self.s_at(t)
        psi_t = psi + max(-35, min(35, self.path.heading(s + self.torso_lead) - psi))
        psi_h = psi + max(-50, min(50, self.path.heading(s + self.head_lead) - psi))
        if self.head_fn:
            psi_h += self.head_fn(t)
        feet = {}
        for leg in ("n", "f"):
            (X, Z, Y), pitch, up, stance = self.foot(t, leg)
            a, b = self.to_body(t, X, Z, psi)
            feet[leg] = (a, b, Y / self.kr, pitch, up, stance)
        Lmax = (L1 + L2) * 0.985
        hip_c = HIP_C
        for leg, (a, b, c, pitch, up, stance) in feet.items():
            if stance:
                hip_c = min(hip_c, c + math.sqrt(max(1.0, Lmax ** 2 - a * a)))
        ph = 2 * math.pi * self.u_at(t)
        legs = {}
        for leg, (a, b, c, pitch, up, stance) in feet.items():
            hb = -HIP_B if leg == "n" else HIP_B
            dx, dy = a, hip_c - c
            d = min(math.hypot(dx, dy), L1 + L2 - 0.5)
            phi = math.atan2(dx, dy)
            al = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
            ka, kc = L1 * math.sin(phi + al), hip_c - L1 * math.cos(phi + al)
            legs[leg] = dict(hip=(0, hb, hip_c), knee=(ka, (hb + b) / 2, kc), ankle=(a, b, c), pitch=pitch, up=up)
        sw = math.cos(ph - 0.3) if not self.idle else 0.15 * math.sin(t * 1.3 + self.ph * 6)
        lean = self.lean0 + (0.8 * math.sin(2 * ph) if not self.idle else 0.6 * math.sin(t * 0.9 + self.ph * 5))
        dc = hip_c - HIP_C
        sh_c = SH_C + dc
        arms = {}
        # near (spear) arm: forearm raised forward holding the shaft; far (shield) arm swings
        mode = getattr(self.A.costume, "arm_mode", "weapon")
        arm_specs = [("n", -SH_B, 14 - 0.35 * self.arm * sw, 72) if mode == "weapon" else ("n", -SH_B, -self.arm * sw, 14 + 8 * max(0, sw)),
                     ("f", SH_B, self.arm * sw, 18 + 8 * max(0, -sw))]
        if self.arm_fn:
            arm_specs = self.arm_fn(t, arm_specs)
        for arm, b0, al, fl in arm_specs:
            sh = (math.sin(math.radians(lean)) * 60, b0, sh_c)
            e = (sh[0] + UA * math.sin(math.radians(al)), b0 * 1.08, sh_c - UA * math.cos(math.radians(al)))
            w = (e[0] + FA * math.sin(math.radians(al + fl)), b0 * 1.1, e[2] - FA * math.cos(math.radians(al + fl)))
            arms[arm] = dict(sh=sh, el=e, wr=w)
        return dict(psi=psi, psi_t=psi_t, psi_h=psi_h, legs=legs, arms=arms, hip_c=hip_c, dc=dc, lean=lean, ph=ph)


# =================================================================== renderer
class TurnDraw:
    """Emits 'draw' entries for a list of TurnWalkers within a depth band, sorted far->near."""

    def __init__(self, ground, walkers, cam, qband=(0, 99), clip_fn=None, light_fn=None, sun=(0.62, 0.24),
                 shadow_q=1.05, tint=(0.6, 0.65, 0.8)):
        self.g, self.walkers, self.cam, self.qband = ground, walkers, cam, qband
        self.clip_fn, self.light_fn, self.sun, self.shadow_q = clip_fn, light_fn, sun, shadow_q
        self.tint = np.array(tint, np.float32)

    def emit(self, t):
        rows = []
        for w in self.walkers:
            s = w.s_at(t)
            if s < 0 or s > w.path.length:
                continue
            X, Z = w.path.at(s)
            q = self.g.f / Z
            if self.qband[0] <= q < self.qband[1]:
                rows.append((q, id(w), w))
        rows.sort(key=lambda r: r[0])
        return [((lambda fr, ctx, cam, w=w, q=q: self._draw(fr, ctx, t, w, q)), None, 1.0, "draw") for q, _, w in rows]

    def _scr(self, ctx, cam, X, Z, Y):
        q = self.g.f / Z
        x, y = self.g.at_height(X, Y, q)
        Lm = layer_matrix(ctx, cam, self.g.parallax(q))
        px = Lm @ np.array([x, y, 1.0])
        return px[0], px[1], q, Lm

    def _draw(self, frame, ctx, t, w, q_root):
        cam = self.cam(t)
        A = w.A
        lvl = A.level(q_root)
        sp = A.sets[lvl]
        pose = w.pose3d(t)
        H, W = frame.shape[:2]
        side = w.side

        def P(abc, psi):
            X, Z, Y = w.world(t, abc[0], abc[1], abc[2], psi)
            x, y, q, _ = self._scr(ctx, cam, X, Z, Y)
            return x, y, q, Z

        ppu_root = w.kr * ctx.pxpd                               # px per fig unit at q = 1
        items = []                                               # (order, name, premult, M, drop)

        views = A.views
        vmax = views[-1]

        def view(psi):
            ap = abs(psi)
            th = ap if side * psi >= 0 else (0.0 if ap < 90 else 180.0)
            th = min(vmax, max(0.0, th))
            return min(views, key=lambda v: abs(v - th))

        def place(spr, x, y, q, ang=0.0, sy=1.0):
            sc = ppu_root * q / (ctx.ppu * w.kr * lvl) * ctx.ppu * w.kr * lvl  # = px per fig unit
            Mm = T(x, y) @ R(ang) @ S(ppu_root * q * (-1 if side < 0 else 1), ppu_root * q * sy)
            return Mm @ spr.pixel_to_unit()

        def limb(key, A3, B3, psi, order, drop=True):
            xa, ya, qa, Za = P(A3, psi)
            xb, yb, qb, Zb = P(B3, psi)
            Lpx = math.hypot(xb - xa, yb - ya)
            base = {"thigh": L1, "shin": L2, "uarm": UA, "farm": FA}[key.split("_")[0]]
            lf_need = Lpx / (ppu_root * qa * base)
            lf = min((1.0, 0.86, 0.72), key=lambda v: abs(v - lf_need))
            spr = sp[(key, lf)]
            ang = math.degrees(math.atan2(-(xb - xa), (yb - ya)))
            sy = max(0.6, min(1.15, lf_need / lf))
            Mm = T(xa, ya) @ R(ang) @ S(ppu_root * qa, ppu_root * qa * sy) @ spr.pixel_to_unit()
            items.append((order, key, spr.premult, Mm, drop, Za))

        psi, psi_t, psi_h = pose["psi"], pose["psi_t"], pose["psi_h"]
        L, Am = pose["legs"], pose["arms"]
        # depth of the two body sides (to order near/far parts)
        z_left = w.world(t, 0, -60, 500, psi_t)[1]
        z_right = w.world(t, 0, 60, 500, psi_t)[1]
        near_is_left = z_left <= z_right + 1e-6
        # legs (always under the tunic)
        for leg in ("f", "n"):
            Lg = L[leg]
            far = (leg == "f") == near_is_left
            o = 0 if far else 1
            k = "thigh_f" if far else "thigh_n"
            limb(k, Lg["hip"], Lg["knee"], psi, o)
            limb(k.replace("thigh", "shin"), Lg["knee"], Lg["ankle"], psi, o + 0.1)
            xa, ya, qa, Za = P(Lg["ankle"], psi)
            bt = sp["boot"][view(psi)]
            pitch = Lg["pitch"] * math.sin(math.radians(view(psi)))
            items.append((o + 0.2, "boot", bt.premult,
                          T(xa, ya) @ R(-pitch * (1 if side > 0 else -1)) @ S(ppu_root * qa * (-1 if side < 0 else 1), ppu_root * qa) @ bt.pixel_to_unit(),
                          False, Za))
        # torso
        th_t = view(psi_t)
        xt, yt, qt, Zt = P((0, 0, pose["hip_c"]), psi_t)
        ts = sp["torso"][th_t]
        items.append((5, "torso", ts.premult, T(xt, yt) @ R(-pose["lean"] * math.sin(math.radians(th_t)) * side)
                      @ S(ppu_root * qt * (-1 if side < 0 else 1), ppu_root * qt) @ ts.pixel_to_unit(), True, Zt))
        # quiver on the back
        xq, yq, qq, Zq = P((-58, 12, pose["hip_c"] + 180), psi_t)
        qv = sp["quiver"].get(th_t)
        q_order = 4 if th_t > 50 else 6
        if qv is not None:
            items.append((q_order, "quiver", qv.premult, T(xq, yq) @ R(-12 * math.sin(math.radians(th_t)) * side)
                          @ S(ppu_root * qq * (-1 if side < 0 else 1), ppu_root * qq) @ qv.pixel_to_unit(), False, Zq))
        # arms + shield + spear
        for arm in ("f", "n"):
            Ar = Am[arm]
            z_sh = w.world(t, Ar["sh"][0], Ar["sh"][1], Ar["sh"][2], psi_t)[1]
            is_near = (z_sh - Zt) < 30 * w.kr          # arms at the sides (front/rear views) stay in front
            o = 7 if is_near else 3
            k = "_n" if is_near else "_f"
            limb("uarm" + k, Ar["sh"], Ar["el"], psi_t, o)
            limb("farm" + k, Ar["el"], Ar["wr"], psi_t, o + 0.1)
            if arm == "f" and sp["shield"]:
                xs, ys, qs, Zs = P((Ar["el"][0] + 10, SH_B * 1.5, pose["hip_c"] + 150), psi_t)
                shs = sp["shield"][th_t]
                items.append((o - 0.5 if not is_near else o + 0.2, "shield", shs.premult,
                              T(xs, ys) @ S(ppu_root * qs * (-1 if side < 0 else 1), ppu_root * qs) @ shs.pixel_to_unit(),
                              False, Zs))
            elif arm == "n" and "spear" in sp:
                xh, yh, qh, _ = P(Ar["wr"], psi_t)
                top = (Ar["wr"][0] + 60, Ar["wr"][1], Ar["wr"][2] + 900)
                xtp, ytp, _, _ = P(top, psi_t)
                ang = math.degrees(math.atan2(-(xh - xtp), (yh - ytp)))
                spr = sp["spear"]
                items.append((o + 0.05, "spear", spr.premult,
                              T(xh, yh) @ R(ang) @ S(ppu_root * qh, ppu_root * qh) @ spr.pixel_to_unit(), True, 0))
                if sp["flag"]:
                    from .compositor import rigid_tile_wave
                    fth = min((0, 45, 90, 135, 180), key=lambda v: abs(v - view(psi_t)))
                    fs = sp["flag"][fth]
                    tip = (Ar["wr"][0] + 60 * 1.05, Ar["wr"][1], Ar["wr"][2] + 900 * 1.02)
                    xf, yf, qf, _ = P(tip, psi_t)
                    pm = rigid_tile_wave(fs.premult, fs.tiles, t + w.ph * 3, 14 * fs.ppu * w.wind, 200 * fs.ppu, 0.8, "x",
                                         0.0, 1.1, 0.0)
                    items.append((o + 0.04, "flag", pm, T(xf, yf) @ R(ang)
                                  @ S(ppu_root * qf * (-1 if side < 0 else 1), ppu_root * qf) @ fs.pixel_to_unit(), True, 0))
        # head (leads the turn)
        xh, yh, qh, _ = P((math.sin(math.radians(pose["lean"])) * 80, 0, NECK_C + pose["dc"]), psi_h)
        hs = sp["head"][view(psi_h)]
        if 135 <= view(psi_h) and view(psi_t) >= 135:   # facing the camera: head must not hide behind the torso
            pass
        items.append((9, "head", hs.premult, T(xh, yh) @ S(ppu_root * qh * (-1 if side < 0 else 1), ppu_root * qh)
                      @ T(0, -210 * ctx.ppu * w.kr * lvl / ctx.ppu / w.kr / lvl) @ hs.pixel_to_unit(), True, 0))
        items.sort(key=lambda it: it[0])
        # ---- per-figure buffer
        boxes = []
        for it in items:
            h_, w_ = it[2].shape[:2]
            c = np.array([[0, 0, 1], [w_, 0, 1], [0, h_, 1], [w_, h_, 1]], float) @ it[3].T
            boxes.append((c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()))
        pad = 10
        x0 = int(max(0, min(b[0] for b in boxes) - pad))
        y0 = int(max(0, min(b[1] for b in boxes) - pad))
        x1 = int(min(W, max(b[2] for b in boxes) + pad))
        y1 = int(min(H, max(b[3] for b in boxes) + pad))
        if x1 <= x0 or y1 <= y0:
            return
        buf = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
        off = T(-x0, -y0)
        kpx = ppu_root * q_root
        sdx, sdy = 7 * kpx, 9 * kpx
        for order, name, pm, Mm, drop, _ in items:
            Mo = off @ Mm
            if drop:
                r = _warp_roi(pm, T(sdx, sdy) @ Mo, buf.shape[1], buf.shape[0])
                if r is not None:
                    ww, a0, b0, a1, b1 = r
                    a = cv2.GaussianBlur(ww[..., 3].astype(np.float32) / 255.0, (0, 0), max(0.6, 3 * kpx))
                    sub = buf[b0:b1, a0:a1]
                    sub[..., :3] *= (1 - 0.42 * a[..., None] * (1 - self.tint))
            r = _warp_roi(pm, Mo, buf.shape[1], buf.shape[0])
            if r is None:
                continue
            ww, a0, b0, a1, b1 = r
            f = ww.astype(np.float32) / 255.0
            sub = buf[b0:b1, a0:a1]
            sub *= 1 - f[..., 3:4]
            sub += f
        # ---- lighting by location (sun / gate shadow / passage) applied to the figure
        light, tint_to = (1.0, None) if self.light_fn is None else self.light_fn(q_root)
        if light < 0.999:
            tt = np.array(tint_to, np.float32) / 255.0
            buf[..., :3] = buf[..., :3] * light + tt * buf[..., 3:4] * (1 - light)
        # ---- clip (tunnel opening at this depth)
        if self.clip_fn is not None:
            poly = self.clip_fn(q_root)
            if poly is not None:
                Lm = layer_matrix(ctx, cam, self.g.parallax(q_root))
                pts = (np.c_[np.array(poly), np.ones(len(poly))] @ Lm.T)[:, :2] - (x0, y0)
                m = np.zeros(buf.shape[:2], np.float32)
                cv2.fillPoly(m, [np.round(pts * 4).astype(np.int32)], 1.0, cv2.LINE_AA, shift=2)
                buf *= m[..., None]
        # ---- ground shadows: contact under each foot (+ projected cast shadow in sunlight)
        sh = np.zeros(buf.shape[:2], np.float32)
        fx_, fy_, _, _ = P((0, 0, 0), psi)
        if q_root >= self.shadow_q:
            shx, sy = self.sun
            fyb = fy_ - y0
            Pm = np.array([[1, -shx, shx * fyb], [0, sy, (1 - sy) * fyb]], np.float32)
            sh = cv2.warpAffine(buf[..., 3], Pm, (buf.shape[1], buf.shape[0]))
            sh = cv2.GaussianBlur(sh, (0, 0), max(0.8, 2.5 * kpx)) * 0.42
        for leg in ("n", "f"):
            Lg = L[leg]
            a, b, c = Lg["ankle"]
            xg, yg, qg, _ = P((a - 20, b, 0), psi)
            ww = 140 * ppu_root * qg
            hh = ww * 0.26
            o = max(0.0, 1 - Lg["up"] / 40) * 0.6
            cv2.ellipse(sh, (int((xg - x0) * 4), int((yg - y0) * 4)), (max(1, int(ww * 2)), max(1, int(hh * 2))), 0, 0, 360,
                        float(o), -1, cv2.LINE_AA, shift=2)
        sh = cv2.GaussianBlur(sh, (0, 0), max(0.8, 1.5 * kpx))
        if self.clip_fn is not None and self.clip_fn(q_root) is not None:
            sh *= 0.6
        roi = frame[y0:y1, x0:x1]
        roi *= 1 - np.clip(sh, 0, 0.8)[..., None] * (1 - self.tint)
        roi *= 1 - buf[..., 3:4]
        roi += buf[..., :3]

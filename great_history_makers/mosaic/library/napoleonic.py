"""Napoleonic-era art kit (Episode 02): costumes for the turning rig, profile figures for
close shots, props and environments. Uniform references: French line infantry 1804-12
(blue habit with white lapels/turnbacks, red collar/cuffs, white breeches, black gaiters,
shako with brass plate, calfskin knapsack), Old Guard grenadiers (bearskin, red plume and
epaulettes), Napoleon (bicorne worn 'en bataille', grey redingote over the green Guard
chasseur coat, white breeches, riding boots), British line infantry 1815 (red coat, Belgic
shako, grey trousers), Coronation robes 1804 (crimson velvet mantle sewn with golden bees,
ermine, gold laurel wreath). Simplified for mosaic; see episodes/ep02_napoleon/HISTORY.md."""
import math
import random

import numpy as np

from ..palette import mix
from .figures import _face, _hand
from . import mesopotamia as M


def _sc(th):
    return math.sin(math.radians(th)), math.cos(math.radians(th))


# =============================================================================== faces
def front_face(p, skin="skin", hair="hair", hair_style="short", moustache=False, yaw=0.0, heavy=0.0, eye_w=1.0):
    """Face seen from the front (yaw=0) or 3/4 (yaw>0 turns toward screen-left, up to ~60).
    Head local coords: neck pivot (0, 210), chin ~ y=190, crown ~ y=20 (same as profile _face)."""
    sh = -yaw / 60.0                            # features shift toward the facing side
    w = 54 + 10 * heavy
    p.smooth([(-w, 70), (-w + 4, 140), (-w * 0.7, 184), (0, 202 + 6 * heavy), (w * 0.7, 184), (w - 4, 140), (w, 70),
              (w * 0.7, 30), (0, 18), (-w * 0.7, 30)], skin, 8)
    if hair_style == "short":
        p.smooth([(-w - 4, 90), (-w - 2, 40), (-w * 0.5, 14), (0, 8), (w * 0.5, 14), (w + 2, 40), (w + 4, 90), (w * 0.7, 52),
                  (0, 40 + 8 * sh), (-w * 0.7, 52)], hair, 6)
    elif hair_style == "long":                  # young officer 1790s: hair to the jaw
        p.smooth([(-w - 8, 160), (-w - 6, 40), (-w * 0.5, 10), (0, 4), (w * 0.5, 10), (w + 6, 40), (w + 8, 160), (w - 4, 120),
                  (w * 0.6, 50), (0, 44), (-w * 0.6, 50), (-w + 4, 120)], hair, 6)
    cx = 30 * sh
    for ex in (-22, 22):
        x = cx + ex * (1 - 0.35 * abs(sh)) * eye_w
        p.ellipse(x, 104, 10, 6, "ivory")
        p.circle(x, 104, 4.5, "black")
        p.curve([(x - 11, 92), (x, 89), (x + 11, 92)], hair, 4)
    p.poly([(cx - 3, 108), (cx + 8 * sh - 9, 142), (cx + 8 * sh + 7, 144)], "skin_sh")   # nose
    p.curve([(cx - 12, 164), (cx, 168), (cx + 12, 164)], "terracotta_dk", 4)              # mouth
    if moustache:
        p.smooth([(cx - 22, 156), (cx, 150), (cx + 22, 156), (cx, 160)], hair, 4)
    p.ellipse(-w + 2, 118, 7, 14, "skin_sh")
    p.ellipse(w - 2, 118, 7, 14, "skin_sh")


def back_head(p, skin="skin", hair="hair", hair_style="short"):
    w = 54
    p.smooth([(-w, 70), (-w + 2, 150), (-w * 0.6, 196), (0, 204), (w * 0.6, 196), (w - 2, 150), (w, 70), (w * 0.7, 26),
              (0, 16), (-w * 0.7, 26)], skin, 8)
    if hair_style == "long":
        p.smooth([(-w - 8, 170), (-w - 6, 40), (0, 4), (w + 6, 40), (w + 8, 170), (0, 186)], hair, 6)
    else:
        p.smooth([(-w - 3, 150), (-w - 2, 40), (0, 8), (w + 2, 40), (w + 3, 150), (0, 166)], hair, 6)
    p.ellipse(-w - 2, 118, 7, 14, "skin_sh")
    p.ellipse(w + 2, 118, 7, 14, "skin_sh")


def profile_face(p, skin="skin", hair="hair", hair_style="short", moustache=False):
    """Profile (facing left), mosaic convention (frontal eye), clean-shaven."""
    _face(p, skin=skin, beard_len=0, ear=True, brow=hair)
    if hair_style == "long":
        p.smooth([(-30, 30), (10, 10), (44, 40), (52, 120), (44, 182), (20, 186), (26, 120), (12, 70), (-20, 52)], hair, 6)
    else:
        p.smooth([(-34, 32), (8, 14), (40, 38), (46, 100), (34, 138), (22, 112), (12, 66), (-24, 52)], hair, 6)
    if moustache:
        p.smooth([(-66, 140), (-48, 134), (-36, 142), (-56, 146)], hair, 4)


def head_by_view(p, th, skin="skin", hair="hair", hair_style="short", moustache=False, heavy=0.0):
    """Head for a turning view th: 0 rear .. 90 profile (facing left) .. 180 front."""
    if th < 34:
        back_head(p, skin, hair, hair_style)
    elif th < 56:                               # rear 3/4: back of head + cheek edge
        back_head(p, skin, hair, hair_style)
        p.smooth([(-58, 96), (-40, 92), (-42, 160), (-56, 190), (-64, 150)], skin, 4)
        p.ellipse(-30, 118, 7, 14, "skin_sh")
    elif th <= 112:
        sx = 1.0 - 0.3 * abs(th - 90) / 34
        p.push()
        p.scale(sx, 1)
        profile_face(p, skin, hair, hair_style, moustache)
        p.pop()
    else:
        front_face(p, skin, hair, hair_style, moustache, yaw=max(0.0, (180 - th) * 0.9), heavy=heavy)


# =============================================================================== hats
def shako(p, th, body="black", plate="brass", pompom="crimson"):
    s, r = _sc(th)
    w = 50 + 6 * abs(r)
    p.poly([(-w, 40), (-w - 6, -150), (w + 6, -150), (w, 40)], body)
    p.rect(-w - 7, -158, 2 * w + 14, 14, plate if False else "umber")
    p.rect(-w, 26, 2 * w, 16, "umber")
    fx = -w * s * 0.85 if th < 170 else 0.0       # front of the shako
    if th > 40:                                     # visor
        if th > 112:
            p.ellipse(fx * 0.4, 44, w + 6, 14, "black", 0, 180)
        else:
            p.poly([(-w - 4, 40), (-w - 50 * s, 52), (-w, 52)], "black")
    if th > 50:                                     # brass plate + pompom on the front
        px = fx * 0.6 if th < 150 else 0.0
        pw = 30 * (abs(r) if th > 95 else 0.35) + 8
        p.poly([(px, -120), (px + pw, -60), (px, -10), (px - pw, -60)], plate)
        p.ellipse(px, -176, 18, 26, pompom)
    else:
        p.ellipse(0, -176, 18, 26, mix(pompom, "black", 0.3))
    p.line([(-w + 4, 36), (-w + 10, 140)], "brass", 4)   # chinscales
    p.line([(w - 4, 36), (w - 10, 140)], "brass", 4)


def bearskin(p, th, plume="crimson", plate="brass"):
    s, r = _sc(th)
    p.smooth([(-62, 44), (-74, -120), (-50, -250), (0, -276), (50, -250), (74, -120), (62, 44)], "black", 8)
    for k in range(-40, 50, 22):
        p.line([(k, -230), (k * 1.1, 30)], "hair", 4)
    if th > 100:
        p.poly([(-38, 10), (0, -80), (38, 10)], plate)
    side = -1 if th < 90 else 1
    p.ellipse(side * 58, -200, 12, 60, plume)
    p.curve([(-54, -40), (0, -10), (54, -40)], "ivory", 5)


def bicorne(p, th, cockade=True):
    """Worn 'en bataille' (points over the shoulders): crescent from front/back, narrow from the side."""
    s, r = _sc(th)
    w = 46 + 92 * abs(r)
    p.smooth([(-w, 24), (-w * 0.6, -54), (0, -86), (w * 0.6, -54), (w, 24), (w * 0.5, 4), (0, 0), (-w * 0.5, 4)], "black", 8)
    p.curve([(-w * 0.9, 18), (-w * 0.5, -40), (0, -70), (w * 0.5, -40), (w * 0.9, 18)], "hair", 4)
    if cockade and th > 60:                         # tricolour cockade on the left side of the hat
        cx = -w * 0.55 if th > 112 else -w * 0.2
        p.circle(cx, -30, 15, "crimson")
        p.circle(cx, -30, 10, "white")
        p.circle(cx, -30, 5, "fr_blue")


def wreath(p):
    """Gold laurel wreath (coronation)."""
    for side in (-1, 1):
        for k in range(7):
            a = math.radians(200 - k * 24) if side < 0 else math.radians(-20 + k * 24)
            x, y = side * 50 * abs(math.cos(a)) * 1.0, 60 - 26 * math.sin(a) * 0 - k * 2
            p.ellipse(side * (54 - k * 3), 66 - k * 9, 14, 7, "gold")
    p.rect(-56, 64, 112, 8, "gold_lt")


# =============================================================================== torsos
def coat_torso(p, th, coat="fr_blue", lapel="white", collar="crimson", turnback="white", vest="white",
               belts=True, long_coat=False, epaulette=None, buttons="brass"):
    """Habit-veste (or long redingote) torso, local origin = pelvis centre (c=425), y down."""
    s, r = _sc(th)
    front = r < 0                                   # th > 90 -> chest toward camera
    sh, wa = 50 * s + 80 * abs(r), 44 * s + 60 * abs(r)
    hem = 210 if long_coat else 120
    he = (70 * s + 82 * abs(r)) if long_coat else wa + 6
    y_sh, y_be = -327, -45
    pts = [(-sh, y_sh + 10), (-sh - 6 * s, y_sh + 80), (-wa, y_be), (-he, hem), (he, hem), (wa, y_be), (sh, y_sh + 60),
           (sh * 0.8, y_sh + 6)]
    p.smooth(pts, coat, 7)
    if not long_coat:                               # tails behind the legs
        tx = 40 * s + 6
        if th < 112:
            p.poly([(wa * 0.2 + tx * 0.3, y_be), (wa + tx * 0.6, y_be), (wa * 0.8 + tx, 230), (wa * 0.1 + tx * 0.5, 230)], coat)
            p.poly([(wa * 0.8 + tx - 8, 160), (wa * 0.8 + tx, 230), (wa * 0.1 + tx * 0.5, 230)], turnback)
        if th < 40:
            p.line([(0, y_be), (0, 230)], mix(coat, "black", 0.4), 5)
    # front details
    if th > 45:
        fx = -sh * s if th <= 112 else 0.0
        lw = 14 + 40 * max(0.0, -r)                 # lapel width grows toward the front view
        if th > 112:
            p.poly([(-lw, y_sh + 30), (lw, y_sh + 30), (lw * 0.8, y_be - 6), (-lw * 0.8, y_be - 6)], lapel)
            for yb in range(int(y_sh + 50), int(y_be), 38):
                p.circle(-lw * 0.7, yb, 5, buttons)
                p.circle(lw * 0.7, yb, 5, buttons)
            p.poly([(-wa * 0.7, y_be), (wa * 0.7, y_be), (wa * 0.5, 70), (-wa * 0.5, 70)], vest)
        else:
            p.poly([(fx, y_sh + 30), (fx + lw, y_sh + 34), (fx + lw * 0.8, y_be - 6), (fx + 4, y_be - 6)], lapel)
            p.poly([(fx + 2, y_be), (fx + 30, y_be), (fx + 22, 60), (fx + 4, 60)], vest)
    p.rect(-sh * 0.6, y_sh - 6, sh * 1.2, 34, collar)
    if belts:                                       # white crossbelts (front or back)
        p.line([(-sh * 0.8, y_sh + 34), (wa * 0.8, y_be + 40)], "white", 14)
        p.line([(sh * 0.8, y_sh + 34), (-wa * 0.8, y_be + 40)], "white", 14)
        if th > 112:
            p.circle(0, y_sh + 150, 9, "brass")
    if epaulette:
        for sx_ in (-1, 1):
            if (th > 112 or th < 68) or sx_ == (1 if th <= 90 else -1):
                p.ellipse(sx_ * (sh - 4), y_sh + 10, 24, 12, epaulette)
                for k in range(-18, 20, 7):
                    p.line([(sx_ * (sh - 4) + k, y_sh + 18), (sx_ * (sh - 4) + k, y_sh + 38)], epaulette, 4)
    p.rect(-20, y_sh - 46, 40, 50, "skin" if th > 40 else coat)


def greatcoat_torso(p, th, coat="grey_coat", collar_up=False, scarf=None):
    s, r = _sc(th)
    sh, wa, he = 52 * s + 82 * abs(r), 50 * s + 66 * abs(r), 80 * s + 92 * abs(r)
    y_sh = -327
    p.smooth([(-sh, y_sh + 10), (-sh - 6 * s, y_sh + 80), (-wa, -45), (-he, 250), (he, 250), (wa, -45), (sh, y_sh + 60),
              (sh * 0.8, y_sh + 6)], coat, 7)
    dk = mix(coat, "black", 0.35)
    for k in (-0.5, 0.0, 0.5):
        p.line([(k * wa, -20), (k * he * 1.1, 240)], dk, 6)
    if th > 112:                                     # double-breasted buttons
        for yb in range(y_sh + 60, 40, 46):
            p.circle(-20, yb, 5, "brass")
            p.circle(20, yb, 5, "brass")
    p.rect(-wa, -56, 2 * wa, 16, dk)
    p.rect(-sh * 0.62, y_sh - (30 if collar_up else 6), sh * 1.24, 44 if collar_up else 30, dk)
    if scarf:
        p.ellipse(0, y_sh - 6, sh * 0.6, 24, scarf)
        if th > 90:
            p.poly([(-10, y_sh), (10, y_sh), (16, y_sh + 120), (-4, y_sh + 116)], scarf)
    p.rect(-20, y_sh - 46, 40, 50, "skin" if th > 40 else coat)


def knapsack(p, th):
    s, r = _sc(th)
    w = 40 * s + 64 * abs(r)
    if th > 100:
        p.rect(-w, -170, 2 * w, 40, "grey_coat")       # rolled greatcoat visible over shoulders
        return
    p.smooth([(-w, -150), (w, -150), (w + 4, 80), (-w - 4, 80)], "brick", 4)    # calfskin pack
    for k in range(-int(w) + 10, int(w) - 6, 16):
        p.line([(k, -140), (k + 4, 70)], mix("brick", "sand", 0.35), 3)
    p.smooth([(-w - 14, -196), (w + 14, -196), (w + 18, -150), (-w - 18, -150)], "grey_coat", 4)   # rolled greatcoat
    p.line([(-w * 0.5, -196), (-w * 0.5, 80)], "white", 6)
    p.line([(w * 0.5, -196), (w * 0.5, 80)], "white", 6)


def boot_view(p, th, col="black"):
    s, _ = _sc(th)
    ln = 22 + 78 * s
    if th > 112:                                     # toes toward the camera: short front oval
        p.smooth([(-24, -28), (24, -28), (30, 30), (0, 40), (-30, 30)], col, 5)
        return
    p.smooth([(-22, -28), (24, -28), (28, 32), (-ln, 32), (-ln - 4, 18), (-ln * 0.55, -6)], col, 5)
    p.poly([(-ln - 4, 24), (28, 24), (28, 36), (-ln - 4, 36)], "black")


def musket(p):
    p.smooth([(-14, 70), (14, 70), (10, -40), (6, -260), (-6, -260), (-10, -40)], "wood", 4)   # stock
    p.line([(0, -260), (0, -900)], "steel", 9)
    p.line([(-3, -260), (-3, -900)], "white", 2)
    p.line([(4, -880), (4, -1140)], "steel", 5)          # bayonet
    p.poly([(2, -1140), (8, -1140), (5, -1180)], "steel")
    p.circle(0, -560, 7, "brass")


def eagle_standard(p):
    p.line([(0, 90), (0, -1100)], "fr_blue_dk", 10)
    p.poly([(0, -1160), (-40, -1200), (-28, -1150), (-8, -1136), (8, -1136), (28, -1150), (40, -1200)], "gold")
    p.circle(0, -1170, 14, "gold_lt")
    p.rect(-24, -1120, 48, 18, "gold")


def flag_1804(p, th):
    """Regimental colour, 1804 pattern: white lozenge, blue and red corners. Hoist at x=0."""
    s, _ = _sc(th)
    w = 60 + 380 * max(0.18, s)
    h = 330
    p.rect(0, 0, w, h, "white")
    p.poly([(0, 0), (w / 2, 0), (0, h / 2)], "fr_blue")
    p.poly([(w, h), (w / 2, h), (w, h / 2)], "fr_blue")
    p.poly([(w, 0), (w / 2, 0), (w, h / 2)], "crimson")
    p.poly([(0, h), (w / 2, h), (0, h / 2)], "crimson")
    p.rect(0, 0, w, 10, "gold")
    p.rect(0, h - 10, w, 10, "gold")
    if w > 160:
        p.ellipse(w / 2, h / 2, 26, 34, "gold")


# =============================================================================== costumes (turnrig)
class NapoCostume:
    front = True
    arm_mode = "weapon"
    torso_rect = (-170, -440, 340, 720)
    flag = None
    shield = None

    def boot(self, p, th):
        boot_view(p, th, self.boot_col)

    def weapon(self, p):
        musket(p)


class FrenchLine(NapoCostume):
    boot_col = "black"

    def __init__(self, variant=0, standard=False):
        self.variant, self.standard = variant, standard
        self.name = f"frline{variant}{'s' if standard else ''}"
        self.coat = ["fr_blue", "fr_blue", "fr_blue_dk"][variant % 3]
        self.skin = ["skin", "skin_dk", "skin"][variant % 3]
        self.hair = ["hair", "hair_lt", "hair"][variant % 3]
        self.pompom = ["crimson", "emerald", "gold"][variant % 3]
        self.tubes = dict(thigh_n=("white", None), thigh_f=("bone", None), shin_n=("white", "black"),
                          shin_f=("bone", "black"), uarm_n=(self.coat, None), uarm_f=(mix(self.coat, "black", 0.3), None),
                          farm_n=(self.coat, "crimson"), farm_f=(mix(self.coat, "black", 0.3), "crimson_dk"))
        if standard:
            self.flag = flag_1804

    def torso(self, p, th):
        coat_torso(p, th, self.coat)

    def head(self, p, th):
        head_by_view(p, th, self.skin, self.hair, moustache=self.variant == 1)
        p.push()
        p.translate(0, 34)
        shako(p, th, pompom=self.pompom)
        p.pop()

    def pack(self, p, th):
        knapsack(p, th)

    def weapon(self, p):
        if self.standard:
            eagle_standard(p)
        else:
            musket(p)


class OldGuard(FrenchLine):
    def __init__(self, variant=0):
        super().__init__(variant)
        self.name = f"oldguard{variant}"
        self.coat = "fr_blue_dk"
        self.tubes.update(uarm_n=(self.coat, None), farm_n=(self.coat, "crimson"))

    def torso(self, p, th):
        coat_torso(p, th, self.coat, epaulette="crimson")

    def head(self, p, th):
        head_by_view(p, th, self.skin, self.hair, moustache=True)
        p.push()
        p.translate(0, 40)
        bearskin(p, th)
        p.pop()


class Redcoat(FrenchLine):
    def __init__(self, variant=0):
        super().__init__(variant)
        self.name = f"redcoat{variant}"
        self.coat = "red_coat"
        self.tubes = dict(thigh_n=("grey_coat", None), thigh_f=("grey_coat_dk", None), shin_n=("grey_coat", "black"),
                          shin_f=("grey_coat_dk", "black"), uarm_n=("red_coat", None), uarm_f=("crimson_dk", None),
                          farm_n=("red_coat", "white"), farm_f=("crimson_dk", "white"))

    def torso(self, p, th):
        coat_torso(p, th, "red_coat", lapel="red_coat", collar="lapis_dk", turnback="white", vest="red_coat")

    def head(self, p, th):
        head_by_view(p, th, self.skin, self.hair)
        p.push()
        p.translate(0, 34)
        shako(p, th, body="black", plate="brass", pompom="white")
        p.pop()


class Retreat(FrenchLine):
    """1812 retreat: greatcoats, wrapped scarves, collars up, shako covers, slung muskets."""

    def __init__(self, variant=0):
        super().__init__(variant)
        self.name = f"retreat{variant}"
        self.gc = ["grey_coat", "smoke", "umber"][variant % 3]
        self.scarf = ["crimson_dk", "olive", "lapis_dk"][variant % 3]
        self.tubes = dict(thigh_n=(self.gc, None), thigh_f=(mix(self.gc, "black", 0.3), None), shin_n=("stone_dk", "umber"),
                          shin_f=("grey_coat_dk", "umber"), uarm_n=(self.gc, None), uarm_f=(mix(self.gc, "black", 0.3), None),
                          farm_n=(self.gc, None), farm_f=(mix(self.gc, "black", 0.3), None))

    def torso(self, p, th):
        greatcoat_torso(p, th, self.gc, collar_up=True, scarf=self.scarf)

    def head(self, p, th):
        head_by_view(p, th, "skin_sh", self.hair, moustache=True)
        p.push()
        p.translate(0, 30)
        shako(p, th, body="smoke", plate="smoke", pompom="smoke")
        p.pop()
        if th > 60:
            p.smooth([(-60, 150), (60, 150), (56, 210), (-56, 210)], self.scarf, 4)   # scarf over the chin


class NapoleonCostume(NapoCostume):
    """Napoleon for the turning rig: grey redingote over the green chasseur coat, bicorne."""
    arm_mode = "swing"
    boot_col = "black"

    def __init__(self, outfit="redingote", heavy=0.0):
        self.outfit, self.heavy = outfit, heavy
        self.name = f"napoleon_{outfit}{heavy}"
        coat = "grey_coat" if outfit == "redingote" else "green_coat"
        self.coat = coat
        self.tubes = dict(thigh_n=("white", None), thigh_f=("bone", None), shin_n=("black", "black"), shin_f=("black", "black"),
                          uarm_n=(coat, None), uarm_f=(mix(coat, "black", 0.3), None), farm_n=(coat, None),
                          farm_f=(mix(coat, "black", 0.3), None))

    weapon = None
    pack = None

    def torso(self, p, th):
        if self.outfit == "redingote":
            greatcoat_torso(p, th, "grey_coat")
            if th > 112:
                p.poly([(-26, -300), (26, -300), (20, -120), (-20, -120)], "green_coat")   # chasseur coat beneath
                p.poly([(-12, -300), (12, -300), (8, -180), (-8, -180)], "white")
        else:
            coat_torso(p, th, "green_coat", lapel="green_coat", collar="crimson", turnback="crimson", belts=False,
                       epaulette="gold")

    def head(self, p, th):
        head_by_view(p, th, "skin", "hair", heavy=self.heavy)
        p.push()
        p.translate(0, 46)
        bicorne(p, th)
        p.pop()


# =============================================================================== profile figures
from ..scene import Figure, PartSpec  # noqa: E402


def napoleon_profile(ctx, k, tile=5.0, outfit="officer", haze=None, haze_amt=0.0, volume=None, pose="stand"):
    """Napoleon in profile facing left. outfit: officer (1793, artillery officer's blue coat, long
    hair), redingote (grey greatcoat, bicorne), coronation (crimson mantle with bees, ermine,
    laurel), exile (green coat, older/heavier)."""
    young = outfit == "officer"
    heavy = 1.0 if outfit == "exile" else 0.0

    def head(p):
        hs = "long" if young else "short"
        profile_face(p, "skin", "hair", hs)
        if heavy:
            p.smooth([(-50, 168), (-30, 196), (10, 200), (24, 170)], "skin", 4)     # fuller jaw
        if outfit == "coronation":
            p.push()
            p.translate(0, 0)
            for kk in range(7):
                p.ellipse(-44 + kk * 14, 46 - abs(kk - 3) * 4, 13, 7, "gold")
            p.rect(-50, 50, 100, 8, "gold_lt")
            p.pop()
        else:
            p.push()
            p.translate(0, 46)
            bicorne(p, 90)
            p.pop()

    def body(p):
        p.rect(-22, 150, 44, 110, "skin")
        if outfit == "coronation":
            p.smooth([(-50, 240), (-66, 330), (-58, 480), (-74, 980), (80, 990), (66, 480), (60, 300), (50, 240)], "ermine", 6)
            p.rect(-62, 460, 124, 18, "gold")
            for y in range(560, 960, 90):
                p.line([(-60, y), (64, y + 6)], "gold_lt", 4)
        elif outfit == "officer":
            p.smooth([(-50, 244), (-70, 320), (-62, 470), (-60, 560), (64, 560), (60, 470), (66, 300), (50, 244)], "fr_blue", 6)
            p.poly([(-62, 300), (-40, 300), (-44, 470), (-60, 470)], "crimson")       # artillery facings
            p.poly([(40, 470), (70, 470), (66, 760), (36, 760)], "fr_blue")          # coat tail
            p.rect(-58, 470, 116, 18, "white")
            p.smooth([(-40, 560), (40, 560), (34, 700), (-34, 700)], "white", 4)     # breeches
            for x in (-28, 18):
                p.smooth([(x - 18, 690), (x + 18, 690), (x + 16, 990), (x - 16, 990)], "black", 4)
                p.ellipse(x - 20, 992, 30, 10, "black")
            p.ellipse(56, 250, 26, 12, "gold")                                        # epaulette
        else:
            coat = "grey_coat" if outfit == "redingote" else "green_coat"
            w = 1.0 + 0.15 * heavy
            p.smooth([(-50 * w, 244), (-74 * w, 330), (-72 * w, 480), (-88 * w, 820), (84 * w, 820), (70 * w, 480),
                      (64 * w, 300), (50 * w, 244)], coat, 6)
            if outfit == "exile":
                p.smooth([(-74 * w, 420), (-40, 410), (-38, 560), (-70 * w, 560)], "white", 4)   # waistcoat
            for x in (-26, 16):
                p.smooth([(x - 18, 800), (x + 18, 800), (x + 16, 990), (x - 16, 990)], "black", 4)
                p.ellipse(x - 20, 992, 30, 10, "black")
            p.rect(-24, 760, 48, 50, "white")

    def mantle(p):
        p.smooth([(10, 236), (70, 244), (160, 520), (220, 980), (-40, 1000), (-10, 700), (0, 400)], "crimson", 8)
        rnd = random.Random(4)
        for _ in range(30):                                                           # golden bees
            x, y = rnd.uniform(0, 170), rnd.uniform(320, 960)
            if x < 30 + (y - 300) * 0.24:
                p.ellipse(x, y, 7, 9, "gold")
        p.smooth([(0, 236), (70, 240), (80, 330), (-20, 340), (-40, 270)], "ermine", 6)  # ermine cape
        for x, y in ((10, 280), (40, 300), (60, 270)):
            p.ellipse(x, y, 4, 8, "black")

    def cape(p):
        p.smooth([(20, 240), (70, 250), (110, 480), (130, 800), (40, 820), (20, 500)], "grey_coat_dk", 8)

    def arm(p):
        col = {"officer": "fr_blue", "coronation": "crimson", "redingote": "grey_coat", "exile": "green_coat"}[outfit]
        p.smooth([(-30, 252), (26, 252), (24, 420), (-10, 470), (-74, 486), (-80, 452), (-18, 420)], col, 6)
        _hand(p, x=-92, y=470)

    def crown_arms(p):                                                                # both arms raised (coronation)
        p.smooth([(-30, 252), (26, 252), (20, 330), (-60, 140), (-90, 160)], "crimson", 6)
        p.smooth([(-90, 160), (-60, 140), (-50, 40), (-80, 30)], "ermine", 5)
        _hand(p, x=-70, y=24)

    def crown(p):
        p.ellipse(-70, -20, 46, 18, "gold")
        for kk in range(5):
            p.ellipse(-104 + kk * 17, -38 - abs(kk - 2) * 4, 9, 14, "gold_lt")
        p.circle(-70, -52, 8, "crimson")

    parts = [PartSpec("body", body, pivot=(0, 990), z=1),
             PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.62)]
    if outfit == "coronation":
        parts += [PartSpec("cloak", mantle, pivot=(40, 250), parent="body", z=0,
                           deform=dict(amp=5, wl=520, speed=0.3, axis="y", anchor=0.0, power=1.5)),
                  PartSpec("arm", crown_arms, pivot=(-2, 262), parent="body", z=4),
                  PartSpec("crown", crown, pivot=(-70, 20), parent="arm", z=5, tile_mul=0.7)]
    else:
        if outfit in ("redingote", "exile"):
            parts.append(PartSpec("cloak", cape, pivot=(40, 250), parent="body", z=0,
                                  deform=dict(amp=9, wl=380, speed=0.5, axis="y", anchor=0.0, power=1.3)))
        parts.append(PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=4))
    return Figure(ctx, f"napprof_{outfit}", parts, k, tile, haze, haze_amt, volume=volume)


def gunner(ctx, k, tile=5.0, variant=0, tool="rammer", volume=None):
    """Foot artillery gunner (blue coat, red facings) with rammer or linstock."""
    def body(p):
        p.rect(-22, 150, 44, 110, "skin" if variant % 2 == 0 else "skin_dk")
        p.smooth([(-50, 244), (-70, 320), (-62, 470), (-62, 560), (64, 560), (60, 470), (66, 300), (50, 244)], "fr_blue_dk", 6)
        p.poly([(40, 470), (70, 470), (66, 720), (36, 720)], "fr_blue_dk")
        p.poly([(56, 640), (66, 720), (36, 720)], "crimson")
        p.line([(-56, 270), (56, 470)], "white", 12)
        p.smooth([(-40, 560), (40, 560), (34, 720), (-34, 720)], "white", 4)
        for x in (-28, 18):
            p.smooth([(x - 18, 700), (x + 18, 700), (x + 16, 990), (x - 16, 990)], "black", 4)
            p.ellipse(x - 20, 992, 30, 10, "black")

    def head(p):
        profile_face(p, "skin" if variant % 2 == 0 else "skin_dk", "hair", "short", moustache=True)
        p.push()
        p.translate(0, 34)
        shako(p, 90, pompom="crimson")
        p.pop()

    def arm(p):
        p.smooth([(-30, 252), (26, 252), (24, 420), (-10, 470), (-74, 486), (-80, 452), (-18, 420)], "fr_blue_dk", 6)
        _hand(p, x=-92, y=470)
        if tool == "rammer":
            p.line([(-300, 330), (160, 560)], "wood", 10)
            p.ellipse(-310, 326, 22, 16, "umber")
        else:
            p.line([(-92, 470), (-200, 200)], "wood", 8)
            p.circle(-204, 192, 9, "fire")

    parts = [PartSpec("body", body, pivot=(0, 990), z=1),
             PartSpec("head", head, pivot=(0, 210), parent="body", z=2, tile_mul=0.62),
             PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=3)]
    return Figure(ctx, f"gunner{variant}{tool}", parts, k, tile, volume=volume)


def courtier(ctx, k, tile=5.0, variant=0, volume=None):
    """Coronation guest: court dress (embroidered habit, sash) or gown (women)."""
    looks = [("m", "crimson_dk", "gold"), ("f", "ivory", "gold"), ("m", "fr_blue", "gold"), ("f", "emerald", "white"),
             ("m", "green_coat", "gold"), ("f", "purple", "gold"), ("c", "crimson", "ivory")]   # c = cardinal
    sex, col, trim = looks[variant % len(looks)]

    def body(p):
        p.rect(-22, 150, 44, 110, "skin")
        hem = 985 if sex in ("f", "c") else 640
        p.smooth([(-46, 244), (-64, 330), (-58, 470), (-76 if sex != "m" else -60, hem), (78 if sex != "m" else 62, hem),
                  (66, 470), (62, 300), (46, 244)], col, 6)
        if sex == "m":
            p.line([(-50, 280), (50, 460)], trim, 10)
            p.smooth([(-40, 640), (40, 640), (34, 760), (-34, 760)], "white", 4)
            for x in (-26, 16):
                p.smooth([(x - 14, 750), (x + 14, 750), (x + 12, 990), (x - 12, 990)], "white", 4)
                p.ellipse(x - 18, 992, 26, 9, "black")
        else:
            p.rect(-60, 360, 124, 14, trim)
            p.poly([(-76, 940), (78, 940), (78, 985), (-76, 985)], trim)

    def head(p):
        if sex == "f":
            profile_face(p, "skin", "hair_lt" if variant % 2 else "hair", "short")
            p.smooth([(-20, 20), (40, 10), (60, 80), (44, 150), (20, 120)], "hair_lt" if variant % 2 else "hair", 5)
            p.ellipse(10, 4, 30, 12, "gold")
        elif sex == "c":
            profile_face(p, "skin", "grey_hair", "short")
            p.ellipse(10, 40, 46, 22, "crimson", 180, 360)
        else:
            profile_face(p, "skin", "grey_hair" if variant == 4 else "hair", "short")

    def arm(p):
        p.smooth([(-28, 252), (24, 252), (26, 430), (-40, 476), (-64, 470), (-58, 440), (-8, 410)], col, 6)
        p.ellipse(-70, 460, 16, 14, "skin")

    parts = [PartSpec("body", body, pivot=(0, 990), z=1),
             PartSpec("head", head, pivot=(0, 210), parent="body", z=2, tile_mul=0.65),
             PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=3)]
    return Figure(ctx, f"courtier{variant}", parts, k, tile, volume=volume)


def pope_seated(ctx, k, tile=5.0, volume=None):
    """Pope Pius VII seated (white cassock, red mozzetta), as present at the coronation."""
    def body(p):
        p.rect(-22, 150, 44, 110, "skin")
        p.smooth([(-46, 244), (-66, 330), (-60, 520), (-140, 560), (-150, 760), (-120, 990), (60, 990), (70, 560), (60, 300),
                  (46, 244)], "white", 6)
        p.smooth([(-50, 244), (50, 244), (66, 360), (-66, 360)], "crimson", 5)
        p.line([(-40, 300), (-30, 600)], "gold", 6)

    def head(p):
        profile_face(p, "skin", "grey_hair", "short")
        p.ellipse(10, 34, 40, 14, "white", 180, 360)

    def arm(p):
        p.smooth([(-28, 252), (24, 252), (20, 420), (-60, 480), (-70, 450)], "white", 6)
        p.ellipse(-76, 460, 16, 14, "skin")

    parts = [PartSpec("body", body, pivot=(0, 990), z=1), PartSpec("head", head, pivot=(0, 210), parent="body", z=2, tile_mul=0.62),
             PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=3)]
    return Figure(ctx, "pope", parts, k, tile, volume=volume)


def cuirassier_horse(ctx, k, tile=5.0, variant=0, volume=None):
    """Horse (gallop rig) with a French cuirassier (steel cuirass, crested helmet)."""
    from .figures import horse
    f = horse(ctx, k, tile, variant=variant, rider=True)
    # replace the Persian rider parts with a cuirassier by redrawing them
    from ..scene import make_sprite as _ms

    def r_body(p):
        p.smooth([(-50, 220), (50, 220), (60, 470), (-60, 470)], "steel", 5)
        p.line([(-30, 260), (-28, 440)], "white", 4)
        p.smooth([(-40, 440), (40, 440), (30, 650), (-30, 650)], "white", 4)
        p.poly([(-60, 600), (30, 600), (34, 680), (-70, 680)], "black")

    def r_head(p):
        p.push()
        p.translate(0, 30)
        p.scale(0.8)
        profile_face(p, "skin", "hair", "short", moustache=True)
        p.smooth([(-50, 80), (-46, 20), (0, -10), (44, 20), (50, 80)], "steel", 5)
        p.smooth([(-20, -10), (30, -60), (70, -20), (60, 60), (30, 20)], "black", 4)      # horsehair crest
        p.pop()

    def r_arm(p):
        p.smooth([(-30, 240), (24, 240), (10, 360), (-90, 360), (-90, 330), (-10, 320)], "fr_blue", 5)
        p.ellipse(-100, 345, 16, 14, "skin")
        p.line([(-100, 345), (-340, 180)], "steel", 7)

    for name, fn in (("rider", r_body), ("rhead", r_head), ("rarm", r_arm)):
        spec = f.by_name[name]
        mul = spec.tile_mul
        f.sprites[name] = _ms(ctx, fn, f.BOUNDS, tile * mul, f"cuir{variant}:{name}", unit_scale=k, outline="outline",
                              volume=volume)
    return f


# =============================================================================== props & environments
def cannon_carriage(p, wheel_rot=0.0):
    p.poly([(-40, 0), (300, -40), (320, 10), (-30, 60)], "wood")              # trail
    p.poly([(-30, -20), (120, -60), (140, -10), (-20, 30)], mix("wood", "black", 0.2))
    cx, cy, r = 80, 20, 120
    p.circle(cx, cy, r, "umber")
    p.circle(cx, cy, r - 20, "wood")
    for kk in range(12):
        a = math.radians(kk * 30 + wheel_rot)
        p.line([(cx, cy), (cx + (r - 20) * math.cos(a), cy + (r - 20) * math.sin(a))], "umber", 10)
    p.circle(cx, cy, 24, "steel")


def cannon_barrel(p):
    p.smooth([(-150, -26), (240, -16), (250, -24), (262, -24), (262, 24), (250, 24), (240, 16), (-150, 30), (-180, 0)], "brass", 5)
    for x in (-110, 40, 200):
        p.rect(x, -28, 14, 58, mix("brass", "umber", 0.4))
    p.circle(-185, 0, 18, "brass")


def gabion(p, x, y, s=1.0):
    p.smooth([(x - 60 * s, y), (x - 66 * s, y - 150 * s), (x + 66 * s, y - 150 * s), (x + 60 * s, y)], "ochre_dk", 5)
    for k in range(6):
        p.line([(x - 64 * s, y - 20 * s - k * 22 * s), (x + 64 * s, y - 20 * s - k * 22 * s)], "wood", 5 * s)
    p.ellipse(x, y - 150 * s, 66 * s, 18 * s, "umber")


def onion_dome(p, x, y, w, h, col, gold_cross=True):
    p.smooth([(x - w * 0.5, y), (x - w * 0.62, y - h * 0.45), (x - w * 0.3, y - h * 0.8), (x, y - h), (x + w * 0.3, y - h * 0.8),
              (x + w * 0.62, y - h * 0.45), (x + w * 0.5, y)], col, 8)
    p.rect(x - w * 0.42, y, w * 0.84, h * 0.5, "ivory")
    if gold_cross:
        p.line([(x, y - h), (x, y - h - h * 0.35)], "gold", max(3, w * 0.05))
        p.line([(x - w * 0.12, y - h - h * 0.22), (x + w * 0.12, y - h - h * 0.22)], "gold", max(3, w * 0.05))


def kremlin_tower(p, x, y, w, h, wall="brick", roof="green_dk"):
    p.rect(x - w / 2, y - h, w, h, wall)
    for kk in range(int(h / 40)):
        p.line([(x - w / 2, y - kk * 40), (x + w / 2, y - kk * 40)], mix(wall, "black", 0.25), 2)
    p.poly([(x - w * 0.6, y - h), (x, y - h - w * 1.6), (x + w * 0.6, y - h)], roof)
    p.circle(x, y - h - w * 1.6, w * 0.08 + 3, "gold")


def europe_land():
    """Very simplified European coastlines (lon, lat) for an artistic mosaic map."""
    mainland = [(-9.5, 43.5), (-8.8, 37), (-6, 36.1), (-2, 36.7), (0.2, 38.8), (3.2, 41.9), (6.5, 43.1), (9, 44.3),
                (10.5, 43.5), (12.4, 41.8), (15.6, 40.1), (16, 38), (17.2, 39.1), (16.9, 40.5), (18.5, 40.1), (15.9, 41.9),
                (13.6, 43.5), (12.3, 45.2), (13.7, 45.6), (15.2, 44.2), (19.4, 41.8), (19.9, 39.6), (21.1, 37.8),
                (22.8, 36.4), (24, 38.2), (23, 40.4), (26, 40.8), (29, 41.1), (32, 41.6), (36, 41.4), (39, 41), (41.5, 41.5),
                (41.5, 47), (36.8, 46.9), (34, 44.4), (33, 45.6), (30.6, 46.5), (29.6, 45.2), (28.7, 44), (27.9, 42.6),
                (28, 41.2), (30, 47), (40, 48), (45, 50), (45, 66), (40, 66), (35, 66.5), (33, 69), (28, 71), (24, 71),
                (18, 69.8), (14, 67.5), (12.5, 65), (10.5, 63.5), (5.3, 62), (5, 59), (7, 58), (10.5, 59.3), (11.2, 58.5),
                (12, 56), (12.9, 55.4), (14.2, 55.4), (14.4, 56.2), (16.5, 57.5), (16.7, 59), (18.5, 59.5), (17.3, 61.5),
                (17.5, 62.6), (21.3, 64.3), (22.4, 65.8), (25.3, 65.2), (25.4, 64.8), (21.7, 63), (21.4, 60.5), (24, 60.3),
                (28, 60.5), (29, 59.9), (28, 59.5), (23.5, 59.2), (23.5, 58.3), (21.5, 57.4), (21, 56.3), (20, 54.9),
                (18.5, 54.5), (14.5, 53.9), (11, 54), (10, 54.9), (8.6, 55.5), (8.6, 57), (10, 57.6), (10.6, 57.7),
                (8.6, 53.6), (7, 53.4), (5, 53.2), (4, 51.8), (2.5, 51.1), (1.6, 50.2), (0.2, 49.6), (-1.6, 49.7),
                (-1.8, 48.7), (-4.7, 48.4), (-2.3, 47.2), (-1.2, 46.2), (-1.6, 43.4), (-4, 43.5)]
    britain = [(-5.7, 50.1), (1.4, 51.2), (1.7, 52.7), (0.2, 53.5), (-0.4, 54.5), (-1.6, 55.6), (-2.1, 56.9), (-1.8, 57.6),
               (-3.8, 57.7), (-3, 58.6), (-5, 58.6), (-6.2, 56.5), (-5.4, 55.6), (-4.6, 54.7), (-3.3, 54.8), (-3.1, 53.4),
               (-4.6, 53.3), (-4.2, 52.2), (-5.1, 51.7), (-3.2, 51.4), (-4.2, 51.2)]
    ireland = [(-6, 52.2), (-6.1, 53.9), (-5.7, 54.7), (-7.3, 55.3), (-8.4, 55), (-10, 54), (-10.2, 51.7), (-8, 51.6)]
    sicily = [(12.4, 38.1), (15.6, 38.3), (15.1, 36.7), (12.6, 37.6)]
    sardinia = [(8.2, 41), (9.6, 41), (9.6, 39.2), (8.5, 38.9)]
    corsica = [(9, 42.9), (9.5, 43), (9.5, 41.5), (8.7, 41.7)]
    africa = [(-10, 30), (-9.5, 32.5), (-6.8, 34), (-1, 35.4), (3, 36.8), (10.3, 37.2), (11, 35), (10, 33.6), (15, 32.3),
              (20, 30.5), (20, 32.6), (25, 31.8), (30, 31.3), (32, 31), (34.5, 31.5), (36, 34), (36, 30), (32, 29),
              (25, 28), (0, 28), (-10, 28)]
    turkey = [(26, 40.2), (27, 36.8), (30, 36.4), (36, 36.6), (36, 34.5), (40, 36), (42, 41.5), (36, 41.6), (29.2, 41.2)]
    return dict(mainland=mainland, britain=britain, ireland=ireland, sicily=sicily, sardinia=sardinia, corsica=corsica,
                africa=africa, turkey=turkey)


# approximate political areas c. 1811-12 (artistic, deliberately soft)
EMPIRE_1812 = [(-1.8, 48.7), (-4.7, 48.4), (-1.2, 46.2), (-1.6, 43.4), (3.2, 42.4), (6.5, 43.1), (9, 44.3), (10.5, 43.5),
               (12.4, 41.8), (13.6, 41.3), (13.8, 42.6), (12.3, 44.4), (11, 44.6), (9.3, 45.3), (7.7, 46.2), (6.8, 46.5),
               (7.6, 47.6), (8.2, 49.2), (7.2, 50.4), (8.5, 51.3), (9.5, 52.5), (10.8, 53.9), (11, 54), (8.6, 53.6),
               (7, 53.4), (5, 53.2), (4, 51.8), (2.5, 51.1), (1.6, 50.2), (0.2, 49.6)]
ILLYRIA = [(13.6, 45.6), (15.2, 44.2), (17.5, 43), (18.5, 42.5), (17, 44.5), (15.5, 45.8), (14, 46.4)]
ALLIED_1812 = [  # Spain (contested), Kingdom of Italy, Naples, Confederation of the Rhine, Duchy of Warsaw, Switzerland
    [(-9.5, 43.5), (-8.8, 37), (-6, 36.1), (-2, 36.7), (0.2, 38.8), (3.2, 41.9), (3.2, 42.4), (-1.6, 43.4), (-4, 43.5)],
    [(7.7, 46.2), (9.3, 45.3), (11, 44.6), (12.3, 44.4), (13.8, 42.6), (12.3, 45.2), (13.7, 45.6), (12, 46.6), (10, 46.6)],
    [(13.6, 41.3), (15.6, 40.1), (16, 38), (17.2, 39.1), (16.9, 40.5), (18.5, 40.1), (15.9, 41.9), (13.8, 42.6)],
    [(7.6, 47.6), (13, 47.5), (13.8, 48.8), (15, 51), (14.5, 53.9), (11, 54), (10.8, 53.9), (9.5, 52.5), (8.5, 51.3),
     (7.2, 50.4), (8.2, 49.2)],
    [(15, 51), (18, 50.1), (23.5, 50.3), (23.8, 52.5), (22.5, 53.8), (20, 54.4), (16.5, 53.4)],
    [(6.1, 46.2), (7.7, 46.2), (10, 46.6), (9.5, 47.6), (7.6, 47.6), (6.8, 47.3)],
]
RUSSIA_LINE = [(23.8, 52.5), (22.5, 53.8), (21, 56.3)]
PLACES_EU = {"PARIS": (2.35, 48.86), "MOSCOW": (37.6, 55.75), "VIENNA": (16.37, 48.21), "BERLIN": (13.4, 52.52),
             "MADRID": (-3.7, 40.4), "ROME": (12.5, 41.9), "WATERLOO": (4.4, 50.7), "ELBA": (10.3, 42.8),
             "LONDON": (-0.12, 51.5)}


# =============================================================================== standards (waving)
def flag_art(kind, w=420, h=300):
    """Drawing function for a flag with its hoist at x=0 (y from 0 to h)."""
    def f(p):
        if kind == "fr1804":
            flag_1804(p, 90)
        elif kind == "fr1812":                       # vertical tricolour (1812 pattern, 1815)
            p.rect(0, 0, w / 3 + 1, h, "fr_blue")
            p.rect(w / 3, 0, w / 3 + 1, h, "white")
            p.rect(2 * w / 3, 0, w / 3, h, "crimson")
            p.rect(0, 0, w, 10, "gold")
            p.rect(0, h - 10, w, 10, "gold")
        elif kind == "russia":                       # imperial standard: black double-headed eagle on gold
            p.rect(0, 0, w, h, "gold")
            p.ellipse(w / 2, h / 2, 60, 80, "black")
            p.poly([(w / 2 - 50, h / 2 - 60), (w / 2 - 110, h / 2 - 110), (w / 2 - 70, h / 2 - 20)], "black")
            p.poly([(w / 2 + 50, h / 2 - 60), (w / 2 + 110, h / 2 - 110), (w / 2 + 70, h / 2 - 20)], "black")
            p.circle(w / 2 - 40, h / 2 - 90, 16, "black")
            p.circle(w / 2 + 40, h / 2 - 90, 16, "black")
        elif kind == "prussia":
            p.rect(0, 0, w, h, "white")
            p.ellipse(w / 2, h / 2, 50, 70, "black")
            p.poly([(w / 2 - 40, h / 2 - 40), (w / 2 - 110, h / 2 - 90), (w / 2 - 60, h / 2 + 10)], "black")
            p.poly([(w / 2 + 40, h / 2 - 40), (w / 2 + 110, h / 2 - 90), (w / 2 + 60, h / 2 + 10)], "black")
            p.circle(w / 2, h / 2 - 80, 18, "black")
        elif kind == "austria":
            p.rect(0, 0, w, h / 2, "black")
            p.rect(0, h / 2, w, h / 2, "gold")
        elif kind == "britain":                      # Union Flag (1801)
            p.rect(0, 0, w, h, "lapis_dk")
            p.line([(0, 0), (w, h)], "white", 60)
            p.line([(0, h), (w, 0)], "white", 60)
            p.line([(0, 0), (w, h)], "crimson", 20)
            p.line([(0, h), (w, 0)], "crimson", 20)
            p.rect(w / 2 - 50, 0, 100, h, "white")
            p.rect(0, h / 2 - 50, w, 100, "white")
            p.rect(w / 2 - 30, 0, 60, h, "crimson")
            p.rect(0, h / 2 - 30, w, 60, "crimson")
        elif kind == "sweden":
            p.rect(0, 0, w, h, "lapis")
            p.rect(w * 0.3, 0, 60, h, "gold")
            p.rect(0, h / 2 - 30, w, 60, "gold")
        elif kind == "ensign":                       # Royal Navy red ensign-style, Union in canton
            p.rect(0, 0, w, h, "crimson")
            p.rect(0, 0, w * 0.45, h * 0.5, "lapis_dk")
            p.line([(0, 0), (w * 0.45, h * 0.5)], "white", 20)
            p.line([(0, h * 0.5), (w * 0.45, 0)], "white", 20)
            p.rect(w * 0.2, 0, 26, h * 0.5, "white")
            p.rect(0, h * 0.22, w * 0.45, 26, "white")
    return f


def flag_pole(ctx, k, kind, tile=5.0, pole_h=1100, finial="eagle", volume=None, haze=None, haze_amt=0.0):
    """Stand-alone standard: pole (feet at y=1000 like figures) + flag waving with rigid tiles."""
    def pole(p):
        p.line([(0, 1000 - pole_h), (0, 1000)], "umber", 12)
        p.line([(-4, 1000 - pole_h), (-4, 1000)], "ochre_dk", 3)
        top = 1000 - pole_h
        if finial == "eagle":
            p.poly([(0, top - 60), (-40, top - 100), (-28, top - 50), (-8, top - 36), (8, top - 36), (28, top - 50), (40, top - 100)], "gold")
            p.circle(0, top - 70, 14, "gold_lt")
        else:
            p.poly([(0, top - 60), (-12, top - 10), (12, top - 10)], "steel")

    def cloth(p):
        p.push()
        p.translate(4, 1000 - pole_h + 10)
        flag_art(kind)(p)
        p.pop()
    parts = [PartSpec("pole", pole, pivot=(0, 1000), z=0),
             PartSpec("banner", cloth, pivot=(0, 1000 - pole_h), parent="pole", z=1,
                      deform=dict(amp=26, wl=260, speed=0.8, axis="x", anchor=0.0, power=1.1))]
    return Figure(ctx, f"flagpole_{kind}{pole_h}", parts, k, tile, haze, haze_amt, volume=volume)

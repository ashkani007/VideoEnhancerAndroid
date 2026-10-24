"""Napoleon Bonaparte (c. 1805), stylized editorial 2D rig, 3/4 view facing screen-right.

Skeleton (local coordinates in character units, y down):
  root (waist) -> torso (lean, breath) -> neck -> head (tilt, nod, yaw)
  torso -> shoulder_near (his right arm, in front) -> upper -> fore -> hand
  torso -> shoulder_far  (his left arm, behind)    -> upper -> fore -> hand
Arm angle 0 = hanging straight down; negative = raised forward (toward screen-right).
Face rig: gaze (gx, gy), blink, lid, brows (raise, knit), mouth (shape, open), plus head yaw/nod that
slide the features across the face (flat-style 3/4 turn). Secondary motion (coat tails, epaulette
fringe, hat cockade) comes in as spring-lagged values in the pose."""
import math

import skia

from gfx import diff, ellipse, fill, glow, lin, moved, poly, rrect, smooth, stroke, toon, PAL

UPPER, FORE = 128.0, 118.0
SH_NEAR, SH_FAR = (-62.0, -268.0), (74.0, -264.0)
NECK = (8.0, -284.0)
HEAD_SCALE = 1.32

DEFAULT = dict(lean=0.0, breath=0.0, tilt=0.0, nod=0.0, yaw=0.0, gx=0.0, gy=0.0, blink=0.0, lid=0.0,
               raise_=0.0, knit=0.0, mouth="neutral", open=0.0, smile=0.0,
               n_sh=8.0, n_el=-10.0, n_wr=0.0, n_hand="relaxed",
               f_sh=6.0, f_el=-12.0, f_wr=0.0, f_hand="relaxed",
               tails=0.0, fringe=0.0, light=(1.0, -0.35), rimlight=0.0)


class Napoleon:
    def __init__(self, light=(1.0, -0.35)):
        self.light = light

    # ----------------------------------------------------------------------------------- parts
    def _shade(self, c, path, mat, depth=14, rim=4, grad=None):
        toon(c, path, mat, mat + "_sh" if mat + "_sh" in PAL else mat, light=self.L, depth=depth,
             hi=(mat + "_hi") if (mat + "_hi") in PAL else None, rim=rim, grad=grad)

    def hand(self, c, kind, side):
        sk, sh = "skin", "skin_sh"
        if kind == "point":
            fist = smooth([(-17, 4), (17, 2), (21, 34), (12, 50), (-10, 50), (-19, 30)])
            self._shade(c, fist, "skin", 8, 3)
            finger = rrect(-3, 30, 11, 92, 7)
            self._shade(c, finger, "skin", 5, 2)
            thumb = smooth([(-17, 18), (-27, 30), (-22, 40), (-10, 34)])
            fill(c, thumb, sh)
            for y in (40, 46):
                stroke(c, poly([(-12, y), (8, y)], False), "skin_sh", 1.6, 200)
        elif kind == "flat":
            palm = smooth([(-18, 2), (18, 0), (26, 40), (20, 78), (-8, 84), (-22, 46)])
            self._shade(c, palm, "skin", 8, 3)
            for x in (-6, 4, 14):
                stroke(c, poly([(x, 52), (x + 2, 80)], False), "skin_sh", 1.6, 170)
            thumb = smooth([(-20, 20), (-34, 34), (-30, 46), (-14, 38)])
            self._shade(c, thumb, "skin", 5, 2)
        elif kind == "open":
            palm = smooth([(-19, 2), (19, 0), (24, 38), (16, 70), (-12, 72), (-22, 40)])
            self._shade(c, palm, "skin", 8, 3)
            for i, x in enumerate((-10, -1, 8, 17)):
                f = rrect(x - 4, 56, x + 4, 94 - abs(i - 1.5) * 6, 4)
                self._shade(c, f, "skin", 4, 2)
            thumb = smooth([(-20, 16), (-40, 26), (-38, 36), (-16, 34)])
            self._shade(c, thumb, "skin", 5, 2)
        else:                                            # relaxed, fingers curled
            palm = smooth([(-17, 2), (17, 0), (20, 40), (10, 62), (-12, 60), (-20, 34)])
            self._shade(c, palm, "skin", 8, 3)
            stroke(c, smooth([(-10, 46), (0, 54), (12, 48)], False), "skin_sh", 1.8, 190)

    def arm(self, c, p, side):
        pre = "n_" if side == "near" else "f_"
        sh, el, wr, kind = p[pre + "sh"], p[pre + "el"], p[pre + "wr"], p[pre + "hand"]
        c.save()
        c.translate(*(SH_NEAR if side == "near" else SH_FAR))
        c.save()
        c.rotate(sh)
        upper = smooth([(-27, -18), (25, -20), (26, 40), (21, UPPER + 6), (-19, UPPER + 8), (-25, 40)])
        self._shade(c, upper, "coat", 16, 4)
        c.save()
        c.translate(0, UPPER)
        c.rotate(el)
        fore = smooth([(-20, -8), (20, -8), (18, 70), (17, FORE - 8), (-17, FORE - 6), (-19, 70)])
        self._shade(c, fore, "coat", 14, 4)
        cuff = rrect(-21, FORE - 30, 21, FORE + 4, 7)
        self._shade(c, cuff, "red", 8, 3)
        flap = smooth([(-21, FORE - 30), (4, FORE - 32), (-6, FORE - 8), (-21, FORE - 6)])
        fill(c, flap, "lapel")
        c.save()
        c.translate(0, FORE + 2)
        c.rotate(wr)
        self.hand(c, kind, side)
        c.restore()
        c.restore()
        c.restore()
        # epaulette stays on the shoulder (follows the arm only a little); fringe swings (secondary motion)
        c.rotate(sh * 0.25)
        ep = smooth([(-34, -26), (0, -36), (34, -24), (30, -6), (-30, -4)])
        self._shade(c, ep, "gold", 7, 3)
        sw = p["fringe"] * 10 - sh * 0.2
        for i in range(9):
            x = -28 + i * 7
            stroke(c, poly([(x, -6), (x + sw * 0.6, 22)], False), "gold_sh" if i % 2 else "gold", 3.2)
        c.restore()

    def torso(self, c, p):
        # coat tails behind (secondary motion)
        sw = p["tails"]
        tails = smooth([(-82, -26), (-40, -17), (-30, 160), (-70 - sw * 26, 230), (-104 - sw * 34, 200), (-100, 40)])
        self._shade(c, tails, "coat", 18, 4)
        body = smooth([(-96, -283), (-30, -300), (40, -300), (100, -279), (106, -214), (86, -103), (82, 10),
                       (60, 120), (-70, 120), (-84, 10), (-92, -103), (-104, -214)])
        self._shade(c, body, "coat", 22, 5, grad=lin((0, -300), (0, 120), PAL["coat_hi"], PAL["coat"]))
        # white waistcoat + lapels (plastron) toward the front (right in 3/4)
        vest = smooth([(4, -257), (64, -257), (74, -103), (66, 20), (12, 26), (2, -103)])
        self._shade(c, vest, "lapel", 10, 3)
        lap_n = smooth([(-18, -288), (14, -274), (22, -129), (6, -103), (-12, -146)])
        self._shade(c, lap_n, "lapel", 8, 3)
        lap_f = smooth([(70, -283), (90, -273), (86, -137), (72, -120), (66, -171)])
        self._shade(c, lap_f, "lapel", 8, 3)
        for y in range(-250, 0, 42):
            fill(c, ellipse(36 + y * 0.02, y, 5, 5), "gold")
            fill(c, ellipse(35 + y * 0.02, y - 1.5, 2, 2), "gold_hi")
        stroke(c, smooth([(-40, -51), (-20, 40)], False), "coat_sh", 3, 160)     # fold
        # standing red collar and black stock
        collar = smooth([(-46, -300), (8, -312), (66, -302), (60, -274), (8, -283), (-40, -276)])
        self._shade(c, collar, "red", 8, 3)
        stroke(c, smooth([(-40, -279), (8, -286), (58, -278)], False), "gold", 3)

    def head(self, c, p):
        yaw, nod = p["yaw"], p["nod"]
        fx, fy = yaw * 14, nod * 10                 # features slide across the face for turns/nods
        c.save()
        c.translate(*NECK)
        c.rotate(p["tilt"])
        c.scale(HEAD_SCALE, HEAD_SCALE)
        neck = rrect(-24, -34, 28, 14, 10)
        self._shade(c, neck, "skin", 10, 3)
        fill(c, rrect(-30, -6, 34, 16, 6), "hat")                 # black stock
        hair_back = smooth([(-74, -110), (-86, -170), (-60, -232), (10, -250), (52, -230), (30, -200), (-30, -180),
                            (-50, -120), (-46, -70), (-66, -60)])
        self._shade(c, hair_back, "hair", 10, 3)
        face = smooth([(14 + fx * 0.4, -22), (46 + fx * 0.5, -38 + fy * 0.3), (60 + fx * 0.6, -66 + fy * 0.5),
                       (63 + fx * 0.65, -92 + fy), (73 + fx * 0.75, -108 + fy), (66 + fx * 0.65, -124 + fy),
                       (63 + fx * 0.55, -158 + fy), (42 + fx * 0.3, -212), (-20, -226), (-58, -196), (-66, -140),
                       (-60, -88), (-38, -44)])
        self._shade(c, face, "skin", 16, 4)
        # ear (moves opposite to the features on yaw)
        ear = smooth([(-46 - fx * 0.4, -132), (-34 - fx * 0.4, -144), (-26 - fx * 0.4, -118), (-36 - fx * 0.4, -96),
                      (-48 - fx * 0.4, -104)])
        self._shade(c, ear, "skin", 6, 2)
        fill(c, smooth([(-40 - fx * 0.4, -128), (-32 - fx * 0.4, -120), (-38 - fx * 0.4, -106)]), "skin_sh")
        # sideburn + front hair with the forelock
        burn = smooth([(-40 - fx * 0.3, -196), (-22 - fx * 0.3, -192), (-26 - fx * 0.3, -142), (-36 - fx * 0.3, -144)])
        fill(c, burn, "hair")
        front = smooth([(-50, -196), (-10, -214 + fy * 0.3), (40 + fx * 0.4, -212), (54 + fx * 0.4, -186 + fy * 0.4),
                        (30 + fx * 0.4, -188 + fy * 0.4), (20 + fx * 0.4, -170 + fy * 0.5), (6 + fx * 0.3, -186 + fy * 0.3),
                        (-24, -184)])
        self._shade(c, front, "hair", 6, 3)
        lock = smooth([(14 + fx * 0.4, -190 + fy * 0.4), (26 + fx * 0.4, -176 + fy * 0.5), (16 + fx * 0.4, -164 + fy * 0.5),
                       (8 + fx * 0.4, -176 + fy * 0.5)])
        fill(c, lock, "hair")
        stroke(c, smooth([(18 + fx * 0.4, -184 + fy * 0.4), (22 + fx * 0.4, -172 + fy * 0.5), (14 + fx * 0.4, -168 + fy * 0.5)], False), "hair_hi", 2.0, 180)
        self.face(c, p, fx, fy)
        self.hat(c, p)
        c.restore()

    def eye(self, c, cx, cy, w, h, p, far=False):
        lid = min(1.0, max(0.0, p["blink"] + p["lid"]))
        white = smooth([(cx - w, cy + 1), (cx - w * 0.2, cy - h), (cx + w, cy - h * 0.25), (cx + w * 0.3, cy + h * 0.75)])
        fill(c, white, "eye_w")
        c.save()
        c.clipPath(white, doAntiAlias=True)
        ix, iy = cx + p["gx"] * w * 0.42 + (2 if far else 0), cy + p["gy"] * h * 0.4
        r = h * (0.95 if not far else 0.85)
        fill(c, ellipse(ix, iy, r * (0.8 if far else 1.0), r), "iris")
        fill(c, ellipse(ix, iy, r * 0.48, r * 0.5), "pupil")
        fill(c, ellipse(ix + r * 0.3, iy - r * 0.38, r * 0.24, r * 0.24), "eye_w", 230)
        # upper lid: skin closes down over the eye (blink / heavy lid)
        top = cy - h * 1.3
        lid_y = top + (h * 2.4) * lid
        fill(c, rrect(cx - w * 1.4, top - 30, cx + w * 1.4, lid_y, 2), "skin")
        fill(c, rrect(cx - w * 1.4, lid_y - 3, cx + w * 1.4, lid_y + 2, 2), "skin_sh", 160)
        c.restore()
        lash = smooth([(cx - w * 1.05, cy + 2), (cx - w * 0.2, cy - h * 1.05 + h * 2.0 * lid), (cx + w * 1.0, cy - h * 0.3 + h * 1.1 * lid)], False)
        stroke(c, lash, "ink", 4.2 if not far else 3.4)
        stroke(c, smooth([(cx - w * 0.6, cy + h * 0.8), (cx + w * 0.4, cy + h * 0.85)], False), "skin_sh", 2.0, 170)

    def face(self, c, p, fx, fy):
        ex1, ex2, ey = 6 + fx, 50 + fx * 1.15, -138 + fy
        self.eye(c, ex1, ey, 15, 9, p)
        self.eye(c, ex2, ey - 1, 10, 8, p, far=True)
        r, k = p["raise_"], p["knit"]
        # brows: knit pulls the inner ends (toward the nose, screen-right for the near brow) down and in
        b1 = [(ex1 - 18, ey - 18 - r * 6 + k * 1), (ex1 - 2, ey - 24 - r * 8 - k * 1), (ex1 + 18 - k * 3, ey - 20 - r * 5 + k * 7)]
        b2 = [(ex2 - 10 + k * 2, ey - 20 - r * 5 + k * 6), (ex2 + 2, ey - 24 - r * 7), (ex2 + 13, ey - 20 - r * 4)]
        for b, w in ((b1, 7.5), (b2, 6.0)):
            stroke(c, smooth(b, False), "hair", w)
        # nose (3/4: a soft wedge pointing right) with its shadow side
        nx = 64 + fx * 1.2
        stroke(c, smooth([(nx - 16, -128 + fy), (nx - 14, -112 + fy), (nx - 6, -102 + fy)], False), "skin_sh", 3.0, 150)
        fill(c, smooth([(nx - 16, -100 + fy), (nx + 4, -98 + fy), (nx - 4, -92 + fy)]), "skin_sh", 190)
        fill(c, ellipse(nx - 4, -112 + fy, 3.5, 5), "skin_hi", 170)
        fill(c, ellipse(34 + fx, -106 + fy, 10, 6), "blush", 70)
        self.mouth(c, 40 + fx * 1.1, -70 + fy, p)

    def mouth(self, c, mx, my, p):
        o, kind, sm = p["open"], p["mouth"], p["smile"]
        w = 22 if kind != "tight" else 18
        if o < 0.05:
            corner = -3 * sm + (3 if kind == "tight" else 0)
            line = smooth([(mx - w, my + corner), (mx - 2, my + 1), (mx + w * 0.6, my + corner * 0.6)], False)
            stroke(c, line, "mouth", 4.0 if kind == "tight" else 3.4)
            stroke(c, smooth([(mx - 8, my + 9), (mx + 6, my + 9)], False), "skin_sh", 3.0, 120)   # lower lip shade
            return
        h = 6 + 26 * o
        shape = smooth([(mx - w, my - 2), (mx, my - 5 - 2 * o), (mx + w * 0.7, my - 1), (mx + w * 0.5, my + h * 0.6),
                        (mx, my + h), (mx - w * 0.8, my + h * 0.5)])
        fill(c, shape, "mouth")
        c.save()
        c.clipPath(shape, doAntiAlias=True)
        fill(c, rrect(mx - w, my - 10, mx + w, my - 3 + 4 * o, 3), "teeth")
        fill(c, ellipse(mx - 2, my + h + 2, w * 0.6, h * 0.45), "tongue")
        c.restore()
        stroke(c, shape, "lip", 2.2, 200)

    def hat(self, c, p):
        # bicorne worn crosswise (en bataille): a wide crescent; the cockade sits front-right
        hat = smooth([(-150, -196), (-96, -226), (-40, -296), (24, -310), (84, -282), (150, -208), (60, -222),
                      (0, -216), (-70, -214)])
        self._shade(c, hat, "hat", 14, 4, grad=lin((0, -310), (0, -200), PAL["hat_hi"], PAL["hat"]))
        stroke(c, smooth([(-140, -201), (-70, -218), (0, -220), (60, -226), (140, -212)], False), "gold", 3.0, 220)
        cx, cy = 66, -246
        for r, col in ((20, (36, 62, 140)), (14, (246, 242, 234)), (8, PAL["red"])):
            fill(c, ellipse(cx, cy, r * 0.8, r), col)

    # ----------------------------------------------------------------------------------- draw
    def draw(self, c, x, y, scale, pose, flip=False, parts="all"):
        p = dict(DEFAULT)
        p.update(pose)
        self.L = p.get("light", self.light)
        c.save()
        c.translate(x, y)
        c.scale(-scale if flip else scale, scale)
        c.rotate(p["lean"])
        c.scale(1.0, 1.0 + p["breath"] * 0.012)
        if parts in ("all", "body"):
            self.arm(c, p, "far")
            self.torso(c, p)
            self.head(c, p)
        if parts in ("all", "near_arm"):
            self.arm(c, p, "near")
        c.restore()


def ik_arm(root, scale, lean, target, side="near", bend=1):
    """Two-link inverse kinematics: shoulder/elbow angles (rig convention: 0 = hanging down, degrees,
    positive = clockwise) that put the wrist on a world-space target. bend=+1 / -1 picks the elbow side."""
    tx, ty = (target[0] - root[0]) / scale, (target[1] - root[1]) / scale
    a = math.radians(-lean)
    lx, ly = tx * math.cos(a) - ty * math.sin(a), tx * math.sin(a) + ty * math.cos(a)   # torso-local target
    sx, sy = SH_NEAR if side == "near" else SH_FAR
    dx, dy = lx - sx, ly - sy
    D = min(math.hypot(dx, dy), UPPER + FORE - 1e-3)
    base = math.degrees(math.atan2(-dx, dy))
    alpha = math.degrees(math.acos(max(-1, min(1, (UPPER ** 2 + D ** 2 - FORE ** 2) / (2 * UPPER * D)))))
    beta = math.degrees(math.acos(max(-1, min(1, (UPPER ** 2 + FORE ** 2 - D ** 2) / (2 * UPPER * FORE)))))
    sh = base + bend * alpha
    el = -bend * (180 - beta)
    return sh, el

"""Young General Bonaparte (Italy, 1796): a painted head-and-shoulders rig for close and medium shots.

Live2D-style parameter rig on a 3D frame: the face outline and every feature are 3D points
(head units, x right, y down, z toward camera; head height ~1) rotated by pitch/yaw/roll and
projected, so small head motions reshape the silhouette believably. Acting parameters:
  pitch, yaw, roll (deg) | gx, gy gaze (-1..1, gy>0 looks down) | lid (0 closed .. 1 wide)
  blink (0..1) | knit (brows pull together/down) | raise (brows up) | tense (mouth set) | breath
Design reference (1796): long straight dark-brown hair to the collar covering the ears, lean
face, grey-blue eyes, white stock, high dark-blue collar with gold oak-leaf embroidery."""
import math

import cv2
import numpy as np

from .paint import catmull, height_from_mask, lambert, normals, ramp, soft, brush_texture

SKIN = [(0.0, (10, 6, 6)), (0.18, (40, 20, 16)), (0.38, (104, 52, 34)), (0.6, (186, 108, 66)),
        (0.8, (236, 160, 100)), (1.0, (255, 212, 150))]
HAIR = [(0.0, (5, 4, 4)), (0.4, (22, 14, 10)), (0.75, (64, 38, 22)), (1.0, (140, 86, 46))]
COAT = [(0.0, (3, 4, 9)), (0.4, (9, 12, 28)), (0.75, (24, 32, 66)), (1.0, (64, 74, 118))]
STOCK = [(0.0, (14, 12, 14)), (0.4, (60, 52, 50)), (0.75, (150, 134, 118)), (1.0, (220, 204, 180))]
GOLD = [(0.0, (30, 18, 6)), (0.4, (110, 70, 20)), (0.75, (226, 168, 70)), (1.0, (255, 230, 150))]

# 3/4 view (face turned to screen-right), base pose
FACE = [(-0.02, -0.50, 0.10), (0.16, -0.44, 0.25), (0.25, -0.30, 0.34), (0.275, -0.16, 0.38), (0.255, -0.065, 0.40),
        (0.29, 0.02, 0.46), (0.335, 0.13, 0.52), (0.30, 0.175, 0.47), (0.268, 0.19, 0.44), (0.272, 0.245, 0.42),
        (0.262, 0.285, 0.41), (0.262, 0.315, 0.41), (0.232, 0.352, 0.39), (0.248, 0.42, 0.36), (0.17, 0.495, 0.28),
        (-0.02, 0.47, 0.15), (-0.20, 0.36, 0.02), (-0.30, 0.10, -0.05), (-0.31, -0.20, -0.02), (-0.22, -0.42, 0.04)]
HAIR_BACK = [(-0.06, -0.60, 0.0), (0.18, -0.56, 0.05), (0.32, -0.38, 0.0), (0.30, -0.20, -0.1), (0.20, 0.10, -0.2),
             (0.16, 0.62, -0.25), (-0.10, 0.80, -0.3), (-0.40, 0.78, -0.25), (-0.50, 0.40, -0.2), (-0.47, -0.10, -0.1),
             (-0.36, -0.46, -0.05)]
HAIR_FRONT_NEAR = [(-0.22, -0.46, 0.15), (-0.05, -0.52, 0.2), (0.12, -0.47, 0.28), (0.18, -0.42, 0.32), (0.02, -0.40, 0.33),
                   (-0.10, -0.37, 0.28), (-0.19, -0.22, 0.18), (-0.22, 0.05, 0.12), (-0.19, 0.28, 0.06), (-0.16, 0.52, 0.02),
                   (-0.32, 0.68, -0.02), (-0.45, 0.62, -0.05), (-0.47, 0.2, -0.05), (-0.42, -0.25, 0.0), (-0.34, -0.42, 0.06)]
HAIR_FRONT_FAR = [(0.10, -0.52, 0.20), (0.24, -0.48, 0.24), (0.31, -0.33, 0.26), (0.28, -0.24, 0.30), (0.20, -0.34, 0.33),
                  (0.12, -0.40, 0.32)]
NECK = [(-0.10, 0.38, 0.05), (0.12, 0.44, 0.22), (0.14, 0.60, 0.18), (0.08, 0.78, 0.1), (-0.14, 0.78, 0.0), (-0.15, 0.52, 0.0)]
STOCK_PTS = [(-0.16, 0.58, 0.08), (0.04, 0.62, 0.24), (0.16, 0.59, 0.22), (0.20, 0.70, 0.2), (0.05, 0.78, 0.22),
             (-0.16, 0.76, 0.08)]
COLLAR = [(-0.40, 0.48, -0.05), (-0.24, 0.52, 0.05), (-0.20, 0.84, 0.12), (0.08, 0.90, 0.25), (0.26, 0.78, 0.25),
          (0.27, 0.56, 0.2), (0.38, 0.56, 0.15), (0.46, 0.98, 0.12), (0.10, 1.06, 0.2), (-0.46, 1.0, 0.0)]
COAT_PTS = [(-0.44, 0.84, -0.1), (-0.95, 1.06, -0.2), (-1.30, 1.40, -0.2), (-1.40, 2.20, -0.2), (1.30, 2.20, -0.1),
            (1.20, 1.40, -0.1), (0.82, 1.06, -0.05), (0.42, 0.86, 0.05)]


class Bonaparte:
    def __init__(self, center, scale, light, seed=4):
        self.cx, self.cy = center
        self.S = scale                    # design units per head unit
        self.light = light                # (x, y) design units, point light in front
        self.seed = seed

    # ------------------------------------------------------------------ projection
    def setpose(self, p):
        self.p = p
        a, b, c = (math.radians(p.get(k, 0.0)) for k in ("pitch", "yaw", "roll"))
        Rx = np.array([[1, 0, 0], [0, math.cos(a), math.sin(a)], [0, -math.sin(a), math.cos(a)]])
        Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
        Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
        self.R = Rz @ Ry @ Rx
        self.breath = p.get("breath", 0.0)

    def P(self, pts, body=False):
        """3D head points -> design units. Body points don't take the head's rotation."""
        A = np.asarray(pts, np.float64)
        if A.ndim == 1:
            A = A[None]
        if body:
            q = A.copy()
            q[:, 1] -= self.breath * 0.012 * (q[:, 1] > 0.8)
        else:
            q = A @ self.R.T
            q[:, 1] -= self.breath * 0.006
        k = 1 + q[:, 2] * 0.05                      # mild perspective
        return np.stack([self.cx + self.S * q[:, 0] * k, self.cy + self.S * q[:, 1] * k], 1)

    # ------------------------------------------------------------------ shading
    def _shade(self, cv, poly, depth, stops, edge=1.2, bumps=None, spec=0.0, rim=0.25, amb=0.05, tex=0.03,
               tex_angle=-70, gloss=None):
        sl = cv.roi_of(poly, pad=depth * 1.2)
        if sl is None:
            return None
        d = cv.sdf(poly, sl)
        a = soft(d, edge)
        if a.max() <= 0:
            return None
        h = height_from_mask(d, depth)
        X, Y = cv.X[sl], cv.Y[sl]
        if bumps is not None:
            h = h + bumps(X, Y) * (a > 0)
        n = normals(h, depth / cv.k * 1.0 * cv.k)  # height in design units
        diff, dist = lambert(n, X, Y, self.light, z=230)
        fall = 1.0 / (1.0 + (dist / 700.0) ** 2)
        v = amb + diff * fall * 1.25 * self.p.get("flicker", 1.0)
        rimv = np.clip(-n[..., 0] * 0.8 - n[..., 1] * 0.3, 0, 1) ** 3 * rim       # cool back light from upper left
        b = brush_texture(cv.H, cv.W, cv.s, self.seed, 22, tex_angle)[sl]
        v = v * (1 + tex * b)
        col = ramp(v, stops)
        col += rimv[..., None] * np.array([0.30, 0.36, 0.52], np.float32)
        if spec:
            hl = np.clip((diff - 0.82) / 0.18, 0, 1) ** 2 * fall * spec
            col += hl[..., None] * np.array([1.0, 0.86, 0.66], np.float32)
        cv.over(sl, col, a)
        return sl, d, a, n, v

    # ------------------------------------------------------------------ features
    def _face_bumps(self):
        S = self.S
        pts = {k: self.P(v)[0] for k, v in dict(
            brow_n=(-0.05, -0.12, 0.42), brow_f=(0.19, -0.13, 0.44), cheek_n=(-0.10, 0.10, 0.34), cheek_f=(0.20, 0.09, 0.42),
            chin=(0.17, 0.42, 0.36), eye_n=(-0.04, -0.03, 0.38), eye_f=(0.20, -0.035, 0.42), temple=(-0.20, -0.18, 0.2),
            lip=(0.21, 0.30, 0.41), nose_a=(0.24, -0.02, 0.46), nose_b=(0.31, 0.13, 0.52), jaw=(-0.10, 0.36, 0.2),
            mouth_side=(0.10, 0.30, 0.36)).items()}

        def g(X, Y, c, sx, sy, A):
            return A * np.exp(-(((X - c[0]) / (sx * S)) ** 2 + ((Y - c[1]) / (sy * S)) ** 2))

        def seg(X, Y, a, b, w, A):
            ab = b - a
            t = np.clip(((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / (ab @ ab), 0, 1)
            dx, dy = X - (a[0] + t * ab[0]), Y - (a[1] + t * ab[1])
            return A * np.exp(-(dx * dx + dy * dy) / (w * S) ** 2)

        def f(X, Y):
            return (g(X, Y, pts["brow_n"], 0.12, 0.035, 0.35) + g(X, Y, pts["brow_f"], 0.07, 0.03, 0.3)
                    + g(X, Y, pts["cheek_n"], 0.10, 0.07, 0.35) + g(X, Y, pts["cheek_f"], 0.06, 0.06, 0.3)
                    + g(X, Y, pts["chin"], 0.07, 0.05, 0.35) + g(X, Y, pts["lip"], 0.05, 0.03, 0.15)
                    - g(X, Y, pts["eye_n"], 0.09, 0.045, 0.22) - g(X, Y, pts["eye_f"], 0.05, 0.04, 0.18)
                    - g(X, Y, pts["temple"], 0.08, 0.10, 0.25) - g(X, Y, pts["mouth_side"], 0.05, 0.05, 0.15)
                    + seg(X, Y, pts["nose_a"], pts["nose_b"], 0.035, 0.75) - g(X, Y, pts["jaw"], 0.12, 0.05, 0.12))
        return f

    def _eye(self, cv, c3, w, h, far=False):
        """Almond eye with lids following the gaze; iris clipped by the lids; candle catchlight."""
        p = self.p
        gx, gy = p.get("gx", 0.0), p.get("gy", 0.0)
        lid = max(0.0, min(1.0, p.get("lid", 0.85) - 0.45 * max(0.0, gy))) * (1 - p.get("blink", 0.0))
        c = self.P(c3)[0]
        S = self.S
        W2, H2 = w * S / 2, h * S
        u = np.linspace(-1, 1, 24)
        tilt = -0.06 if not far else -0.02
        upper = np.stack([c[0] + u * W2, c[1] - H2 * (0.15 + 0.85 * lid) * (1 - u ** 2) ** 0.75 + u * W2 * tilt
                          - p.get("raise", 0) * H2 * 0.1], 1)
        lower = np.stack([c[0] + u[::-1] * W2, c[1] + H2 * 0.42 * (1 - u[::-1] ** 2) ** 0.9 + u[::-1] * W2 * tilt], 1)
        opening = np.vstack([upper, lower])
        sl = cv.roi_of(opening, pad=H2 * 2.5)
        if sl is None:
            return
        X, Y = cv.X[sl], cv.Y[sl]
        d = cv.sdf(opening, sl, ss=3)
        a = soft(d, 0.7)
        # eyeball: warm off-white, darker toward lids and away from the light
        top = np.interp(X, upper[:, 0], upper[:, 1])
        shade = np.clip((Y - top) / (H2 * 1.2), 0, 1)
        lx = np.clip((X - c[0]) / (W2 * 2) + 0.5, 0, 1)
        sclera = ramp(0.35 + 0.5 * shade * (0.5 + 0.5 * lx) * p.get("flicker", 1.0),
                      [(0, (40, 26, 26)), (0.5, (150, 120, 104)), (1.0, (224, 200, 176))])
        cv.over(sl, sclera, a)
        # iris + pupil
        ix, iy = c[0] + gx * W2 * 0.42, c[1] + gy * H2 * 0.30 - H2 * 0.05
        r = W2 * (0.46 if not far else 0.62) * (0.9 if far else 1.0)
        dr = np.hypot((X - ix) / (0.82 if far else 1.0), Y - iy)
        ia = np.clip((r - dr) / 0.9, 0, 1) * a
        ring = np.clip(dr / r, 0, 1)
        iris = ramp(0.2 + 0.6 * (1 - ring) * (0.5 + 0.5 * np.clip((Y - iy) / r + 0.6, 0, 1)) * p.get("flicker", 1.0),
                    [(0, (14, 16, 20)), (0.45, (52, 66, 76)), (0.8, (112, 132, 138)), (1.0, (170, 186, 180))])
        cv.over(sl, iris, ia)
        cv.over(sl, (0.02, 0.015, 0.02), np.clip((r * 0.42 - dr) / 0.8, 0, 1) * a)
        # upper-lid shadow on the eyeball
        cv.over(sl, (0.10, 0.05, 0.04), np.clip(1 - (Y - top) / (H2 * 0.45), 0, 1) ** 2 * a * 0.4)
        # catchlight: the candle reflected low-right in the cornea, stronger as the eye opens toward it
        cl = np.clip(1 - np.hypot(X - (ix + r * 0.32), Y - (iy + r * 0.28)) / (r * 0.2), 0, 1) ** 1.5
        cv.over(sl, (1.0, 0.92, 0.78), cl * a * min(1.0, lid * 1.2) * 0.95 * p.get("flicker", 1.0))
        # lid line and lashes (thick, dark), crease above
        ul = np.zeros((cv.H, cv.W), np.float32)[sl]
        pts = np.dstack([upper[:, 0] * cv.k + cv.ox - sl[1].start, upper[:, 1] * cv.k + cv.oy - sl[0].start])[0]
        cv2.polylines(ul, [(pts * 4).astype(np.int32)], False, 1.0, max(1, int(0.013 * S * cv.k)), cv2.LINE_AA, shift=2)
        cv.over(sl, (0.04, 0.025, 0.025), cv2.GaussianBlur(ul, (0, 0), 0.6))
        crease = np.zeros_like(ul)
        cpts = pts.copy()
        cpts[:, 1] -= H2 * (0.45 + 0.3 * (1 - lid)) * cv.k
        cv2.polylines(crease, [(cpts[3:-3] * 4).astype(np.int32)], False, 1.0, max(1, int(0.005 * S * cv.k)), cv2.LINE_AA, shift=2)
        cv.over(sl, (0.18, 0.08, 0.07), cv2.GaussianBlur(crease, (0, 0), 1.6) * 0.45)
        lw = np.zeros_like(ul)
        lpts = np.dstack([lower[:, 0] * cv.k + cv.ox - sl[1].start, lower[:, 1] * cv.k + cv.oy - sl[0].start])[0]
        cv2.polylines(lw, [(lpts * 4).astype(np.int32)], False, 1.0, max(1, int(0.005 * S * cv.k)), cv2.LINE_AA, shift=2)
        cv.over(sl, (0.3, 0.14, 0.1), cv2.GaussianBlur(lw, (0, 0), 1.0) * 0.4)

    def _stroke(self, cv, pts, width, color, taper=True, blur=0.8, alpha=1.0):
        sl = cv.roi_of(pts, pad=width * 3)
        if sl is None:
            return
        m = np.zeros((sl[0].stop - sl[0].start, sl[1].stop - sl[1].start), np.float32)
        q = np.dstack([pts[:, 0] * cv.k + cv.ox - sl[1].start, pts[:, 1] * cv.k + cv.oy - sl[0].start])[0]
        n = len(q)
        for i in range(n - 1):
            w = width * (math.sin(math.pi * (i + 0.5) / (n - 1)) ** 0.6 if taper else 1.0)
            cv2.line(m, tuple((q[i] * 4).astype(int)), tuple((q[i + 1] * 4).astype(int)), 1.0,
                     max(1, int(w * cv.k)), cv2.LINE_AA, shift=2)
        cv.over(sl, color, cv2.GaussianBlur(m, (0, 0), blur * cv.s) * alpha)

    def _brows(self, cv):
        p = self.p
        k, r = p.get("knit", 0.0), p.get("raise", 0.0)
        for pts3, w in (([(-0.17, -0.105), (-0.10, -0.135), (-0.02, -0.14), (0.06, -0.125 + 0.03 * k)], 0.026),
                        ([(0.15, -0.13 + 0.025 * k), (0.21, -0.145), (0.265, -0.13)], 0.02)):
            P3 = []
            for i, (x, y) in enumerate(pts3):
                inner = (i == len(pts3) - 1) if x < 0.1 else (i == 0)
                dy = -0.025 * r + (0.012 * k if inner else -0.004 * k)
                dx = (0.012 * k if (inner and x < 0.1) else (-0.01 * k if inner else 0))
                P3.append((x + dx, y + dy, 0.43))
            line = catmull(self.P(P3), closed=False, n=8)
            self._stroke(cv, line, w * self.S, (0.07, 0.04, 0.03), taper=True, blur=2.2, alpha=0.75)
            rr = np.random.default_rng(int(abs(P3[0][0]) * 100))
            for _ in range(7):
                off = line + rr.normal(0, 0.004 * self.S, 2)
                self._stroke(cv, off[::2], w * self.S * 0.35, (0.05, 0.03, 0.02), taper=True, blur=0.8, alpha=0.5)

    def _mouth(self, cv):
        t = self.p.get("tense", 0.0)
        pts = [(0.05, 0.288 + 0.006 * t, 0.37), (0.12, 0.284, 0.39), (0.20, 0.282 - 0.002 * t, 0.41),
               (0.25, 0.286 + 0.004 * t, 0.415)]
        line = catmull(self.P(pts), closed=False, n=8)
        self._stroke(cv, line, 0.010 * self.S * (1 - 0.25 * t), (0.14, 0.05, 0.05), taper=True, blur=1.0, alpha=0.85)
        up = line.copy()
        up[:, 1] -= 0.012 * self.S
        self._stroke(cv, up, 0.03 * self.S, (0.30, 0.13, 0.11), taper=True, blur=2.0, alpha=0.35)
        lo = line.copy()
        lo[:, 1] += 0.022 * self.S
        self._stroke(cv, lo[2:-2], 0.025 * self.S, (0.85, 0.52, 0.40), taper=True, blur=2.5, alpha=0.25 * self.p.get("flicker", 1))

    def _nose_details(self, cv):
        nost = self.P([(0.215, 0.168, 0.44), (0.25, 0.178, 0.45)])
        self._stroke(cv, catmull(nost, closed=False, n=6), 0.012 * self.S, (0.16, 0.07, 0.05), blur=2.2, alpha=0.35)
        cast = self.P([(0.12, -0.02, 0.40), (0.15, 0.10, 0.44), (0.20, 0.18, 0.45)])     # shadow side of the nose (light from right)
        self._stroke(cv, catmull(cast, closed=False, n=8), 0.07 * self.S, (0.10, 0.045, 0.05), blur=4.0, alpha=0.35)

    def _hair_strands(self, cv, poly3, n=26, seed=0, light_side=1.0):
        """Strands follow the hair's fall (crown -> ends) and are clipped to the hair shape."""
        poly = catmull(self.P(poly3))
        sl = cv.roi_of(poly, pad=10)
        if sl is None:
            return
        clip = soft(cv.sdf(poly, sl), 1.5)
        r = np.random.default_rng(seed)
        P3 = np.asarray(poly3)
        x0, x1 = P3[:, 0].min(), P3[:, 0].max()
        y0, y1 = P3[:, 1].min(), P3[:, 1].max()
        m = np.zeros(clip.shape, np.float32)
        for i in range(n):
            x = r.uniform(x0, x1)
            pts3 = [(x + 0.02 * r.normal(), y0, 0.1), (x - 0.03 + 0.02 * r.normal(), y0 + (y1 - y0) * 0.4, 0.1),
                    (x - 0.05 + 0.03 * r.normal(), y1, 0.05)]
            q = catmull(self.P(pts3), closed=False, n=10)
            q = np.dstack([q[:, 0] * cv.k + cv.ox - sl[1].start, q[:, 1] * cv.k + cv.oy - sl[0].start])[0]
            cv2.polylines(m, [(q * 4).astype(np.int32)], False, float(r.uniform(0.3, 1.0)),
                          max(1, int(r.uniform(0.002, 0.005) * self.S * cv.k)), cv2.LINE_AA, shift=2)
        X = cv.X[sl]
        side = np.clip((X - (self.cx - 0.3 * self.S)) / (0.6 * self.S), 0, 1)       # brighter toward the candle
        cv.over(sl, (0.62, 0.38, 0.2), cv2.GaussianBlur(m, (0, 0), 0.7) * clip * light_side * (0.25 + 0.75 * side)
                * self.p.get("flicker", 1))

    # ------------------------------------------------------------------ draw
    def draw(self, cv, pose):
        self.setpose(pose)
        S = self.S
        self._shade(cv, self.P(COAT_PTS, body=True), 0.5 * S, COAT, edge=2.0, tex=0.07, rim=0.12)
        self._shade(cv, catmull(self.P(HAIR_BACK)), 0.12 * S, HAIR, edge=3.0, tex=0.12, rim=0.4, tex_angle=-80)
        self._hair_strands(cv, HAIR_BACK, 40, 2, 0.25)
        self._shade(cv, catmull(self.P(NECK)), 0.10 * S, SKIN, edge=1.5, amb=0.06)
        self._shade(cv, catmull(self.P(STOCK_PTS)), 0.08 * S, STOCK, edge=1.5, tex=0.06)
        col = self._shade(cv, catmull(self.P(COLLAR), n=6), 0.06 * S, COAT, edge=1.3, tex=0.06, rim=0.1)
        if col:                                  # thin gold edge on the standing collar, catching the candle
            edge = catmull(self.P([(0.27, 0.57, 0.2), (0.30, 0.72, 0.2), (0.24, 0.80, 0.25), (0.08, 0.89, 0.25)], ), closed=False, n=8)
            self._stroke(cv, edge, 0.012 * S, (1.0, 0.76, 0.36), taper=False, blur=1.2, alpha=0.5 * self.p.get("flicker", 1))
        face = catmull(self.P(FACE), n=10)
        self._shade(cv, face, 0.22 * S, SKIN, edge=1.0, bumps=self._face_bumps(), spec=0.3, rim=0.22, tex=0.015)
        self._nose_details(cv)
        self._eye(cv, (-0.045, -0.03, 0.39), 0.15, 0.036)
        self._eye(cv, (0.205, -0.035, 0.43), 0.078, 0.032, far=True)
        self._brows(cv)
        self._mouth(cv)
        self._shade(cv, catmull(self.P(HAIR_FRONT_FAR)), 0.05 * S, HAIR, edge=2.0, tex=0.12, rim=0.2, tex_angle=-75)
        self._shade(cv, catmull(self.P(HAIR_FRONT_NEAR)), 0.08 * S, HAIR, edge=2.2, tex=0.14, rim=0.45, tex_angle=-85)
        self._hair_strands(cv, HAIR_FRONT_NEAR, 90, 1, 0.45)
        self._hair_strands(cv, HAIR_FRONT_FAR, 30, 3, 0.7)

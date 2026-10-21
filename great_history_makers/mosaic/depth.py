"""2.5D toolkit: a pinhole ground plane, depth-correct parallax and walkers that move
through depth with planted feet and cast shadows.

Coordinates: design units (frame 1080 x 1920). A ground point at lateral X (measured in
units at the reference plane) and depth factor q (q = Z_ref / Z: 1 on the reference plane,
>1 nearer the camera) projects to   x = vpx + X*q ,  y = horizon + D*q.
Everything standing at depth q is scaled by q and moves with parallax p_ref*q, so camera
trucks/dollies produce the right relative motion for every depth.
"""
import math

import numpy as np

from . import motion
from .geom import S, T
from .scene import FigureItem, layer_matrix


class Ground:
    def __init__(self, vpx=480.0, horizon=1000.0, D=330.0, p_ref=0.36, focal=935.0):
        self.vpx, self.h, self.D, self.p_ref, self.f = vpx, horizon, D, p_ref, focal

    def project(self, X, q):
        return self.vpx + X * q, self.h + self.D * q

    def at_height(self, X, Yup, q):
        """Point Yup units above the ground (reference-plane units) at lateral X, depth q."""
        return self.vpx + X * q, self.h + (self.D - Yup) * q

    def q_of_y(self, y):
        return (y - self.h) / self.D

    def parallax(self, q):
        return self.p_ref * q

    def depth(self, q):
        """World depth Z (reference-plane units) of depth factor q."""
        return self.f / q


class DepthWalkers:
    """A column of rigged figures walking along a world path (X, Z) with planted feet.

    path: list of (X, q) waypoints. Walkers are spaced `spacing` world units apart and
    advance at the planted speed of the figure at the reference scale k_ref.
    filter_q: (qmin, qmax) only emit walkers in that depth band (for occlusion ordering).
    fade_q: walkers whose q drops below this fade out (entering a dark passage)."""

    def __init__(self, ground, figures, path, k_ref, n, spacing, period=1.1, swing=20.0, cam=None,
                 shadow=None, t0_offset=0.0, seed=0, fade_q=None):
        self.g, self.figs, self.k_ref, self.n, self.spacing = ground, figures, k_ref, n, spacing
        self.period, self.swing, self.cam, self.shadow = period, swing, cam, shadow
        self.t0, self.fade_q = t0_offset, fade_q
        pts = []
        for (Xa, qa), (Xb, qb) in zip(path, path[1:]):
            for i in range(40):
                u = i / 40
                X, q = Xa + (Xb - Xa) * u, qa + (qb - qa) * u
                pts.append((X, ground.depth(q), q))
        pts.append((path[-1][0], ground.depth(path[-1][1]), path[-1][1]))
        P = np.array(pts)
        seg = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
        self.s = np.concatenate([[0], np.cumsum(seg)])
        self.P = P
        rnd = np.random.default_rng(seed)
        self.var = [(rnd.uniform(0.95, 1.05), rnd.uniform(0, 6.28), rnd.uniform(0.97, 1.03)) for _ in range(n)]
        self.v = motion.planted_speed(k_ref, period, swing)

    def state(self, s):
        X = np.interp(s, self.s, self.P[:, 0])
        q = np.interp(s, self.s, self.P[:, 2])
        return X, q

    def items(self, t, qband=(0, 99)):
        out = []
        for i in range(self.n):
            per_mul, ph, size = self.var[i]
            per = self.period * per_mul
            v = motion.planted_speed(self.k_ref * size, per, self.swing)
            s = (t + self.t0) * v - i * self.spacing
            if s < 0 or s > self.s[-1]:
                continue
            X, q = self.state(s)
            if not (qband[0] <= q < qband[1]):
                continue
            out.append((q, i, X, ph, per, size))
        out.sort()
        return out

    def emitter(self, qband=(0, 99)):
        def fn(t):
            res = []
            cam = self.cam(t) if self.cam else {}
            for q, i, X, ph, per, size in self.items(t, qband):
                x, y = self.g.project(X, q)
                fig = self.figs[i % len(self.figs)]
                op = 1.0
                if self.fade_q and q < self.fade_q[0]:
                    op = max(0.0, (q - self.fade_q[1]) / (self.fade_q[0] - self.fade_q[1]))
                pose = motion.walk_planted(t, per, ph, self.swing)
                pose["_opacity"] = op
                item = FigureItem(fig, x, y, scale=self.k_ref * size * q / fig.k, pose_fn=lambda tt, p=pose: p,
                                  shadow=self.shadow if op > 0.5 else None)
                # depth-correct parallax: this FnItem lives in a p=1 layer; re-map to p(q)
                comp = np.eye(3)
                if self.cam:
                    comp = np.linalg.inv(layer_matrix(_UNIT, cam, 1.0)) @ layer_matrix(_UNIT, cam, self.g.parallax(q))
                for e in item.emit(t):
                    if len(e) > 3:
                        res.append(([(im, comp @ m) for im, m in e[0]], e[1], e[2] * op, e[3], e[4]))
                    else:
                        res.append((e[0], comp @ e[1], e[2] * op))
            return res
        return fn


class _UnitCtx:
    pxpd = 1.0


_UNIT = _UnitCtx()


def depth_item(item, ground, q, cam):
    """Wrap any item standing at depth q so it gets depth-correct parallax inside a p=1 layer."""
    class _W:
        def emit(self, t):
            c = cam(t)
            comp = np.linalg.inv(layer_matrix(_UNIT, c, 1.0)) @ layer_matrix(_UNIT, c, ground.parallax(q))
            out = []
            for e in item.emit(t):
                if len(e) > 3:
                    out.append(([(im, comp @ m) for im, m in e[0]], e[1], e[2], e[3], e[4]))
                else:
                    out.append((e[0], comp @ e[1], e[2]))
            return out
    return _W()


# ------------------------------------------------------------------ perspective drawing
def quad(p, pts, col):
    p.poly(pts, col)


def lerp2(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def perspective_paving(p, g, x_left, x_right, q_near, q_far, rows, cols, col_a, col_b, joint="umber",
                       joint_w=3.0, X_fn=None):
    """Paving slabs on the ground plane between lateral X range and depth range."""
    qs = [q_far * (q_near / q_far) ** (i / rows) for i in range(rows + 1)]
    Xs = [x_left + (x_right - x_left) * j / cols for j in range(cols + 1)]
    for r in range(rows):
        for c in range(cols):
            a = g.project(Xs[c], qs[r])
            b = g.project(Xs[c + 1], qs[r])
            cc = g.project(Xs[c + 1], qs[r + 1])
            d = g.project(Xs[c], qs[r + 1])
            p.poly([a, b, cc, d], col_a if (r + c) % 2 else col_b)
    for q in qs:
        p.line([g.project(x_left, q), g.project(x_right, q)], joint, joint_w * q)
    for X in Xs:
        p.line([g.project(X, q_far), g.project(X, q_near)], joint, joint_w * 1.2)

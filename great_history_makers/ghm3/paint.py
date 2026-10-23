"""Painterly rendering toolkit: smooth shapes as signed-distance fields, form shading from
height fields, colour ramps (painter's value -> colour mapping), brush and canvas texture,
atmosphere. Coordinates are design units (1080x1920); every function takes the output scale s."""
import math

import cv2
import numpy as np

DW, DH = 1080, 1920


def catmull(pts, closed=True, n=12):
    """Smooth Catmull-Rom curve through control points -> dense (N, 2) polyline."""
    P = np.asarray(pts, np.float32)
    if closed:
        P = np.vstack([P[-1:], P, P[:2]])
    else:
        P = np.vstack([P[:1], P, P[-1:]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(P[-2])
    return np.array(out, np.float32)


class Canvas:
    """A float RGB frame plus helpers in design units. A camera (zoom about a focus point) is
    built into the mapping px = x * k + ox, so shapes are always rasterised at full resolution."""

    def __init__(self, W, H, zoom=1.0, focus=(DW / 2, DH / 2)):
        self.W, self.H, self.s = W, H, W / DW
        self.k = self.s * zoom
        self.ox = W / 2 - focus[0] * self.k
        self.oy = H / 2 - focus[1] * self.k
        self.rgb = np.zeros((H, W, 3), np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.X, self.Y = (xx - self.ox) / self.k, (yy - self.oy) / self.k

    def px(self, x, y):
        return x * self.k + self.ox, y * self.k + self.oy

    def roi(self, x0, y0, x1, y1):
        a, b = self.px(x0, y0)
        c, d = self.px(x1, y1)
        a, b, c, d = max(0, int(a)), max(0, int(b)), min(self.W, int(math.ceil(c))), min(self.H, int(math.ceil(d)))
        return (slice(b, d), slice(a, c)) if c > a and d > b else None

    def roi_of(self, poly, pad=40):
        P = np.asarray(poly)
        return self.roi(P[:, 0].min() - pad, P[:, 1].min() - pad, P[:, 0].max() + pad, P[:, 1].max() + pad)

    def sdf(self, poly, sl, ss=2):
        """Signed distance (design units; negative inside) of a closed polyline inside ROI slices."""
        ys, xs = sl
        h, w = ys.stop - ys.start, xs.stop - xs.start
        P = np.asarray(poly, np.float32)
        p = (np.dstack([P[:, 0] * self.k + self.ox - xs.start, P[:, 1] * self.k + self.oy - ys.start])[0] * ss)
        m = np.zeros((h * ss, w * ss), np.uint8)
        cv2.fillPoly(m, [p.astype(np.int32)], 255)
        din = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        dout = cv2.distanceTransform(255 - m, cv2.DIST_L2, 5)
        d = (dout - din) / (self.k * ss)
        if ss > 1:
            d = cv2.resize(d, (w, h), interpolation=cv2.INTER_AREA)
        return d

    def over(self, sl, color, alpha):
        """Paint colour (H, W, 3 or 3,) with alpha (H, W) into the ROI."""
        a = np.clip(alpha, 0, 1)[..., None]
        self.rgb[sl] = self.rgb[sl] * (1 - a) + np.asarray(color, np.float32) * a


def soft(d, edge):
    """Alpha from signed distance with an edge softness in design units (lost-and-found edges)."""
    return np.clip(0.5 - d / np.maximum(edge, 1e-3), 0, 1)


def ramp(v, stops):
    """Painter's value ramp: v (any shape) -> RGB by piecewise-linear colour stops [(v, (r,g,b)), ...]."""
    xs = np.array([p for p, _ in stops], np.float32)
    cs = np.array([c for _, c in stops], np.float32) / 255.0
    v = np.clip(v, xs[0], xs[-1])
    out = np.empty(v.shape + (3,), np.float32)
    for k in range(3):
        out[..., k] = np.interp(v, xs, cs[:, k])
    return out


def height_from_mask(d, depth):
    """A rounded dome from the inside distance: 0 at the edge, 1 at `depth` design units inside."""
    u = np.clip(-d / depth, 0, 1)
    return np.sqrt(1 - (1 - u) ** 2)


def normals(h, scale):
    gy, gx = np.gradient(h * scale)
    n = np.dstack([-gx, -gy, np.ones_like(h)])
    return n / np.linalg.norm(n, axis=2, keepdims=True)


def lambert(n, X, Y, light, z=380.0):
    """Point light at design (lx, ly) in front of the picture plane by z units."""
    lx, ly = light
    L = np.dstack([lx - X, ly - Y, np.full_like(X, z)])
    dist = np.linalg.norm(L, axis=2, keepdims=True)
    L /= dist
    return np.clip((n * L).sum(2), 0, 1), dist[..., 0]


_TEX = {}


def noise(shape, sigma, seed):
    key = (shape, sigma, seed)
    if key not in _TEX:
        r = np.random.default_rng(seed)
        h, w = shape
        F = np.fft.rfft2(r.normal(0, 1, shape))
        fy = np.fft.fftfreq(h)[:, None]
        fx = np.fft.rfftfreq(w)[None, :]
        F *= np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))     # circular Gaussian blur: tileable
        n = np.fft.irfft2(F, s=shape).astype(np.float32)
        _TEX[key] = n / (n.std() + 1e-6)
    return _TEX[key]


def brush_texture(H, W, s, seed=1, length=26, angle=-60):
    """Directional brush-stroke field (static per shot): elongated noise used to break up
    flat values the way visible strokes do. Returned zero-mean, unit-ish std."""
    key = ("brush", H, W, seed, length, angle)
    if key not in _TEX:
        r = np.random.default_rng(seed)
        n = r.normal(0, 1, (H, W)).astype(np.float32)
        k = max(3, int(length * s)) | 1
        ker = np.zeros((k, k), np.float32)
        c = k // 2
        a = math.radians(angle)
        for i in range(k):
            t = i - c
            x, y = int(round(c + t * math.cos(a))), int(round(c + t * math.sin(a)))
            ker[y, x] = 1
        ker /= ker.sum()
        n = cv2.filter2D(n, -1, ker)
        n = cv2.GaussianBlur(n, (0, 0), 0.8 * s)
        _TEX[key] = n / (n.std() + 1e-6)
    return _TEX[key]


def fbm(H, W, s, seed, scales=(220, 90, 36), weights=(0.6, 0.3, 0.1)):
    key = ("fbm", H, W, seed, scales)
    if key not in _TEX:
        acc = np.zeros((H, W), np.float32)
        for sc, w in zip(scales, weights):
            acc += w * noise((H, W), sc * s / 3, seed + int(sc))
        _TEX[key] = acc
    return _TEX[key]


def scroll(tex, dx, dy):
    """Sub-pixel wrap-around scroll of a tileable-enough texture."""
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(tex, M, (tex.shape[1], tex.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def bloom(rgb, threshold=0.75, sigma=30, strength=0.5, s=1.0):
    hi = np.clip(rgb - threshold, 0, None)
    b = cv2.GaussianBlur(hi, (0, 0), sigma * s)
    b += cv2.GaussianBlur(hi, (0, 0), sigma * 3 * s) * 0.6
    rgb += b * strength


def paint_finish(rgb, s, seed=3, stroke=0.012, canvas=0.012, smooth=True):
    """Unifies everything into a painting: edge-preserving smoothing (merges small value
    changes into strokes), directional brush modulation and canvas tooth."""
    H, W = rgb.shape[:2]
    if smooth:
        u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        sm = cv2.bilateralFilter(u8, max(3, int(9 * s)) | 1, 24, 6 * s).astype(np.float32) / 255
        rgb[:] = rgb * 0.35 + sm * 0.65
    L = rgb.mean(2, keepdims=True)
    b = brush_texture(H, W, s, seed)[..., None]
    rgb *= 1 + stroke * b * (0.4 + L)
    c = noise((H, W), 0.7 * s, seed + 9)[..., None]
    rgb *= 1 + canvas * c

"""Turn flat layer art into tesserae: individual stone tiles separated by grout.

Algorithm (a lightweight take on Hausner's "simulated decorative mosaics"):
 1. Colour regions of the flat art are found (art is drawn without AA).
 2. Seeds are placed in rows that follow region outlines (andamento: the
    first rows of tiles hug every contour, as in Roman opus vermiculatum),
    then a jittered brick grid fills region interiors (opus tessellatum).
 3. Voronoi cells of the seeds, cut by region boundaries, become tiles.
 4. Every tile gets a flat stone colour with random variation, a bevel /
    directional light, fine grain, and is separated from its neighbours by grout.

The result is baked once into a sprite and then only moved rigidly (or very
gently deformed) during animation, so the tile texture stays stable.
"""
import hashlib
import os

import cv2
import numpy as np
from scipy.spatial import cKDTree

from .palette import P

CACHE_DIR = os.environ.get("GHM_CACHE", os.path.join(os.path.dirname(__file__), "..", "cache"))


class MosaicSprite:
    """Premultiplied RGBA uint8 image positioned in unit space."""

    def __init__(self, premult, x0, y0, ppu, tiles=None):
        self.premult = premult
        self.x0, self.y0, self.ppu = x0, y0, ppu
        self.tiles = tiles  # optional dict for per-tile animation

    @property
    def size(self):
        return self.premult.shape[1], self.premult.shape[0]

    def pixel_to_unit(self):
        """3x3 matrix: sprite pixel coords -> unit coords."""
        s = 1.0 / self.ppu
        return np.array([[s, 0, self.x0], [0, s, self.y0], [0, 0, 1.0]])


def tint(rgba, color, amount):
    """Atmospheric perspective: blend art colours toward a haze colour."""
    if amount <= 0:
        return rgba
    out = rgba.copy()
    col = np.array(P[color] if isinstance(color, str) else color, np.float32)
    out[..., :3] = np.clip(rgba[..., :3] * (1 - amount) + col * amount, 0, 255).astype(np.uint8)
    return out


def _jittered_brick(w, h, t, rng, jitter):
    rows = []
    y = t * 0.5
    i = 0
    while y < h + t:
        off = (i % 2) * t * 0.5
        xs = np.arange(off + t * 0.5 - t, w + t, t)
        rows.append(np.c_[xs, np.full_like(xs, y)])
        y += t
        i += 1
    pts = np.concatenate(rows)
    return pts + rng.uniform(-jitter * t, jitter * t, pts.shape)


def _contour_seeds(dist, alpha, tile, rows, rng):
    seeds = []
    for k in range(rows):
        lvl = (k + 0.5) * tile
        m = ((dist > lvl) & alpha).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for cnt in cnts:
            pts = cnt[:, 0, :].astype(np.float64)
            if len(pts) < 4:
                continue
            seg = np.linalg.norm(np.diff(pts, axis=0, append=pts[:1]), axis=1)
            cum = np.cumsum(seg)
            total = cum[-1]
            n = int(round(total / tile))
            if n < 1:
                continue
            ts = (np.arange(n) + rng.uniform(0.3, 0.7)) * total / n
            idx = np.clip(np.searchsorted(cum, ts), 0, len(pts) - 1)
            seeds.append(pts[idx])
    return np.concatenate(seeds) if seeds else np.zeros((0, 2))


def _cache_key(rgba, params):
    h = hashlib.sha1()
    h.update(np.ascontiguousarray(rgba).tobytes())
    h.update(repr(sorted(params.items())).encode())
    return h.hexdigest()[:20]


def tessellate(rgba, tile, seed=0, grout_frac=0.15, variation=0.07, rows=2, jitter=0.28,
               grout_color="grout", keep_tiles=False, cache=True, light=(-0.7, -0.7)):
    """rgba: HxWx4 uint8 flat art. tile: tile size in *pixels*.

    Returns (premult_uint8, tiles_or_None).
    """
    params = dict(tile=round(tile, 3), seed=seed, grout=grout_frac, var=variation, rows=rows,
                  jit=jitter, gc=str(grout_color), keep=keep_tiles, light=light, v=3)
    path = None
    if cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, _cache_key(rgba, params) + ".npz")
        if os.path.exists(path):
            z = np.load(path)
            tiles = None
            if keep_tiles:
                tiles = {k[2:]: z[k] for k in z.files if k.startswith("t_")}
            return z["premult"], tiles

    H, W = rgba.shape[:2]
    rng = np.random.default_rng(seed)
    alpha = rgba[..., 3] > 127
    premult = np.zeros((H, W, 4), np.uint8)
    if not alpha.any():
        return premult, None

    col = rgba[..., :3].astype(np.int32)
    key = (col[..., 0] << 16) | (col[..., 1] << 8) | col[..., 2]
    key[~alpha] = -1
    edge = np.zeros((H, W), bool)
    edge[:, 1:] |= key[:, 1:] != key[:, :-1]
    edge[1:, :] |= key[1:, :] != key[:-1, :]
    edge[:, :-1] |= key[:, 1:] != key[:, :-1]
    edge[:-1, :] |= key[1:, :] != key[:-1, :]
    dist = cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, 5)

    # --- seeds: contour-following rows + interior grid ---
    s_edge = _contour_seeds(dist, alpha, tile, rows, rng) if rows > 0 else np.zeros((0, 2))
    grid = _jittered_brick(W, H, tile, rng, jitter)
    gi = np.clip(grid.round().astype(int), 0, [W - 1, H - 1])
    keep = alpha[gi[:, 1], gi[:, 0]] & (dist[gi[:, 1], gi[:, 0]] > (rows - 0.05) * tile)
    if rows == 0:
        keep = np.ones(len(grid), bool)
    seeds = np.concatenate([s_edge, grid[keep]]) if len(s_edge) else grid[keep]
    if len(seeds) < 4:
        seeds = grid

    # --- Voronoi labelling of opaque pixels, split by colour region ---
    ys, xs = np.nonzero(alpha)
    _, lab = cKDTree(seeds).query(np.c_[xs, ys], workers=-1)
    _, reg = np.unique(key[ys, xs], return_inverse=True)
    comb = lab.astype(np.int64) * (reg.max() + 1) + reg
    _, tid = np.unique(comb, return_inverse=True)
    ntiles = tid.max() + 1
    labels = np.full((H, W), -1, np.int32)
    labels[ys, xs] = tid

    # --- tile colours with stone variation ---
    area = np.bincount(tid, minlength=ntiles).astype(np.float64)
    base = np.stack([np.bincount(tid, weights=col[ys, xs, c], minlength=ntiles) / area
                     for c in range(3)], 1)
    lum = rng.normal(1.0, variation, (ntiles, 1))
    chroma = rng.normal(0.0, variation * 0.35, (ntiles, 3))
    odd = rng.random(ntiles) < 0.03
    lum[odd] *= rng.uniform(0.85, 1.12, (odd.sum(), 1))
    tcol = np.clip(base * (lum + chroma), 0, 255)

    # --- grout between tiles ---
    g = max(1, int(round(grout_frac * tile)))
    bnd = np.zeros((H, W), np.uint8)
    bnd[:, 1:] |= (labels[:, 1:] != labels[:, :-1])
    bnd[1:, :] |= (labels[1:, :] != labels[:-1, :])
    if g > 1:
        bnd = cv2.dilate(bnd, np.ones((g, g), np.uint8))
    tiny = area < 0.07 * tile * tile
    grout = (bnd > 0) | (tiny[np.maximum(labels, 0)] & alpha)
    grout &= alpha
    inner = alpha & ~grout

    # --- bevel + directional light + grain ---
    d_in = cv2.distanceTransform(inner.astype(np.uint8), cv2.DIST_L2, 3)
    bw = max(1.0, 0.3 * tile)
    bev = np.clip(d_in / bw, 0, 1)
    bev = bev * bev * (3 - 2 * bev)
    db = cv2.GaussianBlur(d_in, (0, 0), max(0.6, tile * 0.08))
    gx = cv2.Sobel(db, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(db, cv2.CV_32F, 0, 1, ksize=3)
    nrm = np.sqrt(gx * gx + gy * gy) + 1e-4
    direc = (gx * -light[0] + gy * -light[1]) / nrm * (1 - bev)
    shade = 0.80 + 0.20 * bev + 0.11 * direc
    grain = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7) * 0.035
    shade = (shade * (1 + grain)).astype(np.float32)

    gcol = np.array(P[grout_color] if isinstance(grout_color, str) else grout_color, np.float32)
    rgb = tcol[np.maximum(labels, 0)].astype(np.float32) * shade[..., None]
    gmix = gcol * 0.82 + tcol[np.maximum(labels, 0)].astype(np.float32) * 0.18
    rgb[grout] = gmix[grout] * (1 + grain[grout, None] * 2)
    rgb = np.clip(rgb, 0, 255)
    rgb[~alpha] = 0
    premult[..., :3] = rgb.astype(np.uint8)
    premult[..., 3] = alpha.astype(np.uint8) * 255

    tiles = None
    if keep_tiles:
        cx = np.bincount(tid, weights=xs, minlength=ntiles) / area
        cy = np.bincount(tid, weights=ys, minlength=ntiles) / area
        tiles = dict(labels=labels, color=tcol.astype(np.float32), shade=shade, grout=grout,
                     gmix=gmix.astype(np.float16), cx=cx.astype(np.float32), cy=cy.astype(np.float32))
    if path:
        extra = {"t_" + k: v for k, v in (tiles or {}).items()}
        np.savez_compressed(path, premult=premult, **extra)
    return premult, tiles


def render_tiles(tiles, colors):
    """Re-shade a kept tile layout with new per-tile colours (e.g. shimmering water)."""
    lab = tiles["labels"]
    alpha = lab >= 0
    rgb = colors[np.maximum(lab, 0)] * tiles["shade"][..., None]
    g = tiles["grout"]
    rgb[g] = tiles["gmix"][g].astype(np.float32)
    rgb[~alpha] = 0
    out = np.zeros(lab.shape + (4,), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = alpha.astype(np.uint8) * 255
    return out

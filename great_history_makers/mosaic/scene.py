"""Scene graph: layers with parallax, sprites, cut-out figures, animated tiles, camera."""
import zlib

import numpy as np

from .compositor import composite, composite_rgba, composite_shadow, composite_shadow_group, rigid_tile_wave, wave_deform
from .geom import S, T, about
from .painter import Painter
from .tessellate import MosaicSprite, render_tiles, tessellate, tint

DESIGN_W, DESIGN_H = 1080.0, 1920.0


class Ctx:
    """Render context. All art is authored in design units (frame = 1080 x 1920)."""

    def __init__(self, out_w, out_h, fps, ss=1.25):
        self.W, self.H, self.fps, self.ss = out_w, out_h, fps, ss
        self.pxpd = out_w / DESIGN_W
        self.ppu = self.pxpd * ss  # sprite pixels per design unit


def stable_seed(name):
    return zlib.crc32(name.encode()) & 0x7FFFFFFF


def make_sprite(ctx, draw, rect, tile, name, unit_scale=1.0, haze=None, haze_amt=0.0,
                keep_tiles=False, rows=2, variation=0.07, pad=0.0, grout_frac=0.15, jitter=0.28,
                outline=None, outline_w=2.4, key_color=None, clip=None, volume=None):
    """Paint `draw(painter)` in unit-space `rect`, crop and tessellate it.

    tile: tesserae size in design units. unit_scale: design units per drawing unit
    (figures are drawn in their own 1000-unit-tall coordinate system)."""
    x0, y0, w, h = rect
    ppu = ctx.ppu * unit_scale
    p = Painter(x0, y0, w, h, ppu)
    draw(p)
    arr = p.array()
    if key_color is not None:  # paint with key colour to punch holes (e.g. gate openings)
        hole = np.all(arr[..., :3] == key_color, axis=-1)
        arr[hole] = 0
    if clip is not None:  # keep only unit-space rect (cx0, cy0, cx1, cy1)
        m = np.zeros(arr.shape[:2], bool)
        q = [int(round((clip[0] - x0) * ppu)), int(round((clip[1] - y0) * ppu)),
             int(round((clip[2] - x0) * ppu)), int(round((clip[3] - y0) * ppu))]
        m[max(0, q[1]):max(0, q[3]), max(0, q[0]):max(0, q[2])] = True
        arr[~m] = 0
    a = arr[..., 3] > 127
    if not a.any():
        return None
    ys, xs = np.nonzero(a)
    orad = int(round(outline_w * ctx.ppu)) if outline else 0
    padp = int(round(pad * ppu)) + 2 + orad
    cx0, cy0 = max(0, xs.min() - padp), max(0, ys.min() - padp)
    cx1, cy1 = min(arr.shape[1], xs.max() + padp + 1), min(arr.shape[0], ys.max() + padp + 1)
    arr = arr[cy0:cy1, cx0:cx1]
    if pad:
        big = np.zeros((arr.shape[0] + 2 * padp, arr.shape[1] + 2 * padp, 4), np.uint8)
        big[padp:-padp, padp:-padp] = arr
        arr = big
        cx0 -= padp
        cy0 -= padp
    if outline and orad > 0:
        # dark contour row around every cut-out piece, as in figural mosaics
        import cv2
        from .palette import P
        a8 = (arr[..., 3] > 127).astype(np.uint8)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * orad + 1, 2 * orad + 1))
        ring = (cv2.dilate(a8, k) > 0) & (a8 == 0)
        arr = arr.copy()
        arr[ring] = P[outline] + (255,)
    if haze:
        arr = tint(arr, haze, haze_amt)
    pm, tiles = tessellate(arr, tile * ctx.ppu, seed=stable_seed(name), rows=rows,
                           variation=variation, keep_tiles=keep_tiles, grout_frac=grout_frac,
                           jitter=jitter, volume=volume)
    return MosaicSprite(pm, x0 + cx0 / ppu, y0 + cy0 / ppu, ppu, tiles)


# ---------------------------------------------------------------- items
class SpriteItem:
    def __init__(self, sprite, offset=None, opacity=None):
        self.sprite, self.offset, self.opacity = sprite, offset, opacity

    def emit(self, t):
        if self.sprite is None:
            return []
        dx, dy = self.offset(t) if self.offset else (0.0, 0.0)
        op = self.opacity(t) if self.opacity else 1.0
        return [(self.sprite.premult, T(dx, dy) @ self.sprite.pixel_to_unit(), op)]


class TileAnimItem:
    """Sprite whose individual tiles change colour over time (water shimmer, glints)."""

    def __init__(self, sprite, color_fn):
        self.sprite, self.color_fn = sprite, color_fn

    def emit(self, t):
        tl = self.sprite.tiles
        img = render_tiles(tl, self.color_fn(tl, t))
        return [(img, self.sprite.pixel_to_unit(), 1.0)]


class TileScatterItem:
    """Moves individual tesserae as rigid units by forward-splatting their pixels.

    offset_fn(tiles, t) -> (dx, dy, visible) arrays per tile, in sprite pixels.
    Used for tiles assembling into an image or falling out of an aged mosaic."""

    def __init__(self, sprite, offset_fn, below=None, opacity=1.0):
        self.sprite, self.offset_fn, self.opacity = sprite, offset_fn, opacity
        tl = sprite.tiles
        ys, xs = np.nonzero(tl["labels"] >= 0)
        self.ys, self.xs = ys.astype(np.int32), xs.astype(np.int32)
        self.tid = tl["labels"][ys, xs]
        self.px = sprite.premult[ys, xs]
        self.below = below  # optional premult image drawn first (e.g. bare plaster)

    def emit(self, t):
        h, w = self.sprite.premult.shape[:2]
        dx, dy, vis = self.offset_fn(self.sprite.tiles, t)
        img = self.below.copy() if self.below is not None else np.zeros((h, w, 4), np.uint8)
        x = self.xs + np.rint(dx[self.tid]).astype(np.int32)
        y = self.ys + np.rint(dy[self.tid]).astype(np.int32)
        ok = vis[self.tid] & (x >= 0) & (x < w) & (y >= 0) & (y < h)
        img[y[ok], x[ok]] = self.px[ok]
        op = self.opacity(t) if callable(self.opacity) else self.opacity
        return [(img, self.sprite.pixel_to_unit(), op)]


class PartSpec:
    def __init__(self, name, draw, pivot=(0, 0), parent=None, z=0, tile_mul=1.0, deform=None,
                 variation=0.07):
        self.name, self.draw, self.pivot, self.parent = name, draw, pivot, parent
        self.z, self.tile_mul, self.deform, self.variation = z, tile_mul, deform, variation


FIGURE_VOLUME = {"value": None}


class volume_shading:
    """with volume_shading(dict(light=(-0.6, -0.8))): figures built inside get 2.5D form shading."""

    def __init__(self, vol):
        self.vol = vol

    def __enter__(self):
        self.prev = FIGURE_VOLUME["value"]
        FIGURE_VOLUME["value"] = self.vol

    def __exit__(self, *a):
        FIGURE_VOLUME["value"] = self.prev


class Figure:
    """Cut-out puppet: every body part is its own tessellated sprite drawn in a shared
    figure coordinate system (height ~1000 units, feet at y=1000, facing -x)."""

    BOUNDS = (-650, -520, 1300, 1720)

    def __init__(self, ctx, name, parts, k, tile, haze=None, haze_amt=0.0, volume=None):
        self.name, self.k = name, k
        volume = volume or FIGURE_VOLUME["value"]
        self.parts = sorted(parts, key=lambda p: p.z)
        self.by_name = {p.name: p for p in parts}
        self.sprites = {}
        for p in parts:
            pad = p.deform.get("amp", 0) * 1.6 if p.deform else 0
            self.sprites[p.name] = make_sprite(
                ctx, p.draw, self.BOUNDS, tile * p.tile_mul, f"{name}:{p.name}", unit_scale=k,
                haze=haze, haze_amt=haze_amt, variation=p.variation, pad=pad, outline="outline",
                keep_tiles=bool(p.deform), volume=volume,
                rows=2 if tile * p.tile_mul * ctx.ppu > 3 else 1)

    def emit_at(self, root, pose, t):
        world = {}
        out = []
        for p in self.parts:
            world_of(p, self, root, pose, world)
        for p in self.parts:
            spr = self.sprites[p.name]
            if spr is None:
                continue
            pm = spr.premult
            if p.deform:
                d = p.deform
                wind = pose.get("_wind", 1.0)
                fn = rigid_tile_wave if spr.tiles is not None else wave_deform
                extra = (spr.tiles,) if spr.tiles is not None else ()
                pm = fn(pm, *extra, t + pose.get("_phase", 0.0), d["amp"] * spr.ppu * wind, d["wl"] * spr.ppu,
                        d.get("speed", 0.5), d.get("axis", "y"), d.get("phase", 0.0), d.get("power", 1.4),
                        d.get("anchor", 0.0))
            out.append((pm, world[p.name] @ spr.pixel_to_unit(), pose.get("_opacity", 1.0)))
        return out


def world_of(p, fig, root, pose, cache):
    if p.name in cache:
        return cache[p.name]
    parent = root if p.parent is None else world_of(fig.by_name[p.parent], fig, root, pose, cache)
    ang, dx, dy = pose.get(p.name, (0.0, 0.0, 0.0))
    M = parent @ T(dx, dy) @ about(p.pivot[0], p.pivot[1], _rot(ang))
    cache[p.name] = M
    return M


def _rot(deg):
    from .geom import R
    return R(deg)


class FigureItem:
    """Places a Figure in a layer. pose_fn(t) -> {part: (deg, dx, dy)};
    motion_fn(t) -> (dx, dy) in layer units (walking, bobbing)."""

    def __init__(self, figure, x, y, flip=False, pose_fn=None, motion_fn=None, scale=1.0, shadow=None):
        self.figure, self.x, self.y, self.flip = figure, x, y, flip
        self.pose_fn, self.motion_fn, self.scale = pose_fn, motion_fn, scale
        self.shadow = shadow  # dict(shx, sy, cast, contact, blur) -> grounded 2.5D shadows

    def emit(self, t):
        mx, my = self.motion_fn(t) if self.motion_fn else (0.0, 0.0)
        k = self.figure.k * self.scale
        fx, fy = self.x + mx, self.y + my
        root = T(fx, fy) @ S(-k if self.flip else k, k) @ T(0, -1000)  # (x, y) = feet on the ground
        pose = self.pose_fn(t) if self.pose_fn else {}
        parts = self.figure.emit_at(root, pose, t)
        if not self.shadow:
            return parts
        sh = self.shadow
        out = []
        if sh.get("contact", 0.5):
            spr = contact_sprite()
            w = 210 * k * sh.get("width", 1.0)
            out.append(([(spr, T(fx - w / 2, fy - w * 0.09) @ S(w / spr.shape[1], w * 0.18 / spr.shape[0]))],
                        np.eye(3), sh.get("contact", 0.5), "shadowgroup", sh.get("contact_blur", 3.0) * k))
        if sh.get("cast", 0.4):
            shx, sy = sh.get("shx", 0.55), sh.get("sy", 0.22)
            P = np.array([[1, -shx, shx * fy], [0, sy, (1 - sy) * fy], [0, 0, 1.0]])
            out.append(([(img, P @ M) for img, M, _ in parts], np.eye(3), sh.get("cast", 0.4) * pose.get("_opacity", 1.0),
                        "shadowgroup", sh.get("blur", 2.0)))
        return out + parts


_CONTACT = {}


def contact_sprite():
    """Soft elliptical contact shadow (premultiplied RGBA, alpha only matters)."""
    if "s" not in _CONTACT:
        h, w = 48, 128
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        a = np.exp(-(((xx - w / 2) / (w * 0.32)) ** 2 + ((yy - h / 2) / (h * 0.3)) ** 2) * 1.4)
        img = np.zeros((h, w, 4), np.uint8)
        img[..., 3] = (a * 255).astype(np.uint8)
        _CONTACT["s"] = img
    return _CONTACT["s"]


class FnItem:
    def __init__(self, fn):
        self.fn = fn

    def emit(self, t):
        return self.fn(t)


class Layer:
    """blur: None, a number or fn(t) -> Gaussian sigma in design units (depth of field /
    rack focus). A blurred layer is rendered to its own RGBA buffer first."""

    def __init__(self, parallax, items, name="", blur=None):
        self.p, self.items, self.name, self.blur = parallax, items, name, blur


def layer_matrix(ctx, cam, p):
    """Design-unit -> pixel matrix for a layer with parallax p (0 = infinitely far)."""
    z, ox, oy = cam.get("zoom", 1.0), cam.get("ox", 0.0), cam.get("oy", 0.0)
    zl = 1.0 + (z - 1.0) * p
    return S(ctx.pxpd) @ about(DESIGN_W / 2, DESIGN_H / 2, S(zl)) @ T(-ox * p, -oy * p)


class Scene:
    """camera(t) -> dict(ox, oy, zoom) in design units. Local time t may run slightly
    outside [0, duration] during transitions."""

    def __init__(self, name, duration, layers, camera, fx=(), bg=(30, 26, 22)):
        self.name, self.duration, self.layers = name, duration, layers
        self.camera, self.fx, self.bg = camera, list(fx), bg

    def render(self, ctx, t):
        frame = np.empty((ctx.H, ctx.W, 3), np.float32)
        frame[:] = np.array(self.bg, np.float32) / 255.0
        cam = self.camera(t)
        z, ox, oy = cam.get("zoom", 1.0), cam.get("ox", 0.0), cam.get("oy", 0.0)
        cx, cy = DESIGN_W / 2, DESIGN_H / 2
        for layer in self.layers:
            L = layer_matrix(ctx, cam, layer.p)
            sig = layer.blur(t) if callable(layer.blur) else (layer.blur or 0.0)
            target = frame
            if sig * ctx.pxpd > 0.4:
                target = np.zeros((ctx.H, ctx.W, 4), np.float32)
            for item in layer.items:
                for e in item.emit(t):
                    img, M, op = e[0], e[1], e[2]
                    if op <= 0.003:
                        continue
                    if len(e) > 3 and e[3] == "shadowgroup":
                        composite_shadow_group(frame, [(im, L @ m) for im, m in img], op, e[4] * ctx.pxpd)
                        continue
                    if len(e) > 3 and e[3] == "shadow":
                        composite_shadow(frame, img, L @ M, op, e[4] * ctx.pxpd if len(e) > 4 else 2.0)
                    elif target is frame:
                        composite(frame, img, L @ M, op)
                    else:
                        composite_rgba(target, img, L @ M, op)
            if target is not frame:
                import cv2
                bl = cv2.GaussianBlur(target, (0, 0), sig * ctx.pxpd)
                frame *= 1 - bl[..., 3:4]
                frame += bl[..., :3]
        for fx in self.fx:
            fx(frame, t, ctx, cam)
        return frame

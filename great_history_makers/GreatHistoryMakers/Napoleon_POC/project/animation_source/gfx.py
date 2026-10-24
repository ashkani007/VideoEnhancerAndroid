"""Vector drawing helpers on Skia: smooth shapes, cel shading with path booleans, gradients, glow.

Style: stylized editorial 2D. Flat colour masses, one shadow tone carved on the side away from the
key light (path difference), a thin rim on the lit side, soft linear gradients, no tiles or textures."""
import math

import numpy as np
import skia


def rgb(c, a=255):
    if isinstance(c, str):
        c = PAL[c]
    return skia.Color(int(c[0]), int(c[1]), int(c[2]), int(a))


PAL = {
    # character
    "skin": (238, 186, 150), "skin_sh": (196, 132, 108), "skin_hi": (255, 216, 186), "blush": (226, 140, 120),
    "hair": (52, 36, 30), "hair_sh": (34, 22, 20), "hair_hi": (92, 66, 52),
    "coat": (36, 52, 104), "coat_sh": (24, 33, 70), "coat_hi": (70, 94, 160),
    "lapel": (240, 234, 220), "lapel_sh": (196, 186, 170), "red": (178, 44, 46), "red_sh": (122, 28, 34),
    "gold": (232, 182, 72), "gold_sh": (176, 120, 40), "gold_hi": (255, 226, 140),
    "hat": (30, 28, 34), "hat_sh": (16, 15, 20), "hat_hi": (72, 70, 84),
    "eye_w": (250, 246, 240), "iris": (82, 108, 132), "pupil": (22, 20, 26), "ink": (40, 26, 26),
    "lip": (190, 106, 96), "mouth": (92, 34, 38), "teeth": (246, 240, 230), "tongue": (184, 82, 84),
    # soldiers
    "shako": (28, 26, 30), "belt": (236, 232, 222), "trouser": (226, 222, 210), "gaiter": (38, 34, 36),
    "musket": (96, 64, 40), "steel": (190, 196, 204),
}


def poly(pts, closed=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if closed:
        p.close()
    return p


def smooth(pts, closed=True, tension=0.5):
    """Catmull-Rom through points, emitted as cubic Beziers (clean editorial curves)."""
    P = [tuple(map(float, q)) for q in pts]
    n = len(P)
    p = skia.Path()
    p.moveTo(*P[0])
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
        p1, p2 = P[i], P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[(i + 1) % n]
        k = tension / 3.0 * 2
        c1 = (p1[0] + (p2[0] - p0[0]) * k / 2, p1[1] + (p2[1] - p0[1]) * k / 2)
        c2 = (p2[0] - (p3[0] - p1[0]) * k / 2, p2[1] - (p3[1] - p1[1]) * k / 2)
        p.cubicTo(*c1, *c2, *p2)
    if closed:
        p.close()
    return p


def ellipse(cx, cy, rx, ry):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


def rrect(x0, y0, x1, y1, r):
    p = skia.Path()
    p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x0, y0, x1, y1), r, r))
    return p


def moved(path, dx, dy):
    q = skia.Path(path)
    q.offset(dx, dy)
    return q


def diff(a, b):
    return skia.Op(a, b, skia.PathOp.kDifference_PathOp)


def inter(a, b):
    return skia.Op(a, b, skia.PathOp.kIntersect_PathOp)


def fill(canvas, path, color, alpha=255, shader=None, blur=0.0):
    paint = skia.Paint(AntiAlias=True, Color=rgb(color, alpha))
    if shader is not None:
        paint.setShader(shader)
    if blur:
        paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    canvas.drawPath(path, paint)


def stroke(canvas, path, color, width, alpha=255, cap=skia.Paint.kRound_Cap, blur=0.0):
    paint = skia.Paint(AntiAlias=True, Color=rgb(color, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                       StrokeCap=cap, StrokeJoin=skia.Paint.kRound_Join)
    if blur:
        paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    canvas.drawPath(path, paint)


def lin(p0, p1, c0, c1, a0=255, a1=255):
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], [rgb(c0, a0), rgb(c1, a1)])


def radial(c, r, c0, c1, a0=255, a1=0):
    return skia.GradientShader.MakeRadial(skia.Point(*c), r, [rgb(c0, a0), rgb(c1, a1)])


def toon(canvas, path, base, shadow, light=(1.0, -0.6), depth=14.0, hi=None, rim=4.0, outline=None, ow=2.2,
         grad=None):
    """Cel-shaded fill: base (optionally gradient), shadow carved on the side away from the light,
    thin highlight rim on the lit side, optional darker outline."""
    lx, ly = light
    L = math.hypot(lx, ly) or 1.0
    lx, ly = lx / L, ly / L
    fill(canvas, path, base, shader=grad)
    sh = diff(path, moved(path, lx * depth, ly * depth))
    fill(canvas, sh, shadow, alpha=235)
    if hi is not None and rim > 0:
        h = diff(path, moved(path, -lx * rim, -ly * rim))
        fill(canvas, h, hi, alpha=200)
    if outline is not None:
        stroke(canvas, path, outline, ow, alpha=170)


def glow(canvas, cx, cy, r, color, alpha=160):
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(radial((cx, cy), r, color, color, alpha, 0))
    paint.setBlendMode(skia.BlendMode.kScreen)
    canvas.drawCircle(cx, cy, r, paint)


def to_numpy(surface):
    img = surface.makeImageSnapshot()
    return np.array(img.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3])   # explicit RGBA -> RGB

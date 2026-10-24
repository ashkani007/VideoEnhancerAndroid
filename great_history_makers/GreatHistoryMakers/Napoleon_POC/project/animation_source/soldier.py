"""French line infantryman (c. 1805-1812), stylized editorial 2D, profile facing screen-right.

Rig: hips (bob) -> torso -> head (shako with plume); legs thigh -> shin -> foot with a 2-key-pose
walk cycle (contact / passing) interpolated smoothly; near arm holds the musket on the shoulder,
far arm swings opposite the near leg. phase in [0, 1) per stride; variation per soldier."""
import math

from gfx import ellipse, fill, lin, poly, rrect, smooth, stroke, toon, PAL

THIGH, SHIN = 92.0, 88.0


def _leg(c, ang_t, ang_s, light, far):
    c.save()
    c.rotate(ang_t)
    thigh = rrect(-15, -6, 15, THIGH + 4, 13)
    toon(c, thigh, "trouser", "lapel_sh", light=light, depth=7 if not far else 12, hi=None)
    c.translate(0, THIGH)
    c.rotate(ang_s)
    shin = rrect(-13, -4, 13, SHIN, 11)
    toon(c, shin, "gaiter", "hat_sh", light=light, depth=6, hi="hat_hi", rim=2)
    foot = smooth([(-12, SHIN - 12), (30, SHIN - 8), (34, SHIN + 6), (-14, SHIN + 8)])
    toon(c, foot, "hat", "hat_sh", light=light, depth=4)
    c.restore()


def walk_angles(ph):
    """Thigh/shin angles (deg) for one leg at phase ph (0 = heel strike)."""
    a = 2 * math.pi * ph
    thigh = -24 * math.cos(a)                      # swing: forward (negative = toward screen-right)
    knee = 10 + 34 * max(0.0, math.sin(a)) ** 1.4    # knee bends in the swing phase
    return thigh, knee


def draw(c, x, y, scale, ph, light=(1, -0.4), haze=0.0, flag=None):
    c.save()
    c.translate(x, y)
    c.scale(scale, scale)
    bob = -6 * abs(math.cos(2 * math.pi * ph)) + 3
    c.translate(0, bob)
    tf, sf = walk_angles(ph + 0.5)
    tn, sn = walk_angles(ph)
    # far leg + far arm (darker)
    c.save()
    _leg(c, tf, sf, light, True)
    c.restore()
    swing = 26 * math.cos(2 * math.pi * ph)
    c.save()
    c.translate(-2, -150)
    c.rotate(swing)
    toon(c, rrect(-12, -8, 12, 120, 11), "coat_sh", "hair_sh", light=light, depth=6)
    fill(c, ellipse(0, 126, 11, 13), "skin_sh")
    c.restore()
    # torso: coat with white crossbelts, turnbacks, pack
    pack = rrect(-58, -168, -22, -86, 10)
    toon(c, pack, "musket", "hair", light=light, depth=8)
    body = smooth([(-30, -178), (30, -176), (36, -100), (30, -10), (-34, -8), (-38, -100)])
    toon(c, body, "coat", "coat_sh", light=light, depth=12, hi="coat_hi", rim=3)
    tail = smooth([(-34, -40), (-10, -30), (-20, 18), (-46, 10)])
    toon(c, tail, "lapel", "lapel_sh", light=light, depth=5)
    stroke(c, poly([(-26, -170), (28, -40)], False), "belt", 7)
    stroke(c, poly([(26, -172), (-24, -44)], False), "belt", 7)
    fill(c, rrect(24, -170, 40, -150, 4), "red")                         # epaulette
    # near leg
    c.save()
    _leg(c, tn, sn, light, False)
    c.restore()
    # head and shako
    c.save()
    c.translate(6, -186)
    head = smooth([(-18, -2), (20, -4), (26, -26), (22, -50), (-14, -52), (-22, -26)])
    toon(c, head, "skin", "skin_sh", light=light, depth=6, hi="skin_hi", rim=2)
    fill(c, ellipse(12, -32, 3, 3.4), "ink")
    stroke(c, poly([(4, -40), (16, -42)], False), "hair", 3)
    fill(c, smooth([(24, -28), (31, -20), (23, -18)]), "skin_sh")
    shako = smooth([(-20, -46), (24, -48), (26, -96), (-20, -92)])
    toon(c, shako, "shako", "hat_sh", light=light, depth=6, hi="hat_hi", rim=2)
    fill(c, rrect(-4, -50, 34, -44, 3), "hat")                          # peak
    stroke(c, poly([(-20, -92), (26, -96)], False), "gold", 3)
    fill(c, ellipse(-2, -110, 7, 15), "red")                            # pompom
    fill(c, smooth([(6, -78), (14, -84), (12, -70)]), "gold")           # plate
    c.restore()
    # musket at the slope: butt held low in front by the near hand, barrel resting back over the shoulder
    musket = poly([(26, -46), (36, -50), (-26, -300), (-34, -298)])
    fill(c, musket, "musket")
    stroke(c, poly([(-30, -299), (-40, -346)], False), "steel", 3)        # bayonet
    fill(c, rrect(22, -58, 42, -36, 5), "musket")                         # butt
    c.save()
    c.translate(10, -162)
    c.rotate(-14)
    toon(c, rrect(-12, -6, 12, 66, 11), "coat", "coat_sh", light=light, depth=6, hi="coat_hi", rim=2)
    c.translate(0, 62)
    c.rotate(4)
    toon(c, rrect(-11, -4, 11, 54, 10), "coat", "coat_sh", light=light, depth=6)
    fill(c, rrect(-12, 38, 12, 52, 4), "red")
    fill(c, ellipse(0, 60, 12, 12), "skin")
    c.restore()
    c.restore()

"""Napoleon POC: three animated scenes (12 s), camera moves and transitions. Design space 1080x1920.

Scene 1  0-4 s   The Decision: planning room at night, medium shot pushing into a close-up.
Scene 2  4-8 s   The Command: low-angle medium shot at the dawn window; raises his head, points, commands.
Scene 3  8-12 s  The March: misty battlefield, columns advancing under flags, Napoleon in the foreground.
Cuts: 4.0 s match-cut on the head lift; 8.0 s whip-pan in the pointing direction."""
import math

import numpy as np
import skia

import soldier
from anim import Track, blink, ease, spring
from gfx import PAL, ellipse, fill, glow, lin, poly, radial, rgb, rrect, smooth, stroke, toon
from napoleon import Napoleon, ik_arm

DW, DH = 1080, 1920
NAP = Napoleon()


def flick(t, seed=0.0):
    return 0.84 + 0.08 * math.sin(t * 13.0 + seed) + 0.05 * math.sin(t * 7.1 + 1.7 + seed) + 0.03 * math.sin(t * 29.0)


# ======================================================================= scene 1: the decision
S1 = dict(
    gx=Track([(0, -0.55), (0.35, -0.55), (0.55, -0.05, "out"), (0.9, -0.05), (1.05, 0.45, "out"), (1.6, 0.45),
              (1.75, 0.15, "out"), (2.2, 0.2), (2.35, 0.55, "out"), (4.0, 0.55)]),
    gy=Track([(0, 1.0), (4.0, 1.0)]),
    lid=Track([(0, 0.32), (2.5, 0.32), (2.9, 0.42), (4.0, 0.42)]),
    tilt=Track([(0, 17), (2.4, 18), (2.9, 15.5), (4.0, 16)]),
    nod=Track([(0, 1.0), (4.0, 1.0)]),
    yaw=Track([(0, -0.15), (1.6, 0.1), (2.4, 0.25), (4.0, 0.25)]),
    knit=Track([(0, 0.15), (2.45, 0.15), (2.85, 1.0, "out"), (4.0, 1.0)]),
    lean=Track([(0, 5.0), (1.0, 5.0), (2.3, 8.0), (4.0, 8.0)]),
    hand_x=Track([(0, 610), (0.95, 610), (2.25, 790), (4.0, 792)]),
    hand_y=Track([(0, 1520), (0.95, 1520), (1.6, 1500), (2.25, 1530), (4.0, 1530)]),
    n_wr=Track([(0, -18), (2.25, -14), (2.42, -24, "out"), (2.52, -12), (2.68, -24, "out"), (2.8, -14), (4.0, -14)]),
    f_sh=Track([(0, -26), (4.0, -26)]),
    f_el=Track([(0, -46), (4.0, -46)]),
)


ROOT1, K1 = (450, 1740), 1.8


def pose1(t):
    p = {k: v(t) for k, v in S1.items()}
    tap = 6 * max(0.0, math.sin((t - 2.38) / 0.16 * math.pi)) if 2.38 < t < 2.86 else 0.0
    p["n_sh"], p["n_el"] = ik_arm(ROOT1, K1, p["lean"], (p.pop("hand_x"), p.pop("hand_y") - tap), bend=1)
    p["n_hand"] = "flat" if t < 2.25 else "point"
    p["mouth"] = "tight" if t > 2.7 else "neutral"
    p["blink"] = blink(t, [1.22, 3.55])
    p["breath"] = math.sin(t * 2 * math.pi / 3.4)
    p["tails"] = 0.0
    p["light"] = (1.0, -0.05)
    return p


def room_night(c, t):
    f = flick(t)
    fill(c, rrect(-200, -200, 1300, 2200, 0), (0, 0, 0), shader=lin((0, 0), (0, 1700), (30, 40, 56), (52, 50, 56)))
    for x in range(-40, 1100, 170):                               # wall panels
        r = rrect(x + 14, 300, x + 156, 1300, 10)
        fill(c, r, (38, 48, 62))
        stroke(c, r, (60, 70, 84), 3, 200)
        fill(c, rrect(x + 14, 1300, x + 156, 1316, 4), (26, 32, 44))
    # moonlit window (left)
    win = smooth([(90, 1120), (90, 520), (150, 410), (240, 380), (330, 410), (390, 520), (390, 1120)])
    fill(c, win, (0, 0, 0), shader=lin((240, 380), (240, 1120), (110, 150, 196), (54, 84, 130)))
    glow(c, 300, 520, 140, (210, 226, 255), 120)
    for x in (165, 240, 315):
        stroke(c, poly([(x, 430), (x, 1120)], False), (26, 32, 44), 9)
    for y in (620, 820, 1000):
        stroke(c, poly([(95, y), (385, y)], False), (26, 32, 44), 9)
    stroke(c, win, (24, 30, 40), 16)
    # framed campaign map on the right wall
    fr = rrect(640, 420, 1010, 760, 6)
    fill(c, fr, (92, 62, 40))
    fill(c, rrect(660, 440, 990, 740, 4), (214, 192, 150))
    stroke(c, smooth([(670, 640), (760, 590), (850, 640), (980, 600)], False), (90, 120, 160), 5)
    for (x, y, col) in ((760, 530, (52, 74, 140)), (880, 560, (230, 226, 216)), (820, 690, (52, 74, 140))):
        fill(c, rrect(x, y, x + 44, y + 18, 3), col)
    # candle glow on the wall (flickers)
    glow(c, 860, 1300, 900 * (0.96 + 0.04 * f), (255, 170, 90), int(150 * f))


def table_night(c, t):
    f = flick(t)
    top = poly([(-120, 1420), (1200, 1400), (1200, 2600), (-120, 2600)])
    fill(c, top, (0, 0, 0), shader=lin((0, 1400), (0, 2000), (122, 78, 48), (70, 44, 30)))
    fill(c, poly([(-120, 1400), (1200, 1380), (1200, 1420), (-120, 1440)]), (150, 100, 62))
    mp = poly([(80, 1460), (980, 1440), (1010, 1880), (40, 1900)])
    fill(c, mp, (0, 0, 0), shader=lin((500, 1440), (500, 1900), (236, 216, 172), (204, 178, 132)))
    stroke(c, smooth([(90, 1600), (300, 1560), (480, 1630), (700, 1580), (980, 1650)], False), (84, 120, 168), 9)
    for x, y in ((180, 1720), (260, 1760), (420, 1800)):
        fill(c, smooth([(x - 40, y), (x, y - 36), (x + 40, y)]), (176, 150, 104))
    for x, y in ((520, 1500), (600, 1520), (330, 1680)):
        fill(c, rrect(x, y, x + 54, y + 22, 4), (52, 74, 140))
    for x, y in ((650, 1680), (740, 1650), (700, 1730)):
        fill(c, rrect(x, y, x + 54, y + 22, 4), (236, 232, 222))
        stroke(c, rrect(x, y, x + 54, y + 22, 4), (60, 50, 44), 2)
    stroke(c, smooth([(400, 1700), (520, 1640), (620, 1620)], False), (178, 44, 46), 6)      # the plan
    fill(c, poly([(620, 1608), (652, 1622), (618, 1638)]), (178, 44, 46))
    fill(c, ellipse(160, 1520, 38, 24), (150, 120, 70))                                        # compass
    fill(c, ellipse(160, 1516, 30, 18), (230, 220, 190))
    stroke(c, poly([(146, 1520), (176, 1510)], False), (178, 44, 46), 3)
    # light pool from the candle
    p = skia.Paint(AntiAlias=True)
    p.setShader(radial((860, 1560), 700, (255, 190, 110), (255, 190, 110), int(90 * f), 0))
    p.setBlendMode(skia.BlendMode.kOverlay)
    c.drawRect(skia.Rect.MakeLTRB(-120, 1380, 1200, 2000), p)


def candle(c, x, y, t):
    f = flick(t)
    fill(c, ellipse(x, y + 150, 70, 20), (150, 110, 50))
    fill(c, rrect(x - 22, y, x + 22, y + 150, 8), (0, 0, 0), shader=lin((x - 22, 0), (x + 22, 0), (255, 246, 222), (214, 196, 160)))
    sway = 3 * math.sin(t * 2.7) + 1.5 * math.sin(t * 6.3)
    h = 46 * f
    fl = smooth([(x + sway, y - h), (x + 11 + sway * 0.4, y - h * 0.45), (x + 7, y - 4), (x - 7, y - 4),
                 (x - 11 + sway * 0.4, y - h * 0.45)])
    glow(c, x, y - 20, 160 * f, (255, 180, 80), int(200 * f))
    fill(c, fl, (255, 150, 50))
    fill(c, smooth([(x + sway * 0.8, y - h * 0.8), (x + 6, y - h * 0.35), (x, y - 6), (x - 6, y - h * 0.35)]), (255, 236, 170))
    stroke(c, poly([(x, y - 2), (x, y - 12)], False), (40, 30, 30), 3)


def scene1(c, t):
    room_night(c, t)
    p = pose1(t)
    NAP.draw(c, ROOT1[0], ROOT1[1], K1, p, parts="body")
    table_night(c, t)
    candle(c, 930, 1300, t)
    NAP.draw(c, ROOT1[0], ROOT1[1], K1, p, parts="near_arm")


def cam1(t):
    u = ease((t - 1.7) / 2.1)
    return 1.0 + 0.75 * u, (540 + 120 * u, 1160 - 190 * u)


# ======================================================================= scene 2: the command
S2 = dict(
    gy=Track([(4.0, 0.8), (4.18, 0.8), (4.42, -0.1, "out"), (8.0, -0.05)]),
    gx=Track([(4.0, 0.4), (4.42, 0.55), (5.1, 0.85, "out"), (8.0, 0.85)]),
    lid=Track([(4.0, 0.35), (4.42, 0.0, "out"), (5.2, -0.05), (8.0, 0.05)]),
    tilt=Track([(4.0, 9.0), (4.25, 10.5), (4.8, -4.0, "out"), (5.1, -6.0), (5.5, -3.0), (8.0, -2.5)]),
    nod=Track([(4.0, 0.9), (4.25, 1.0), (4.8, -0.35, "out"), (8.0, -0.3)]),
    yaw=Track([(4.0, 0.2), (4.8, 0.35), (5.3, 0.55), (8.0, 0.5)]),
    knit=Track([(4.0, 0.9), (4.5, 0.6), (5.0, 1.0, "out"), (8.0, 1.0)]),
    raise_=Track([(4.0, 0.0), (4.55, 0.35, "out"), (5.0, 0.0), (8.0, 0.0)]),
    lean=Track([(4.0, 6.0), (4.8, -2.0, "out"), (5.0, -4.0), (5.35, 6.0, "back"), (6.0, 4.5), (8.0, 4.0)]),
    n_sh=Track([(4.0, 8), (4.75, 14), (5.02, 30, "out"), (5.38, -104, "back"), (7.3, -100), (7.9, -84)]),
    n_el=Track([(4.0, -16), (4.75, -24), (5.02, -96, "out"), (5.38, -6, "back"), (8.0, -10)]),
    n_wr=Track([(4.0, 0), (5.02, 10), (5.38, -8, "back"), (8.0, -6)]),
    open=Track([(4.0, 0.0), (5.12, 0.0), (5.3, 0.92, "out"), (5.55, 0.45), (5.72, 0.85), (5.98, 0.25), (6.15, 0.7),
                (6.45, 0.0), (8.0, 0.0)]),
    f_sh=Track([(4.0, 6), (5.2, 14), (8.0, 12)]),
    f_el=Track([(4.0, -14), (5.2, -30), (8.0, -26)]),
)


def pose2(t):
    p = {k: v(t) for k, v in S2.items()}
    p["n_hand"] = "point" if 5.15 < t else "relaxed"
    p["mouth"] = "shout" if 5.1 < t < 6.5 else "tight"
    p["blink"] = blink(t, [4.32, 6.95])
    p["breath"] = math.sin(t * 2 * math.pi / 3.2) + (1.6 if 4.3 < t < 5.1 else 0.0)
    # secondary motion: coat tails and epaulette fringe lag the torso and the arm
    p["tails"] = (spring(lambda s: S2["lean"](s) / 8.0, t, 50, 5, t0=4.0) - S2["lean"](t) / 8.0) * 3.0
    p["fringe"] = (spring(lambda s: S2["n_sh"](s) / 60.0, t, 70, 6, t0=4.0) - S2["n_sh"](t) / 60.0) * 3.0
    p["light"] = (1.0, -0.45)
    return p


def room_dawn(c, t):
    fill(c, rrect(-200, -200, 1300, 2200, 0), (0, 0, 0), shader=lin((0, 0), (0, 1900), (44, 46, 66), (64, 58, 66)))
    # tall window with the pre-dawn sky
    sky = rrect(560, 240, 1080, 1500, 8)
    fill(c, sky, (0, 0, 0), shader=lin((0, 240), (0, 1500), (70, 86, 140), (246, 168, 120)))
    glow(c, 860, 1380, 380, (255, 200, 140), 150)
    for i in range(5):                                            # distant hills through the glass
        xs = [560 + j * 60 for j in range(10)]
        pts = [(x, 1300 - 30 * math.sin(x / 90 + i) - i * 18) for x in xs] + [(1080, 1500), (560, 1500)]
        fill(c, smooth(pts), (90 - i * 8, 84 - i * 8, 110 - i * 6), 120)
    for x in (690, 820, 950):
        stroke(c, poly([(x, 240), (x, 1500)], False), (34, 32, 44), 12)
    for y in (560, 900, 1240):
        stroke(c, poly([(560, y), (1080, y)], False), (34, 32, 44), 12)
    stroke(c, sky, (30, 28, 40), 22)
    # curtains moving in the breeze (animated background element)
    for side, x0 in ((0, 500), (1, 1020)):
        sw = 16 * math.sin(t * 1.6 + side) + 8 * math.sin(t * 3.1 + side)
        pts = [(x0, 200), (x0 + 120, 200), (x0 + 110 + sw * 0.5, 900), (x0 + 130 + sw, 1600), (x0 - 10 + sw, 1600),
               (x0 + 10 + sw * 0.5, 900)]
        fill(c, smooth(pts), (0, 0, 0), shader=lin((x0, 0), (x0 + 130, 0), (120, 36, 40), (170, 56, 54)))
        for k in range(3):
            stroke(c, smooth([(x0 + 30 + k * 30, 220), (x0 + 30 + k * 30 + sw * 0.4, 900), (x0 + 30 + k * 30 + sw, 1580)], False),
                   (96, 26, 32), 4, 160)
    fill(c, rrect(-200, 1500, 1300, 2200, 0), (0, 0, 0), shader=lin((0, 1500), (0, 2000), (70, 52, 44), (40, 30, 28)))


def scene2(c, t):
    room_dawn(c, t)
    candle(c, 150, 1520, t)
    NAP.draw(c, 400, 1860, 2.0, pose2(t))
    # map table edge in the foreground for continuity
    fill(c, poly([(-100, 1840), (700, 1800), (760, 2000), (-100, 2000)]), (0, 0, 0),
         shader=lin((0, 1800), (0, 2000), (122, 78, 48), (60, 38, 26)))


def cam2(t):
    u = ease((t - 4.0) / 4.0)
    return 1.04 + 0.04 * u, (540 + 20 * u, 980 - 20 * u)


# ======================================================================= scene 3: the march
def flag(c, x, y, h, t, seed=0.0):
    fill(c, poly([(x - 3, y), (x + 3, y), (x + 3, y - h * 2.3), (x - 3, y - h * 2.3)]), (90, 66, 44))
    fill(c, ellipse(x, y - h * 2.32, 7, 7), "gold")
    fw, fh = h * 1.3, h * 0.85
    cols = [(42, 64, 150), (240, 236, 228), (196, 50, 52)]
    for b in range(3):
        pts_top, pts_bot = [], []
        for i in range(9):
            u = (b + i / 8) / 3
            wv = (math.sin(u * 6 - t * 6 + seed) * 0.12 + math.sin(u * 2.5 - t * 3.3) * 0.06) * fh * u
            xx = x + u * fw
            pts_top.append((xx, y - h * 2.3 + wv))
            pts_bot.append((xx, y - h * 2.3 + fh + wv))
        shade = 0.82 + 0.18 * math.cos((b + 0.5) / 3 * 6 - t * 6 + seed)
        col = tuple(min(255, int(v * shade)) for v in cols[b])
        fill(c, poly(pts_top + pts_bot[::-1]), col)


def battlefield(c, t, cam_dx):
    fill(c, rrect(-300, -300, 1400, 2200, 0), (0, 0, 0), shader=lin((0, 0), (0, 1150), (70, 96, 138), (246, 196, 156)))
    glow(c, 700 - cam_dx * 0.05, 1010, 420, (255, 220, 170), 210)
    fill(c, ellipse(700 - cam_dx * 0.05, 1010, 70, 70), (255, 240, 210), 230)
    for i, (base, col, par) in enumerate(((1060, (124, 132, 160), 0.1), (1100, (104, 112, 140), 0.2), (1150, (86, 100, 112), 0.35))):
        xs = list(range(-300, 1500, 80))
        pts = [(x - cam_dx * par, base - 40 * math.sin(x / 170 + i * 2) - 22 * math.sin(x / 70 + i)) for x in xs]
        fill(c, smooth(pts + [(1500, 2200), (-300, 2200)]), col)
    fill(c, rrect(-300, 1180, 1500, 2200, 0), (0, 0, 0), shader=lin((0, 1180), (0, 1900), (120, 128, 96), (70, 84, 56)))
    # mist bands drifting
    for k, (y, a, sp) in enumerate(((1190, 120, 18), (1260, 90, 28), (1400, 70, 40))):
        for j in range(6):
            x = ((j * 320 + t * sp + k * 90) % 1900) - 400 - cam_dx * (0.3 + k * 0.2)
            fill(c, ellipse(x, y, 260, 34 + k * 8), (236, 230, 226), a, blur=18)


def troops(c, t, cam_dx):
    rows = [(1215, 0.40, 76, 0.55, 14), (1365, 0.58, 108, 0.8, 11)]
    for r, (y, sc, gap, par, n) in enumerate(rows):
        speed = 62 * sc / 0.58                           # stride-matched speed (design units / s)
        for i in range(n):
            x = -300 + i * gap + t * speed - cam_dx * par + r * 30
            x = ((x + 400) % (n * gap)) - 400
            ph = (t * 1.05 + i * 0.13 + r * 0.31) % 1.0
            soldier.draw(c, x, y, sc, ph, light=(1, -0.6))
            if i in (3, 8) and r == 1 or i == 6 and r == 0:
                flag(c, x - 30 * sc, y - 120 * sc, 120 * sc, t, i)
        # atmospheric haze over the far row
        if r == 0:
            fill(c, rrect(-300, 950, 1500, 1260, 0), (226, 214, 206), 70)


def smoke(c, t, cam_dx):
    for j in range(5):
        x = 60 + j * 230 + 20 * t - cam_dx * 0.6
        y = 1260 - 30 * math.sin(j)
        r = 90 + 30 * math.sin(t * 0.7 + j)
        fill(c, ellipse(x, y, r * 1.6, r * 0.7), (214, 206, 200), 80, blur=24)


def grass(c, t, cam_dx):
    fill(c, smooth([(-300, 1760), (200, 1720), (700, 1750), (1400, 1730), (1400, 2200), (-300, 2200)]), (42, 50, 36))
    for i in range(70):
        x = -200 + i * 22 - cam_dx * 1.2
        h = 40 + 30 * math.sin(i * 1.7)
        sw = 8 * math.sin(t * 2.4 + i * 0.4)
        stroke(c, smooth([(x, 1770), (x + sw * 0.5, 1770 - h * 0.6), (x + sw, 1770 - h)], False), (58, 70, 46), 5)


def pose3(t):
    wind = math.sin(t * 2.3) + 0.5 * math.sin(t * 5.1)
    return dict(gx=Track([(8, 0.6), (9.6, 0.6), (10.2, 0.85), (12, 0.85)])(t), gy=0.15,
                tilt=Track([(8, -2), (10.5, -2.5), (10.85, 4.0, "out"), (11.3, 0.5), (12, 1)])(t), yaw=Track([(8, 0.35), (10.4, 0.6), (12, 0.6)])(t),
                knit=0.55, mouth="tight", lid=0.12, blink=blink(t, [9.3, 11.4]),
                breath=math.sin(t * 2 * math.pi / 3.6), lean=1.5,
                n_sh=14, n_el=-30, n_hand="relaxed", f_sh=10, f_el=-20,
                tails=0.55 * wind, fringe=0.6 * wind, light=(1.0, -0.7))


def scene3(c, t, cam_dx):
    battlefield(c, t, cam_dx)
    troops(c, t, cam_dx)
    smoke(c, t, cam_dx)
    grass(c, t, cam_dx)
    NAP.draw(c, 140 - cam_dx * 1.3, 2230, 2.0, pose3(t))
    # warm rim of dawn light along the foreground and a gentle haze
    fill(c, rrect(-300, -300, 1400, 2200, 0), (255, 214, 170), 22)


def cam3(t):
    u = ease((t - 8.0) / 4.0)
    return 1.0 + 0.04 * u, (540, 1080), 70 * u

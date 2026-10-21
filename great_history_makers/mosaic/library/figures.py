"""Character designs as cut-out rigs (profile view, facing left, 1000 units tall).

Profile figures follow the convention of ancient Near Eastern reliefs and many
mosaic panels: frontal almond eye in a profile head, flat costume areas with
pleat lines that the tessellator turns into rows of tesserae.

Costume sources (artistic reconstruction): Achaemenid reliefs at Persepolis and
the Susa glazed-brick archers (later than Cyrus, c. 500 BCE); Median riding dress
(hood/bashlyk, tunic, trousers); Neo-Babylonian royal stelae and seals for
fringed Babylonian garments.
"""
from ..painter import catmull_rom
from ..scene import Figure, PartSpec


# ----------------------------------------------------------------- shared head parts
def _face(p, skin="skin", beard="hair", beard_len=1.0, curls="hair_lt", ear=True, brow="hair"):
    # neck is drawn by the body; this is the head itself (pivot ~ (0, 200))
    p.smooth([(-18, 38), (-50, 66), (-57, 96), (-52, 106), (-71, 128), (-56, 136), (-57, 148),
              (-50, 168), (8, 182), (36, 150), (40, 92), (22, 44)], skin)
    # beard (long, squared Persian / Babylonian style with rows of curls)
    if beard_len > 0:
        bot = 170 + 115 * beard_len
        pts = [(-56, 141), (-66, 156), (-64, 190), (-60, bot - 30), (-50, bot), (4, bot + 4),
               (16, bot - 40), (20, 190), (24, 150), (6, 136), (-28, 141)]
        p.smooth(pts, beard, samples=6)
        y = 172
        while y < bot - 8:
            for x in range(-52, 14, 14):
                p.circle(x + (7 if (y // 22) % 2 else 0), y, 5, curls)
            y += 22
        p.smooth([(-60, 141), (-40, 136), (-22, 146), (-44, 152)], beard, samples=4)  # moustache
    # eye: ancient frontal eye in profile
    p.smooth([(-50, 103), (-38, 96), (-25, 102), (-38, 108)], "ivory", samples=6)
    p.circle(-40, 102, 5, "black")
    p.curve([(-55, 90), (-40, 86), (-22, 90)], brow, 5)
    p.curve([(-71, 128), (-60, 131), (-56, 136)], "skin_sh", 3)
    if ear:
        p.ellipse(10, 118, 9, 15, "skin_sh")


def _hair_back(p, color="hair", curls="hair_lt", length=1.0):
    # bunched Persian hair at the nape
    p.ellipse(30, 120 + 40 * length, 34, 42 + 10 * length, color)
    for (x, y) in [(22, 140), (40, 150), (24, 170), (42, 178), (30, 196)]:
        if y < 150 + 60 * length:
            p.circle(x, y, 6, curls)


def _crown(p):
    # crenellated royal crown (reconstruction based on Achaemenid royal imagery)
    pts = [(-54, 62), (-56, -6), (-40, -6), (-40, -22), (-22, -22), (-22, -6), (-4, -6), (-4, -22),
           (14, -22), (14, -6), (30, -6), (30, -22), (46, -22), (46, 62)]
    p.poly(pts, "gold")
    p.rect(-56, 28, 102, 14, "lapis")
    for x in range(-46, 44, 18):
        p.circle(x, 35, 4, "gold_lt")
    p.rect(-56, 56, 102, 8, "gold_lt")


def _fluted_hat(p, color="sand", flute="sand_dk"):
    p.smooth([(-52, 66), (-48, 10), (-30, -10), (20, -14), (40, 4), (46, 66)], color, 6)
    for x in range(-34, 40, 16):
        p.line([(x, 4), (x + 1, 56)], flute, 3)
    p.rect(-54, 52, 100, 12, "ochre_dk")


def _hood_back(p, color="ochre"):
    # Median felt hood (bashlyk): the back and neck flap sit behind the face
    p.smooth([(-40, 60), (-10, 0), (40, 18), (60, 90), (60, 190), (34, 226), (-10, 230), (-20, 170),
              (10, 120)], color)


def _hood(p, color="ochre", shade="ochre_dk"):
    p.smooth([(-52, 74), (-48, 30), (-10, 0), (40, 18), (50, 70), (20, 70), (-10, 78)], color)
    p.curve([(-44, 62), (-10, 40), (30, 46)], shade, 6)


def _veil(p, color="bone", edge="terracotta"):
    p.smooth([(-52, 76), (-44, 30), (-8, 6), (38, 20), (70, 120), (86, 280), (40, 300), (20, 200),
              (24, 130), (-10, 80)], color)
    p.curve([(-50, 74), (-40, 34), (-8, 10), (36, 22)], edge, 8)


# ----------------------------------------------------------------- Persian robe body
def _persian_robe(p, robe, pleat, trim, front_panel=None, neck_skin="skin", belt="gold"):
    p.rect(-24, 150, 46, 110, neck_skin)  # neck (hidden seam under the rotating head)
    body = [(-48, 244), (-72, 320), (-66, 470), (-82, 640), (-110, 985), (98, 990), (80, 640),
            (62, 470), (66, 300), (48, 244)]
    p.smooth(body, robe, samples=6)
    if front_panel:
        p.poly([(-64, 490), (-48, 490), (-90, 985), (-110, 985)], front_panel)
    for i, x in enumerate([-70, -42, -14, 14, 42, 66]):
        p.line([(x * 0.55, 500), (x * 1.25, 980)], pleat, 7)
    # diagonal Persepolis-style folds across the skirt front
    for y in (560, 640, 720):
        p.line([(-74, y), (-20, y + 60)], pleat, 6)
    p.rect(-68, 466, 132, 20, belt)
    p.poly([(-112, 958), (100, 962), (98, 990), (-110, 985)], trim)
    p.ellipse(-118, 990, 30, 12, "umber")  # shoe tip


def _sleeve_arm(p, robe, pleat, skin="skin", hand_pose="rest"):
    # upper arm + forearm inside a wide Persian sleeve; hand at the wrist
    p.smooth([(-34, 252), (26, 250), (30, 420), (-6, 470), (-84, 488), (-90, 456), (-22, 420)], robe, 6)
    p.smooth([(-74, 470), (-6, 466), (36, 470), (40, 620), (-6, 650), (-52, 560)], robe, 6)
    p.line([(-40, 500), (-20, 610)], pleat, 6)
    p.line([(0, 490), (14, 630)], pleat, 6)


def _hand(p, x=-98, y=470, skin="skin", holding=False):
    p.ellipse(x, y, 20, 15, skin)
    p.ellipse(x - 14, y - 4, 10, 8, skin)  # thumb
    if holding:
        p.rect(x - 22, y - 10, 30, 6, "skin_sh")


# ----------------------------------------------------------------- designs
def cyrus(ctx, k, tile=6.0, haze=None, haze_amt=0.0):
    """Cyrus II ('the Great'). No contemporary portrait survives; costume and crown are a
    reconstruction built from later Achaemenid royal imagery."""
    robe, pleat = "purple", "purple_dk"

    def cloak(p):
        pts = [(16, 238), (70, 244), (118, 400), (150, 690), (176, 960), (54, 980), (30, 700), (14, 400)]
        p.smooth(pts, "gold", samples=8)
        inner = [(26, 252), (64, 258), (106, 404), (136, 690), (158, 946), (64, 962), (42, 700), (26, 404)]
        p.smooth(inner, "crimson", samples=8)
        for x0 in (70, 100, 124):
            p.line([(x0 - 30, 420), (x0, 930)], "crimson_dk", 7)

    def body(p):
        _persian_robe(p, robe, pleat, "gold", front_panel="ivory")

    def staff(p):
        p.line([(-150, 150), (-150, 990)], "gold", 13)
        p.circle(-150, 140, 18, "gold_lt")
        p.ellipse(-138, 420, 20, 16, "skin")  # far hand

    def arm(p):
        _sleeve_arm(p, robe, pleat)

    def hand(p):
        _hand(p)

    def head(p):
        _hair_back(p)
        _face(p, beard_len=1.05)
        _crown(p)

    parts = [
        PartSpec("cloak", cloak, pivot=(40, 250), parent="body", z=0,
                 deform=dict(amp=9, wl=420, speed=0.45, axis="y", anchor=0.0, power=1.3)),
        PartSpec("staff", staff, pivot=(-140, 420), parent="body", z=1),
        PartSpec("body", body, pivot=(0, 990), z=2),
        PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.62),
        PartSpec("arm", arm, pivot=(-4, 262), parent="body", z=4),
        PartSpec("hand", hand, pivot=(-84, 472), parent="arm", z=5, tile_mul=0.7),
    ]
    return Figure(ctx, "cyrus", parts, k, tile, haze, haze_amt)


def persian_guard(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0, spear=True):
    """Persian guardsman: robe, fluted headdress, spear with pomegranate butt and a quiver
    (after the Susa archer friezes)."""
    robes = [("ochre", "ochre_dk", "terracotta"), ("terracotta", "terracotta_dk", "gold"),
             ("sand", "sand_dk", "lapis")]
    robe, pleat, trim = robes[variant % len(robes)]

    def quiver(p):
        p.poly([(40, 250), (84, 236), (118, 600), (76, 616)], "umber")
        p.poly([(44, 260), (82, 248), (90, 330), (52, 342)], trim)

    def body(p):
        _persian_robe(p, robe, pleat, trim, belt="umber")
        for y in range(330, 940, 70):
            for x in range(-50, 60, 34):
                p.circle(x + (17 if (y // 70) % 2 else 0), y, 6, trim)

    def spear_(p):
        p.line([(-112, -120), (-112, 990)], "umber", 10)
        p.poly([(-112, -190), (-124, -130), (-112, -110), (-100, -130)], "stone")
        p.circle(-112, 990, 17, "gold")

    def arm(p):
        _sleeve_arm(p, robe, pleat)

    def hand(p):
        _hand(p, x=-104, y=470, holding=True)

    def head(p):
        _hair_back(p)
        _face(p, beard_len=0.65)
        _fluted_hat(p)

    parts = [
        PartSpec("quiver", quiver, pivot=(60, 260), parent="body", z=0),
        PartSpec("body", body, pivot=(0, 990), z=1),
        PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.62),
        PartSpec("arm", arm, pivot=(-4, 262), parent="body", z=4),
        PartSpec("hand", hand, pivot=(-90, 472), parent="arm", z=6, tile_mul=0.7),
    ]
    if spear:
        parts.append(PartSpec("spear", spear_, pivot=(-112, 470), parent="arm", z=5))
    return Figure(ctx, f"guard{variant}", parts, k, tile, haze, haze_amt)


def persian_soldier(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0, standard=False, shield=True):
    """Marching soldier in Median riding dress (hood, belted tunic, trousers).

    Rig: thigh/shin per leg (walk cycle), swinging spear arm with a spear that sways
    on its own pivot, a wicker shield (spara, after Achaemenid reliefs and Herodotus
    7.61) slung on the far side, and for standard bearers a golden-eagle standard
    (Xenophon) with a cloth banner animated tile-by-tile."""
    tunics = [("terracotta", "terracotta_dk", "lapis", "ochre"),
              ("ochre", "ochre_dk", "terracotta", "sand"),
              ("lapis", "lapis_dk", "sand", "ochre"),
              ("green", "green_dk", "ochre", "sand")]
    tun, tun_dk, trous, hood = tunics[variant % len(tunics)]

    def leg(shade):
        def thigh(p):
            p.smooth([(-34, 560), (34, 560), (30, 790), (-26, 790)], shade, 4)

        def shin(p):
            p.smooth([(-26, 770), (28, 770), (24, 960), (-22, 960)], shade, 4)
            p.poly([(-70, 990), (-60, 950), (26, 950), (28, 1000), (-70, 1000)], "umber")
        return thigh, shin

    def body(p):
        p.rect(-24, 150, 46, 110, "skin")
        p.smooth([(-48, 244), (-70, 320), (-62, 470), (-84, 760), (80, 760), (60, 470), (64, 300),
                  (48, 244)], tun, 6)
        p.rect(-66, 462, 128, 18, "umber")
        p.poly([(-86, 740), (82, 740), (80, 762), (-84, 762)], hood)
        for x in (-50, -10, 30):
            p.line([(x * 0.7, 490), (x * 1.3, 744)], tun_dk, 6)
        p.poly([(44, 270), (86, 256), (112, 560), (72, 572)], "umber")  # quiver / bow case

    def shield_(p):
        # spara: tall wicker shield with leather rim, carried on the far side
        p.smooth([(-20, 300), (150, 290), (166, 520), (150, 780), (-10, 790), (-24, 540)], "umber", 6)
        p.smooth([(-6, 314), (138, 306), (150, 520), (136, 764), (4, 772), (-10, 540)], "ochre", 6)
        for y in range(330, 770, 34):
            p.line([(0, y), (144, y - 4)], "ochre_dk", 6)
        for x in range(20, 140, 30):
            p.line([(x, 320), (x + 2, 760)], "sand", 3)

    def arm(p):
        p.smooth([(-30, 252), (26, 252), (24, 430), (-10, 470), (-70, 486), (-74, 452), (-18, 420)], tun, 6)
        p.line([(-6, 300), (-4, 420)], tun_dk, 6)

    def hand(p):
        _hand(p, x=-86, y=468, holding=True)

    def spear_(p):
        if standard:
            # Achaemenid royal standard: golden eagle with spread wings on a lance
            p.line([(-100, -400), (-100, 990)], "umber", 10)
            p.poly([(-100, -470), (-200, -520), (-160, -440), (-112, -420), (-88, -420), (-40, -440),
                    (0, -520)], "gold")
            p.circle(-100, -480, 20, "gold_lt")
            p.poly([(-112, -410), (-100, -380), (-88, -410)], "gold")
        else:
            p.line([(-100, -150), (-100, 990)], "umber", 10)
            p.poly([(-100, -220), (-112, -160), (-100, -140), (-88, -160)], "stone")
            p.circle(-100, 990, 15, "gold")

    def head(p):
        _hood_back(p, hood)
        _face(p, beard="umber", curls="hair_lt", beard_len=0.55, ear=False)
        _hood(p, hood, "umber")

    tf, sf = leg(trous)
    tb, sb = leg(mix_dark(trous))
    parts = [
        PartSpec("thigh_b", tb, pivot=(0, 575), parent="body", z=0, variation=0.05),
        PartSpec("shin_b", sb, pivot=(0, 780), parent="thigh_b", z=0),
        PartSpec("body", body, pivot=(0, 600), z=2),
        PartSpec("thigh_f", tf, pivot=(0, 575), parent="body", z=1.5),
        PartSpec("shin_f", sf, pivot=(0, 780), parent="thigh_f", z=1.5),
        PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.62),
        PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=5),
        PartSpec("spear", spear_, pivot=(-100, 470), parent="arm", z=4),
        PartSpec("hand", hand, pivot=(-74, 470), parent="arm", z=6, tile_mul=0.7),
    ]
    if shield and not standard:
        parts.append(PartSpec("shield", shield_, pivot=(70, 300), parent="body", z=1))
    if standard:
        def banner(p):
            p.poly([(-96, -390), (190, -378), (210, -150), (-96, -160)], "crimson")
            p.poly([(-96, -390), (190, -378), (192, -352), (-96, -362)], "gold")
            p.poly([(-96, -186), (206, -176), (210, -150), (-96, -160)], "gold")
            p.circle(50, -270, 34, "gold")
            p.circle(50, -270, 16, "crimson_dk")
            for x in range(-80, 200, 28):  # fringe
                p.line([(x, -152), (x + 2, -126)], "gold", 6)
        parts.append(PartSpec("banner", banner, pivot=(-100, -270), parent="spear", z=4,
                              deform=dict(amp=22, wl=230, speed=0.85, axis="x", anchor=0.0, power=1.1)))
    return Figure(ctx, f"soldier{variant}{'s' if standard else ''}{'' if shield else 'n'}", parts, k, tile,
                  haze, haze_amt)


def mix_dark(name):
    """Far-side limbs are drawn one shade darker so the two legs read separately."""
    return {"lapis": "lapis_dk", "terracotta": "terracotta_dk", "sand": "sand_dk", "ochre": "ochre_dk"}.get(name, name)


def babylonian_official(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0):
    """Babylonian dignitary in a long fringed wrap-around garment (Neo-Babylonian dress)."""
    looks = [("ivory", "lapis", "bone", "cap"), ("bone", "crimson", "sand", "band"),
             ("sand", "turquoise", "sand_dk", "cap"), ("ivory", "terracotta", "bone", "band")]
    robe, fringe, robe_dk, hat = looks[variant % len(looks)]

    def body(p):
        p.rect(-24, 150, 46, 110, "skin")
        p.smooth([(-46, 244), (-66, 330), (-60, 480), (-80, 985), (84, 990), (70, 480), (64, 300), (46, 244)],
                 robe, 6)
        # diagonal fringed shawl, a hallmark of Mesopotamian dress
        p.poly([(-62, 380), (66, 300), (70, 360), (-60, 450)], fringe)
        p.poly([(-78, 900), (82, 860), (84, 900), (-80, 940)], fringe)
        for x in range(-76, 84, 12):
            p.line([(x, 938 - (x + 78) * 0.25), (x, 984)], robe_dk, 5)
        for y in (520, 640, 760):
            p.line([(-40, y), (60, y - 30)], robe_dk, 5)

    def arms(p):
        # hands clasped at the waist (a common Mesopotamian posture of attendance)
        p.smooth([(-30, 252), (26, 252), (30, 420), (-40, 470), (-74, 470), (-70, 440), (-10, 410)], robe, 6)
        p.line([(-60, 455), (-12, 420)], robe_dk, 5)
        p.ellipse(-80, 456, 18, 15, "skin")

    def head(p):
        _hair_back(p, length=1.6)
        _face(p, beard_len=0.95, beard="hair" if variant != 2 else "grey_hair",
              curls="hair_lt" if variant != 2 else "stone")
        if hat == "cap":
            p.smooth([(-52, 70), (-48, 0), (0, -24), (42, 4), (44, 70)], fringe, 6)
            p.rect(-54, 56, 100, 14, "gold")
        else:
            p.smooth([(-50, 70), (-36, 26), (10, 18), (42, 50), (44, 80)], "hair", 6)
            p.rect(-54, 54, 100, 14, fringe)

    parts = [
        PartSpec("body", body, pivot=(0, 990), z=1),
        PartSpec("head", head, pivot=(0, 210), parent="body", z=2, tile_mul=0.62),
        PartSpec("arm", arms, pivot=(-2, 262), parent="body", z=3),
    ]
    return Figure(ctx, f"babofficial{variant}", parts, k, tile, haze, haze_amt)


def babylonian_citizen(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0):
    """Townspeople: men in tunic and shawl, women in long dress with head shawl."""
    looks = [("m", "sand", "terracotta"), ("f", "terracotta", "bone"), ("m", "bone", "lapis"),
             ("f", "lapis", "sand"), ("m", "ochre", "umber"), ("f", "olive", "ivory")]
    sex, robe, acc = looks[variant % len(looks)]
    dk = {"sand": "sand_dk", "terracotta": "terracotta_dk", "bone": "sand", "lapis": "lapis_dk",
          "ochre": "ochre_dk", "olive": "green_dk"}[robe]

    def body(p):
        p.rect(-22, 150, 42, 110, "skin")
        hem = 985 if sex == "f" else 820
        p.smooth([(-44, 244), (-62, 330), (-56, 480), (-74, hem), (76, hem), (64, 480), (60, 300), (44, 244)],
                 robe, 6)
        if sex == "m":
            p.rect(-20, 800, 24, 170, "skin")
            p.ellipse(-26, 985, 26, 12, "umber")
            p.poly([(-60, 340), (62, 290), (64, 330), (-58, 390)], acc)
        else:
            p.poly([(-70, 900), (72, 900), (74, 930), (-72, 930)], acc)
        p.line([(-10, 500), (-30, hem - 10)], dk, 5)
        p.line([(30, 500), (40, hem - 10)], dk, 5)

    def arm(p):
        p.smooth([(-28, 252), (24, 252), (26, 430), (-40, 476), (-64, 470), (-58, 440), (-8, 410)], robe, 6)
        p.ellipse(-70, 460, 16, 14, "skin")

    def head(p):
        if sex == "f":
            _face(p, beard_len=0, ear=False)
            _veil(p, acc if acc != "lapis" else "bone", "terracotta")
        else:
            _hair_back(p, length=1.2)
            _face(p, beard_len=0.6)
            p.smooth([(-50, 72), (-34, 28), (12, 20), (42, 52), (44, 84)], "hair", 6)
            p.rect(-52, 58, 96, 12, acc)

    parts = [
        PartSpec("body", body, pivot=(0, 990), z=1),
        PartSpec("head", head, pivot=(0, 210), parent="body", z=2, tile_mul=0.65),
        PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=3),
    ]
    return Figure(ctx, f"babcitizen{variant}", parts, k, tile, haze, haze_amt)


def mini_person(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0):
    """Very small distant figure for crowds: body + bobbing head (few tiles each)."""
    cols = ["terracotta", "bone", "lapis", "ochre", "sand", "olive", "crimson", "ivory"]
    col = cols[variant % len(cols)]

    def body(p):
        p.smooth([(-60, 260), (60, 260), (90, 990), (-90, 990)], col, 4)

    def head(p):
        p.circle(0, 160, 80, "skin" if variant % 3 else "skin_dk")
        p.ellipse(10, 120, 84, 60, "hair", 180, 360)

    parts = [PartSpec("body", body, pivot=(0, 990), z=0),
             PartSpec("head", head, pivot=(0, 240), parent="body", z=1)]
    return Figure(ctx, f"mini{variant}", parts, k, tile, haze, haze_amt)


# ======================================================================= V2 additions
def _legs(shade, shade_far=None, shoe="umber", hip=575, knee=780):
    """Thigh/shin part pairs for any walking figure (same proportions as the soldier)."""
    def thigh(col):
        def f(p):
            p.smooth([(-32, hip - 15), (32, hip - 15), (28, knee + 10), (-24, knee + 10)], col, 4)
        return f

    def shin(col):
        def f(p):
            p.smooth([(-24, knee - 10), (26, knee - 10), (22, 960), (-20, 960)], col, 4)
            p.poly([(-66, 990), (-56, 952), (24, 952), (26, 1000), (-66, 1000)], shoe)
        return f
    far = shade_far or mix_dark(shade)
    return [PartSpec("thigh_b", thigh(far), pivot=(0, hip), parent="body", z=0),
            PartSpec("shin_b", shin(far), pivot=(0, knee), parent="thigh_b", z=0),
            PartSpec("thigh_f", thigh(shade), pivot=(0, hip), parent="body", z=1.5),
            PartSpec("shin_f", shin(shade), pivot=(0, knee), parent="thigh_f", z=1.5)]


def townsman(ctx, k, tile=6.0, variant=0, tool=None, haze=None, haze_amt=0.0):
    """Babylonian man in a knee-length tunic with real legs (walks) and a working arm.

    tool: None | 'hammer' | 'brick' | 'basket' (carried on the head) | 'stylus' (scribe
    with a clay tablet) | 'bundle' (returning traveller)."""
    looks = [("sand", "terracotta", "skin"), ("bone", "lapis", "skin_dk"), ("ochre", "umber", "skin"),
             ("terracotta", "sand", "skin_dk"), ("olive", "bone", "skin")]
    robe, acc, skin = looks[variant % len(looks)]
    dk = {"sand": "sand_dk", "bone": "sand", "ochre": "ochre_dk", "terracotta": "terracotta_dk",
          "olive": "green_dk"}[robe]

    def body(p):
        p.rect(-22, 150, 42, 110, skin)
        p.smooth([(-44, 244), (-62, 330), (-56, 480), (-70, 790), (72, 790), (64, 480), (60, 300), (44, 244)],
                 robe, 6)
        p.poly([(-60, 340), (62, 290), (64, 330), (-58, 390)], acc)
        p.rect(-60, 470, 122, 16, acc)
        p.line([(-10, 500), (-30, 780)], dk, 5)
        p.line([(30, 500), (40, 780)], dk, 5)
        if tool == "bundle":
            p.smooth([(30, 260), (130, 250), (150, 420), (40, 440)], "bone", 5)
            p.line([(40, 300), (140, 300)], "umber", 6)

    def arm(p):
        # bare forearm: sleeve to the elbow, then skin, hand at (-92, 470)
        p.smooth([(-26, 252), (24, 252), (22, 400), (-12, 410), (-18, 330)], robe, 5)
        p.smooth([(-14, 380), (16, 392), (-70, 486), (-90, 462)], skin, 5)
        p.ellipse(-94, 468, 18, 15, skin)
        if tool == "hammer":
            p.line([(-94, 468), (-150, 360)], "umber", 9)
            p.rect(-178, 330, 56, 34, "stone_dk")
        elif tool == "brick":
            p.rect(-150, 430, 80, 40, "brick")
            p.line([(-150, 450), (-70, 450)], "terracotta_dk", 3)
        elif tool == "stylus":
            p.line([(-96, 470), (-140, 420)], "bone", 6)

    def tablet(p):
        p.smooth([(-150, 400), (-60, 396), (-56, 520), (-150, 524)], "sand", 4)
        for y in range(414, 512, 16):
            for x in range(-142, -66, 12):
                p.poly([(x, y), (x + 8, y + 3), (x, y + 6)], "sand_dk")

    def head(p):
        _hair_back(p, length=1.2)
        _face(p, beard_len=0.6, skin=skin)
        p.smooth([(-50, 72), (-34, 28), (12, 20), (42, 52), (44, 84)], "hair", 6)
        p.rect(-52, 58, 96, 12, acc)
        if tool == "basket":
            p.ellipse(-4, 6, 92, 30, "ochre_dk")
            p.ellipse(-4, -14, 84, 34, "ochre")
            for x in range(-70, 70, 22):
                p.line([(x, -40), (x + 6, 20)], "ochre_dk", 4)

    parts = [PartSpec("body", body, pivot=(0, 600), z=2),
             PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.65),
             PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=5)] + _legs(robe if robe != "bone" else "sand",
                                                                                 shoe="umber")
    for prt in parts:
        if prt.name.startswith(("thigh", "shin")):
            prt.draw = (lambda f, s=skin: (lambda p: _skin_leg(p, f, s)))(prt.draw)
    if tool == "stylus":
        parts.append(PartSpec("tablet", tablet, pivot=(-100, 460), parent="body", z=4, tile_mul=0.6))
    return Figure(ctx, f"townsman{variant}{tool or ''}", parts, k, tile, haze, haze_amt)


def _skin_leg(p, f, skin):
    """Bare legs below the tunic: recolour by drawing the leg shape in skin tone."""
    from ..painter import Painter  # noqa: F401 (documentation of intent)
    f.__call__(_Recolor(p, skin))


class _Recolor:
    """Painter proxy that paints every primitive in one colour except 'umber' shoes."""

    def __init__(self, p, col):
        self.p, self.col = p, col

    def __getattr__(self, name):
        fn = getattr(self.p, name)

        def wrap(*a, **kw):
            a = list(a)
            for i, v in enumerate(a):
                if isinstance(v, str) and v != "umber":
                    a[i] = self.col
            return fn(*a, **kw)
        return wrap


def babylonian_guard(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0):
    """Babylonian wall guard: conical helmet, scale-pattern tunic, round shield, spear."""
    tun = ["terracotta", "sand", "ochre"][variant % 3]

    def body(p):
        p.rect(-22, 150, 44, 110, "skin")
        p.smooth([(-46, 244), (-64, 330), (-58, 480), (-74, 820), (76, 820), (64, 480), (60, 300), (46, 244)], tun, 6)
        for y in range(280, 800, 28):
            for x in range(-52, 60, 26):
                p.ellipse(x + (13 if (y // 28) % 2 else 0), y, 10, 7, mix_dark(tun) if tun != "sand" else "sand_dk")
        p.rect(-60, 470, 124, 18, "umber")
        p.circle(70, 470, 120, "umber")
        p.circle(70, 470, 104, "lapis_dk" if variant % 2 else "brick")
        p.circle(70, 470, 30, "gold")
        p.rect(-22, 820, 22, 150, "skin")
        p.ellipse(-30, 985, 28, 12, "umber")

    def arm(p):
        p.smooth([(-28, 252), (24, 252), (22, 420), (-10, 460), (-74, 482), (-78, 450), (-18, 412)], tun, 6)
        p.ellipse(-88, 466, 18, 15, "skin")

    def spear(p):
        p.line([(-90, -180), (-90, 990)], "umber", 10)
        p.poly([(-90, -250), (-102, -190), (-90, -170), (-78, -190)], "stone")

    def head(p):
        _hair_back(p, length=1.0)
        _face(p, beard_len=0.8)
        p.poly([(-54, 74), (-40, 20), (-6, -60), (30, 20), (46, 74)], "stone")
        p.rect(-56, 62, 104, 14, "gold")

    parts = [PartSpec("body", body, pivot=(0, 990), z=1),
             PartSpec("head", head, pivot=(0, 210), parent="body", z=3, tile_mul=0.62),
             PartSpec("arm", arm, pivot=(-2, 262), parent="body", z=5),
             PartSpec("spear", spear, pivot=(-90, 466), parent="arm", z=4)]
    return Figure(ctx, f"babguard{variant}", parts, k, tile, haze, haze_amt)


def horse(ctx, k, tile=6.0, variant=0, rider=True, pack=False, haze=None, haze_amt=0.0):
    """Horse (or pack donkey) in profile facing left, with four swinging legs, a neck
    that nods, a swishing tail and an optional Persian rider with a spear."""
    coat, mane = [("umber", "black"), ("sand_dk", "umber"), ("bone", "stone_dk"), ("brick", "black")][variant % 4]
    if pack:
        coat, mane = "stone", "stone_dk"

    def leg(x, top, col):
        def f(p):
            p.smooth([(x - 26, top), (x + 26, top), (x + 16, 900), (x - 14, 900)], col, 4)
            p.poly([(x - 20, 900), (x + 18, 900), (x + 22, 1000), (x - 26, 1000)], "black")
        return f

    def body(p):
        p.smooth([(-300, 520), (-200, 470), (100, 470), (280, 500), (320, 580), (260, 660), (-220, 670), (-310, 610)],
                 coat, 8)
        if pack:
            p.smooth([(-140, 420), (60, 420), (80, 600), (-160, 600)], "ochre", 5)
            for x in range(-140, 70, 30):
                p.line([(x, 430), (x + 6, 590)], "ochre_dk", 4)
            p.line([(-150, 470), (70, 470)], "umber", 6)
        elif rider:
            p.poly([(-140, 470), (100, 470), (90, 540), (-130, 540)], "crimson")
            p.poly([(-140, 530), (100, 530), (96, 548), (-136, 548)], "gold")

    def neck(p):
        if pack:  # donkey: shorter neck, long ears
            p.smooth([(-250, 560), (-330, 440), (-420, 430), (-450, 480), (-360, 540), (-280, 620)], coat, 6)
            p.poly([(-350, 440), (-340, 330), (-320, 440)], coat)
            p.poly([(-330, 440), (-300, 336), (-300, 446)], coat)
        else:
            p.smooth([(-230, 560), (-320, 380), (-390, 300), (-470, 320), (-480, 370), (-400, 420), (-300, 620)],
                     coat, 6)
            p.smooth([(-300, 380), (-250, 470), (-210, 520), (-260, 420), (-330, 330)], mane, 4)
            p.poly([(-380, 310), (-370, 260), (-350, 305)], coat)
        p.circle(-420 if not pack else -400, 350 if not pack else 470, 8, "black")

    def tail(p):
        p.smooth([(290, 530), (360, 560), (390, 700), (360, 820), (330, 700), (300, 600)], mane, 6)

    parts = [
        PartSpec("leg_hb", leg(200, 600, mix_dark(coat) if coat in ("sand", "ochre", "lapis") else coat), pivot=(200, 620), parent="body", z=0),
        PartSpec("leg_fb", leg(-200, 600, coat), pivot=(-200, 620), parent="body", z=0),
        PartSpec("tail", tail, pivot=(295, 540), parent="body", z=0.5,
                 deform=dict(amp=14, wl=300, speed=0.9, axis="y", anchor=0.0, power=1.2)),
        PartSpec("body", body, pivot=(0, 600), z=1),
        PartSpec("neck", neck, pivot=(-240, 560), parent="body", z=2),
        PartSpec("leg_hf", leg(250, 610, coat), pivot=(250, 630), parent="body", z=3),
        PartSpec("leg_ff", leg(-250, 610, coat), pivot=(-250, 630), parent="body", z=3),
    ]
    if rider and not pack:
        def r_body(p):
            p.smooth([(-50, 220), (50, 220), (60, 470), (-60, 470)], "terracotta" if variant % 2 else "lapis", 5)
            p.smooth([(-40, 440), (40, 440), (30, 650), (-30, 650)], "ochre", 4)  # leg along the flank
            p.poly([(-60, 640), (30, 640), (32, 670), (-70, 670)], "umber")

        def r_head(p):
            p.push()
            p.translate(0, 30)
            p.scale(0.8)
            _hood_back(p, "sand")
            _face(p, beard="umber", curls="hair_lt", beard_len=0.5, ear=False)
            _hood(p, "sand", "umber")
            p.pop()

        def r_arm(p):
            p.smooth([(-30, 240), (24, 240), (10, 360), (-90, 360), (-90, 330), (-10, 320)], "terracotta" if variant % 2 else "lapis", 5)
            p.ellipse(-100, 345, 16, 14, "skin")
            p.line([(-300, 250), (200, 420)], "umber", 9)
            p.poly([(-300, 250), (-350, 228), (-296, 238)], "stone")
        parts += [PartSpec("rider", r_body, pivot=(0, 470), parent="body", z=2.5),
                  PartSpec("rhead", r_head, pivot=(0, 230), parent="rider", z=2.7, tile_mul=0.62),
                  PartSpec("rarm", r_arm, pivot=(0, 250), parent="rider", z=2.8)]
    return Figure(ctx, f"horse{variant}{'p' if pack else ''}{'r' if rider else ''}", parts, k, tile, haze, haze_amt)


def banner_pole(ctx, k, tile=6.0, variant=0, haze=None, haze_amt=0.0):
    """Free-standing camp standard: pole, golden eagle finial and a waving cloth."""
    col = ["crimson", "lapis", "terracotta"][variant % 3]

    def pole(p):
        p.line([(0, 0), (0, 1000)], "umber", 12)
        p.poly([(0, -60), (-90, -100), (-60, -30), (-12, -12), (12, -12), (60, -30), (90, -100)], "gold")
        p.circle(0, -70, 18, "gold_lt")

    def cloth(p):
        p.poly([(4, 40), (300, 50), (320, 250), (4, 240)], col)
        p.poly([(4, 40), (300, 50), (302, 74), (4, 64)], "gold")
        p.circle(150, 150, 36, "gold")
        for x in range(16, 320, 26):
            p.line([(x, 240), (x + 2, 270)], "gold", 6)

    parts = [PartSpec("pole", pole, pivot=(0, 1000), z=0),
             PartSpec("banner", cloth, pivot=(0, 140), parent="pole", z=1,
                      deform=dict(amp=24, wl=240, speed=0.8, axis="x", anchor=0.0, power=1.1))]
    return Figure(ctx, f"bannerpole{variant}", parts, k, tile, haze, haze_amt)

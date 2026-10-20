"""Tesserae palette: the limited stone/glass colours every asset draws from.

Keeping all artwork on one curated palette is what keeps scenes and episodes
visually consistent. Values are sRGB tuples.
"""

P = {
    # stones
    "ivory": (236, 224, 196),
    "bone": (222, 207, 175),
    "sand": (214, 186, 140),
    "sand_dk": (186, 154, 108),
    "ochre": (196, 146, 72),
    "ochre_dk": (160, 112, 52),
    "terracotta": (172, 86, 54),
    "terracotta_dk": (128, 58, 40),
    "brick": (150, 96, 66),
    "umber": (98, 68, 48),
    "outline": (54, 40, 33),
    "black": (34, 28, 25),
    "stone": (156, 146, 130),
    "stone_dk": (112, 104, 94),
    # glass / precious
    "gold": (200, 160, 76),
    "gold_lt": (226, 196, 116),
    "lapis": (46, 78, 140),
    "lapis_dk": (30, 50, 98),
    "blue_deep": (36, 54, 96),
    "blue_mid": (78, 112, 158),
    "blue_pale": (156, 176, 186),
    "sky_pale": (206, 206, 190),
    "turquoise": (74, 130, 136),
    "white": (242, 238, 226),
    "purple": (98, 50, 82),
    "purple_dk": (70, 34, 60),
    "crimson": (148, 44, 42),
    "crimson_dk": (104, 30, 32),
    "green": (92, 112, 74),
    "green_dk": (62, 80, 54),
    "olive": (128, 124, 74),
    # skin / hair
    "skin": (198, 142, 100),
    "skin_sh": (162, 108, 74),
    "skin_dk": (146, 98, 68),
    "hair": (48, 36, 30),
    "hair_lt": (74, 56, 44),
    "grey_hair": (150, 142, 132),
    # sunset
    "sun": (238, 196, 112),
    "sun_hot": (246, 222, 160),
    "dusk_orange": (214, 128, 70),
    "dusk_rose": (178, 98, 84),
    "dusk_violet": (104, 76, 98),
    "grout": (62, 54, 46),
}


def c(name, a=255):
    r, g, b = P[name]
    return (r, g, b, a)


def mix(a, b, t):
    a = P.get(a, a) if isinstance(a, str) else a
    b = P.get(b, b) if isinstance(b, str) else b
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3)) + (255,)

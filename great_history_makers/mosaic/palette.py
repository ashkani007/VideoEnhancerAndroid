"""Tesserae palette: the limited stone/glass colours every asset draws from.

Keeping all artwork on one curated palette is what keeps scenes and episodes
visually consistent. Values are sRGB tuples.
"""

P = {
    # V3 palette: richer stones and glass (saturated but never neon)
    "ivory": (242, 230, 200),
    "bone": (228, 210, 170),
    "sand": (228, 186, 122),
    "sand_dk": (194, 146, 86),
    "ochre": (222, 148, 46),
    "ochre_dk": (174, 104, 32),
    "amber": (238, 152, 28),
    "terracotta": (200, 80, 38),
    "terracotta_dk": (142, 50, 28),
    "brick": (172, 88, 50),
    "umber": (98, 58, 36),
    "outline": (40, 28, 24),
    "black": (24, 18, 16),
    "stone": (162, 148, 126),
    "stone_dk": (110, 98, 86),
    "gold": (230, 172, 46),
    "gold_lt": (248, 208, 104),
    "lapis": (28, 70, 172),
    "lapis_dk": (16, 42, 120),
    "cobalt": (22, 60, 196),
    "blue_deep": (14, 30, 88),
    "navy": (12, 20, 56),
    "blue_mid": (52, 118, 200),
    "blue_pale": (124, 174, 222),
    "sky_pale": (186, 210, 226),
    "turquoise": (22, 152, 164),
    "white": (246, 242, 230),
    "purple": (116, 36, 96),
    "purple_dk": (78, 20, 66),
    "crimson": (182, 26, 40),
    "crimson_dk": (120, 14, 30),
    "burgundy": (110, 18, 40),
    "green": (54, 134, 70),
    "green_dk": (30, 92, 48),
    "emerald": (20, 124, 84),
    "olive": (122, 130, 50),
    # skin / hair
    "skin": (208, 138, 90),
    "skin_sh": (170, 100, 64),
    "skin_dk": (154, 90, 58),
    "hair": (40, 28, 22),
    "hair_lt": (74, 50, 34),
    "grey_hair": (158, 146, 132),
    # light
    "sun": (252, 188, 76),
    "sun_hot": (255, 226, 148),
    "dusk_orange": (236, 110, 40),
    "dusk_rose": (198, 68, 76),
    "dusk_violet": (90, 48, 112),
    "grout": (40, 32, 28),
    # Napoleonic additions (Episode 02)
    "fr_blue": (26, 46, 122),
    "fr_blue_dk": (16, 28, 82),
    "grey_coat": (134, 128, 118),
    "grey_coat_dk": (92, 88, 82),
    "green_coat": (28, 86, 54),
    "red_coat": (186, 30, 36),
    "ermine": (246, 242, 234),
    "snow": (228, 236, 244),
    "snow_sh": (166, 184, 208),
    "ice": (192, 210, 228),
    "smoke": (128, 118, 108),
    "smoke_lt": (184, 176, 166),
    "fire": (250, 140, 30),
    "fire_hot": (255, 214, 96),
    "steel": (176, 182, 190),
    "brass": (214, 170, 70),
    "wood": (120, 76, 44),
    "night": (18, 20, 40),
}


def c(name, a=255):
    r, g, b = P[name]
    return (r, g, b, a)


def mix(a, b, t):
    a = P.get(a, a) if isinstance(a, str) else a
    b = P.get(b, b) if isinstance(b, str) else b
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3)) + (255,)

"""LOCKED map style for Great History Makers (client decision 2026-10-26).

The approved reference is the animated maps of the original Napoleon Short (episodes_v4/napoleon_ep01, rendered by
ghm4.mapshot) and the 1805 campaign map of the approved Napoleon_20s_POC (ghm4/data/maps/campaign_1805_austerlitz.json).
Their look is LOCKED. Do not change it without the client's explicit, dated approval. In particular, leave alone:
- sand parchment land, navy sea with shoreline ripples, faint graticule, coastline stroke;
- thin river lines with italic river names, small relief chevrons;
- bold blue (French) and red (enemy) campaign arrows with travelling dashes and a dark outline;
- white place dots, red dashed rings, gold battle stars with glow;
- gold tracked kicker, ivory date ticker, ivory labels with shadow, bottom-left legend bars;
- top and bottom scrims, vignette 0.24, grain 0.008;
- continental scale with modest camera zoom along a spline.

Technical improvements are allowed when they do not change that appearance: collision-safe labels (`safe_labels`), QC
checks, 1080p and 16:9 output (camera widths keep their meaning as the short side of the frame, so a 16:9 map shows
the same scale as the vertical original), accuracy notes.

Map features that were NOT in the approved style are refused unless the map JSON carries
"style_override_approved": "<date and client approval reference>".
"""

# visual features introduced after the approved style; usable only with an explicit, dated client approval
NON_ORIGINAL_FEATURES = {
    "units": "unit blocks with corps numerals and trails (not in the approved maps; use campaign arrows)",
    "smooth_rivers": "splined rivers (the approved maps draw rivers as straight polylines)",
}
NON_ORIGINAL_ROUTE_KEYS = {"hide": "fading campaign arrows (approved arrows stay on the map once drawn)"}
NON_ORIGINAL_LABEL_KEYS = {"out": "fading labels (approved labels stay once shown)"}

# element scale on screen is proportional to element_scale / camera width (short side). Range of the approved maps
# (Ep01 + POC): about 0.07-0.14 for most of the shot; the POC map closes in to about 0.2 before it fades.
SCALE_RANGE = (0.06, 0.22)

DEFAULTS = {"vignette": 0.24, "grain": 0.008}


class MapStyleLocked(ValueError):
    pass


def violations(cfg):
    """Non-original visual features used by a map JSON without an approval key."""
    if cfg.get("style_override_approved"):
        return []
    out = [f"'{k}': {v}" for k, v in NON_ORIGINAL_FEATURES.items() if cfg.get(k)]
    for r in cfg.get("routes", []):
        out += [f"route '{k}': {v}" for k, v in NON_ORIGINAL_ROUTE_KEYS.items() if k in r]
    for lb in cfg.get("labels", []):
        out += [f"label '{k}': {v}" for k, v in NON_ORIGINAL_LABEL_KEYS.items() if k in lb]
    return sorted(set(out))


def check(cfg, path=""):
    v = violations(cfg)
    if v:
        raise MapStyleLocked(f"{path}: the map style is LOCKED (ghm4/map_style.py); not in the approved style: "
                             + "; ".join(v) + ". Add \"style_override_approved\" only with the client's explicit approval.")


def scale_issues(cfg):
    """Camera keys whose element scale on screen leaves the approved range (oversized or tiny map graphics)."""
    es = cfg.get("element_scale", 1.0)
    end = (cfg.get("fade_out") or [0, 1e9])[1]
    out = []
    for t, lon, lat, w in cfg.get("camera", []):
        if t > end:                                               # keys after the map has faded out are never seen
            continue
        r = es / w
        if not SCALE_RANGE[0] <= r <= SCALE_RANGE[1]:
            out.append((t, round(r, 3)))
    return out

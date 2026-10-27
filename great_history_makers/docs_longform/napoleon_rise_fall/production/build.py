"""Build the production files of *Napoleon: The Rise and Fall of an Emperor* from three sources:
NARRATION.txt (frozen script), shots.py (shot list) and maps_src.py (map data, LOCKED style).

    py docs_longform/napoleon_rise_fall/production/build.py [--words chapters/chN/words_aligned.json ...]

Timing: until the narration is recorded, every word gets a planned time (140 words per minute plus pauses at
punctuation). When a chapter's forced-aligned words exist (chapters/<ch>/audio/words_aligned.json, written by
ghm4.narrate align), they replace the plan, and every cut and map event moves onto the real words.

Writes (all regenerated, never hand-edited):
- maps/<id>.json                        resolved map files (graphics scale and arrow stroke checked against the preset)
- chapters/<ch>/storyboard.json         full chapter storyboard (plates, maps, cards, captions, music, SFX)
- chapters/<ch>/maps_storyboard.json    the chapter's map shots back to back (renderable now)
- SHOT_LIST.md                          human-readable shot list with planned timecodes
- ../../../jobs/specs/napoleon_doc_<ch>.json   ComfyUI jobs for the chapter's paintings (at most 40 images each)
"""
import argparse
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, GHM)
sys.path.insert(0, HERE)

from ghm4 import map_style  # noqa: E402
from maps_src import MAPS  # noqa: E402
from shots import CHAPTERS  # noqa: E402

WPM = 140.0
PAUSE = {".": 0.45, "?": 0.45, "!": 0.45, ",": 0.12, ";": 0.25, ":": 0.25}
PARA = 0.8
CARD = 4.5            # chapter card length (s); narration starts after it
LEAD_CH1 = 1.5        # chapter 1 opens on the first painting
TAIL = 2.0            # silence after a chapter's last word
FILM_TITLE = 7.0      # film title after the cold open
END_CARD = 6.0
SEEDS0 = {"ch1": 7101, "ch2": 7201, "ch3": 7301, "ch4": 7401, "ch5": 7501, "ch6": 7601, "ch7": 7701}


def norm(w):
    return re.sub(r"[^\w']", "", w.lower().replace("’", "'"))


def read_narration():
    txt = open(os.path.join(HERE, "NARRATION.txt"), encoding="utf-8").read()
    parts = re.split(r"^\[(CH\d)[^\]]*\]\s*$", txt, flags=re.M)
    return {k.lower(): v.strip() for k, v in zip(parts[1::2], parts[2::2])}


def plan_words(text, t0):
    """[(word, start, end)] at the planned speaking rate."""
    out, t = [], t0
    for para in text.split("\n"):
        for w in para.split():
            d = 60.0 / WPM
            out.append((w, t, t + d * 0.9))
            t += d + PAUSE.get(w[-1], 0.0)
        t += PARA
    return out


def words_for(ch, text, t0):
    p = os.path.join(HERE, "chapters", ch, "audio", "words_aligned.json")
    if os.path.exists(p):                      # real timing from forced alignment of the lead-in-padded take (chapter time)
        aw = json.load(open(p))
        return [(a["word"], a["start"], a["end"]) for a in aw]
    return plan_words(text, t0)


def tokens(text):
    """Hyphenated words count as separate tokens (aligners split them too)."""
    return [p for p in (norm(x) for x in re.split(r"[\s\-–]+", text)) if p]


def find(words, phrase, after=0.0):
    key = tokens(phrase)
    nw, tw = [], []
    for w in words:
        for p in tokens(w[0]):
            nw.append(p)
            tw.append(w[1])
    for i in range(len(nw) - len(key) + 1):
        if nw[i:i + len(key)] == key and tw[i] >= after - 1e-6:
            return tw[i]
    raise KeyError(f"phrase not in narration: {phrase!r}")


def resolve(v, words, base, end):
    """Anchors '@phrase[+/-s]' -> map-local seconds; '@END' -> map end."""
    if isinstance(v, str) and v.startswith("@"):
        m = re.match(r"@(.*?)([+-]\d+(\.\d+)?)?$", v)
        phrase, off = m.group(1).strip(), float(m.group(2) or 0)
        t = end if phrase == "END" else find(words, phrase) - base
        return round(t + off, 3)
    if isinstance(v, list):
        return [resolve(x, words, base, end) for x in v]
    if isinstance(v, dict):
        return {k: resolve(x, words, base, end) for k, x in v.items()}
    return v


def retime_cfg(cfg, f):
    """Apply a time map f to every time field of a map config (used for the approved base maps)."""
    c = copy.deepcopy(cfg)
    for r in c.get("routes", []):
        if "draw" in r:
            r["draw"] = [f(x) for x in r["draw"]]
        if "legs" in r:
            r["legs"] = [[f(a), f(b), i] for a, b, i in r["legs"]]
    c["dots"] = [[d[0], f(d[1])] + d[2:] for d in c.get("dots", [])]
    c["rings"] = [[r[0], f(r[1]), f(r[2])] + r[3:] for r in c.get("rings", [])]
    c["stars"] = [[s[0], f(s[1])] + s[2:] for s in c.get("stars", [])]
    for lb in c.get("labels", []):
        lb["at"] = f(lb["at"])
    c["camera"] = [[f(k[0])] + k[1:] for k in c["camera"]]
    if c.get("kicker"):
        c["kicker"] = [c["kicker"][0], f(c["kicker"][1])]
    c["dates"] = [[f(d[0]), d[1]] for d in c.get("dates", [])]
    c["legend"] = [[l[0], l[1], f(l[2])] for l in c.get("legend", [])]
    for rg in c.get("regions", []):
        rg["reveal"] = [f(x) for x in rg["reveal"]]
    if c.get("fade_out"):
        c["fade_out"] = [f(x) for x in c["fade_out"]]
    return c


def piecewise(points):
    xs = sorted(points)
    ys = [points[x] for x in xs]

    def f(t):
        if t <= xs[0]:
            return ys[0] + (t - xs[0])
        for i in range(1, len(xs)):
            if t <= xs[i]:
                u = (t - xs[i - 1]) / (xs[i] - xs[i - 1])
                return round(ys[i - 1] + u * (ys[i] - ys[i - 1]), 3)
        return round(ys[-1] + (t - xs[-1]), 3)
    return f


def coverage_issues(cfg):
    """The 16:9 frame must fit inside the map canvas at every camera key; otherwise mapshot clamps the camera wider
    than authored and the graphics shrink below the approved size."""
    import math
    kx = math.cos(math.radians(cfg.get("ref_lat", 48)))
    lon0, lon1, lat0, lat1 = cfg["bounds"]
    out = []
    for t, lon, lat, w in cfg["camera"]:
        hw, hh = w * 16 / 9 / 2, w / 2
        if (lon - lon0) * kx < hw or (lon1 - lon) * kx < hw or lat - lat0 < hh or lat1 - lat < hh:
            out.append(f"camera at {t}s leaves the canvas (bounds too small for 16:9)")
    return out


def fit_bounds(cfg, margin=0.6):
    """Grow the canvas so the 16:9 frame fits at every camera key (canvas extent does not change the look)."""
    import math
    kx = math.cos(math.radians(cfg.get("ref_lat", 48)))
    lon0, lon1, lat0, lat1 = cfg["bounds"]
    for t, lon, lat, w in cfg["camera"]:
        hw, hh = (w * 16 / 9 / 2 + margin) / kx, w / 2 + margin
        lon0, lon1, lat0, lat1 = min(lon0, lon - hw), max(lon1, lon + hw), min(lat0, lat - hh), max(lat1, lat + hh)
    cfg["bounds"] = [round(lon0, 2), round(lon1, 2), round(lat0, 2), round(lat1, 2)]
    mp = (lon1 - lon0) * kx * cfg.get("ppu", 220) * (lat1 - lat0) * cfg.get("ppu", 220) / 1e6
    return mp


OVERSAMPLE = 1.6      # canvas pixels per output pixel at the closest zoom (approved maps: v2 1.26-1.8, Ep01 about 2)


def set_resolution(cfg, short=1080, cap_mp=20.0):
    """Raise the canvas resolution (ppu) so the parchment, sea and coast base is oversampled like the approved maps;
    resolution only, the look is unchanged. cap_mp is in config units: the renderer multiplies ppu by 1.275 at 1080p,
    so 20 MP here is about 33 MP per render worker (a 3-worker render stays inside 15 GB; 36 MP config OOM-killed one)."""
    import math
    kx = math.cos(math.radians(cfg.get("ref_lat", 48)))
    lon0, lon1, lat0, lat1 = cfg["bounds"]
    area = (lon1 - lon0) * kx * (lat1 - lat0)
    want = OVERSAMPLE * short / min(k[3] for k in cfg["camera"])
    ppu = max(cfg.get("ppu", 220), min(want, math.sqrt(cap_mp * 1e6 / area)))
    cfg["ppu"] = int(math.ceil(ppu))
    return area * cfg["ppu"] ** 2 / 1e6


def build_map(mid, words, base, end):
    src = MAPS[mid]
    if "_base" in src:
        cfg = json.load(open(os.path.join(GHM, src["_base"]), encoding="utf-8"))
        anchors = {float(k): resolve(v, words, base, end) for k, v in src["_retime"].items()}
        cfg = retime_cfg(cfg, piecewise(anchors))
        cfg["_about"] = src["_about"] + " BASE: " + cfg.get("_about", src["_base"])
        cfg.setdefault("safe_labels", True)
    else:
        cfg = resolve({k: v for k, v in src.items()}, words, base, end)
    cfg["_generated"] = "by production/build.py from maps_src.py; do not edit by hand"
    fit_bounds(cfg)
    mp = set_resolution(cfg)
    if mp > 45:
        print(f"  note: {mid} canvas {mp:.0f} MP")
    issues = coverage_issues(cfg) + map_style.violations(cfg) + [f"scale {x}" for x in map_style.scale_issues(cfg)] + \
        [f"stroke {x}" for x in map_style.stroke_issues(cfg, end=end)]
    return cfg, issues


def sfx_for(sh, a, b):
    fx, out = sh.get("fx", []), []
    if sh["type"] == "M":
        out.append({"type": "drum", "start": a + 0.3, "end": b - 0.3, "period": 0.5, "gain": 0.16})
        return out
    if "puffs" in fx or "smoke" in fx and any(k in sh.get("scene", "") for k in ("Battle", "battery", "artillery", "siege", "attack", "charge")):
        out += [{"type": "cannon", "start": a + 1.2, "gain": 0.45}, {"type": "cannon", "start": a + 4.6, "gain": 0.3, "dist": 0.7},
                {"type": "volley", "start": a + 2.4, "end": a + 4.0, "gain": 0.18}]
    if "fire" in fx:
        out.append({"type": "fire", "start": a, "end": b, "gain": 0.22})
    if "snow" in fx:
        out.append({"type": "wind", "start": a, "end": b, "gain": 0.45})
    if "water" in fx:
        out.append({"type": "water", "start": a, "end": b, "gain": 0.25})
    if "flags" in fx:
        out.append({"type": "flutter", "start": a, "end": b, "gain": 0.14})
    if "ranks" in fx:
        out.append({"type": "march", "start": a + 0.5, "end": b - 0.5, "gain": 0.16})
    if sh["id"] == "c4_coronation":
        out.append({"type": "bell", "start": a + 0.8, "gain": 0.3})
    if sh["id"] == "c2_revolution":
        out.append({"type": "crowd", "start": a, "end": b, "gain": 0.25})
    if not out:
        out.append({"type": "wind", "start": a, "end": b, "gain": 0.12})
    return out


def text_caption(lines):
    out = [{"text": lines[0], "preset": "date", "size": 30, "x": 640, "y": 96, "at": 0.6, "out": [6.0, 6.6]}]
    if len(lines) > 1:
        out.append({"text": lines[1], "preset": "legend", "size": 20, "track": 6, "x": 640, "y": 132, "color": "gold",
                    "at": 1.0, "out": [6.0, 6.6]})
    return out


RECON = {"text": "ARTISTIC RECONSTRUCTION", "preset": "legend", "size": 13, "track": 3, "x": 1250, "y": 40, "align": "r",
         "at": 0.5, "out": [4.0, 4.6]}
CAMERA = {"push": {"from": {"zoom": 1.03}, "to": {"zoom": 1.12}, "ease": "inout"},
          "pull": {"from": {"zoom": 1.12}, "to": {"zoom": 1.03}, "ease": "inout"},
          "drift": {"from": {"zoom": 1.08}, "to": {"zoom": 1.08}, "ease": "inout"}}


def build_chapter(ch, text):
    cid = ch["id"]
    t0 = LEAD_CH1 if cid == "ch1" else CARD + 0.5
    words = words_for(cid, text, t0)
    shots, maps_out, report = [], {}, []
    starts = []
    for i, sh in enumerate(ch["shots"]):
        s = 0.0 if (i == 0 and cid == "ch1") else round(find(words, sh["cue"]) - 0.25, 3)
        starts.append(s)
    last_word = words[-1][2]
    end = round(last_word + TAIL + (FILM_TITLE if cid == "ch1" else 0) + (END_CARD if cid == "ch7" else 0), 3)
    bounds = starts[1:] + [end]
    first_map_start = {}
    sfx = []
    first_plate = next(s for s in ch["shots"] if s["type"] == "P")
    out_shots = []
    if ch["card"]:
        plate_id = first_plate["id"]
        out_shots.append({"id": f"{cid}_card", "type": "plate", "start": 0.0, "end": round(starts[0], 3),
                          "plate": f"../../plates/{plate_id}.png", "meta": f"../../plates/{plate_id}.json",
                          "camera": {"from": {"zoom": 1.16}, "to": {"zoom": 1.12}}, "scrim": [[0, 720, 0.62]],
                          "text": [{"text": f"CHAPTER {ch['card']}", "preset": "kicker", "size": 26, "x": 640, "y": 300, "at": 0.3},
                                   {"text": ch["title"].upper(), "preset": "title", "size": 64, "x": 640, "y": 372, "at": 0.6},
                                   {"rule": 360, "x": 640, "y": 398, "at": 1.0},
                                   {"text": ch["years"], "preset": "date", "size": 30, "x": 640, "y": 446, "at": 1.2}]})
        sfx.append({"type": "whoosh", "start": 0.1, "gain": 0.25})
    for sh, a, b in zip(ch["shots"], starts, bounds):
        if sh["type"] == "M":
            mid = sh["map"]
            if "offset_from" in sh:
                base_shot = first_map_start[sh["offset_from"]]
                off = round(a - base_shot, 3)
                out = {"id": sh["id"], "type": "map", "start": a, "end": b, "map": f"../../maps/{mid}.json", "map_offset": off}
            else:
                first_map_start[sh["id"]] = a
                out = {"id": sh["id"], "type": "map", "start": a, "end": b, "map": f"../../maps/{mid}.json"}
            maps_out.setdefault(mid, {"base": a, "end": b - a})
            maps_out[mid]["end"] = round(b - maps_out[mid]["base"], 3)
            out_shots.append(out)
        else:
            out = {"id": sh["id"], "type": "plate", "start": a, "end": b,
                   "plate": f"../../plates/{sh['id']}.png", "meta": f"../../plates/{sh['id']}.json",
                   "camera": copy.deepcopy(CAMERA[sh.get("motion", "push")]), "_motion": sh.get("motion", "push"), "_fx": sh.get("fx", [])}
            if "blink" in sh.get("fx", []):
                out["blink"] = [round((b - a) * 0.45, 2)]
            if "haze" in sh.get("fx", []) or "fog" in sh.get("fx", []):
                out["haze"] = 0.1
            txt = text_caption(sh["caption"]) if sh.get("caption") else []
            if sh.get("caption") or sh["id"] == first_plate["id"]:
                txt.append(dict(RECON))
            if sh.get("end_title"):
                tt = round(last_word + 1.2 - a, 2)
                out["scrim"] = [[0, 720, 0.0]]
                out["title_at"] = tt
                txt += [{"text": "NAPOLEON", "preset": "title", "size": 96, "x": 640, "y": 330, "at": tt},
                        {"rule": 520, "x": 640, "y": 356, "at": tt + 0.6},
                        {"text": "THE RISE AND FALL OF AN EMPEROR", "preset": "kicker", "size": 28, "x": 640, "y": 400, "at": tt + 0.9}]
            if sh.get("end_card"):
                tt = round(last_word + 1.5 - a, 2)
                txt += [{"text": "GREAT HISTORY MAKERS", "preset": "kicker", "size": 30, "x": 640, "y": 340, "at": tt},
                        {"rule": 420, "x": 640, "y": 366, "at": tt + 0.5},
                        {"text": "NAPOLEON: THE RISE AND FALL OF AN EMPEROR", "preset": "legend", "size": 22, "track": 4, "x": 640, "y": 404,
                         "color": "gold", "at": tt + 0.8}]
            if txt:
                out["text"] = txt
            out_shots.append(out)
        sfx += sfx_for(sh, a, b)
    # resolve maps (anchors relative to the map's first shot)
    for mid, info in maps_out.items():
        cfg, issues = build_map(mid, words, info["base"], info["end"])
        json.dump(cfg, open(os.path.join(HERE, "maps", f"{mid}.json"), "w"), indent=1, ensure_ascii=False)
        report.append((mid, issues))
    # transitions
    trans = []
    for prev, cur in zip(out_shots, out_shots[1:]):
        kind = "ink" if "map" in (prev["type"], cur["type"]) else "dissolve"
        trans.append({"at": cur["start"], "type": kind})
    sb = {"id": f"napoleon_doc_{cid}", "format": "landscape", "fps": 30, "duration": end, "fade_out": 0.8,
          "vignette": 0.2, "grain": 0.006,
          "_status": "Chapter storyboard generated by production/build.py. Plates and narration pending (see PRODUCTION_REPORT.md).",
          "_timing": "aligned" if os.path.exists(os.path.join(HERE, "chapters", cid, "audio", "words_aligned.json")) else "planned (140 wpm)",
          "shots": out_shots, "transitions": trans,
          "captions": {"transcript": "audio/transcript.txt", "words": "audio/words_aligned.json", "y": 975, "size": 46},
          "audio": {"narration_file": "audio/narration.mp3", "narration_lead_in": t0, "bed_under_voice_db": 20, "bed_in_pauses_db": 11,
                    "music_level": 1.0, "sfx_level": 0.8,
                    "music": {"seed": ch["music"]["seed"], "root_hz": ch["music"]["root_hz"], "mode": "minor",
                              "drum_from": min([s["start"] for s in out_shots if s["type"] == "map"] or [end]),
                              "drum_to": max([s["end"] for s in out_shots if s["type"] == "map"] or [end])},
                    "sfx": sfx}}
    d = os.path.join(HERE, "chapters", cid)
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    json.dump(sb, open(os.path.join(d, "storyboard.json"), "w"), indent=1, ensure_ascii=False)
    open(os.path.join(d, "audio", "transcript.txt"), "w", encoding="utf-8").write(text + "\n")
    # map-only storyboard: map shots back to back, each with its own music bed slice
    ms, t, msfx, mtrans = [], 0.0, [], []
    for s in out_shots:
        if s["type"] != "map":
            continue
        dur = round(s["end"] - s["start"], 3)
        m = dict(s, start=round(t, 3), end=round(t + dur, 3))
        m["map"] = s["map"].replace("../../maps/", "../../maps/")
        if ms:
            mtrans.append({"at": m["start"], "type": "ink"})
        ms.append(m)
        msfx.append({"type": "drum", "start": t + 0.3, "end": t + dur - 0.3, "period": 0.5, "gain": 0.18})
        t += dur
    if ms:
        msb = {"id": f"napoleon_doc_{cid}_maps", "format": "landscape", "fps": 30, "duration": round(t, 3), "fade_out": 0.6,
               "_status": "Finished map shots of the chapter (LOCKED style), planned narration timing, music bed only.",
               "shots": ms, "transitions": mtrans,
               "audio": {"music_level": 1.0, "sfx_level": 0.8,
                         "music": {"seed": ch["music"]["seed"], "root_hz": ch["music"]["root_hz"], "mode": "minor", "drum_from": 0.3, "drum_to": t - 0.3},
                         "sfx": msfx}}
        json.dump(msb, open(os.path.join(d, "maps_storyboard.json"), "w"), indent=1, ensure_ascii=False)
    return sb, report, words


def job_specs(ch):
    """Image jobs for the chapter's new paintings (POC plates are already in napoleon_longform_poc_v1)."""
    plates = [s for s in ch["shots"] if s["type"] == "P" and s.get("reuse") != "poc"]
    specs, seed = [], SEEDS0[ch["id"]]
    for part in range(0, len(plates), 10):
        shots = []
        for s in plates[part:part + 10]:
            j = {"id": s["id"], "characters": [], "framing": s["framing"], "scene": s["scene"], "lighting": s["lighting"],
                 "seeds": [seed + k for k in range(4)]}
            seed += 10
            if s.get("chars") and not s.get("child"):
                j["characters"] = list(s["chars"])
                j["variants"] = dict(s["chars"])
            j["negative_extra"] = ", ".join(x for x in ["text, letters, watermark", s.get("negative_extra", "")] if x)
            shots.append(j)
        suffix = "" if len(plates) <= 10 else chr(ord("a") + part // 10)
        specs.append({"job_id": f"napoleon_doc_{ch['id']}{suffix}_v1", "created": "2026-10-27",
                      "notes": f"Napoleon documentary, chapter {ch['id'][2:]} ({ch['title']}): {len(shots)} paintings x 4 seeds, 16:9, "
                               "style ghm_painterly_v2. Client picks; nothing is final before approval.",
                      "style": "ghm_painterly_v2", "workflow": "sdxl_hires", "shots": shots})
    return specs


def fmt(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def main():
    argparse.ArgumentParser().parse_args()
    narr = read_narration()
    os.makedirs(os.path.join(HERE, "maps"), exist_ok=True)
    md = ["# Shot list: *Napoleon: The Rise and Fall of an Emperor*", "",
          "Generated by `production/build.py` from `NARRATION.txt`, `shots.py` and `maps_src.py`. Timecodes are chapter-local and "
          "**planned** (140 words per minute) until the narration is recorded and aligned; then they are regenerated from the real words.",
          "Types: **P** painting, **M** map (locked style), **C** chapter card.", ""]
    total, problems, chapter_rows = 0.0, [], []
    for ch in CHAPTERS:
        sb, report, words = build_chapter(ch, narr[ch["id"]])
        for mid, issues in report:
            if issues:
                problems.append((mid, issues))
        n_p = sum(1 for s in sb["shots"] if s["type"] == "plate" and not s["id"].endswith("_card"))
        n_m = sum(1 for s in sb["shots"] if s["type"] == "map")
        map_t = sum(s["end"] - s["start"] for s in sb["shots"] if s["type"] == "map")
        chapter_rows.append((ch, total, sb["duration"], n_p, n_m, map_t))
        md += [f"## Chapter {ch['id'][2:]}: {ch['title']} ({ch['years']}) — {fmt(sb['duration'])} (film {fmt(total)}–{fmt(total + sb['duration'])})", "",
               "| # | Shot | Type | In | Out | Cue | Content | Motion / FX |", "|---|---|---|---|---|---|---|---|"]
        src = {s["id"]: s for s in ch["shots"]}
        for i, s in enumerate(sb["shots"], 1):
            o = src.get(s["id"], {})
            if s["id"].endswith("_card"):
                typ, content, mo = "C", f"CHAPTER {ch['card']} · {ch['title'].upper()} · {ch['years']}", "type reveal over darkened plate"
            elif s["type"] == "map":
                typ, content, mo = "M", f"`{os.path.basename(s['map'])}`" + (f" (continued, +{s['map_offset']:.1f} s)" if "map_offset" in s else ""), "locked map animation"
            else:
                typ = "P"
                content = ("POC plate (approved job)" if o.get("reuse") == "poc" else o.get("scene", ""))[:150]
                mo = ", ".join([o.get("motion", "")] + o.get("fx", []))
            cue = o.get("cue", "")
            md.append(f"| {i} | `{s['id']}` | {typ} | {fmt(s['start'])} | {fmt(s['end'])} | {cue} | {content} | {mo} |")
        md.append("")
        total += sb["duration"]
        for spec in job_specs(ch):
            json.dump(spec, open(os.path.join(GHM, "jobs", "specs", spec["job_id"] + ".json"), "w"), indent=1, ensure_ascii=False)
    md[5:5] = ["| Chapter | Starts | Length | Paintings | Map shots | Map time |", "|---|---|---|---|---|---|"] + \
        [f"| {c['id'][2:]}. {c['title']} | {fmt(s)} | {fmt(d)} | {p} | {m} | {fmt(mt)} |" for c, s, d, p, m, mt in chapter_rows] + \
        [f"| **Total** | | **{fmt(total)}** | {sum(r[3] for r in chapter_rows)} | {sum(r[4] for r in chapter_rows)} | {fmt(sum(r[5] for r in chapter_rows))} |", ""]
    open(os.path.join(HERE, "SHOT_LIST.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    aligned = all(os.path.exists(os.path.join(HERE, "chapters", c["id"], "audio", "words_aligned.json")) for c in CHAPTERS)
    ts = [f"{int(st // 60)}:{int(st % 60):02d} {c['title']}" for c, st, *_ in chapter_rows]
    open(os.path.join(HERE, "CHAPTER_TIMESTAMPS.txt"), "w", encoding="utf-8").write(
        ("# FINAL (from the aligned narration)\n" if aligned else
         "# PLANNED timing (140 wpm); regenerated from the recorded narration before delivery\n") + "\n".join(ts) + "\n")
    print(f"total {fmt(total)} ({total:.0f} s)")
    for c, s, d, p, m, mt in chapter_rows:
        print(f"  {c['id']} {fmt(s)} +{fmt(d)}  plates {p}  maps {m} ({mt:.0f} s)")
    if problems:
        print("MAP STYLE PROBLEMS:")
        for mid, iss in problems:
            print("  ", mid, iss)
        sys.exit(1)
    print("all maps inside the locked preset ranges")


if __name__ == "__main__":
    main()

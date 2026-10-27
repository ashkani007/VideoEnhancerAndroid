"""Side-by-side contact sheet of ACTUAL video frames: an approved reference map video against new map renders.

    py tools/map_compare_sheet.py out.jpg --ref ref.mp4 --cols "Label=video.mp4" ["Label=video.mp4" ...]
        --pairs "12.0:3.0,14.0:6.5,..." [--notes "row note|row note|..."] [--map new_map.json]

Each row shows the reference frame at the first time and every other column at the second time. Frames are taken
straight from the MP4s with ffmpeg (no re-rendering). With --map, each row is annotated with the arrow stroke and
graphics scale measured at that moment (ghm4.map_style), next to the approved range from the locked preset.
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

H = 420                                     # row height in the sheet
BG, FG, GOLD, GREY = (24, 22, 20), (225, 236, 240), (90, 190, 230), (150, 150, 150)


def same_scale(img_full_res):
    """Centre crop of a portrait frame scaled so its SHORT side equals the row height: map graphics then appear at the
    same size as in the 16:9 tiles (camera widths and graphics sizes are defined on the short side)."""
    h, w = img_full_res.shape[:2]
    img = cv2.resize(img_full_res, (H, round(h * H / w)), interpolation=cv2.INTER_AREA)
    y0 = (img.shape[0] - H) // 2
    return img[y0:y0 + H].copy()


def grab_raw(video, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def grab(video, t):
    img = grab_raw(video, t)
    if img is None:
        raise SystemExit(f"no frame at {t}s in {video}")
    return cv2.resize(img, (round(img.shape[1] * H / img.shape[0]), H), interpolation=cv2.INTER_AREA)


def put(img, text, xy, scale=0.55, col=FG, th=1):
    for dx, dy in ((1, 1), (2, 2), (-1, 1), (1, -1)):        # dark shadow (an outline pass would widen the glyphs)
        cv2.putText(img, text, (xy[0] + dx, xy[1] + dy), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), th, cv2.LINE_AA)
    cv2.putText(img, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)


def metrics(cfg, t):
    from ghm4.map_style import hermite_width
    w = hermite_width(cfg, t)
    es = cfg.get("element_scale", 1.0)
    strokes = [r.get("width", 34) * es / (220 * w) * 1000 for r in cfg.get("routes", [])]
    return es / w, strokes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-label", default="APPROVED: Ep01 Short (actual frames)")
    ap.add_argument("--cols", nargs="+", required=True)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--map", help="map JSON of the LAST column, for measured stroke / scale")
    ap.add_argument("--title", default="Map style match: approved Ep01 frames vs new 16:9 sample (same beats)")
    a = ap.parse_args()
    cols = [c.split("=", 1) for c in a.cols]
    pairs = [tuple(float(x) for x in p.split(":")) for p in a.pairs.split(",")]
    notes = a.notes.split("|") if a.notes else []
    cfg = json.load(open(a.map)) if a.map else None
    from ghm4 import map_style
    rng_s, rng_k = map_style.STROKE_RANGE, map_style.SCALE_RANGE

    rows = []
    for i, (tr, tn) in enumerate(pairs):
        tiles = [grab(a.ref, tr), same_scale(grab_raw(a.ref, tr))] + [grab(v, tn) for _, v in cols]
        put(tiles[0], f"Ep01 t={tr:.1f}s", (8, H - 12), 0.6, GOLD, 2)
        put(tiles[1], "Ep01 centre, SAME map scale", (8, H - 12), 0.55, GOLD, 2)
        for (lab, _), tile in zip(cols, tiles[2:]):
            put(tile, f"{lab}  t={tn:.1f}s", (10, H - 12), 0.6, GOLD, 2)
        if cfg is not None:
            sc, st = metrics(cfg, tn)
            put(tiles[-1], "arrows " + " / ".join(f"{s:.1f}" for s in st) + f" permille (approved {rng_s[0]:g}-{rng_s[1]:g})"
                + f"   scale {sc:.3f} ({rng_k[0]:g}-{rng_k[1]:g})", (10, 24), 0.5, FG, 1)
        gap = np.full((H, 8, 3), BG, np.uint8)
        row = tiles[0]
        for tile in tiles[1:]:
            row = np.hstack([row, gap, tile])
        if i < len(notes) and notes[i]:
            band = np.full((30, row.shape[1], 3), BG, np.uint8)
            put(band, notes[i], (10, 21), 0.55, FG, 1)
            row = np.vstack([row, band])
        rows.append(row)
    width = max(r.shape[1] for r in rows)
    head = np.full((70, width, 3), BG, np.uint8)
    put(head, a.title, (12, 30), 0.8, GOLD, 2)
    put(head, "Columns: " + a.ref_label + "  |  Ep01 centre crop at the same short-side scale as 16:9  |  "
        + "  |  ".join(l for l, _ in cols), (12, 58), 0.55, GREY, 1)
    sheet = [head]
    for r in rows:
        r = np.hstack([r, np.full((r.shape[0], width - r.shape[1], 3), BG, np.uint8)])
        sheet += [r, np.full((10, width, 3), BG, np.uint8)]
    cv2.imwrite(a.out, np.vstack(sheet), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(a.out, np.vstack(sheet).shape)


if __name__ == "__main__":
    main()

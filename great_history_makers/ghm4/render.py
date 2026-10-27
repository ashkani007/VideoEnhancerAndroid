#!/usr/bin/env python3
"""ghm4: storyboard-driven renderer for illustration plates + motion graphics (direction approved 2026-10-25).

  python -m ghm4.render <storyboard.json>                 # 720x1280 preview with music/SFX -> <dir>/output/
  python -m ghm4.render <storyboard.json> --final         # 1080x1920
  ("format": "landscape" in the storyboard: 1280x720 preview / 1920x1080 final, design space 1280x720)
  python -m ghm4.render <storyboard.json> --still 7.4     # one frame
  python -m ghm4.render <storyboard.json> --sheet         # contact sheet of 15 frames
  python -m ghm4.render <storyboard.json> --patch old_picture.mp4 --shots b02,b07   # re-render only these shots
                                                          (+0.5 s on each side for transitions); other frames are copied
                                                          (patched files are encoded at CRF 10 to limit generation loss)

Outputs: <id>_<W>x<H>_picture.mp4 (video only, the input of the narration stage) and <id>_<W>x<H>_preview.mp4
(picture + procedural music/SFX, for review). Narration and subtitles are added by `python -m ghm4.narrate`.

storyboard.json:
{
  "id": "...", "fps": 30, "duration": 20.0, "fade_out": 0.65, "grain": 0.008, "vignette": 0.24,
  "shots": [
    {"type": "plate", "start": 0, "end": 4.4, "plate": "plates/a.png", "meta": "plates/a.json",
     "camera": {"from": {"zoom": 1.22, "focus": [470, 705]}, "to": {"zoom": 1.06, "focus": [470, 830]},
                "ease": "inout"|"out"|"linear", "parallax": 0.55},
     "blink": [3.0], "puffs": [[0.9, 912, 928]], "gains": {"flags": 2.0, "bob": 1.7, "smoke": 1.0},
     "haze": 0.14, "sharpen": 0.4, "scrim": [[700, 1280, 0.68]], "exit_focus": [440, 420],
     "text": [... see ghm4.text.draw_items ...]},
    {"type": "map", "start": 9.0, "end": 15.0, "map": "maps/austerlitz_1805.json"}
  ],
  "transitions": [{"at": 4.4, "type": "whip"|"ink"|"flash"|"dissolve"|"cut"}],   flash: optional "strength" 0-1, "dur" s
  "audio": {... mosaic.audio cfg: music, sfx ...}
}
Plate focus/zoom are in plate pixels at the plate meta's ref_width; zoom 1 = the plate covers the frame.
"""
import argparse
import functools
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import cv2
import numpy as np

from . import map_style, mapshot
from . import text as T
from .plate import Plate, tileable_noise

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GHM)
FLASH = np.array([1.0, 0.93, 0.78], np.float32)
EASES = {"inout": T.ease, "out": lambda u: 1 - (1 - min(1.0, max(0.0, u))) ** 2.2, "linear": lambda u: min(1.0, max(0.0, u))}


def landscape(sb):
    return sb.get("format") == "landscape"


def design_width(sb):
    return 1280 if landscape(sb) else 720


def output_size(sb, final):
    if landscape(sb):
        return (1920, 1080) if final else (1280, 720)
    return (1080, 1920) if final else (720, 1280)


class Renderer:
    def __init__(self, sb_path, OW, OH):
        self.path = os.path.abspath(sb_path)
        self.dir = os.path.dirname(self.path)
        self.sb = json.load(open(self.path, encoding="utf-8"))
        self.dw = design_width(self.sb)
        self.OW, self.OH, self.U = OW, OH, OW / float(self.dw)
        self.fps = self.sb.get("fps", 30)
        self.dur = self.sb["duration"]
        self.shots = sorted(self.sb["shots"], key=lambda s: s["start"])
        self.trans = {round(tr["at"], 3): tr["type"] for tr in self.sb.get("transitions", [])}
        self.tparams = {round(tr["at"], 3): tr for tr in self.sb.get("transitions", [])}
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        self.XO, self.YO = xx, yy
        self.vig_shape = (np.clip(np.hypot((xx - OW / 2) / (OW * 0.62), (yy - OH / 2) / (OH * 0.62)) - 0.35, 0, 1) ** 1.4)[..., None]
        self.wipe_noise = cv2.resize(tileable_noise(160, 90, 4, 21), (OW, OH), interpolation=cv2.INTER_CUBIC)
        self.haze_noise = cv2.resize(tileable_noise(96, 256, 7, 33), (OW * 2, OH), interpolation=cv2.INTER_CUBIC)

    # ---------------------------------------------------------------- plates
    @functools.lru_cache(None)
    def plate(self, path, meta, factor):
        return Plate(os.path.join(self.dir, path), os.path.join(self.dir, meta) if meta else None, factor)

    def plate_for(self, shot):
        """Work at the resolution the shot needs (its maximum zoom), not at the plate's full size."""
        if "_factor" not in shot:
            im = cv2.imread(os.path.join(self.dir, shot["plate"]), cv2.IMREAD_UNCHANGED)
            H0, W0 = im.shape[:2]
            cam = shot.get("camera", {})
            zmax = max(cam.get("from", {}).get("zoom", 1.0), cam.get("to", {}).get("zoom", 1.0)) * 1.18
            cover = max(self.OW / W0, self.OH / H0)
            shot["_factor"] = min(1.0, cover * zmax * 1.15)
        return self.plate(shot["plate"], shot.get("meta"), round(shot["_factor"], 4))

    def place(self, layer, P, z, fx, fy, interp=cv2.INTER_LANCZOS4):
        """fx, fy in working pixels; zoom 1 = cover."""
        s = max(self.OW / P.W, self.OH / P.H) * z
        hw, hh = self.OW / (2 * s), self.OH / (2 * s)
        fx, fy = min(max(fx, hw), P.W - hw), min(max(fy, hh), P.H - hh)
        M = np.float32([[s, 0, self.OW / 2 - fx * s], [0, s, self.OH / 2 - fy * s]])
        return cv2.warpAffine(layer, M, (self.OW, self.OH), flags=interp, borderMode=cv2.BORDER_REFLECT)

    def zoom_blur(self, img, amt, cx=None, cy=None, n=7):
        if amt < 0.004:
            return img
        cx = self.OW / 2 if cx is None else cx
        cy = self.OH / 2 if cy is None else cy
        acc = np.zeros_like(img)
        for i in range(n):
            s = 1 + amt * i / (n - 1)
            M = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
            acc += cv2.warpAffine(img, M, (self.OW, self.OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return acc / n

    def shot_plate(self, sh, tl, t, mods):
        P = self.plate_for(sh)
        cam = sh.get("camera", {})
        centre = [P.W / P.k / 2, P.H / P.k / 2]                      # defaults: zoom 1 (cover), plate centre
        a = dict({"zoom": 1.0, "focus": centre}, **cam.get("from", {}))
        b = dict(a, **cam.get("to", {})) if cam.get("to") else a
        u = EASES[cam.get("ease", "inout")]((tl) / (sh["end"] - sh["start"]))
        z0 = a["zoom"]
        z = a["zoom"] + (b["zoom"] - a["zoom"]) * u
        fx = (a["focus"][0] + (b["focus"][0] - a["focus"][0]) * u) * P.k
        fy = (a["focus"][1] + (b["focus"][1] - a["focus"][1]) * u) * P.k
        w = mods.get("whip", 0.0)
        if w > 0:
            ef = sh.get("exit_focus")
            z *= 1 + 0.45 * w
            if ef:
                fx, fy = fx + (ef[0] * P.k - fx) * w, fy + (ef[1] * P.k - fy) * w
        z *= mods.get("zoom_mul", 1.0)
        bg = P.background(tl, t, sh.get("gains"), sh.get("puffs", ()))
        fg = P.foreground(tl, t, sh.get("blink", ()), sh.get("blink_dur", 0.30))
        if P.alpha is None:
            img = self.place(self._merge_single(P, bg, fg), P, z, fx, fy)
        else:
            par = cam.get("parallax", 0.55)
            zb = z0 + (z - z0) * par
            bl = self.place(bg, P, zb, fx, fy)
            fl = self.place(fg, P, z, fx, fy)
            al = np.clip(fl[..., 3:4], 0, 1)
            img = bl * (1 - al) + fl[..., :3] * al
        img = np.clip(img, 0, 1)
        sharp = sh.get("sharpen", 0.4 if max(self.OW / P.W, self.OH / P.H) * z > 1.3 else 0.0)
        if sharp:
            img = img + sharp * (img - cv2.GaussianBlur(img, (0, 0), 1.0 * self.U))
        if sh.get("haze"):
            off = int(40 * self.U * tl) % self.OW
            n = self.haze_noise[:, off:off + self.OW]
            ah = (np.clip((n - 0.5) / 0.3, 0, 1) * sh["haze"] * np.clip((self.YO / self.U - 420) / 500, 0, 1))[..., None]
            img = img * (1 - ah) + np.array([0.86, 0.78, 0.72], np.float32) * ah
        blur = mods.get("blur", 0.0)
        if blur:
            img = self.zoom_blur(img, blur, self.OW * 0.47, self.OH * 0.36)
        for y0, y1, k, *top in sh.get("scrim", []):
            img = T.scrim(img, y0, y1, k, bool(top and top[0]), self.U)
        cv = T.Canvas(self.OW, self.OH, self.dw)
        T.draw_items(cv, sh.get("text", []), tl)
        return cv.apply(img)

    @staticmethod
    def _merge_single(P, bg, fg):
        """No matte: background effects and foreground effects (blink, wind) act on one image."""
        out = bg.copy()
        diff = np.abs(fg - P.img).sum(-1, keepdims=True) > 1e-6     # pixels changed by blink/wind
        return np.where(diff, fg, out)

    def shot_map(self, sh, tl, t, mods):
        m = mapshot.get(os.path.join(self.dir, sh["map"]), self.OW, self.OH)
        return m.frame(tl)

    def render_shot(self, sh, t, mods=None):
        tl = t - sh["start"]
        fn = self.shot_plate if sh["type"] == "plate" else self.shot_map
        return fn(sh, tl, t, mods or {})

    # ---------------------------------------------------------------- timeline + transitions
    def frame(self, t):
        idx = max([i for i, s in enumerate(self.shots) if s["start"] <= t + 1e-9] + [0])
        sh = self.shots[idx]
        prev = self.shots[idx - 1] if idx > 0 else None
        nxt = self.shots[idx + 1] if idx + 1 < len(self.shots) else None
        cut_in, cut_out = round(sh["start"], 3), round(nxt["start"], 3) if nxt else None
        tin, tout = self.trans.get(cut_in, "cut"), self.trans.get(cut_out, "cut") if nxt else None
        tl = t - sh["start"]
        mods = {}
        if tout == "whip" and t > cut_out - 0.28:
            w = ((t - (cut_out - 0.28)) / 0.28) ** 2
            mods.update(whip=w, blur=0.10 * w)
        if tin == "whip" and prev and tl < 0.35:
            st = 1 - T.ease(tl / 0.35)
            mods.update(zoom_mul=1 + 0.10 * st, blur=0.08 * st)
        if tin == "flash" and prev and tl < 0.7:
            mods["zoom_mul"] = 1 + 0.14 * (1 - T.easeout(tl / 0.7))
        img = self.render_shot(sh, t, mods)
        # two-shot transitions
        if tout == "ink" and t > cut_out - 0.25:
            img = self.ink(img, self.render_shot(nxt, t), (t - (cut_out - 0.25)) / 0.5)
        elif tin == "ink" and prev and tl < 0.25:
            img = self.ink(self.render_shot(prev, t), img, (tl + 0.25) / 0.5)
        if tout == "dissolve" and t > cut_out - 0.3:
            a = T.ease((t - (cut_out - 0.3)) / 0.6)
            img = img * (1 - a) + self.render_shot(nxt, t) * a
        elif tin == "dissolve" and prev and tl < 0.3:
            a = T.ease((tl + 0.3) / 0.6)
            img = self.render_shot(prev, t) * (1 - a) + img * a
        if tout == "flash":                       # optional "strength" (peak, default 0.92) and "dur" (each side, 0.4 s)
            fp = self.tparams.get(cut_out, {})
            fd, fs = fp.get("dur", 0.4), fp.get("strength", 0.92)
            if t > cut_out - fd:
                f = T.ease((t - (cut_out - fd)) / fd) ** 2 * fs
                img = img * (1 - f) + FLASH * f
        if tin == "flash" and prev:
            fp = self.tparams.get(cut_in, {})
            fd, fs = fp.get("dur", 0.4), fp.get("strength", 0.92)
            if tl < fd:
                f = (1 - T.ease(tl / fd)) * fs
                img = img * (1 - f) + FLASH * f
        vg, grain = self.finish_look(sh)
        img = img * (1 - vg * self.vig_shape)
        fo = self.sb.get("fade_out", 0.65)
        img = img * (1 - T.ease((t - (self.dur - fo)) / (fo - 0.03)))
        g = np.random.default_rng(int(t * self.fps + 0.5)).normal(0, grain, (self.OH, self.OW, 1)).astype(np.float32)
        return np.clip(img + g, 0, 1)

    def finish_look(self, sh):
        """Vignette and grain for a shot: its own keys, else the LOCKED map defaults for map shots (so a painterly
        storyboard setting never changes the approved map look), else the storyboard's."""
        if sh["type"] == "map":
            d = map_style.DEFAULTS
            return sh.get("vignette", d["vignette"]), sh.get("grain", d["grain"])
        return sh.get("vignette", self.sb.get("vignette", 0.24)), sh.get("grain", self.sb.get("grain", 0.008))

    def ink(self, a, b, p):
        dg = (self.XO / self.OW) * 0.55 + (1 - self.YO / self.OH) * 0.45
        e = T.ease(p) * 1.3 - 0.15 - dg + 0.12 * (self.wipe_noise - 0.5)
        m = np.clip(e / 0.012 + 0.5, 0, 1)[..., None]
        return a * (1 - m) + b * m + (np.exp(-(e / 0.007) ** 2) * 0.3)[..., None] * np.array(T.COLORS["gold"], np.float32)


# ---------------------------------------------------------------- CLI
_R = None


def _init(path, OW, OH):
    global _R
    _R = Renderer(path, OW, OH)


def _work(i):
    return (_R.frame(i / _R.fps) * 255 + 0.5).astype(np.uint8).tobytes()


def save(img, path):
    cv2.imwrite(path, cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--still", type=float)
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) - 0)))
    ap.add_argument("--out", default=None)
    ap.add_argument("--patch", help="existing picture.mp4 to copy unchanged frames from")
    ap.add_argument("--shots", help="comma-separated shot ids to re-render (with --patch)")
    a = ap.parse_args()
    OW, OH = output_size(json.load(open(a.storyboard, encoding="utf-8")), a.final)
    R = Renderer(a.storyboard, OW, OH)
    out_dir = a.out or os.path.join(R.dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    sid = R.sb["id"]
    if a.still is not None:
        p = os.path.join(out_dir, f"still_{a.still:.2f}.png")
        save(R.frame(a.still), p)
        print(p)
        return
    if a.sheet:
        ts = np.linspace(0.4, R.dur - 0.4, 15)
        tiles = []
        for t in ts:
            th = cv2.resize(R.frame(float(t)), (240, 427) if OH > OW else (384, 216), interpolation=cv2.INTER_AREA)
            th = (th * 255).astype(np.uint8)
            cv2.putText(th, f"{t:.1f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            tiles.append(th)
        sheet = np.vstack([np.hstack(tiles[i:i + 5]) for i in range(0, 15, 5)])
        p = os.path.join(out_dir, f"{sid}_contact.png")
        cv2.imwrite(p, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
        print(p)
        return
    n = int(round(R.fps * R.dur))
    picture = os.path.join(out_dir, f"{sid}_{OW}x{OH}_picture.mp4")
    todo = set(range(n))
    old = None
    if a.patch:
        ids = set(a.shots.split(",")) if a.shots else set()
        unknown = ids - {s["id"] for s in R.shots}
        if unknown or not ids:
            sys.exit(f"--patch needs --shots with known ids (unknown: {sorted(unknown)})")
        todo = set()
        for s in R.shots:
            if s["id"] in ids:
                todo.update(range(max(0, int((s["start"] - 0.5) * R.fps)), min(n, int(np.ceil((s["end"] + 0.5) * R.fps)))))
        old = cv2.VideoCapture(a.patch)
        if int(old.get(cv2.CAP_PROP_FRAME_COUNT)) < n or int(old.get(cv2.CAP_PROP_FRAME_WIDTH)) != OW:
            sys.exit(f"{a.patch} does not match this storyboard ({n} frames, {OW}x{OH})")
        picture = picture.replace("_picture.mp4", "_picture_patched.mp4")
        print(f"patch: re-rendering {len(todo)} of {n} frames ({sorted(ids)}), copying the rest from {a.patch}")
    t0 = time.time()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(R.fps),
                           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "10" if a.patch else ("18" if not a.final else "15"), "-profile:v", "high",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", picture], stdin=subprocess.PIPE)
    ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
    order = sorted(todo)
    with ctx.Pool(a.workers, initializer=_init, initargs=(R.path, OW, OH)) as pool:
        rendered = pool.imap(_work, order, chunksize=2)
        for k in range(n):
            if old is not None:
                ok, fr = old.read()
                if not ok:
                    sys.exit(f"could not read frame {k} of {a.patch}")
            if k in todo:
                buf = next(rendered)
            else:
                buf = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).tobytes()
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"frame {k}/{n} {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"picture: {picture} ({time.time() - t0:.0f}s)")
    if R.sb.get("audio"):
        from mosaic.audio import build_mix
        wav = os.path.join(out_dir, f"{sid}_music_sfx.wav")
        cfg = {"duration": R.dur, "audio": dict(R.sb["audio"], narration_file="__none__")}
        build_mix(R.dir, cfg, wav)
        prev = os.path.join(out_dir, f"{sid}_{OW}x{OH}_preview.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", picture, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-shortest", "-movflags", "+faststart", prev], check=True)
        os.remove(wav)
        print(f"preview: {prev}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render a v2 storyboard (illustration plates + limited animation + motion graphics).

  python -m ghm2.render <episode_dir>                 # 540x960 preview + QC
  python -m ghm2.render <episode_dir> --final         # 1080x1920
  python -m ghm2.render <episode_dir> --still 7.5     # one PNG frame (preview size)

storyboard.json:
  fps, duration, comps[{id, start, end, kind: plate|map, bg, layers[{png, depth, blur, rigs[]}],
  camera{from{zoom,x,y}, to{...}}, overlays[], grade{}, map{...}}], transitions[{at, type, dur}],
  graphics[] (absolute-time text / timeline elements), captions (v1 format), audio (v1 format)
All times are absolute episode seconds so animation can be placed on narration words.
"""
import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mosaic import audio, captions, qc, text  # noqa: E402
from mosaic.fx import CinematicGrade  # noqa: E402
from mosaic.render import encoder_args, mux, pick_encoder  # noqa: E402
from mosaic.scene import Ctx  # noqa: E402

from ghm2 import mograph, overlays  # noqa: E402
from ghm2.anim import DW, Camera, smooth  # noqa: E402
from ghm2.puppet import Puppet  # noqa: E402

LOOKS = {
    "warm": dict(sat=1.22, vibrance=0.3, local=0.34, warm=(1.09, 1.0, 0.86), cool=(0.9, 0.95, 1.1)),
    "interior": dict(sat=1.2, vibrance=0.3, local=0.4, warm=(1.1, 1.0, 0.84), cool=(0.88, 0.94, 1.12)),
    "regal": dict(sat=1.24, vibrance=0.32, local=0.36, warm=(1.08, 1.0, 0.88), cool=(0.9, 0.95, 1.1)),
    "map": dict(sat=1.08, vibrance=0.2, local=0.2),
    "none": None,
}


def load_plate(path, scale):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    im = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
    if scale != 1.0:
        im = cv2.resize(im, (int(im.shape[1] * scale), int(im.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    f = im.astype(np.float32) / 255.0
    f[..., :3] *= f[..., 3:4]
    return f


class Comp:
    def __init__(self, ep, spec, W, H):
        self.spec, self.W, self.H = spec, W, H
        self.start, self.end = spec["start"], spec["end"]
        self.cam = Camera(dict(start=self.start, end=self.end, **spec.get("camera", {})), self.end)
        self.kind = spec.get("kind", "plate")
        self.layers = []
        if self.kind == "plate":
            for L in spec["layers"]:
                raw = cv2.imread(os.path.join(ep, L["png"]), cv2.IMREAD_UNCHANGED)
                pw = raw.shape[1]
                sc = min(1.0, W * Camera.BASE * 1.12 / pw)          # keep just enough resolution for the move
                plate = load_plate(os.path.join(ep, L["png"]), sc)
                rigs = [dict(r, **{k: _scale(r[k], sc) for k in ("eye", "center", "radius", "pivot") if k in r})
                        for r in L.get("rigs", [])]
                self.layers.append(dict(spec=L, plate=plate, pw=pw * sc, puppet=Puppet(plate, rigs) if rigs else None))
        else:
            self.map = mograph.Map(resolve_geo(spec["map"]), self.cam)
        self.fx = [overlays.build(o) for o in spec.get("overlays", [])]
        g = LOOKS[spec.get("look", "warm")]
        self.grade = CinematicGrade(**g) if g else None
        self.ctx = Ctx(W, H, 30)
        self.bg = np.array(spec.get("bg", (20, 16, 12)), np.float32) / 255

    def render(self, t):
        W, H = self.W, self.H
        frame = np.empty((H, W, 3), np.float32)
        frame[:] = self.bg
        cam = self.cam.at(t)
        if self.kind == "map":
            self.map(frame, t, W, H)
        for L in self.layers:
            img = L["puppet"].at(t) if L["puppet"] else L["plate"]
            M = self.cam.matrix(cam, L["spec"].get("depth", 1.0), L["pw"] / DW, W / DW,
                                cover=L["spec"].get("cover", True))
            out = cv2.warpAffine(img, M[:2], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(0, 0, 0, 0))
            b = L["spec"].get("blur", 0)
            if b:
                out = cv2.GaussianBlur(out, (0, 0), b * W / DW)
            frame *= 1 - out[..., 3:4]
            frame += out[..., :3]
        for f in self.fx:
            f(frame, t, W, H, cam)
        if self.grade:
            self.grade(frame, t, self.ctx, cam)
        return frame, cam


def resolve_geo(m):
    """Map data may name shared files in ghm2/data: land "europe_simplified", poly "file:key"."""
    m = dict(m)
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if isinstance(m.get("land"), str):
        m["land"] = json.load(open(os.path.join(data, m["land"] + ".json")))["polygons"]
    regs = []
    for r in m.get("regions", []):
        if isinstance(r["poly"], str):
            f, key = r["poly"].split(":")
            r = dict(r, poly=json.load(open(os.path.join(data, f + ".json")))[key])
        regs.append(r)
    m["regions"] = regs
    return m


def _scale(v, s):
    return [x * s for x in v]


class Episode:
    def __init__(self, ep, W, H):
        self.dir, self.W, self.H = ep, W, H
        self.cfg = json.load(open(os.path.join(ep, "storyboard.json"), encoding="utf-8"))
        self.comps = [Comp(ep, c, W, H) for c in self.cfg["comps"]]
        self.trans = sorted(self.cfg.get("transitions", []), key=lambda x: x["at"])
        self.graphics = [self._graphic(g) for g in self.cfg.get("graphics", [])]
        ctx = Ctx(W, H, self.cfg.get("fps", 30))
        cc = self.cfg.get("captions")
        self.caps = []
        if cc:
            cues = captions.build_groups(cc["groups"], os.path.join(ep, cc["transcript"]), os.path.join(ep, cc["words"]),
                                         spoken=cc.get("spoken"))
            self.cues = cues
            self.caps = [text.caption(ctx, c["text"], c["start"], c["end"], y=cc.get("y", 1410), size=cc.get("size", 60))
                         for c in cues]
        self.finish = [overlays.Vignette(self.cfg.get("vignette", 0.3)), overlays.Grain(self.cfg.get("grain", 0.014))]

    def _graphic(self, g):
        g = dict(g)
        kind = g.pop("type")
        if kind == "text":
            for k in ("color", "glow"):
                if k in g and g[k] is not None:
                    g[k] = tuple(g[k])
            return mograph.Text(**g)
        if kind == "timeline":
            return mograph.Timeline(**g)
        if kind == "title":
            return _V1Title(text.title(Ctx(self.W, self.H, 30), g["text"], g.get("sub"), g["start"], g["end"],
                                       g.get("y", 300), g.get("size", 96)))
        raise ValueError(kind)

    def comp_at(self, t):
        for i, c in enumerate(self.comps):
            if t < c.end or i == len(self.comps) - 1:
                return i
        return len(self.comps) - 1

    def frame(self, t):
        i = self.comp_at(t)
        f, cam = self.comps[i].render(t)
        for tr in self.trans:
            d = tr.get("dur", 0.4)
            if abs(t - tr["at"]) < d / 2:
                j = self.comp_at(tr["at"] + 1e-3)
                k = self.comp_at(tr["at"] - 1e-3)
                a, _ = self.comps[k].render(t)
                b, _ = self.comps[j].render(t)
                u = smooth((t - (tr["at"] - d / 2)) / d)
                f = transition(tr.get("type", "dissolve"), a, b, u)
        for g in self.graphics:
            g(f, t, self.W, self.H, cam)
        for c in self.caps:
            c.apply(f, t)
        for fx in self.finish:
            fx(f, t, self.W, self.H, cam)
        return np.clip(f, 0, 1)


class _V1Title:
    def __init__(self, ov):
        self.ov = ov

    def __call__(self, frame, t, W, H, cam):
        self.ov.apply(frame, t)


def transition(kind, a, b, u):
    if kind == "flash":
        f = a * (1 - u) + b * u
        f += (np.sin(np.pi * u) ** 2) * 0.55 * np.array([1.0, 0.86, 0.62], np.float32)
        return f
    if kind == "whip":
        W = a.shape[1]
        sh = int(W * u)
        k = max(1, int(W * 0.12 * np.sin(np.pi * u)))
        f = np.concatenate([a[:, sh:], b[:, :sh]], axis=1) if sh else a.copy()
        return cv2.blur(f, (k, 1))
    return a * (1 - u) + b * u


_EP = None


def _init(ep, W, H):
    global _EP
    _EP = Episode(ep, W, H)


def _work(i):
    f = _EP.frame(i / _EP.cfg.get("fps", 30))
    return (f * 255 + 0.5).astype(np.uint8).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--still", type=float)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out")
    a = ap.parse_args()
    ep = os.path.abspath(a.episode)
    cfg = json.load(open(os.path.join(ep, "storyboard.json"), encoding="utf-8"))
    W, H = (1080, 1920) if a.final else (540, 960)
    name = os.path.basename(ep.rstrip("/"))
    out_dir = a.out or os.path.join(ROOT, "output", "v2", name)
    os.makedirs(out_dir, exist_ok=True)
    if a.still is not None:
        e = Episode(ep, W, H)
        p = os.path.join(out_dir, f"still_{a.still:05.2f}.png")
        cv2.imwrite(p, cv2.cvtColor((e.frame(a.still) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(p)
        return
    t0 = time.time()
    fps, dur = cfg.get("fps", 30), cfg["duration"]
    n = int(round(dur * fps))
    q = "final" if a.final else "preview"
    tag = f"{name}_{q}_{W}x{H}"
    wav = os.path.join(out_dir, f"{name}_mix.wav")
    voice = audio.build_mix(ep, cfg, wav)
    enc = pick_encoder(True)
    silent = os.path.join(out_dir, f"{tag}_video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(fps), "-i", "-"] + encoder_args(enc, q) + ["-pix_fmt", "yuv420p", silent],
                          stdin=subprocess.PIPE)
    with mp.get_context("fork").Pool(a.workers, _init, (ep, W, H)) as pool:
        for k, buf in enumerate(pool.imap(_work, range(n), chunksize=4)):
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"[v2] frame {k}/{n}  {time.time() - t0:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    final = os.path.join(out_dir, f"{tag}.mp4")
    mux(silent, wav, final, cfg.get("audio", {}).get("loudness_lufs", -14))
    os.remove(silent)
    if cfg.get("captions"):
        cc = cfg["captions"]
        cues = captions.build_groups(cc["groups"], os.path.join(ep, cc["transcript"]), os.path.join(ep, cc["words"]),
                                     spoken=cc.get("spoken"))
        text.write_srt(cues, os.path.join(out_dir, f"{name}.en.srt"))
    rep = qc.run(final, cfg, os.path.join(out_dir, tag), W, H)
    rep.update(encoder=enc, narration=voice, render_seconds=round(time.time() - t0))
    json.dump(rep, open(os.path.join(out_dir, f"{tag}_qc.json"), "w"), indent=2)
    print(json.dumps(rep["checks"]))
    print("[qc] PASSED" if rep["passed"] else "[qc] ISSUES FOUND - see report", final, f"({rep['render_seconds']}s)")


if __name__ == "__main__":
    main()

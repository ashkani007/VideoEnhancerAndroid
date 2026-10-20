"""Episode timeline: scenes, transitions, overlays -> finished frames."""
import importlib.util
import json
import os

import numpy as np

from . import fx, text
from .geom import smoothstep
from .scene import Ctx


def load_config(ep_dir):
    with open(os.path.join(ep_dir, "episode.json"), encoding="utf-8") as f:
        return json.load(f)


def load_scenes_module(ep_dir, cfg):
    path = os.path.join(ep_dir, cfg.get("scenes_module", "scenes.py"))
    spec = importlib.util.spec_from_file_location("episode_scenes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Episode:
    def __init__(self, ep_dir, ctx, burn_subtitles=True, only_scenes=None):
        self.dir, self.ctx = ep_dir, ctx
        self.cfg = load_config(ep_dir)
        mod = load_scenes_module(ep_dir, self.cfg)
        self.timeline = self.cfg["scenes"]
        order = list(mod.SCENES)
        self.scenes = []
        for i, entry in enumerate(self.timeline):
            if only_scenes is None or i in only_scenes:
                self.scenes.append(order[i](ctx))
            else:
                self.scenes.append(None)
        self.transitions = []
        for tr in self.cfg.get("transitions", []):
            w = None
            if tr["type"] == "mosaic":
                w = fx.MosaicWipe(ctx, tile=tr.get("tile", 48), direction=tr.get("direction", (1, 0.3)),
                                  seed=int(tr["at"] * 10))
            self.transitions.append((tr, w))
        self.overlays = [text.from_spec(ctx, s) for s in self.cfg.get("titles", [])]
        if burn_subtitles:
            self.overlays += [text.subtitle(ctx, c["text"], c["start"], c["end"])
                              for c in self.cfg.get("subtitles", [])]
        self.duration = self.cfg["duration"]

    def _scene_index(self, t):
        for i, e in enumerate(self.timeline):
            if t < e["start"] + e["duration"]:
                return i
        return len(self.timeline) - 1

    def _render_scene(self, i, t):
        e = self.timeline[i]
        sc = self.scenes[i]
        if sc is None:
            return np.zeros((self.ctx.H, self.ctx.W, 3), np.float32)
        return sc.render(self.ctx, t - e["start"])

    def frame(self, t):
        out = None
        for tr, wipe in self.transitions:
            d = tr["duration"]
            if abs(t - tr["at"]) < d / 2:
                ia = self._scene_index(tr["at"] - 1e-3)
                ib = self._scene_index(tr["at"] + 1e-3)
                p = (t - (tr["at"] - d / 2)) / d
                a, b = self._render_scene(ia, t), self._render_scene(ib, t)
                if wipe is not None:
                    out = wipe.blend(a, b, p)
                else:
                    m = smoothstep(p)
                    out = a * (1 - m) + b * m
                break
        if out is None:
            out = self._render_scene(self._scene_index(t), t)
        if t < 0.4:
            out *= smoothstep(t / 0.4)
        for ov in self.overlays:
            ov.apply(out, t)
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def make_ctx(cfg, quality):
    fps = cfg.get("fps", 24)
    if quality == "final":
        return Ctx(1080, 1920, fps, ss=1.25)
    if quality == "draft":
        return Ctx(480, 854, fps, ss=1.25)
    return Ctx(720, 1280, fps, ss=1.25)

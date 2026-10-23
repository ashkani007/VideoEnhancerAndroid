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
        order = list(getattr(mod, "SHOTS", None) or mod.SCENES)
        with_dur = hasattr(mod, "SHOTS")
        self.scenes = []
        for i, entry in enumerate(self.timeline):
            if only_scenes is None or i in only_scenes:
                self.scenes.append(order[i](ctx, entry["duration"]) if with_dur else order[i](ctx))
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
        if hasattr(mod, "map_labels") and "map_labels" in self.cfg:
            ml = self.cfg["map_labels"]
            for name, x, y in mod.map_labels():
                self.overlays.append(text.note(ctx, name, ml["start"], ml["end"], y, 30, x, kind="label"))
        self.cues = self.subtitle_cues()
        if burn_subtitles:
            style = self.cfg.get("captions", {}).get("style", self.cfg.get("subtitle_style", "plate"))
            size = self.cfg.get("captions", {}).get("size", self.cfg.get("subtitle_size", 60))
            for c in self.cues:
                if style == "outline":
                    self.overlays.append(text.caption(ctx, c["text"], c["start"], c["end"], c.get("y", 1300), size))
                else:
                    self.overlays.append(text.subtitle(ctx, c["text"], c["start"], c["end"], c.get("y", 1300)))
        self.duration = self.cfg["duration"]

    def subtitle_cues(self):
        """Cues from forced-alignment word timestamps when configured, else from episode.json."""
        cc = self.cfg.get("captions")
        if not cc:
            return self.cfg.get("subtitles", [])
        from . import captions
        cues = captions.build_groups(cc["groups"], os.path.join(self.dir, cc["transcript"]),
                                     os.path.join(self.dir, cc["words"]), spoken=cc.get("spoken"))
        for c in cues:
            shot = self.timeline[self._scene_index(c["start"] + 0.05)]
            c["y"] = shot.get("cap_y", 1300)
        return cues

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

    def frame(self, t, solo=None):
        """solo=scene index renders that scene alone (no transitions), with soft clip edges."""
        if solo is not None:
            e = self.timeline[solo]
            out = self._render_scene(solo, t)
            edge = min(t - e["start"], e["start"] + e["duration"] - t)
            out *= smoothstep(edge / 0.25)
            for ov in self.overlays:
                ov.apply(out, t)
            return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
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
        if t < 0.2:
            out *= smoothstep(t / 0.2)
        for ov in self.overlays:
            ov.apply(out, t)
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def make_ctx(cfg, quality):
    fps = cfg.get("fps", 24)
    if quality == "final":
        return Ctx(1080, 1920, fps, ss=1.25)
    if quality == "draft":
        return Ctx(540, 960, fps, ss=1.25)
    return Ctx(720, 1280, fps, ss=1.25)

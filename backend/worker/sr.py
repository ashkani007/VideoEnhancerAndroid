"""Super-resolution engines and per-eye tiled inference (mirrors the Android core module).

Engines
  * OnnxEngine  — the converted Real-ESRGAN general v3 model via onnxruntime (CPU, or CUDA
                  when onnxruntime-gpu is installed). Verified by the test suite.
  * TorchEngine — the original Real-ESRGAN .pth checkpoints (SRVGGNetCompact) in PyTorch,
                  with deep network interpolation for denoise strength; CUDA when available.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


def regions(width: int, height: int, layout: str) -> list[Rect]:
    """Stereo eyes are separate regions so no convolution mixes the two eyes."""
    if layout == "SIDE_BY_SIDE":
        return [Rect(0, 0, width // 2, height), Rect(width // 2, 0, width - width // 2, height)]
    if layout == "TOP_BOTTOM":
        return [Rect(0, 0, width, height // 2), Rect(0, height // 2, width, height - height // 2)]
    return [Rect(0, 0, width, height)]


def axis(length: int, window: int, overlap: int) -> list[tuple[int, int, int]]:
    """(window_start, core_start, core_end) along one axis; cores partition [0, length)."""
    if length <= window:
        return [(0, 0, length)]
    stride = window - 2 * overlap
    starts, s = [], 0
    while s + window < length:
        starts.append(s)
        s += stride
    starts.append(length - window)
    bounds = [0] + [(starts[i + 1] + starts[i] + window) // 2 for i in range(len(starts) - 1)] + [length]
    return [(st, bounds[i], bounds[i + 1]) for i, st in enumerate(starts)]


def tiles(width: int, height: int, layout: str, window: int, overlap: int):
    for r in regions(width, height, layout):
        for wy, cy0, cy1 in axis(r.h, window, overlap):
            for wx, cx0, cx1 in axis(r.w, window, overlap):
                yield r, Rect(r.x + wx, r.y + wy, window, window), Rect(r.x + cx0, r.y + cy0, cx1 - cx0, cy1 - cy0)


def extract_window(frame: np.ndarray, win: Rect, region: Rect) -> np.ndarray:
    """HWC uint8 frame -> CHW float32 window with replicate padding inside the region only."""
    ys = np.clip(np.arange(win.y, win.y + win.h), region.y, region.bottom - 1)
    xs = np.clip(np.arange(win.x, win.x + win.w), region.x, region.right - 1)
    return np.ascontiguousarray(frame[np.ix_(ys, xs)].transpose(2, 0, 1), dtype=np.float32) / 255.0


def area_resize(img: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Exact coverage-weighted downscaling of a CHW float image (same as PixelOps.areaResize)."""
    def weights(n_in: int, n_out: int) -> np.ndarray:
        f = n_in / n_out
        m = np.zeros((n_out, n_in), dtype=np.float32)
        for o in range(n_out):
            a, b = o * f, (o + 1) * f
            for i in range(int(np.floor(a)), min(int(np.ceil(b)), n_in)):
                m[o, i] = max(0.0, min(b, i + 1) - max(a, i))
        return m / f
    c, h, w = img.shape
    return np.einsum("oh,chw,pw->cop", weights(h, out_h), img, weights(w, out_w), optimize=True)


class Engine:
    scale = 4
    window = 192

    def run(self, x: np.ndarray) -> np.ndarray:  # CHW float -> CHW float (x4)
        raise NotImplementedError


class NearestEngine(Engine):
    """Exact reference engine for tests (not used in production)."""

    def __init__(self, window: int = 64):
        self.window = window

    def run(self, x):
        return x.repeat(4, axis=1).repeat(4, axis=2)


class OnnxEngine(Engine):
    def __init__(self, model_path: str, expected_sha256: str | None, window: int = 192):
        import onnxruntime as ort

        if expected_sha256:
            digest = hashlib.sha256(open(model_path, "rb").read()).hexdigest()
            if digest != expected_sha256:
                raise RuntimeError(f"Model integrity check failed for {model_path}")
        providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.window = window
        self.providers = self.session.get_providers()

    def run(self, x):
        return self.session.run(["output"], {"input": x[None]})[0][0]


class TorchEngine(Engine):
    """Original checkpoints in PyTorch. Requires the GPU worker image (torch installed)."""

    def __init__(self, x4v3_path: str, wdn_path: str, denoise_strength: float, window: int = 256):
        import torch
        from torch import nn
        from torch.nn import functional as F

        class SRVGGNetCompact(nn.Module):  # realesrgan/archs/srvgg_arch.py (BSD-3-Clause)
            def __init__(self, num_feat=64, num_conv=32, upscale=4):
                super().__init__()
                self.upscale = upscale
                self.body = nn.ModuleList([nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)])
                for _ in range(num_conv):
                    self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
                    self.body.append(nn.PReLU(num_parameters=num_feat))
                self.body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
                self.upsampler = nn.PixelShuffle(upscale)

            def forward(self, x):
                out = x
                for layer in self.body:
                    out = layer(out)
                return self.upsampler(out) + F.interpolate(x, scale_factor=self.upscale, mode="nearest")

        a = torch.load(x4v3_path, map_location="cpu", weights_only=True)["params"]
        b = torch.load(wdn_path, map_location="cpu", weights_only=True)["params"]
        s = float(min(max(denoise_strength, 0.0), 1.0))
        state = {k: s * a[k] + (1 - s) * b[k] for k in a}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.half = self.device.type == "cuda"
        net = SRVGGNetCompact()
        net.load_state_dict(state, strict=True)
        self.net = net.eval().to(self.device)
        if self.half:
            self.net = self.net.half()
        self.torch = torch
        self.window = window

    def run(self, x):
        t = self.torch.from_numpy(x[None]).to(self.device)
        if self.half:
            t = t.half()
        with self.torch.inference_mode():
            y = self.net(t).float().clamp_(0, 1)
        return y[0].cpu().numpy()


def upscale_frame(engine: Engine, frame: np.ndarray, layout: str, out_w: int, out_h: int, overlap: int = 16) -> np.ndarray:
    """HWC uint8 -> HWC uint8 at (out_h, out_w). Same algorithm as core FrameUpscaler."""
    h, w, _ = frame.shape
    s = engine.scale
    if out_w > w * s or out_h > h * s or out_w < w or out_h < h:
        raise ValueError("output size must be between 1x and the model's native scale")
    sx, sy = out_w / w, out_h / h
    out = np.empty((out_h, out_w, 3), dtype=np.uint8)
    for region, win, core in tiles(w, h, layout, engine.window, overlap):
        y = engine.run(extract_window(frame, win, region))
        c = y[:, (core.y - win.y) * s:(core.bottom - win.y) * s, (core.x - win.x) * s:(core.right - win.x) * s]
        x0, x1 = round(core.x * sx), round(core.right * sx)
        y0, y1 = round(core.y * sy), round(core.bottom * sy)
        if (x1 - x0, y1 - y0) != (core.w * s, core.h * s):
            c = area_resize(c, y1 - y0, x1 - x0)
        out[y0:y1, x0:x1] = np.clip(np.rint(c.transpose(1, 2, 0) * 255.0), 0, 255).astype(np.uint8)
    return out


def load_engine(settings, denoise: bool) -> Engine:
    if settings.sr_engine == "torch":
        return TorchEngine(
            os.path.join(settings.model_dir, "realesr-general-x4v3.pth"),
            os.path.join(settings.model_dir, "realesr-general-wdn-x4v3.pth"),
            1.0 if denoise else 0.0,
            window=settings.tile,
        )
    manifest = json.load(open(os.path.join(settings.model_dir, "models.json")))
    want = 1.0 if denoise else 0.0
    m = next(m for m in manifest["models"] if abs(m["denoise_strength"] - want) < 1e-6)
    eng = OnnxEngine(os.path.join(settings.model_dir, m["file"]), m["sha256"], window=settings.tile)
    eng.model_info = m  # type: ignore[attr-defined]
    return eng

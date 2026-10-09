#!/usr/bin/env python3
"""Convert Real-ESRGAN "general v3" compact checkpoints (SRVGGNetCompact) to ONNX.

Reproducible, torch-free conversion:
  * reads the official PyTorch checkpoints (zip + pickle) with a *restricted*
    unpickler that only rebuilds float tensors (no arbitrary code execution),
  * optionally blends the two published checkpoints with deep network
    interpolation (DNI), exactly as Real-ESRGAN's own `--denoise_strength`,
  * builds the ONNX graph for the published architecture
    (realesrgan/archs/srvgg_arch.py): conv3x3 + PReLU blocks, a final conv to
    3*s*s channels, PixelShuffle (DepthToSpace CRD) and a nearest-upsampled
    input residual; output clipped to [0, 1].

Weights: https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0
  realesr-general-x4v3.pth      sha256 8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292
  realesr-general-wdn-x4v3.pth  sha256 1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca
License: BSD-3-Clause (Real-ESRGAN, Xintao Wang et al.).

Usage:
  convert_realesrgan_onnx.py --x4v3 realesr-general-x4v3.pth --wdn realesr-general-wdn-x4v3.pth \
      --denoise-strength 1.0 --out realesr_general_x4v3_dn100.onnx
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pickle
import re
import sys
import zipfile

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

EXPECTED_SHA256 = {
    "realesr-general-x4v3.pth": "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292",
    "realesr-general-wdn-x4v3.pth": "1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _StorageRef:
    def __init__(self, key: str, dtype: str):
        self.key, self.dtype = key, dtype


def _rebuild_tensor_v2(storage, offset, size, stride, *_):
    return ("tensor", storage, offset, tuple(size), tuple(stride))


class _Unpickler(pickle.Unpickler):
    """Allows only the globals a plain float state_dict needs."""

    ALLOWED = {
        ("collections", "OrderedDict"): collections.OrderedDict,
        ("torch._utils", "_rebuild_tensor_v2"): _rebuild_tensor_v2,
        ("torch", "FloatStorage"): "float32",
    }

    def find_class(self, module, name):
        try:
            return self.ALLOWED[(module, name)]
        except KeyError:
            raise pickle.UnpicklingError(f"Refusing to load global {module}.{name}") from None

    def persistent_load(self, pid):
        kind, storage_type, key, _location, _numel = pid
        if kind != "storage" or storage_type != "float32":
            raise pickle.UnpicklingError(f"Unsupported storage {pid}")
        return _StorageRef(key, storage_type)


def load_state_dict(path: str) -> dict[str, np.ndarray]:
    with zipfile.ZipFile(path) as z:
        root = z.namelist()[0].split("/")[0]
        obj = _Unpickler(z.open(f"{root}/data.pkl")).load()
        raw = {}

        def materialize(t):
            _, ref, offset, size, stride = t
            if ref.key not in raw:
                raw[ref.key] = np.frombuffer(z.read(f"{root}/data/{ref.key}"), dtype="<f4")
            buf = raw[ref.key]
            arr = np.lib.stride_tricks.as_strided(
                buf[offset:], shape=size, strides=tuple(s * 4 for s in stride)
            )
            return np.array(arr, dtype=np.float32)

        params = obj.get("params", obj.get("params_ema", obj))
        return {k: materialize(v) for k, v in params.items()}


def architecture(sd: dict[str, np.ndarray]) -> tuple[int, int, int]:
    """Returns (num_feat, num_conv, upscale) inferred from the weights."""
    idx = sorted({int(m.group(1)) for k in sd if (m := re.match(r"body\.(\d+)\.", k))})
    convs = [i for i in idx if sd[f"body.{i}.weight"].ndim == 4]
    num_feat = sd["body.0.weight"].shape[0]
    last = sd[f"body.{convs[-1]}.weight"]
    upscale = int(round((last.shape[0] / 3) ** 0.5))
    return num_feat, len(convs) - 2, upscale


def blend(a: dict, b: dict, wa: float) -> dict:
    assert a.keys() == b.keys(), "checkpoints differ in structure"
    return {k: (wa * a[k] + (1.0 - wa) * b[k]).astype(np.float32) for k in a}


def build_onnx(sd: dict[str, np.ndarray], meta: dict) -> onnx.ModelProto:
    num_feat, num_conv, scale = architecture(sd)
    nodes, inits = [], []
    x = "input"
    i = 0
    n_body = max(int(k.split(".")[1]) for k in sd if k.startswith("body.")) + 1
    while i < n_body:
        w = sd[f"body.{i}.weight"]
        if w.ndim == 4:
            inits += [numpy_helper.from_array(w, f"w{i}"), numpy_helper.from_array(sd[f"body.{i}.bias"], f"b{i}")]
            nodes.append(helper.make_node("Conv", [x, f"w{i}", f"b{i}"], [f"c{i}"], kernel_shape=[3, 3], pads=[1, 1, 1, 1]))
            x = f"c{i}"
        else:  # PReLU, one slope per channel
            inits.append(numpy_helper.from_array(w.reshape(-1, 1, 1), f"a{i}"))
            nodes.append(helper.make_node("PRelu", [x, f"a{i}"], [f"p{i}"]))
            x = f"p{i}"
        i += 1
    nodes.append(helper.make_node("DepthToSpace", [x], ["shuffled"], blocksize=scale, mode="CRD"))
    inits.append(numpy_helper.from_array(np.array([1, 1, scale, scale], dtype=np.float32), "scales"))
    nodes.append(helper.make_node(
        "Resize", ["input", "", "scales"], ["base"], mode="nearest",
        coordinate_transformation_mode="asymmetric", nearest_mode="floor",
    ))
    nodes.append(helper.make_node("Add", ["shuffled", "base"], ["sum"]))
    inits += [numpy_helper.from_array(np.array(0.0, np.float32), "lo"), numpy_helper.from_array(np.array(1.0, np.float32), "hi")]
    nodes.append(helper.make_node("Clip", ["sum", "lo", "hi"], ["output"]))

    graph = helper.make_graph(
        nodes, "srvgg_compact",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, "h", "w"])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3, "h4", "w4"])],
        inits,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], producer_name="vrvision-convert")
    model.ir_version = 8
    meta = dict(meta, num_feat=num_feat, num_conv=num_conv, scale=scale)
    for k, v in meta.items():
        entry = model.metadata_props.add()
        entry.key, entry.value = k, str(v)
    onnx.checker.check_model(model)
    return model


def reference_forward(sd: dict[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    """Independent numpy implementation of SRVGGNetCompact used to validate the ONNX graph."""
    _, _, scale = architecture(sd)
    out = x
    n_body = max(int(k.split(".")[1]) for k in sd if k.startswith("body.")) + 1
    for i in range(n_body):
        w = sd[f"body.{i}.weight"]
        if w.ndim == 4:
            out = _conv3x3(out, w, sd[f"body.{i}.bias"])
        else:
            a = w.reshape(1, -1, 1, 1)
            out = np.where(out >= 0, out, a * out)
    n, c, h, wd = out.shape
    oc = c // (scale * scale)
    out = out.reshape(n, oc, scale, scale, h, wd).transpose(0, 1, 4, 2, 5, 3).reshape(n, oc, h * scale, wd * scale)
    base = x.repeat(scale, axis=2).repeat(scale, axis=3)
    return np.clip(out + base, 0.0, 1.0)


def _conv3x3(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    n, c, h, wd = x.shape
    p = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    cols = np.stack([p[:, :, dy:dy + h, dx:dx + wd] for dy in range(3) for dx in range(3)], axis=2)  # n,c,9,h,w
    wf = w.reshape(w.shape[0], c, 9)
    return np.einsum("nckhw,ock->nohw", cols, wf, optimize=True) + b.reshape(1, -1, 1, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--x4v3", required=True)
    ap.add_argument("--wdn", required=True)
    ap.add_argument("--denoise-strength", type=float, default=1.0,
                    help="1.0 = realesr-general-x4v3 (strong denoise), 0.0 = wdn (weak denoise); as in Real-ESRGAN")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", help="write model metadata JSON here")
    args = ap.parse_args()

    for path in (args.x4v3, args.wdn):
        name = path.rsplit("/", 1)[-1]
        digest = sha256(path)
        if EXPECTED_SHA256.get(name) != digest:
            print(f"checksum mismatch for {name}: {digest}", file=sys.stderr)
            return 1

    s = min(max(args.denoise_strength, 0.0), 1.0)
    sd = blend(load_state_dict(args.x4v3), load_state_dict(args.wdn), s)
    meta = {
        "model_name": "Real-ESRGAN general v3 (SRVGGNetCompact)",
        "model_version": "v0.2.5.0",
        "denoise_strength": s,
        "source_weights": "realesr-general-x4v3.pth, realesr-general-wdn-x4v3.pth (DNI blend)",
        "license": "BSD-3-Clause",
        "input": "float32 NCHW RGB in [0,1]",
        "output": "float32 NCHW RGB in [0,1], 4x spatial size",
    }
    model = build_onnx(sd, meta)
    onnx.save(model, args.out)
    full_meta = {**meta, "file": args.out.rsplit("/", 1)[-1], "sha256": sha256(args.out),
                 **{p.key: p.value for p in model.metadata_props if p.key in ("num_feat", "num_conv", "scale")}}
    if args.json:
        with open(args.json, "w") as f:
            json.dump(full_meta, f, indent=2)
    print(json.dumps(full_meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

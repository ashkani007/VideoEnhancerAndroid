#!/usr/bin/env python3
"""Real-ESRGAN x4plus upscaling on the CPU without PyTorch (cloud container fallback for small plates).

  python tools/esrgan_cpu.py <weights RealESRGAN_x4plus.pth> <in.png> <out.png> [--scale 2] [--tile 192]

- The weights must match the SHA-256 pinned in comfyui/windows/ghm_install.lock.json, otherwise nothing is loaded.
- The .pth (a zip with a pickle) is read with a restricted unpickler: only OrderedDict and plain float tensors are
  rebuilt, every other global is refused, so no code from the file is executed.
- The RRDBNet graph (23 RRDB blocks) is built as ONNX and run with onnxruntime, tile by tile with overlap.
- Output: x4 result resized to --scale (default 2x) with INTER_AREA. Licence of the model: BSD-3-Clause.
The PC worker's `upscale2x` job does the same on the GPU; this is for stand-ins and crops when the PC is not available.
"""
import argparse
import collections
import hashlib
import json
import os
import pickle
import sys
import time
import zipfile

import cv2
import numpy as np

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(GHM, "comfyui", "windows", "ghm_install.lock.json")


def pinned_sha():
    lock = json.load(open(LOCK))
    for m in lock["models"]:
        if "RealESRGAN_x4plus" in json.dumps(m):
            return m["sha256"]
    raise SystemExit("Real-ESRGAN entry not found in the lock file")


def load_pth(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != pinned_sha():
        raise SystemExit(f"STOPPED: {path} SHA-256 {h} does not match the pinned hash")
    z = zipfile.ZipFile(path)
    root = z.namelist()[0].split("/")[0]

    def storage(key, numel):
        return np.frombuffer(z.read(f"{root}/data/{key}"), np.float32)[:numel]

    def rebuild(stor, offset, size, stride, *_):
        n = int(np.prod(size)) if size else 1
        arr = stor[offset:offset + n] if offset or len(stor) != n else stor
        return np.lib.stride_tricks.as_strided(stor[offset:], size, [s * 4 for s in stride]).copy() if size else arr.copy()

    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if (mod, name) == ("collections", "OrderedDict"):
                return collections.OrderedDict
            if (mod, name) == ("torch._utils", "_rebuild_tensor_v2"):
                return rebuild
            if (mod, name) == ("torch", "FloatStorage"):
                return "float32"
            raise pickle.UnpicklingError(f"refused global {mod}.{name}")

        def persistent_load(self, pid):
            _, dtype, key, _, numel = pid
            if dtype != "float32":
                raise pickle.UnpicklingError("only float32 storages are allowed")
            return storage(key, numel)
    sd = U(z.open(f"{root}/data.pkl")).load()
    return sd.get("params_ema", sd.get("params", sd))


def build_model(sd):
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    nodes, inits = [], []
    cnt = [0]

    def nm(p):
        cnt[0] += 1
        return f"{p}_{cnt[0]}"

    def conv(x, key, act=False):
        w, b = sd[key + ".weight"], sd[key + ".bias"]
        inits.extend([numpy_helper.from_array(w.astype(np.float32), key + ".weight"), numpy_helper.from_array(b.astype(np.float32), key + ".bias")])
        y = nm("conv")
        nodes.append(helper.make_node("Conv", [x, key + ".weight", key + ".bias"], [y], pads=[1, 1, 1, 1], kernel_shape=[3, 3]))
        if act:
            z = nm("lrelu")
            nodes.append(helper.make_node("LeakyRelu", [y], [z], alpha=0.2))
            return z
        return y

    def const(v):
        n = nm("c")
        inits.append(numpy_helper.from_array(np.array(v, np.float32), n))
        return n
    c02 = const(0.2)

    def axpy(a, x):                      # a*0.2 + x
        m, s = nm("mul"), nm("add")
        nodes.append(helper.make_node("Mul", [a, c02], [m]))
        nodes.append(helper.make_node("Add", [m, x], [s]))
        return s

    def rdb(x, p):
        feats = [x]
        for i in range(1, 6):
            inp = feats[0] if len(feats) == 1 else nm("cat")
            if len(feats) > 1:
                nodes.append(helper.make_node("Concat", feats, [inp], axis=1))
            y = conv(inp, f"{p}.conv{i}", act=i < 5)
            feats.append(y)
        return axpy(feats[-1], x)

    def up(x):
        y = nm("up")
        nodes.append(helper.make_node("Resize", [x, "", const([1, 1, 2, 2])], [y], mode="nearest"))
        return y
    feat = conv("input", "conv_first")
    x = feat
    nb = len({k.split(".")[1] for k in sd if k.startswith("body.")})
    for i in range(nb):
        y = x
        for r in (1, 2, 3):
            y = rdb(y, f"body.{i}.rdb{r}")
        x = axpy(y, x)
    body = conv(x, "conv_body")
    s = nm("add")
    nodes.append(helper.make_node("Add", [feat, body], [s]))
    f = conv(up(s), "conv_up1", True)
    f = conv(up(f), "conv_up2", True)
    f = conv(f, "conv_hr", True)
    out = conv(f, "conv_last")
    nodes.append(helper.make_node("Identity", [out], ["output"]))
    g = helper.make_graph(nodes, "rrdbnet", [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, None, None])],
                          [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3, None, None])], inits)
    return helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)], ir_version=8).SerializeToString()


def upscale(weights, img_bgr, tile=192, pad=12):
    import onnxruntime as ort
    sess = ort.InferenceSession(build_model(load_pth(weights)), providers=["CPUExecutionProvider"])
    x = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255
    _, _, H, W = x.shape
    out = np.zeros((3, H * 4, W * 4), np.float32)
    t0 = time.time()
    for y0 in range(0, H, tile):
        for x0 in range(0, W, tile):
            y1, x1 = min(H, y0 + tile), min(W, x0 + tile)
            ya, xa, yb, xb = max(0, y0 - pad), max(0, x0 - pad), min(H, y1 + pad), min(W, x1 + pad)
            r = sess.run(None, {"input": x[:, :, ya:yb, xa:xb]})[0][0]
            out[:, y0 * 4:y1 * 4, x0 * 4:x1 * 4] = r[:, (y0 - ya) * 4:(y0 - ya + y1 - y0) * 4, (x0 - xa) * 4:(x0 - xa + x1 - x0) * 4]
        print(f"  rows {y1}/{H} {time.time() - t0:.0f}s", flush=True)
    return cv2.cvtColor((np.clip(out.transpose(1, 2, 0), 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--tile", type=int, default=192)
    a = ap.parse_args()
    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"cannot read {a.src}")
    big = upscale(a.weights, img, a.tile)
    H, W = img.shape[:2]
    if a.scale != 4:
        big = cv2.resize(big, (int(round(W * a.scale)), int(round(H * a.scale))), interpolation=cv2.INTER_AREA)
    cv2.imwrite(a.dst, big)
    print(f"{a.src} {W}x{H} -> {a.dst} {big.shape[1]}x{big.shape[0]}")


if __name__ == "__main__":
    main()

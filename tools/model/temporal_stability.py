#!/usr/bin/env python3
"""Temporal stability check for per-frame super resolution.

A static scene (skimage 'astronaut', NASA, public domain) is downscaled 2x and given fresh
Gaussian noise every frame, like sensor noise in a locked-off shot. Because the scene does not
move, any frame-to-frame change in the output is flicker. We report the mean absolute
frame-to-frame difference (on a 0-255 scale) of:

  * bicubic 2x upscaling of the noisy frames (reference: noise passes straight through),
  * the AI model run per frame, output area-resampled from 4x to 2x (the app's pipeline).

Per-frame (image) SR models have no temporal memory, so this measures how much they amplify
or suppress frame-to-frame noise; it does not measure motion-related artefacts.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import onnxruntime as ort
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--sigma", type=float, default=4.0, help="noise std on the 0-255 scale")
    args = ap.parse_args()

    import skimage.data as data

    hr = data.astronaut()[96:352, 96:352]  # 256x256 static scene
    lr = np.asarray(Image.fromarray(hr).resize((128, 128), Image.BICUBIC)).astype(np.float32)
    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(0)

    bic, sr = [], []
    for _ in range(args.frames):
        noisy = np.clip(lr + rng.normal(0, args.sigma, lr.shape), 0, 255)
        bic.append(np.asarray(Image.fromarray(noisy.round().astype(np.uint8)).resize((256, 256), Image.BICUBIC)).astype(np.float32))
        x = (noisy / 255.0).transpose(2, 0, 1)[None].astype(np.float32)
        y = sess.run(["output"], {"input": x})[0][0]  # 3x512x512
        y2 = y.reshape(3, 256, 2, 256, 2).mean(axis=(2, 4))  # exact area 4x -> 2x
        sr.append(y2.transpose(1, 2, 0) * 255.0)

    def flicker(seq):
        return float(np.mean([np.abs(seq[i + 1] - seq[i]).mean() for i in range(len(seq) - 1)]))

    report = {
        "model": args.onnx.rsplit("/", 1)[-1],
        "noise_sigma": args.sigma,
        "frames": args.frames,
        "flicker_bicubic": round(flicker(bic), 3),
        "flicker_model": round(flicker(sr), 3),
        "error_vs_clean_bicubic": round(float(np.mean([np.abs(b - hr).mean() for b in bic])), 2),
        "error_vs_clean_model": round(float(np.mean([np.abs(s - hr).mean() for s in sr])), 2),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

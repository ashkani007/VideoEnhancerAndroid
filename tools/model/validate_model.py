#!/usr/bin/env python3
"""Validate a converted SRVGGNetCompact ONNX model.

1. Graph correctness: ONNX Runtime output vs the independent numpy reference
   implementation in convert_realesrgan_onnx.py (same weights, random input).
2. Real super resolution: photos are downscaled 4x (bicubic), super-resolved,
   and compared with the originals. Reports PSNR for the model and for plain
   bicubic/Lanczos upscaling, plus a gradient-energy sharpness ratio. A GAN-trained
   model is not PSNR-optimised, so PSNR is expected near bicubic; the check guards
   against a broken conversion (which yields structured garbage, PSNR << bicubic).
3. Stereo consistency: an SBS frame made of identical eyes must produce identical
   eyes when each eye is processed as its own region (as the app and worker do).
4. Host CPU timing for a 128x128 tile (host only; NOT a phone benchmark).

Test images: scikit-image sample data (astronaut: NASA, public domain;
coffee, chelsea: CC0) — see skimage.data documentation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import onnxruntime as ort
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert_realesrgan_onnx as conv  # noqa: E402


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(1.0 / mse)


def grad_energy(img: np.ndarray) -> float:
    gx = np.diff(img, axis=1)
    gy = np.diff(img, axis=0)
    return float(np.mean(gx ** 2) + np.mean(gy ** 2))


def run(sess: ort.InferenceSession, rgb01_hwc: np.ndarray) -> np.ndarray:
    x = np.ascontiguousarray(rgb01_hwc.transpose(2, 0, 1)[None].astype(np.float32))
    return sess.run(["output"], {"input": x})[0][0].transpose(1, 2, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--x4v3", required=True)
    ap.add_argument("--wdn", required=True)
    ap.add_argument("--denoise-strength", type=float, required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    report: dict = {"model": os.path.basename(args.onnx), "onnxruntime": ort.__version__}

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    sess = ort.InferenceSession(args.onnx, opts, providers=["CPUExecutionProvider"])

    # 1. ONNX vs numpy reference.
    sd = conv.blend(conv.load_state_dict(args.x4v3), conv.load_state_dict(args.wdn), args.denoise_strength)
    rng = np.random.default_rng(0)
    x = rng.random((1, 3, 24, 20), dtype=np.float32)
    ref = conv.reference_forward(sd, x)
    got = sess.run(["output"], {"input": x})[0]
    report["max_abs_diff_vs_numpy_reference"] = float(np.max(np.abs(ref - got)))
    report["output_shape"] = list(got.shape)
    ok_graph = got.shape == (1, 3, 96, 80) and report["max_abs_diff_vs_numpy_reference"] < 1e-4

    # 2. Real SR on photos.
    import skimage.data as data

    photos = {"astronaut": data.astronaut(), "coffee": data.coffee(), "chelsea": data.chelsea()}
    quality = {}
    ok_quality = True
    for name, hr in photos.items():
        h, w = (hr.shape[0] // 4) * 4, (hr.shape[1] // 4) * 4
        hr = hr[:h, :w]
        lr = np.asarray(Image.fromarray(hr).resize((w // 4, h // 4), Image.BICUBIC))
        sr = run(sess, lr.astype(np.float32) / 255.0)
        bic = np.asarray(Image.fromarray(lr).resize((w, h), Image.BICUBIC)).astype(np.float32) / 255.0
        lan = np.asarray(Image.fromarray(lr).resize((w, h), Image.LANCZOS)).astype(np.float32) / 255.0
        hrf = hr.astype(np.float32) / 255.0
        b = 8  # ignore borders
        crop = (slice(b, -b), slice(b, -b))
        q = {
            "psnr_model": round(psnr(sr[crop], hrf[crop]), 2),
            "psnr_bicubic": round(psnr(bic[crop], hrf[crop]), 2),
            "psnr_lanczos": round(psnr(lan[crop], hrf[crop]), 2),
            "sharpness_ratio_model_vs_hr": round(grad_energy(sr[crop]) / grad_energy(hrf[crop]), 3),
            "sharpness_ratio_bicubic_vs_hr": round(grad_energy(bic[crop]) / grad_energy(hrf[crop]), 3),
        }
        quality[name] = q
        ok_quality &= q["psnr_model"] > q["psnr_bicubic"] - 2.5 and q["sharpness_ratio_model_vs_hr"] > q["sharpness_ratio_bicubic_vs_hr"]
        strip = np.concatenate([bic, sr, hrf], axis=1)
        Image.fromarray((np.clip(strip, 0, 1) * 255).round().astype(np.uint8)).save(
            os.path.join(args.out_dir, f"{name}_bicubic_model_original.png"))
    report["quality_4x"] = quality

    # 3. Stereo: identical eyes processed as separate regions stay identical.
    eye = data.chelsea()[:64, :96].astype(np.float32) / 255.0
    left, right = run(sess, eye), run(sess, eye.copy())
    report["stereo_identical_eyes_max_diff"] = float(np.max(np.abs(left - right)))
    ok_stereo = report["stereo_identical_eyes_max_diff"] == 0.0

    # 4. Host timing.
    tile = rng.random((1, 3, 128, 128), dtype=np.float32)
    sess.run(["output"], {"input": tile})
    t0 = time.perf_counter()
    n = 5
    for _ in range(n):
        sess.run(["output"], {"input": tile})
    report["host_cpu_ms_per_128px_tile"] = round((time.perf_counter() - t0) / n * 1000, 1)
    report["host_note"] = "Host x86 CPU, 4 threads. Not representative of phone performance."

    report["passed"] = bool(ok_graph and ok_quality and ok_stereo)
    print(json.dumps(report, indent=2))
    with open(os.path.join(args.out_dir, report["model"] + ".validation.json"), "w") as f:
        json.dump(report, f, indent=2)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

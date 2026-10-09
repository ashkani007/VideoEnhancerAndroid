# AI model integration

## What is used

| | |
|---|---|
| Model | Real-ESRGAN "general v3" compact network (`SRVGGNetCompact`, 64 features, 32 conv blocks, 4× PixelShuffle, nearest-upsampled residual) |
| Source weights | `realesr-general-x4v3.pth`, `realesr-general-wdn-x4v3.pth` from the official [Real-ESRGAN v0.2.5.0 release](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0) (BSD-3-Clause) |
| Parameters | ~1.2 M; 4.86 MB per FP32 ONNX file |
| Native scale | 4×. The app's 2× default is produced by running the 4× network and **area-downsampling** its output to 2× (the same approach as Real-ESRGAN's own `--outscale`). This is real AI super resolution followed by an exact box filter, not bicubic interpolation. |
| Denoising | The two published checkpoints blended with deep network interpolation, exactly as Real-ESRGAN's `--denoise_strength`: **AI denoise on** = strength 1.0 (`realesr-general-x4v3`, strong denoise), **off** = strength 0.0 (`wdn` = weak-denoise variant, keeps more grain). Denoising and super resolution happen in the same network; "off" still denoises somewhat. |
| On-device runtime | ONNX Runtime Mobile for Android 1.31.0, default CPU execution provider |
| Cloud runtime | onnxruntime (CPU, or CUDA with onnxruntime-gpu) or PyTorch with the original `.pth` (GPU image) |

### Why ONNX Runtime instead of LiteRT

LiteRT is the default recommendation for Android, but in this project's build environment
Google's Maven repository was not reachable, so LiteRT artifacts could neither be resolved nor
verified, and no PyTorch→LiteRT converter could be installed. ONNX Runtime is on Maven Central,
and the exact same runtime version (1.31.0) is available for the host, so the shipped `.onnx`
files were validated with the same engine that runs on the phone. The model adapter is behind
the `SrEngine` interface (`android/core/.../FrameUpscaler.kt`); a LiteRT engine can be added
without touching the pipeline.

GPU/NPU execution providers (NNAPI, QNN, XNNPACK EP) are **not enabled** because none has been
benchmarked or validated on target hardware. The CPU provider is used.

## Conversion (reproducible)

`tools/model/convert_realesrgan_onnx.py`:

1. Verifies the SHA-256 of both checkpoints.
2. Reads the PyTorch zip/pickle with a **restricted unpickler** (only float tensor
   reconstruction is allowed; no arbitrary code execution) — no PyTorch needed.
3. Blends the checkpoints (DNI) for the requested denoise strength.
4. Builds the ONNX graph (opset 17): Conv/PRelu chain → DepthToSpace (CRD = PixelShuffle) →
   + Resize(nearest, asymmetric, floor) of the input → Clip[0,1]. Metadata (name, version,
   denoise strength, license) is embedded in the model.

CI re-runs the conversion from the downloaded checkpoints and asserts the result is
**byte-identical** to the committed models.

## Validation (`tools/model/validate_model.py`, results in `docs/validation/`)

| Check | dn100 (denoise on) | dn0 (denoise off) |
|---|---|---|
| Max abs difference, ONNX Runtime vs independent numpy implementation | 1.7e-6 | 1.1e-5 |
| 4× PSNR on photos (model / bicubic), astronaut | 23.37 / 25.28 dB | 23.71 / 25.28 dB |
| coffee | 25.32 / 25.78 dB | 25.77 / 25.78 dB |
| chelsea | 28.24 / 29.92 dB | 28.71 / 29.92 dB |
| Gradient energy vs ground truth (model / bicubic), astronaut | 0.96 / 0.21 | 0.86 / 0.21 |
| Identical stereo eyes → identical outputs | exact | exact |
| Host CPU time per 128×128 tile (x86, 4 threads; **not a phone number**) | 192 ms | 190 ms |

Interpretation: as expected for a GAN-trained model, PSNR is slightly *below* bicubic while the
output is 3–4.5× sharper (closer to the real image's detail energy). Visual inspection
(`docs/validation/astronaut_crop_bicubic_model_original.png`) shows a coherent sharp result
**with invented detail** (e.g. facial features differ from the original). That is inherent to
generative SR and is why the app always shows a preview and lets the user reject it.

Test images: scikit-image sample data (astronaut: NASA, public domain; coffee, chelsea: CC0).

## Temporal stability (`tools/model/temporal_stability.py`)

Per-frame image models have no temporal memory. On a static scene with fresh Gaussian noise
per frame (any frame-to-frame output change is flicker), mean absolute frame-to-frame
difference on a 0–255 scale:

| Noise σ | Bicubic 2× | dn100 | dn0 |
|---|---|---|---|
| 4 | 3.56 | 1.88 | 2.50 |
| 8 | 7.02 | 3.20 | 4.46 |

So the model *reduces* noise flicker on static content. This test does **not** cover
motion: GAN SR can produce texture "boiling" on moving content, which has not been measured.

### Alternatives considered but not evaluated here

- **Real-ESRGAN x4plus (RRDBNet, 16.7 M params)** — the classic Real-ESRGAN baseline; ~14×
  larger, impractical on a phone for video. Can be added to the GPU worker; not evaluated.
- **Video SR with temporal propagation** (BasicVSR++, RealBasicVSR, VRT/RVRT) — better
  temporal consistency on motion; heavy and GPU-only; candidates for the cloud worker. Not
  evaluated (no GPU was available).
- **Stereo-aware SR** (e.g. iPASSR, NAFSSR) — would use the other eye for consistent detail.
  Not evaluated; currently each eye is processed independently with identical weights, which
  guarantees identical treatment of identical content but not cross-eye consistency of
  invented detail.

## Tiling and stereo handling

- Each eye of an SBS/TB frame is a separate region; windows are replicate-padded **inside the
  region only**, so convolutions never see the other eye (tested: identical eyes in → bit-
  identical eyes out, on the real model).
- Fixed window (128 px on device, configurable on the server) with 16 px overlap; only the
  window core is kept and cores partition the region exactly (proven bit-exact with a
  reference engine in Kotlin and Python tests).
- The 4× core is area-resampled to the requested scale before being written.

## Adding a model

1. Produce an ONNX file with input `input` [1,3,H,W] float RGB 0..1 and output `output`
   [1,3,sH,sW]; add it to `assets/models` and `backend/models`.
2. Add an entry to both `models.json` files with its SHA-256 (the app and the worker refuse a
   file whose hash does not match).
3. Validate with `tools/model/validate_model.py` (adapt the reference implementation).

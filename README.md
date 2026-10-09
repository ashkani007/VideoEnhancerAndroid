# VRVision

Android VR video player and video enhancer for passive phone headsets, initially targeting the
Samsung Galaxy S25 Ultra. Import a local video, optionally enhance it with **real AI super
resolution** (Real-ESRGAN) on the phone or on your own cloud backend, check a 10-second
before/after preview, then watch the verified result in a calibrated stereoscopic player.

No ads, no subscriptions, no analytics, no accounts. Videos stay on the phone unless you
explicitly consent to an upload for that specific video.

> **Status (honest summary).** The Android app builds in CI, passes unit tests and lint, and
> produces a debug APK. The VR math, routing, planning and tiling logic are unit-tested on
> the JVM. The backend passes 28 tests including an end-to-end run with real model inference,
> and its Docker image builds and passes a smoke test in CI. **Nothing has been run on a
> physical phone or in a headset yet**; on-device behaviour, performance and calibration
> quality are unverified. See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Repository layout

| Path | What it is |
|---|---|
| `android/core` | Pure-Kotlin logic: stereo texture mapping, projection meshes, calibration, head-pose conversion, media state machine, output planner, hybrid router, tiling, pixel ops. Builds and tests with only a JDK. |
| `android/app` | The Android app (Compose, Media3 ExoPlayer/Transformer, OpenGL ES 3, Room, WorkManager, ONNX Runtime). |
| `android/app/src/main/assets/models` | Two converted Real-ESRGAN models + SHA-256 manifest. |
| `backend` | FastAPI API, Celery worker (FFmpeg + real SR inference), Docker/Compose. See [backend/README.md](backend/README.md). |
| `tools/model` | Reproducible checkpoint → ONNX conversion, model validation and temporal-stability scripts. |
| `docs` | Architecture, model integration, calibration, testing, limitations, dependency notes, validation reports. |
| `VideoEnhancerAndroid_GitHubBuild.zip`, `.github/workflows/build-apk.yml` | The repository's original Java prototype, preserved unchanged. |

## Getting the APK

**From CI (no local setup):** every push runs `.github/workflows/vrvision.yml`. Open the
workflow run in the repository's *Actions* tab → *Artifacts* → `VRVision-debug-apk`. It is a
debug build signed with the CI's temporary debug key, suitable for personal testing only.

**Build locally:**

```bash
# Requirements: JDK 17+, Android SDK with platform 36 (ANDROID_HOME or android/local.properties)
cd android
./gradlew :core:test            # JVM unit tests (works without an Android SDK)
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
# -> android/app/build/outputs/apk/debug/app-debug.apk
```

Install with `adb install -r app-debug.apk`, or copy the file to the phone and allow
"Install unknown apps" for your file manager.

## Using the app

1. **Library → Import video** (Storage Access Framework; the file is not copied).
2. **Video information**: check metadata and confirm the format — projection (flat / VR180 /
   VR360), stereo layout (mono / side-by-side / top-bottom), half or full packing, and eye swap.
   File-name hints are suggestions only; nothing is applied silently.
3. **Play in VR**, or **Enhance**:
   - *Enhancement settings*: 2× AI super resolution (default), AI denoise on, conservative
     sharpening on, HEVC preferred, Hybrid mode, and the 10-second preview segment. The analysis
     shows output size (2× = 4× the pixels), codec support, estimated file size, storage,
     battery and thermal state. If the phone can't encode/play the target, smaller sizes are
     offered — your selection is never changed without you choosing one.
   - *Recommendation*: Local, Cloud or Unsupported, with the reasons.
   - *Cloud consent* (only if you choose cloud): what is uploaded, where, retention; nothing is
     sent until you tick the box and confirm.
   - *Processing*: real progress (frames processed or server-reported), measured ETA, cancel.
   - *Before/after*: frame-accurate split comparison with zoom, model name and version, timings,
     estimated full size. **Reject** deletes the preview; **Process full video** continues.
4. **Enhanced** tab: verified outputs (codec, size, frame count, duration, audio, decodability).
5. **Headset**: calibration with grid/checkerboard patterns, lens distortion, per-eye optical
   centers, lens separation, offsets, zoom, FOV; multiple profiles; JSON export/import.

## Cloud processing

Optional and off by default. Run your own backend (`backend/README.md`), then in
*Settings and privacy* disable *Local only*, enable cloud, and enter the backend URL and the API
key you configured on the server. No cloud service is provided or preconfigured by this project.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, data flow, implementation checklist
- [docs/MODELS.md](docs/MODELS.md) — model choice, conversion, validation results, runtime
- [docs/CALIBRATION.md](docs/CALIBRATION.md) — headset calibration guide
- [docs/TESTING.md](docs/TESTING.md) — what is tested, how, and what is not
- [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
- [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) — how versions were chosen and verified
- [backend/README.md](backend/README.md) — API, deployment, GPU worker, retention policy

## Licenses

App and backend code: as chosen by the repository owner. Bundled model weights: Real-ESRGAN
(BSD-3-Clause, © Xintao Wang et al.). ONNX Runtime: MIT. AndroidX/Media3: Apache-2.0.

# Architecture

```
┌──────────────────────────── Android app (android/app) ────────────────────────────┐
│ Compose UI (12 screens) ── simple back-stack Navigator                             │
│   │                                                                                │
│   ├─ data/      Room (videos, calibrations, jobs) · SAF import · MetadataReader     │
│   ├─ player/    ExoPlayer → SurfaceTexture → VrRenderer (GLES 3, 2 passes)          │
│   │             HeadTracker (game rotation vector) · PlayerController (reducer)     │
│   ├─ device/    DeviceInspector (MediaCodecInfo limits, storage, battery, thermal,  │
│   │             RAM, connectivity)                                                  │
│   ├─ enhance/   JobManager → WorkManager EnhanceWorker (foreground)                 │
│   │             ├─ LocalEnhancer: MediaCodec ↔ FrameUpscaler(OrtSrEngine) ↔ Muxer  │
│   │             ├─ ConventionalUpscaler: Media3 Transformer + Lanczos (not AI)      │
│   │             └─ CloudClient (OkHttp) → backend                                   │
│   └─ assets/models  Real-ESRGAN ONNX ×2 + SHA-256 manifest                          │
│                                                                                    │
│ android/core (pure Kotlin, JVM-tested): StereoMapper · MeshFactory · HeadPose ·     │
│   HeadsetCalibration/ViewportLayout/DistortionModel/ProfileManager · MediaReducer · │
│   OutputPlanner · RoutingEngine · TilePlanner/FrameUpscaler/PixelOps               │
└────────────────────────────────────────────────────────────────────────────────────┘
                          │ HTTPS (only after per-video consent)
┌──────────────────────── backend (FastAPI + Celery) ─────────────────────────────────┐
│ API: token auth · quote · consent-gated jobs · resumable upload · ffprobe validation │
│      preview → full · cancel · delete · Range download                               │
│ Worker: FFmpeg decode → per-eye tiled Real-ESRGAN (ONNX Runtime | PyTorch/CUDA)      │
│         → FFmpeg HEVC + source audio → ffprobe validation                            │
│ PostgreSQL (jobs) · Redis (queue) · S3/MinIO (objects) · Celery beat (retention)     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Browser (Phase 2)

The Browser tab (WebView + Compose) is documented in [BROWSER.md](BROWSER.md). It reuses the VR
renderer (a web page is just another texture on a flat virtual screen), the VR player (Media3,
now with HLS/DASH) and the whole enhancement flow (a confirmed download is imported into the
library and enters the normal analyze → preview → compare → full → play path). Navigation is a
bottom bar: Home | Library | Browser | Enhance | Settings.

Phase 2 also corrected the headset projection: each eye now uses an off-axis projection whose
principal point is that eye's lens center, so "straight ahead" lands where the lens distortion
is centered (previously it was the middle of the eye viewport).

## Key design decisions

**Pure-Kotlin core.** Everything that can be wrong numerically — eye texture rectangles, mesh
geometry, sensor-to-camera conversion, distortion, viewport placement, planning, routing,
tiling, colour conversion — lives in `android/core` with 66 JVM unit tests. The app layer is thin
glue to Android APIs. This also made testing possible in an environment without the Android
SDK.

**Rendering (Phase 1).** ExoPlayer decodes into a `SurfaceTexture` (external OES texture).
Pass 1 renders each eye into its own framebuffer: the projection mesh (flat quad keeping the
eye's aspect ratio, or an inward-facing VR180/VR360 sphere) samples only that eye's rectangle
of the frame, clamped half a texel inside it so bilinear filtering never bleeds the other eye's
pixels across the SBS/TB seam. Pass 2 draws each eye framebuffer into its screen viewport with
radial pre-distortion around that eye's lens center (`DistortionModel`, mirrored by the GLSL).
Calibration patterns replace pass 1 when enabled, so the user sees exactly how the lens
correction affects straight lines.

**Head tracking.** `TYPE_GAME_ROTATION_VECTOR` (fallback `TYPE_ROTATION_VECTOR`) quaternion →
`HeadPoseConverter`: Android world (east-north-up) → render world (Y up, −Z forward), times the
camera basis for the current display rotation (the camera looks out of the back of the phone,
screen-up is camera-up). Recentering removes yaw only. Unit tests cover forward/up/right for
both landscape rotations, yaw, pitch, roll and recentering.

**Planning and routing (Phases 2, 5).** `OutputPlanner` never changes the user's choice: if
the device's encoders/decoders can't handle it, the plan is blocking and lists alternative
sizes the user may pick. `RoutingEngine` evaluates local feasibility (model present, encoder,
RAM model, storage/battery/thermal) and cloud feasibility (privacy setting, configuration,
connectivity, server quote and limits) and recommends Local, Cloud or Unsupported with
reasons. A cloud recommendation still requires the consent screen.

**Local enhancement (Phase 3).** Decode with `MediaCodec` (flexible YUV), convert to 8-bit
RGB, run `FrameUpscaler`: per-eye regions → fixed-size windows (replicate-padded inside the
region only) → ONNX Runtime → keep window cores (which partition the region exactly) →
area-resample the model's native 4× to the requested size → write into the output frame.
Whole-frame RGB→YUV (no chroma seams), optional luma unsharp mask (conventional, labelled),
`MediaCodec` encode with original presentation timestamps (shifted to start at 0), AAC audio
copied for the same range, `MediaMuxer`, then validation. Thermal SEVERE aborts; cancellation
deletes partial output; OOM and unsupported encoder sizes surface as UNSUPPORTED.

**Cloud (Phase 4).** Same model and the same tiling contract (Python port, tested against the
Kotlin behaviour). Raw RGB frames are piped between two FFmpeg processes around the model.

**Privacy.** No analytics. Backup/device transfer excluded. Cloud disabled by default and
"Local only" on by default. Per-video consent with a versioned consent text, recorded by the
server. The server stores data under its retention policy and deletes on request.

## Implementation checklist

| Phase | Item | State |
|---|---|---|
| 1 | SAF import, persisted URI permission, metadata (size, duration, fps, rotation, codec/profile, bit depth, HDR, audio, subtitles) | Implemented, compiles; untested on device |
| 1 | Flat / VR180 / VR360, mono / SBS / TB, half/full packing, eye swap | Implemented; mapping and meshes unit-tested |
| 1 | Head tracking + recenter, touch look-around fallback | Implemented; math unit-tested |
| 1 | Per-eye rendering, lens distortion, per-eye optical centers, lens separation, offsets, zoom, FOV | Implemented; layout/distortion unit-tested |
| 1 | Play/pause/seek/volume/subtitles, keep screen on, large controls, error handling | Implemented; reducer unit-tested |
| 1 | Calibration grid/checker patterns, multiple profiles, JSON export/import, cutout handling | Implemented; persistence rules unit-tested |
| 2 | Output analysis: size, fps, codec, bit depth, stereo, projection, size estimate, storage, battery, thermal, codec limits, explicit alternatives | Implemented; planner unit-tested |
| 3 | Local AI pipeline (decode → SR → sharpen → encode → audio → validate → save) | Implemented, compiles; **not run on a device** |
| 3 | Real model with metadata, integrity check, tiling with overlap, stereo-separated regions | Implemented; model validated on host; tiling proven exact in tests |
| 3 | Conventional GPU upscale, labelled as not AI | Implemented, compiles |
| 4 | FastAPI backend, auth, consent, resumable upload, quotas, preview/full, cancel, download, cleanup | Implemented; 28 tests pass |
| 4 | GPU worker (PyTorch/CUDA) | Implemented; **not run** (no GPU available) |
| 4 | Docker/Compose | API image built and smoke-tested in CI; compose validated, not run as a stack |
| 5 | Hybrid routing with reasons and overrides | Implemented; unit-tested |
| 6 | Preview selector, frame comparison, model/version, resolutions, timings, size estimate, reject | Implemented, compiles |
| 7 | 12 screens, dark theme, large touch targets, no fake progress | Implemented, compiles |
| 8 | Device test matrix | **Not done** — needs hardware; see TESTING.md |
| 9 | CI: Gradle build, unit tests, lint, APK artifact, backend tests, Docker build | Done and green |

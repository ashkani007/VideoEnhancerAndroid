# Known limitations

## Verification status

- **No physical-device testing yet.** The app compiles, passes lint and unit tests, and the APK is
  produced in CI. On an Android emulator the app launches and the local AI enhancement pipeline
  runs end to end on a tiny clip (see TESTING.md). It has not been installed on a phone or used
  in a headset: rendering, head tracking, calibration feel, hardware codec behaviour, WorkManager
  foreground execution and real performance are unverified on hardware.
- **No phone performance numbers.** Host CPU timing (≈190 ms per 128×128 tile on an x86 CPU) is
  not representative. Back-of-envelope estimate (not a measurement): the network costs about
  2.4 MFLOP per source pixel, i.e. ~5 TFLOP per 1080p frame, so CPU inference on a phone is
  likely tens of seconds per 1080p frame and a 10-second 30 fps preview could take hours.
  Use *Measure local speed* (real on-device benchmark) — the recommendation screen then shows
  the estimated preview time — and prefer the cloud GPU worker or short clips for local AI.
- **GPU cloud worker not run.** The PyTorch/CUDA engine and `Dockerfile.worker-gpu` are written
  but untested (no GPU available). The CPU worker path is tested end to end.
- The full Compose stack (Postgres + Redis + MinIO + worker + beat) has not been started as a
  whole; the API image is smoke-tested and the compose files are validated in CI.

## Local enhancement

- CPU inference only (ONNX Runtime default CPU provider). GPU/NPU providers are not enabled
  until benchmarked.
- Frames make CPU round trips (decode → RGB → model → YUV → encode); no zero-copy GPU path.
- 8-bit SDR processing: 10-bit/HDR sources are converted to 8-bit and tagged BT.709 SDR; the
  planner warns about this. HDR is not preserved.
- Only AAC audio is copied; other audio codecs are dropped with a visible note (no re-encode).
- An interrupted local job restarts from the beginning (no frame-level resume).
- The conventional (Lanczos) path filters across the stereo seam (≈3 source pixels).
- Color standard is taken from the decoder when signalled, else assumed BT.709 (≥720p) or
  BT.601.

## AI output quality

- Real-ESRGAN is generative: it invents plausible detail that may not match the scene (faces,
  text). Each eye is processed independently with identical weights, so identical content is
  treated identically, but invented detail is not guaranteed to be stereo-consistent for
  differing eye views.
- Per-frame model: no temporal propagation; texture flicker on motion has not been measured.
- 2× output is produced by area-downsampling the model's 4× output.

## Cloud

- Variable-frame-rate sources (nominal vs. average rate differing by > 1%) are rejected by the
  worker; process those locally.
- The worker outputs at the source's average frame rate, so per-frame timestamps of slightly
  irregular sources are regularized (total duration and audio sync preserved).
- No user accounts: access is by operator-issued API keys. Quotas are per job and per client
  key, not per person. Prices are only shown if the operator configures them.
- HTTPS must be provided by a reverse proxy; `VRV_REQUIRE_HTTPS=true` enforces it.

## Player

- Subtitles are drawn as a 2D overlay duplicated per eye (no depth placement). External subtitle
  files are not supported, only embedded text tracks.
- No neck model / positional tracking (3DoF only).
- Stereo layout and projection are not auto-detected from spatial-media metadata (only file-name
  and aspect hints, which are always presented as suggestions).

## Build and dependencies

- Compose is pinned to 1.11.x (BOM 2026.06.01) because Compose 1.12 requires compileSdk 37 and
  AGP 9.1. Moving to AGP 9 (built-in Kotlin) is the next dependency upgrade.
- The release build is not configured for signing; only the debug APK is produced.

## Browser (Phase 2)

- Detection is best-effort: only sources the page exposes directly (video/source elements,
  media links, media-looking request URLs) are found. Many sites use script-generated streams
  (blob:), DRM, signed or login-only URLs, or block other players; those stay in the page.
- The native player and downloads never receive the site's cookies or headers, so videos that
  need a login or a referrer can't be opened or enhanced outside the page — by design.
- HLS/DASH can be played but not enhanced (enhancement needs one downloadable file).
- HTTP-only sites are not loaded (HTTPS-first without HTTP fallback).
- VR browser mode: the page is rendered at 1280×720; text entry inside VR needs a Bluetooth
  keyboard (the on-screen keyboard is not usable in a headset); fullscreen HTML5 video in VR mode
  is not routed to the virtual screen (use *Open in VRVision Player* for VR videos).
- Drawing the WebView into the VR surface uses a hardware canvas every frame; performance and
  battery use on a phone are not measured yet.
- Downloads use Android's DownloadManager and are visible in the system notification; there is no
  pause/resume UI beyond what DownloadManager does itself.
- Gaze/controller input and the VR rendering of web pages have not been tried in a real headset.

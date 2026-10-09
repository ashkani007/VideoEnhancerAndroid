# Testing

## Automated (run in CI on every push)

| Suite | Where | What it proves |
|---|---|---|
| Core unit tests (66) | `android/core/src/test` | Stereo eye rectangles (mono/SBS/TB, swap, no overlap), eye aspect for half/full packing, format hints are only suggestions; flat quad aspect/distance, VR180 spans ±90°, VR360 seam behind the viewer, sphere geometry; head pose for ROTATION_90/270, yaw/pitch/roll direction, recentering keeps pitch, view = inverse camera; calibration clamping, JSON round trip and hostile input, profile persistence rules (always one active, last can't be deleted, unique names), viewport/lens placement incl. cutout inset, distortion fixed point and monotonicity; media reducer lifecycle, seek clamping, sticky errors, keep-screen-on, volume/subtitles, error classification; output planner (2× = 4× pixels, encoder limits → blocking + explicit alternatives, HEVC→AVC warning, storage/battery/thermal), routing (privacy local-only, offline, RAM, server limits, slow-local → cloud); tiling partitions every region exactly, cores stay away from window edges, stereo cores never cross the seam, window extraction never reads the other eye, YUV↔RGB round trip, area resampling, unsharp mask; tiled upscaling with an exact engine is bit-identical to whole-frame upscaling. |
| App unit tests | `android/app` | Compilation of the app test source set (no Android-dependent unit tests yet). |
| Android lint | `:app:lintDebug` | No lint errors (abortOnError). |
| Debug APK | `:app:assembleDebug` | The app builds with all native libraries and models packaged. |
| Backend tests (28) | `backend/tests` | Auth (missing/invalid key, invalid/expired token), consent required and versioned, quotas (size, output scale, layout, active jobs), owner-only access, resumable upload (wrong offset refused, resume from server offset, early completion refused), checksum mismatch and corrupt files rejected and purged, **end-to-end preview and full processing with real ONNX inference** on an FFmpeg-generated SBS clip with audio (resolution, frame count, audio present, eye-difference not increased, HEVC output, Range download), cancel deletes staged data, retention cleanup and delete-now remove objects, quote has no fake price; tiling contract and exact reference-engine upscaling in Python; real model keeps identical eyes bit-identical; model integrity check. |
| Model reproducibility | CI `backend` job | Re-converting the official checkpoints yields byte-identical ONNX files. |
| Docker | CI `backend-docker` job | API image builds; container serves `/v1/health`, issues a token, has ffmpeg and onnxruntime; compose files validate. |

## Host-side model validation (manual, results committed)

`tools/model/validate_model.py` and `tools/model/temporal_stability.py`; results in
`docs/validation/` and summarized in [MODELS.md](MODELS.md).

## Not yet tested — requires hardware

None of the following has been executed; they are the acceptance tests for a device session
(Galaxy S25 Ultra + passive headset). Use footage you own or that is licensed for testing
(e.g. self-recorded clips, or CC-BY VR footage with attribution); record the source and
license of every clip used.

| Area | Test |
|---|---|
| Formats | Flat 2D MP4; SBS half and full; TB half and full; VR180 SBS; VR360 mono and TB; HEVC 8/10-bit; 30 and 60 fps; short and > 30 min files |
| Errors | Corrupt file, audio-only file, unsupported codec (e.g. ProRes), > decoder-limit resolution, revoked SAF permission |
| Player | No eye inversion (calibration dots), correct aspect, no unexpected frame drops (dumpsys gfxinfo / Media3 analytics), A/V sync on long playback, subtitles, seek, volume, screen stays on only while playing |
| Tracking | Both landscape orientations, recenter, drift over 10 min, sensor absent (touch fallback) |
| Calibration | Grid straightness for a real headset, profile save/restore after app restart, export/import |
| Local AI | Preview on 1080p SBS: real inference runs, timing, temperature; full job; cancel mid-way deletes output; app killed during job; storage nearly full; thermal throttling triggers abort; validation catches a truncated output |
| Cloud | Network loss during upload resumes from server offset; server timeout surfaces an error; consent screen required before any upload (verify with a proxy that no bytes leave the phone before consent); delete-after-download |
| Performance | Measure on-device ms per megapixel with *Measure local speed* and a real preview; report results with device, temperature and battery state. No performance numbers for phones are claimed until measured. |

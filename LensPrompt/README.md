# LensPrompt

A mobile teleprompter for people recording themselves with a phone. Its main feature is **Smart Follow**: the app listens to you and keeps the text in step with where you actually are in the script. You don't have to match a fixed scroll speed.

> I read naturally. LensPrompt follows me.

## Modules

| Module | What it is | Needs |
|---|---|---|
| `core/` | Pure-Kotlin Smart Follow engine, the recognition simulator and their tests | JDK 17+ |
| `app/` | Android app (Kotlin, Jetpack Compose, CameraX, SpeechRecognizer) | Android SDK 35 |

`settings.gradle.kts` includes `:app` only when it finds an Android SDK (`local.properties` → `sdk.dir`, `ANDROID_HOME` or `ANDROID_SDK_ROOT`). That way the engine can be built and tested anywhere.

## Build

```bash
cd LensPrompt
./gradlew :core:test          # Smart Follow engine tests (no Android SDK needed)
./gradlew test assembleDebug  # everything + debug APK (needs Android SDK 35)
# APK: app/build/outputs/apk/debug/app-debug.apk
```

CI (`.github/workflows/lensprompt.yml`) runs `test` and `assembleDebug` on every push that touches `LensPrompt/`. The debug APK is uploaded as the `LensPrompt-debug-apk` artifact. A second job boots an API 34 emulator and runs `connectedDebugAndroidTest` (`app/src/androidTest/.../SmokeTest.kt`): app launch, script creation, manual scrolling, and Smart Follow end to end with the debug speech simulator.

## Smart Follow architecture

```
SpeechRecognizer (partial + final results, audio level)       app/speech/SpeechRecognitionManager
  │  continuous sessions, controlled restarts, back-off
  ▼
SmartFollowController  (worker thread, clock injected)          core/SmartFollowController
  ├─ TextNormalizer      Unicode-aware tokens + char spans        core/TextNormalizer
  ├─ ScriptIndex         token weights (rare words = evidence)    core/ScriptIndex
  ├─ ScriptAligner       weighted local alignment + confidence    core/ScriptAligner
  ├─ accept / hold / confirm-jump / reject   (position decisions)
  ├─ ReadingVelocityEstimator  weighted regression + EMA          core/ReadingVelocityEstimator
  ├─ VoiceActivityDetector + PauseDetector   (same file)
  └─ state machine: IDLE LISTENING TRACKING SHORT_GAP PAUSED LOW_CONFIDENCE RECOVERING ERROR
  ▼  FollowOutput(targetProgress, targetVelocity, state, …)
TeleprompterScrollController  (main thread, every frame)        core/TeleprompterScrollController
  feed-forward velocity + bounded correction, accel/decel/velocity limits,
  backward dead-zone  →  px offset
  ▼
ProgressMapper: token progress ↔ y px, interpolated within lines (continuous)
```

**Where the speaker is.** The last ~8 recognized words (earlier finalized words fill in context after a recognizer restart) are aligned against a window around the last reliable position. The alignment is a Smith-Waterman-style DP with:

- fuzzy token similarity;
- informativeness weights;
- insertion and deletion penalties;
- split/merge moves ("every day" ↔ "everyday", Persian ZWNJ compounds).

A distance prior prefers continuity, so a lone "the", or a repeated phrase elsewhere, can't pull the text away. Confidence combines how much of the query is explained, how much evidence was matched, and the margin over the runner-up candidate.

**Accepting a position.**

| Situation | Behaviour |
|---|---|
| Small forward step | Accepted as tracking |
| Small step back (speaker repeating) | Held, so no reverse scrolling |
| Large jump (skip or restart) | Needs strong evidence or agreeing confirmations |
| Low-confidence measurement | Rejected, so off-script speech holds the last reliable position |

After repeated rejections the search window widens, and later covers the whole script.

**How fast.** Accepted (time, progress) samples feed a recency-weighted least-squares slope with clamping and EMA smoothing. After a pause the sample history is dropped, so silence doesn't read as slow speech.

**Pauses.**

- The target coasts at reading speed between results, up to about 3 words past the last fix, to hide recognition latency.
- The real-time audio level (`onRmsChanged`, adaptive noise floor) stops the coast at once when you go quiet.
- No progress for `shortGapMs` gives SHORT_GAP; no progress for `pauseMs` gives PAUSED, where target velocity is 0.

**Smooth motion.** Recognition results are measurements; the scroll controller turns them into continuous motion. Position changes only through velocity × dt, and velocity changes only under acceleration limits.

All tuning values live in `core/SmartFollowConfig.kt`, each with a comment. The three user sliders (responsiveness, pause sensitivity, alignment strictness) map onto them via `SmartFollowConfig.fromUserSettings`.

### Testing without speaking

`core/RecognitionSimulator.kt` has `SpeechScenario` and `SmartFollowSimulator`. A scenario turns a reading plan into realistic recognizer events:

- reading speed and speed ramps, pauses;
- misrecognitions, repeats, skips, off-script speech;
- cumulative partial results with latency, finals plus session restarts, audio levels.

The simulator then runs the controller and scroll controller at 60 fps. `SmartFollowScenarioTest` covers the spec's scenarios: normal, fast, slow, pause, resume, misrecognition, repeated words, correction, skipped sentence, off-script, repeated phrases, starting mid-script, Persian, and no-audio-level fallback.

For tuning, print frame traces with:

```bash
LENSPROMPT_TRACE=1 ./gradlew :core:test --tests '*SimulationTraceTool*' -i
```

In the app, **Settings → Debug mode** shows a live HUD: recognized text, matched index, confidence, velocities, state, pause timer, recognizer restarts and frame time. It also adds "Debug: simulated speech" to the prompter's quick settings.

## App features

- **Script library.** Create, paste, edit (autosave), rename, duplicate, delete and search. Recent scripts come first. Storage is atomic JSON files (`AtomicFile`).
- **Prompter.**
  - Smart Follow or manual auto-scroll, with adjustable speed.
  - Start / pause / resume / stop / back to start, and a 0/3/5/10 s countdown.
  - Display: font size, line spacing, margins, alignment, reading anchor, horizontal and vertical mirroring.
  - Drag the text to reposition it; Smart Follow restarts from the new position.
  - Auto-hiding controls, and a status chip with a green mic icon while listening.
  - RTL and Persian text are laid out by content direction.
- **Camera.** CameraX preview behind dimmed text, front/rear switching, and video recording to `Movies/LensPrompt` with a timer. With sound on, LensPrompt records the audio itself so Smart Follow keeps working (see below).
- **Floating teleprompter.** A movable, resizable, transparent teleprompter over Samsung Camera and other camera apps, with Smart Follow when the microphone is free (see below).
- **Languages.** Device default, English, Persian, Dutch and more. Tokenization and number spelling support EN/NL/FA.

## Smart Follow while recording video with sound

**What failed on a real phone (V3, commit 41f4dac) and why.**

- V3 captured the microphone with `AudioSource.CAMCORDER`. Since Android 10 that source is privacy-sensitive: while LensPrompt held it, every other app capturing audio got silence.
- V3 then handed its audio to the system recognizer with `EXTRA_AUDIO_SOURCE` (Android 13+). That extra is *optional* for recognition services. A service that ignores it opens the microphone itself and, because of the first point, hears only silence.
- `ERROR_NO_MATCH` / `ERROR_SPEECH_TIMEOUT` were treated as normal session ends, so such a recognizer was restarted forever, and nothing measured whether it ever read the stream.

**V4: one microphone capture, a recognizer that reads it.**

```
AudioCaptureEngine (one AudioRecord, MIC source, 48 kHz mono)
  ├─ PCM file ──────► AvMuxer → soundtrack of the CameraX video-only MP4
  ├─ levels ────────► voice-activity detector
  └─ 16 kHz PCM ────► offline recognizer (Vosk, in-process)  → words → alignment → Smart Follow
                  └─► (fallback) pipe → system recognizer, under a health check
```

Route selection (`PrompterViewModel.applyRoute`, shown as "Route" in the debug HUD):

1. **Offline pack installed** for the recognition language → the offline recognizer reads LensPrompt's PCM. No second microphone client, no session restarts.
2. Not recording → the system recognizer opens the microphone itself, as before.
3. Recording, Android 13+, no pack → the system recognizer is fed through a non-blocking pipe. A health check (`core/RecognizerHealth.kt`) stops it if the service never drains the pipe (writes fail with EAGAIN) or produces no word in 8 s of voiced speech. The verdict is remembered per recognition service, so it is never retried in a loop.
4. Otherwise → pacing by voice and lip activity at the learned reading speed.

The MIC source is not privacy-sensitive, so LensPrompt's own capture never silences anyone else.

**Offline speech packs** (Settings → Offline speech): small Vosk models, downloaded on demand from alphacephei.com or imported from a `.zip`. They are not bundled.

| Language | Model | Download |
|---|---|---|
| English | vosk-model-small-en-us-0.15 | ~40 MB |
| Dutch | vosk-model-small-nl-0.22 | ~39 MB |
| Persian | vosk-model-small-fa-0.42 (falls back to 0.5, 0.4) | ~53 MB |
| German / French / Spanish | vosk-model-small-de-0.15 / fr-0.22 / es-0.42 | ~40 MB |

Why Vosk:

- It was the only engine found that streams partial results offline for English, Dutch *and* Persian with small models.
- sherpa-onnx has no streaming Dutch or Persian models.
- whisper.cpp is not streaming and is heavy.
- The Android `SpeechRecognizer` cannot be relied on to read app audio (see above).

The engine sits behind `PcmSpeechEngine`, so another engine can be plugged in per language. Small-model accuracy is below Google's online recognizer, but Smart Follow aligns fuzzily against the known script. Persian Smart Follow with the system recognizer is unchanged when not recording.

The native library adds ~10 MB per ABI. The APK ships arm64-v8a, armeabi-v7a and x86_64.

## Floating teleprompter over the phone's camera app

"Use with phone camera" (prompter top bar, or the script menu in the library) does the following:

1. Explains the mode.
2. Opens Android's "Display over other apps" screen if needed (`SYSTEM_ALERT_WINDOW`).
3. Asks for the microphone, and for notifications on Android 13+.
4. Starts `OverlayService`, a foreground service of type `specialUse|microphone` that draws a `TYPE_APPLICATION_OVERLAY` window.
5. Optionally opens the default camera app in video mode.

The window:

- **Script viewport** (`overlay/ScriptViewport.kt`). The whole script is laid out for the current width, font, line spacing and alignment, and only the part inside the window is drawn. Text can't render outside the window.
  - Smart Follow and manual scrolling move the text inside it.
  - Resizing, font or spacing changes reflow immediately and keep the reading position.
  - The script is scrollable from the first line to the last.
- **Compact toolbar**: `[⠿ drag] [MODE] [▶] [⚙] [🔒]`.
  - The mode chip shows MAN (manual, or forced because the camera app has the mic), OFF (press ▶), WAIT (listening or finding the place), SMART (following words) or VOICE (following voice activity).
  - Tap the chip to switch between Smart Follow and manual.
  - After 3 s without interaction the toolbar and resize grip fade out, leaving a small ⋯ handle. Tap the script or the handle to bring them back.
- **Gestures are separate**:
  - ⠿ (or ⋯) moves the window.
  - The bottom-right grip resizes width and height continuously, with a minimum size, and always stays on screen.
  - Dragging the script area scrolls the text, and Smart Follow continues from there.
- **⚙ opens a floating settings panel**, a second small overlay window, so the camera app stays open. Every change applies live:
  - text size slider (A− … A+, 18–72 sp), line spacing, background opacity (0–100 %), text opacity;
  - window width and height, manual scroll speed;
  - Smart Follow, center text, mirror text, lock, auto-hide;
  - layout presets: **Near camera** (a narrow ~3-line strip at the top; drag it next to your selfie camera, wherever it is), Top band and Large;
  - back to start, open camera, close.
- **Lock** (🔒):
  - the window can't be moved, resized or scrolled by accident;
  - the controls disappear and a small 🔒 badge unlocks it;
  - scrolling and Smart Follow keep running.
- **Closing (three ways, all doing the same cleanup).** Every exit stops scrolling and Smart Follow, releases the microphone and recognizer, saves the layout, removes the overlay windows at once, removes the notification and stops the service. The camera app and the LensPrompt process keep running.
  1. **✕** on the overlay. It sits at the right end of the toolbar, behind a divider, away from ▶ and ⚙. In narrow windows the mode chip and 🔒 are dropped first, so ✕ always fits. When the controls are auto-hidden, tap ⋯ (or the script) and then ✕. When locked, tap 🔒 to reveal `UNLOCK | ✕` for 4 s.
  2. **"Stop teleprompter"** in the notification. It works even if the overlay UI is stuck.
  3. **"STOP FLOATING MODE"** inside LensPrompt (library, prompter and settings) while floating mode is on.
- **Rotation.** The window keeps its relative place and size, is clamped inside the new screen, and keeps font, settings and script position. `core/OverlayGeometry.kt` holds this logic and is unit-tested.
- **Persistence.** Position, size, font, line spacing, background and text opacity, alignment, mirror, Smart Follow, lock and auto-hide are remembered. A saved layout from another screen size is adapted.

Smart Follow in the overlay uses LensPrompt's own AudioRecord and the offline pack (or the system recognizer without one).

**Platform limit.** When the camera app records video *with sound*, it captures the microphone with a privacy-sensitive source, and Android gives every other app silence. No app can listen at that moment. LensPrompt detects this (`AudioRecordingConfiguration.isClientSilenced`, plus a run of exact-zero samples), shows "Camera app is using the mic — manual speed", scrolls at the manual speed, and resumes following when the microphone is free. Smart Follow over a camera app therefore follows the voice before and between recordings, or while the camera app records without sound. For hands-free following *while* recording with sound, use LensPrompt's own camera, where one capture feeds both.

## Diagnostics

With Settings → Debug mode on, the prompter HUD shows:

- route and mic owner;
- AudioRecord source and state;
- PCM read rate, and whether Android silences the capture;
- recognizer engine, state, start and restart counts, partial and final counts, and result age;
- last error and health verdict;
- pipe bytes, full drops and failures;
- voiced-without-words time;
- recording and mux state.

"Copy diagnostics" copies every value. While Smart Follow runs, a full line is logged every 2 s (and on every route or mic event):

```bash
adb logcat -s LensPromptDiag
```

The emulator CI also runs `OfflineRecognitionTest`:

1. Downloads the small EN/NL/FA models.
2. Synthesizes speech with espeak-ng.
3. Streams it in 20 ms chunks through the real `VoskSpeechEngine`.
4. Feeds the recognized words to `SmartFollowController`.

English must recognize at least half the script and Smart Follow must reach its second half. Dutch and Persian are run and logged; espeak's synthetic voices are too unlike real speech to assert accuracy.

## Known limitations (honest list)

- **Recognizer behaviour varies by device.** Android's `SpeechRecognizer` is session-based. LensPrompt restarts sessions in a controlled way, but some devices play a short sound on every restart and some cap session length. This needs testing on real devices.
- **Recording without an offline pack.** Without a pack, the system recognizer is only usable while recording if it reads LensPrompt's stream. That needs Android 13+ and depends on the service, and it is checked at runtime. Otherwise Smart Follow paces by voice and lip activity. It stops when you stop, but it can't detect skipped or repeated sentences.
- **Offline pack accuracy.** Small Vosk models are less accurate than large online recognizers, especially for Persian. Accuracy on real speech has not yet been measured on a device.
- **A/V sync of the muxed sound** comes from CameraX status callbacks and the audio HAL timestamp. It's verified on the emulator and should be within a few tens of milliseconds, but it needs checking on real phones.
- **Overlay while the camera app records sound.** Android silences other apps' microphones, so the overlay falls back to manual speed then (see above). It is not yet verified on a Samsung device.
- **Recognition location.** Where recognition runs (on-device or online) is decided by the device's recognition service. "Prefer on-device" is a request, not a guarantee.
- **Tuning is simulator-based.** The Smart Follow defaults come from the simulator. Real speech and recognizer latency on a device may call for adjusting `SmartFollowConfig`.

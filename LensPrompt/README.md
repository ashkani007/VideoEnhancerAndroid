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

CI (`.github/workflows/lensprompt.yml`) runs `test` and `assembleDebug` on every push that touches `LensPrompt/`. The debug APK is uploaded as the `LensPrompt-debug-apk` artifact.

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
- **Camera.** CameraX preview behind dimmed text, front/rear switching, and video recording to `Movies/LensPrompt` with a timer. Audio is optional.
- **Floating overlay.** A foreground service draws a draggable, resizable, semi-transparent teleprompter over other apps. It scrolls at the manual speed.
- **Languages.** Device default, English, Persian, Dutch and more. Tokenization and number spelling support EN/NL/FA.

## Known limitations (honest list)

- **Recognizer behaviour varies by device.** Android's `SpeechRecognizer` is session-based. LensPrompt restarts sessions in a controlled way, but some devices play a short sound on every restart and some cap session length. This needs testing on real devices.
- **Sharing the microphone while recording video with sound.** On some phones, Android gives the microphone to only one of the recognizer service and the camera recorder. The app explains this when it happens, and offers "Record audio with video" (turn off to record sound separately) and manual mode as fallbacks. It doesn't hide the problem.
- **Overlay is manual only.** The overlay doesn't support Smart Follow, because background microphone use is restricted and would compete with the other camera app's audio.
- **Recognition location.** Where recognition runs (on-device or online) is decided by the device's recognition service. "Prefer on-device" is a request, not a guarantee.
- **Tuning is simulator-based.** The Smart Follow defaults come from the simulator. Real speech and recognizer latency on a device may call for adjusting `SmartFollowConfig`.

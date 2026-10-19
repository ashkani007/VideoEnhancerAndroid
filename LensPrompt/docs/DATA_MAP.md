# LensPrompt data map — source audit, 18 October 2026

Scope: branch `claude/lensprompt-android-dev-s2ojat`, head `b255abee786d447f6cc8aba6e3cf3532c563e4b3`, plus proposed publishing changes. This is source inspection, not a traffic capture or proof of the exact uploaded AAB. See `PUBLISHING_STATUS_2026-10-18.md` for verification limits.

| Data / access | Implementation and use | Storage / recipients | Retention / controls |
|---|---|---|---|
| Script title, body and dates | `data/ScriptRepository.kt`; JSON in `files/scripts/`; atomic persistence; user-created/pasted scripts | App-private files; Android backup and device transfer can copy them | Delete in library, clear app storage or uninstall; provider backups can retain old copies |
| Settings, language and overlay geometry | `data/SettingsRepository.kt`; `lensprompt_settings` SharedPreferences | App private; Android backup/transfer | Change settings or clear app storage |
| Clipboard script import | `ui/LibraryScreen.kt` reads clipboard only on explicit import action | New local script | Same as scripts |
| Offline Smart Follow microphone data | `audio/AudioCaptureEngine.kt` → `speech/OfflineRecognizer.kt` → `core` alignment | PCM/text in process memory; no upload in this route; audio may also be recorded when requested | Ends with session; recording cache/video exception below |
| System speech recognition | `speech/SpeechRecognitionManager.kt` and route selection in `PrompterViewModel.kt` / `OverlayService.kt` | Android-selected recognition provider; microphone or an app-provided PCM pipe; provider may send audio/metadata online | Provider policy determines server retention; stop/revoke mic permission or use manual mode |
| Recognition configuration | `EXTRA_LANGUAGE`, calling package, recognition options; no script prompt/hints sent | Selected system speech provider | Provider-specific |
| Recognition fallback | Automatic mode uses system recognition outside recording. Failed offline/model routes can also use the system service. `EXTRA_PREFER_OFFLINE` can be dropped after a language failure | May change from local processing to a provider's remote processing | Do not equate “pack installed” or “prefer offline” with a strict offline guarantee |
| Video with sound | `PrompterCamera.kt`, `PrompterViewModel.saveRecording`, `AvMuxer.kt`; CameraX video-only plus PCM audio, later muxed | Temporary cache; Android 10+ shared `Movies/LensPrompt`; Android 8–9 app-specific Movies; private internal fallback if unavailable | Normal completion deletes temporary files. Interrupted jobs may leave cache. Shared videos survive uninstall; private videos may not. Gallery backups have separate policies |
| Camera frames / mouth movement | `camera/LipTracker.kt` → bundled ML Kit face contours → scalar mouth openness | Frame/contour analysis stays on device. No identity recognition or face database. Frames not separately stored; ordinary video recording can save the same scene | Disable camera/lip feature; image lifecycle closes proxies |
| ML Kit technical data | `com.google.mlkit:face-detection:16.1.7`; official docs confirm bundled version. SDK diagnostic/usage reporting includes an installation ID | Google; HTTPS according to provider; diagnostics and usage analytics | Provider-controlled. No app metrics opt-out. Disabling lip analysis does not prove initialization telemetry stops |
| Offline speech model download | `SpeechModelManager.kt`; `HttpURLConnection` from `alphacephei.com/vosk/models/`; EN/NL/FA/DE/FR/ES candidates, roughly 39–53 MB | Host/delivery network receives IP and ordinary request data. Model ZIP is downloaded and installed under `files/vosk/`; zip paths checked against traversal | User-initiated download/cancel/delete; packs excluded from Android backup/transfer |
| Model ZIP import | Android Storage Access Framework selected URI, read by `SpeechModelManager.import` | Selected local/cloud document provider → private pack storage | Provider policy plus local delete/uninstall |
| Recognizer compatibility verdicts | `speech/RecognizerVerdicts.kt`; provider component and failure verdict | Private preferences; explicitly excluded from backup and transfer | “Forget and test again” / clear app data |
| Debug/support diagnostics | `diag/Diagnostics.kt`; timing, levels, provider, errors, last 60 characters of recognized speech | Memory/HUD/explicit clipboard export. Audited internal source also logs snippets during route/failure events even if periodic debug logging is off | Device logs/clipboard are OS controlled. Proposed change redacts routine log text, retaining explicit export |
| Purchases | Billing 8.0.0 present; default build flag false → `DisabledProRepository`, not `PlayBillingRepository` | No default purchase flow or billing connection. An explicitly enabled build would use Play Billing | Verify actual uploaded flags before submission |
| Support email | External mail action to verified owner contact `abbasian7iraj@gmail.com`; message composed by user | User's email provider and developer mailbox | Support response/necessary retention; deletion requests by email |

## Permissions

| Explicit permission | Purpose / activation |
|---|---|
| `android.permission.RECORD_AUDIO` | Running Smart Follow and requested video sound; OS runtime permission |
| `android.permission.CAMERA` | Built-in preview, video and optional lip assistance; runtime permission |
| `android.permission.INTERNET` | Models, SDK/provider network activity; normal permission |
| `android.permission.SYSTEM_ALERT_WINDOW` | Floating text window over other apps; user grants special access |
| `android.permission.FOREGROUND_SERVICE` | User-started overlay's ongoing service |
| `android.permission.FOREGROUND_SERVICE_SPECIAL_USE` | Floating teleprompter service on API 34+; declared subtype names the actual use |
| `android.permission.FOREGROUND_SERVICE_MICROPHONE` | Smart Follow while overlay is in front of another app; permission granted before service start |
| `android.permission.POST_NOTIFICATIONS` | Floating-mode status/Stop control, API 33+ runtime notification choice |

Only MainActivity is exported. OverlayService is not exported, uses immutable PendingIntents, and is not sticky. App background handling stops the built-in prompter microphone and recording on ON_STOP. Overlay mode intentionally persists until stopped. Camera and microphone hardware are optional manifest features. No location, contacts, SMS, call log, broad media-read or accessibility permission is explicitly requested.

Billing and other SDK manifests may merge additional normal permissions (for example `com.android.vending.BILLING`). A fresh debug merged manifest has now been generated: it contains the eight explicit permissions above plus `com.android.vending.BILLING`, `android.permission.ACCESS_NETWORK_STATE` and `com.lensprompt.app.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`. The latter is a signature-level internal receiver protection rather than a runtime user permission. No advertising-ID permission appears. ML Kit and AndroidX startup providers are non-exported; ML Kit initialization is present regardless of the lip-assistance toggle. This is the locally built debug artifact, not proof of the exact uploaded AAB. The fresh resolved dependency graph is recorded in `verification/2026-10-18/selected-sdk-dependencies.txt`; release-AAB matching remains pending.

## SDK evidence and Data safety consequences

- Direct dependencies contain no advertising, developer marketing analytics or developer crash-reporting SDK. AndroidX/Compose/CameraX, Kotlin/coroutines, Vosk/JNA, ML Kit and Billing are declared. This does not negate ML Kit telemetry or platform collection.
- Google currently documents face-detection **16.1.7** as the bundled SDK used here: https://developers.google.com/ml-kit/vision/face-detection/android
- Technical metrics and per-installation identifiers are documented at https://developers.google.com/ml-kit/android-data-disclosure and https://developers.google.com/ml-kit/terms . Collection by SDKs counts even when it goes to Google rather than the developer. Do not answer “no data collected.”
- Scripts/recordings that remain local are outside Data safety collection scope. User-controlled Android backup, externally selected file providers and external camera/gallery services still need accurate policy disclosure; they are not proof of a developer-operated upload.
- The system speech provider is not fixed by the app. Audio transmission, transcript handling, encryption, deletion and provider role need resolution in the worksheet before a final declaration. Do not simply label it ephemeral, unshared or always encrypted.

Use `PLAY_CONSOLE.md` for the conservative worksheet and unresolved questions. All Console answers are drafts until owner review and saved-state verification.

Fresh generated debug BuildConfig confirms `APPLICATION_ID=com.lensprompt.app`, version 1.0.0/code 1, `BILLING_ENABLED=false`, and the verified policy URL and owner support email. This verifies defaults for this local build; Console AAB configuration still requires comparison. Vosk’s official documentation also confirms offline Android recognition (https://alphacephei.com/vosk/), matching the inspected local Model/Recognizer PCM route.

Resolved dependency verification: ML Kit Common 18.11.0, Google DataTransport and Firebase encoder/component libraries accompany Face Detection 16.1.7. There is no Firebase Analytics/Crashlytics or advertising library in the resolved debug graph. Billing transitively links Play Services Location 19.0.0, but no location permission or application location API call was found; dependency presence alone is not a collection declaration. See `ANDROID_BUILD_RESULTS_2026-10-18.md` for the fresh build, 75 passing unit tests and APK alignment evidence.

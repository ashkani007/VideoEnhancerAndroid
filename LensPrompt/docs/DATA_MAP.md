# LensPrompt data map (1.0 Release Candidate)

This map is built from the code, not from intentions. Each row names the code that handles the data.

Verification levels used below:

- **Verified (code):** read and confirmed in this repository.
- **Third party:** depends on another company's software. LensPrompt cannot verify what that software does; the row says so.

## 1. Data LensPrompt handles

| Data | Where it comes from | Where it goes / is stored | Leaves the device? | Retention | Code | Level |
|---|---|---|---|---|---|---|
| **Scripts** (title, text, dates) | Typed or pasted by the user | Private app storage, `files/scripts/*.json` | Only through **Android backup / device transfer** if the user has it on (Google account backup, encrypted by Android) | Until the user deletes the script or uninstalls | `data/ScriptRepository.kt`, `res/xml/*backup*` | Verified (code) |
| **Settings** (display, Smart Follow, overlay layout) | User choices | Private SharedPreferences `lensprompt_settings` | Same as scripts (backup) | Until uninstall or cleared | `data/SettingsRepository.kt` | Verified (code) |
| **Recognizer verdicts** (name of the phone's speech service, e.g. `com.google…`, plus a reason) | Measured by LensPrompt | Private SharedPreferences `lensprompt_recognizer_verdicts` | No (excluded from backup and transfer) | Until "Forget and test again" or uninstall | `speech/RecognizerVerdicts.kt` | Verified (code) |
| **Microphone audio: offline pack path** | Microphone, via LensPrompt's own `AudioRecord` | In memory → offline recognizer (Vosk) inside the app → recognized words → Smart Follow | **No.** LensPrompt makes no network call with audio or text. | Not stored (except while recording a video, see below) | `audio/AudioCaptureEngine.kt`, `speech/OfflineRecognizer.kt` | Verified (code) |
| **Microphone audio: system recognizer path** (no offline pack; or the user chose "System recognizer") | Microphone, opened by the phone's speech recognition service (Google, Samsung, …) | The **third-party recognition service**. LensPrompt only receives the recognized text. | **Possibly.** The service may process audio online. LensPrompt asks for on-device processing only if "Prefer on-device recognition" is on (`EXTRA_PREFER_OFFLINE`), and the service decides. | Decided by the service provider | `speech/SpeechRecognitionManager.kt` | Verified (code) + Third party |
| **Microphone audio while recording video with sound** | LensPrompt's `AudioRecord` | Temporary PCM file in the app cache → encoded into the video → temp file deleted | No | The PCM temp file is deleted after saving. If the app is killed mid-save it can remain in the cache until Android clears it. | `prompter/PrompterViewModel.kt` (`pcm.delete()`), `audio/AvMuxer.kt` | Verified (code) |
| **Recorded videos** (picture and sound) | Camera + microphone, only when the user presses record | Android 10+: `Movies/LensPrompt` in shared storage (MediaStore). Android 8–9: app-specific external storage, `Android/data/com.lensprompt.app/files/Movies`. | No. Other apps with media access can read shared storage. | Until the user deletes them. On Android 8–9 they are removed on uninstall. Excluded from Auto Backup. | `camera/PrompterCamera.kt`, `PrompterViewModel.saveRecording` | Verified (code) |
| **Camera frames for lip tracking** | Front camera preview, when "Lip tracking" is on | ML Kit face detection, **on-device** (bundled model `com.google.mlkit:face-detection`) → one number (mouth openness) → Smart Follow | Frames: no. See the ML Kit row in section 2 for SDK telemetry. | Not stored | `camera/LipTracker.kt` | Verified (code) + Third party |
| **Recognized text / diagnostics** | Smart Follow internals | In memory; shown on the HUD when "Diagnostics overlay" is on. Logged to logcat every 2 s only when diagnostics are on (in release builds). Copied to the clipboard only when the user taps "Copy diagnostics"; this includes up to 60 characters of the last recognized speech. | No. Logcat is readable only by the system, adb, and the app itself. | Logcat ring buffer | `diag/Diagnostics.kt`, `PrompterViewModel.startDiagLog` | Verified (code) |
| **Clipboard** | Read only when the user taps "New script from clipboard" | Becomes a script | No | As scripts | `ui/LibraryScreen.kt` | Verified (code) |
| **Offline speech packs** (Vosk models) | Downloaded **only when the user taps Download**, from `https://alphacephei.com/vosk/models/…`, or imported from a file the user picks | Private `files/vosk/<lang>/` | The download request reveals the device's **IP address** and an HTTP user agent to alphacephei.com. No user data is sent. | Until "Delete" or uninstall. Excluded from backup. | `speech/SpeechModelManager.kt` | Verified (code) |
| **Purchases (LensPrompt Pro)** | Google Play | Google Play Billing | **Disabled in 1.0** (`BILLING_ENABLED=false`, no connection to Play Billing). When enabled, Google Play processes payments; LensPrompt receives purchase tokens and product IDs only and stores nothing itself. | n/a | `billing/*` | Verified (code) |

## 2. Third-party software that may collect data

| Component | What it does in LensPrompt | Possible data collection | Status |
|---|---|---|---|
| Phone's speech recognition service (Google app, Samsung, …) | Speech-to-text when no offline pack is used | Audio and transcripts under the provider's own privacy policy | Third party. Disclose in the policy. |
| ML Kit Face Detection (bundled) | On-device face contours | Google documents that ML Kit SDKs may send usage and diagnostic information (device and app info, performance metrics) to Google. **The exact current disclosure must be checked against Google's ML Kit "data disclosure" page before filling in Data safety.** | **TO VERIFY.** It determines the Data safety answer for "App info and performance". |
| Google Play Billing | Purchases (off in 1.0) | Google Play processes payments | Disclose when billing is turned on |
| Android Auto Backup / device transfer | Copies scripts and settings to the user's Google account backup or a new phone | Part of Android, controlled by the user | Disclose |
| alphacephei.com | Hosts offline speech packs | Server logs (IP address, time, file) | Third party. Disclose. |

LensPrompt contains **no** analytics SDK, advertising SDK, crash-reporting SDK, account system or backend server of its own. This was verified from the dependencies in `app/build.gradle.kts`. Play Console "Android vitals" crash data is collected by Google Play and Android, not by the app.

## 3. Permissions and why

| Permission | Used for | Requested when |
|---|---|---|
| `RECORD_AUDIO` | Smart Follow listening; sound in videos | Starting Smart Follow, recording with sound, starting the floating teleprompter |
| `CAMERA` | Camera preview, video recording, lip tracking | Opening the prompter with "Camera preview" on |
| `SYSTEM_ALERT_WINDOW` | Floating teleprompter over other apps | "Use with phone camera" (system settings screen) |
| `FOREGROUND_SERVICE`, `…_SPECIAL_USE`, `…_MICROPHONE` | Keeping the floating teleprompter alive and listening while the camera app is in front | Starting the floating teleprompter |
| `POST_NOTIFICATIONS` | The ongoing "Floating teleprompter is on" notification with its Stop action | Starting the floating teleprompter (Android 13+) |
| `INTERNET` | Downloading offline speech packs (and Play Billing once enabled) | Download button |
| `com.android.vending.BILLING` (added by the Billing library) | LensPrompt Pro purchases. Present but unused while billing is off. | — |

## 4. Draft Google Play Data safety answers

**These are drafts. Confirm the ML Kit row (§2) first.**

- **Data collected or shared by the app (developer):** none of personal info, messages, contacts, location or financial info (while billing is off). Audio and video are processed or stored only on the device. Disclose audio as **collected? → No** for the offline path. Google's guidance treats data sent to a third-party SDK or service as "shared", and the system recognizer path sends audio to the device's speech service. That service is part of the user's OS setup and is not invoked as an SDK, so whether to declare it is a judgement call. **Owner decision:** either disclose it as shared ("Audio → Voice or sound recordings, for app functionality, optional"), which is the safer choice, or default Smart Follow to offline packs.
- **App info and performance:** depends on the ML Kit disclosure (§2).
- **Is data encrypted in transit?** Model downloads use HTTPS. Yes.
- **Can users request deletion?** All data is on-device and deleted by the user in the app or on uninstall. No account exists.

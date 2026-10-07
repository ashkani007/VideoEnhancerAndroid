# LensPrompt 1.0 production audit

Audited at commit `c7cce39` on `claude/lensprompt-android-dev-s2ojat`. No app code was changed for this audit.

**Severity**

- **Blocker:** Play Console will reject the upload, or a policy is violated.
- **High:** should be fixed before 1.0.
- **Medium:** fix soon after.
- **Low:** polish.

**How each finding was established**

- *verified:* checked in the code, the build output or the CI logs.
- *policy:* depends on a Google Play rule; recheck it in Play Console, because these rules change.

## 1. Build and release configuration

| # | Finding | Severity | Basis |
|---|---|---|---|
| B1 | **No release signing config.** `release` has no `signingConfig`, so CI can only produce debug-signed APKs. Play needs an upload key (Play App Signing). | Blocker | verified (`app/build.gradle.kts`) |
| B2 | **CI builds an APK, not an Android App Bundle.** Play requires `.aab` for new apps. There is no `bundleRelease` task in CI. | Blocker | verified + policy |
| B3 | **targetSdk / compileSdk = 35.** Play raises the minimum target API every year (35 became required in Aug 2025). Check the current requirement in Play Console; if it is 36, raise compileSdk/targetSdk to 36 and recheck behaviour changes (edge-to-edge, foreground services, overlays). | Likely blocker | policy |
| B4 | **R8 / minify disabled** (`isMinifyEnabled = false`). The release build is larger and unobfuscated. Enabling R8 needs keep rules for JNA/Vosk (JNA uses reflection on `Structure`/`Library` classes). The current `proguard-rules.pro` says "no reflection", which is no longer true since Vosk was added. | High | verified |
| B5 | `versionCode = 1` and `versionName = "1.0.0"` are hard-coded. CI has no versioning scheme, so every Play upload needs a higher versionCode. | Medium | verified |
| B6 | `abiFilters` includes **x86_64** (kept for the emulator). With an AAB, Play serves per-ABI splits, so this only costs download size for x86 devices. It is fine to keep, but the release bundle could drop it. | Low | verified |
| B7 | Toolchain: AGP 8.7.3 and Kotlin 2.1.20. These work, but a newer AGP is needed for compileSdk 36 (see B3). | Medium | verified |

## 2. Native code: Google Play 16 KB page-size rule

Apps targeting Android 15+ must support 16 KB memory pages for 64-bit native libraries.

| Library | arm64-v8a | x86_64 | 32-bit |
|---|---|---|---|
| `libvosk.so` (vosk-android 0.3.75) | 0x4000 ✅ | 0x4000 ✅ | 0x1000 (32-bit is exempt) |
| `libjnidispatch.so` (JNA 5.18.1) | 0x4000 ✅ | 0x4000 ✅ | 0x4000 |
| ML Kit face detection 16.1.7 native libs | **not checked** | **not checked** | — |

The Vosk and JNA rows were verified with `readelf -l` on the published AARs.

The ML Kit artifacts can't be downloaded from this environment (maven.google.com is blocked here). Add a CI step that runs `zipalign -c -P 16 -v 4` and `readelf` on the built APK/AAB. If ML Kit 16.1.7 is not aligned, update it to a release that is. **Rated High until checked.**

## 3. Manifest, permissions and Play policy declarations

| # | Finding | Severity | Basis |
|---|---|---|---|
| P1 | **`FOREGROUND_SERVICE_SPECIAL_USE` and `FOREGROUND_SERVICE_MICROPHONE`.** The Play Console foreground-service declaration needs a description and a demo video for each type. specialUse is reviewed manually; the subtype text in the manifest must match the real use (floating teleprompter over the camera app). | Blocker (for review) | policy |
| P2 | **`SYSTEM_ALERT_WINDOW`.** Not a restricted Play permission, but the store listing and the in-app permission screen must explain it. The in-app explanation exists (`FloatingPrompterDialog`). | Medium | verified + policy |
| P3 | **`RECORD_AUDIO` / `CAMERA`** need a privacy policy, plus accurate Data safety answers: audio is processed on-device with offline packs, or by the device recognition service, which may send it to Google; nothing is uploaded by LensPrompt. | Blocker (privacy policy URL is mandatory for these permissions) | policy |
| P4 | `INTERNET` is used only to download offline speech packs over HTTPS from alphacephei.com. Data safety should say that no user data is sent. | Medium | verified |
| P5 | Exported components: only `MainActivity` (launcher). The service is `exported=false`, and its PendingIntents are `FLAG_IMMUTABLE`. | OK | verified |
| P6 | **`allowBackup="true"` with no backup rules.** Offline speech packs (40–53 MB each) sit in `filesDir/vosk`. Android Auto Backup skips an app whose data exceeds 25 MB, so **once a pack is installed, the user's scripts would not be backed up at all.** Add `dataExtractionRules` (Android 12+) and `fullBackupContent` that exclude `vosk/` and the caches. | High | verified (file layout) + Android backup limits |
| P7 | No `networkSecurityConfig`. Cleartext is disabled by default on API 28+, so this is acceptable. | OK | verified |

## 4. Product and user-facing quality

| # | Finding | Severity |
|---|---|---|
| Q1 | **UI text is hard-coded in Kotlin.** There are 47 `Text("…")` literals and 0 `stringResource` uses; the overlay and notification strings are also in code. Localization (EN/FA/NL were requested) is impossible until they move to `strings.xml`. | High |
| Q2 | **No privacy policy, terms or open-source licenses screen.** Vosk is Apache-2.0 and JNA is LGPL-2.1/Apache-2.0 dual-licensed, so attribution is needed. Model licenses must be confirmed per model: the small en/nl/fa models are believed to be Apache-2.0, but this was not checked because alphacephei.com is blocked here. | Blocker (policy URL) / High (licenses) |
| Q3 | **No crash or ANR reporting.** Choosing between Firebase Crashlytics and Play Console vitals only is your decision; vitals need no SDK and are already available. | Medium |
| Q4 | **Debug features ship in release.** Debug mode, "simulated speech" and the diagnostics HUD are user-toggleable in Settings, and `Diagnostics` logs a full line every 2 s while Smart Follow runs. For release: keep Copy diagnostics for support, but rate-limit or gate the logcat output, and consider hiding "simulated speech" in release builds. | Medium |
| Q5 | **App icon / store assets.** There is an adaptive icon (vector foreground), but no 512×512 Play icon, feature graphic, screenshots or listing text in the repo. | Blocker for the listing (not for the code) |
| Q6 | **Onboarding.** There is a first-run card. There is no guided flow for the three key permissions (mic, overlay, notifications) or for downloading the offline pack. | Medium |
| Q7 | **Accessibility.** Content descriptions exist on the main controls and overlay. Not checked: TalkBack order in the overlay, contrast of the toolbar on bright camera previews, and font scaling in Settings. | Medium |
| Q8 | **Monetization.** None is implemented, and none was specified in the visible part of the request. | Decision |

## 5. Reliability: what is already in place

These are not findings. They describe what the 1.0 work builds on, all covered by CI:

- **Core engine and app logic:** about 70 unit tests, including Smart Follow scenarios, the hybrid follow, recognizer health and overlay geometry.
- **Emulator tests (10):**
  - app launch and script CRUD;
  - manual and simulated Smart Follow;
  - A/V mux;
  - real offline recognition for EN/NL/FA through Vosk and Smart Follow;
  - the overlay viewport never drawing outside its bounds;
  - every overlay exit path (×, lock strip ×, notification stop, in-app stop) and relaunching.
- **Floating mode:** confirmed by you on a Samsung device, together with the resize and text controls.

**Not covered by any automated test:**

- real-device recording with sound;
- A/V sync on phones;
- long sessions (battery, thermal, memory with an offline model loaded);
- Android 8–9 devices (minSdk 26).

## 6. Proposed order of work

One logical commit per item, so each can be reverted on its own:

1. Release build: signing config read from CI secrets (never committed), `bundleRelease` in CI, versionCode from the CI run number.
2. Backup rules that exclude speech packs (P6).
3. R8 enabled with JNA/Vosk keep rules, verified on the emulator, including `OfflineRecognitionTest` (B4).
4. 16 KB alignment check in CI; update ML Kit if needed (§2).
5. targetSdk/compileSdk 36 if Play requires it (B3).
6. Strings moved to resources, then EN/FA/NL translations (Q1).
7. About screen: version, privacy policy link, open-source licenses (Q2).
8. Release gating of debug features and log volume (Q4).
9. Permission onboarding (Q6).
10. Store listing material: text, screenshots plan, Data safety answers, foreground-service declaration text (P1, P3, Q5).

**Needs from you:**

- the upload keystore, stored as GitHub secrets;
- a privacy-policy URL (or permission to generate a policy page for you to host);
- the monetization model, if any;
- the final package name. `com.lensprompt.app` is permanent once published.

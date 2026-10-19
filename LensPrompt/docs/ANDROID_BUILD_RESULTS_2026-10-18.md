# Fresh Android build and test evidence — 18 October 2026

These results apply to the local readiness source derived from commit `b255abee786d447f6cc8aba6e3cf3532c563e4b3`, including the publication fixes. They do not certify the exact bundle already uploaded to Google Play. No APK or AAB was uploaded or promoted.

| Check | Fresh result |
|---|---|
| `:core:test` | **66 tests, 0 failures, 0 errors, 0 skipped**; 9 classes |
| `:app:testDebugUnitTest` | **9 tests, 0 failures, 0 errors, 0 skipped**; 3 classes |
| Diagnostic privacy regression | Passed: routine log output excludes recognized speech; explicit user-requested diagnostics retain their excerpt |
| `:app:lintDebug` | **Passed: 0 errors, 20 warnings** after scoped API fixes |
| `:app:assembleDebug` | Passed |
| `:app:compileDebugAndroidTestKotlin` | Passed, including the actual-interface screenshot test |
| `:app:assembleQa` | Passed with R8 minification, resource shrinking and vital lint tasks; debug-signed QA variant, never intended for Play upload |
| `:app:dependencies --configuration debugRuntimeClasspath` | Passed; selected SDK inventory recorded alongside this report |
| 64-bit native ELF alignment | All 12 ARM64/x86_64 libraries passed the repository 16 KB checker in both debug and QA APKs |
| APK native ZIP alignment | Official Android build-tools `zipalign -c -P 16 -v 4` passed for both debug and QA APKs |
| Package/version in both APKs | `com.lensprompt.app`, 1.0.0, version code 1; no package/version change |
| Generated default BuildConfig | Billing disabled; correct public policy and verified support contact |
| Instrumented UI/device checks | Not yet executed; source compilation does not exercise UI, camera, microphone or overlay behavior |
| Play installation / Play App Signing | Not verified; local APK checks do not verify the active Play artifact or sideload signature compatibility |

The app unit classes are `AppLogicTest` (4), `DiagnosticPrivacyTest` (1), and `EntitlementTest` (4). See `CORE_TEST_RESULTS_2026-10-18.md` for the core class counts.

`verification/2026-10-18/build-summary.json` records APK hashes, sizes and parsed package badging. The directory also contains the merged-manifest inventory, selected SDK dependencies, native alignment output and official ZIP-alignment output. Generated APKs and local build tools are intentionally not included in the publication packet or repository changes.

## Resolved dependencies and permissions

The generated debug manifest contains the eight explicit permissions described in `DATA_MAP.md` plus Billing, network-state access and an internal AndroidX signature-level receiver permission. No advertising ID or location permission is present. ML Kit and AndroidX startup providers are not exported.

The resolved graph confirms ML Kit Face Detection 16.1.7, ML Kit Common 18.11.0, Google DataTransport, Firebase encoders/components, Billing 8.0.0, Vosk 0.3.75 and JNA 5.18.1. Firebase encoding/transport components are not the Firebase Analytics or Crashlytics product. Neither advertising libraries, Firebase Analytics nor Crashlytics appears in this graph. This does not negate ML Kit's documented analytics and diagnostic reporting. Billing also brings a transitive Play Services Location library; no location permission or app location API call was found, so dependency presence alone is not evidence of location collection.

## Lint follow-up

The initial full debug lint run found two `NewApi` errors at `Os.fcntlInt`: `RecognizerAudioFeed.openSession` did not declare its API contract. Its only caller was already gated to Android 13+, when `EXTRA_AUDIO_SOURCE` is supported. The method now explicitly requires API 33. Lint also highlighted the microphone foreground-service type at API 29; its actual API 30 introduction is now respected. These are scoped compatibility/contract fixes, not evidence of a reproduced device crash. The final verification successfully reran lint, unit tests, both builds and instrumentation compilation after these changes. Lint now reports **0 errors and 20 warnings**, covering localization, accessibility, resource reflection, icon theming and maintenance suggestions; they remain recorded in `verification/2026-10-18/lint-summary.json` for review.

## Environment and remaining limits

The official Gradle 8.14.3 distribution and full Temurin JDK 17 download were checksum-verified. Android SDK API 36 and build-tools 35.0.0 were installed from Google's official repository. Existing network proxy settings and the normal system CA trust store enabled dependency resolution; certificate verification was not disabled.

There is no connected user phone. The emulator acceleration check returned “KVM requires a CPU that supports vmx or svm.” A disposable API 35 emulator with acceleration disabled reported boot completion after 554 seconds. Its first setup command (`adb shell svc power stayon true`) then exceeded a 20-second timeout before app installation or instrumentation began. The owned emulator was stopped; no screenshots were captured. This is a setup/performance limitation, not an observed app failure. The exact attempt is recorded in `verification/2026-10-18/software-emulator-attempt.json`. No successful runtime test, screenshot or Android 15/16 behavior claim follows from these build results. The prepared CI matrix uses API 35 and 36 with accelerated emulators once GitHub writes are available.

Before production, compare the active/uploaded AAB's source commit and flags, Play signing certificate, version code, merged manifest and bundle-generated split APKs. Repeat alignment checks on the actual release artifact; an aligned debug/QA APK does not by itself prove final AAB delivery alignment or all runtime behavior on a 16 KB device.

## Disclosure-copy follow-up

After connector access was restored, the offline-pack description in English, Persian and Dutch was corrected to describe possible system-service fallback instead of claiming that nothing is uploaded. The speech-engine comment and publication status were aligned with this behavior. Fresh `:app:processDebugResources` and `:app:testDebugUnitTest` passed; all 9 app tests have 0 failures/errors/skips. The APK hashes above remain evidence for the earlier build and are not claimed as hashes of a rebuilt follow-up APK. The remote API 35/36 jobs must finish before runtime success is reported.

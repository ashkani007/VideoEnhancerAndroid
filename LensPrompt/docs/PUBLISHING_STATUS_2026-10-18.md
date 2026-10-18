# LensPrompt publication readiness — 18 October 2026

## Result

The source audit and publishing materials are prepared. The public privacy policy is live at **https://lensprompt-privacy.ideal-jam-4118.chatgpt.site**, without sign-in. Its anonymous HTTP response was 200, and the served HTML contains the policy title, contact and all 13 sections. The page has a viewport declaration and responsive CSS; a mobile browser rendering has not been inspected.

**No Play Console section was modified or submitted. No app release was uploaded, promoted or published. No tester was added or invited.** Existing internal-track status is user-reported and was not independently reverified.

## Access and verification

| Operation | Result / evidence |
|---|---|
| GitHub read | Successful: `ashkani007/VideoEnhancerAndroid`, specified development branch, head `b255abee786d447f6cc8aba6e3cf3532c563e4b3` |
| GitHub writes | Creating a branch and Git tree both returned **403 Resource not accessible by integration**. No remote branch, commit or PR was created. Repository metadata saying the user has admin rights does not grant those rights to this integration. |
| Play Console browser | Opening the exact user-supplied `https://play.google.com/console` was rejected by automatic browser security review. It reported authority for a different origin (`https://google.play`). No attempt was made to bypass this rejection. |
| GitHub Pages | Repository `has_pages=false`; browser was signed out on the Pages settings URL. No Pages settings changed. The policy was published with Sites instead. |
| Browser recovery | Subsequent secure GitHub sign-in documentation request failed with a browser transport disconnect. No password or verification code requested. |
| Existing CI | Run **37666303409** on the audited source is marked successful. Downloaded emulator report shows **10 tests, 0 failures, 0 skipped**, generated 7 October 2026. The workflow uses an **API 34** emulator. This is historical evidence, not validation of today's changes or Android 15/16. |
| New unit/instrumentation tests | Not run. Local Gradle distribution download failed with “Network is unreachable”; Android SDK/emulator are absent. A proxy-configured retry also failed. GitHub write failure prevents launching the new workflow. |
| Static checks | XML parsing, workflow YAML parsing, `git diff --check`, listing character limits and PNG dimensions/modes checked. These do not replace a compile or device test. |

## Source-backed findings

Eight permissions are explicitly requested: `RECORD_AUDIO`, `CAMERA`, `INTERNET`, `SYSTEM_ALERT_WINDOW`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_SPECIAL_USE`, `FOREGROUND_SERVICE_MICROPHONE`, `POST_NOTIFICATIONS`. Camera/front camera/microphone features are optional in the manifest. Only the launcher activity is exported; the overlay service is not exported. See `DATA_MAP.md` for purposes and data routes. A merged manifest can contain additional SDK permissions, including Billing; inspect the actual uploaded AAB before final declarations.

- Default build: package `com.lensprompt.app`; version 1.0.0 / default code 1; min API 26; target/compile API 36; ARM64, ARMv7 and x86_64. The uploaded AAB's exact source commit and build flags remain unverified.
- Scripts and settings are local but included in Android backup/device transfer. No app backend uploads them. Private video fallback files and older-device transfer rules must not be described as universally excluded.
- Offline Vosk runs locally when that route is active. **An installed model does not guarantee all recognition is offline.** Automatic mode normally uses the system recognizer outside recording; failures can fall back to it, including when an offline engine was chosen. The system service can transmit audio and generate transcripts. Do not promise strict offline mode.
- ML Kit Face Detection 16.1.7 uses bundled camera analysis. Google documents technical usage/diagnostic collection and per-installation identifiers, including for bundled features. There is no independent metrics opt-out. Do not declare “no data collected” or “no analytics” for the entire app.
- No advertising SDK, developer analytics SDK, developer crash-reporting SDK or app account system is directly declared. ML Kit metrics and Android/Play telemetry remain distinct, real data handling.
- Play Billing 8.0.0 is linked but standard configuration sets `BILLING_ENABLED=false`; `DisabledProRepository` is used and does not connect to Play. Verify uploaded build configuration before declaring purchases absent.
- Floating Smart Follow can lose microphone audio to a sound-recording camera and switch to manual speed. This is an expected platform constraint; it must be shown honestly in testing and listing copy.
- `specialUse` and `microphone` foreground services need Console declarations and an actual demonstration. The notification Stop action and in-app/window close paths exist, but notification denial and API 35/36 behavior still need testing.

## Prepared changes

1. Set default HTTPS policy link and support email in `app/build.gradle.kts`. The contact was retrieved from the authenticated GitHub profile; it was not invented. Existing About buttons become visible in a build using those defaults.
2. Correct English, Persian and Dutch privacy summaries for Android backup, system speech and ML Kit metrics. Preserve functionality and package identity.
3. Redact the recognized-speech excerpt from routine diagnostic log lines, including unconditional failure/route logs. Keep explicit user-requested diagnostic exports useful. Add a regression test.
4. Explicitly disable cleartext network traffic in the manifest. Existing app URLs use HTTPS.
5. Add actual-interface screenshot capture and an API 35/36 QA workflow. This code is prepared but has not run; there are **no new app screenshots yet**.
6. Prepare English store text, icon/feature graphic, Data safety worksheet and a closed-test plan.

Local code changes require compilation and review before merge. Applying them to the already-uploaded internal version eventually requires a **necessary update with a higher version code**; a store-policy field cannot change an installed binary. Do not rebuild/upload merely to investigate “Item not found.” Do not replace package identity or remove the current release.

## Remaining blockers in order

1. Restore a permitted Play Console browser session and a GitHub connection with repository write capability. No Google/GitHub password, OTP or signing password should be sent in chat.
2. Push/review the local changes and run the new QA workflow. Inspect merged permissions, dependency tree, build flags, release signing/16 KB native alignment and actual screenshots. Match the Console AAB to source/version evidence.
3. Resolve the speech-provider Data safety classification and security/retention questions in `PLAY_CONSOLE.md`. Public policy notice alone does not replace an in-app disclosure/affirmative consent where required. Verify consent and metrics treatment for intended markets before production.
4. Save and verify the Console setup sections, review the IARC questionnaire and age target, then ask the owner before any final attestations, agreements or production rollout.
5. Configure closed testing using the existing bundle where appropriate, an actual tester list and the exact Console opt-in link. At least 12 real testers must remain opted in for 14 consecutive days before applying for production access; internal testing does not meet this requirement. No start date, eligible tester count or completed day count was verified in this session.
6. Complete device acceptance tests, review feedback and fix critical failures. Production access is an application reviewed by Google, not an automatic unlock on day 14.

## Sources checked

- https://support.google.com/googleplay/android-developer/answer/14151465?hl=en — personal-account testing and production access.
- https://support.google.com/googleplay/android-developer/answer/9845334?hl=en — tracks, propagation, internal/closed opt-in interaction.
- https://support.google.com/googleplay/android-developer/answer/10787469?hl=en — Data safety scope, ephemeral collection and sharing exceptions.
- https://support.google.com/googleplay/android-developer/answer/10144311?hl=en — policy, in-app disclosure and consent.
- https://developers.google.com/ml-kit/android-data-disclosure — ML Kit telemetry; the current face-detection integration guide also lists bundled 16.1.7, matching this source. Inspect resolved transitive dependencies and the uploaded artifact before submission.
- https://developers.google.com/ml-kit/terms — input analysis on device; SDK metrics off device.
- https://developer.android.com/reference/android/speech/SpeechRecognizer — remote service behavior.
- https://support.google.com/googleplay/android-developer/answer/9866151?hl=en — store assets and limits.

GitHub source: https://github.com/ashkani007/VideoEnhancerAndroid/tree/claude/lensprompt-android-dev-s2ojat

Historical CI evidence: https://github.com/ashkani007/VideoEnhancerAndroid/actions/runs/37666303409

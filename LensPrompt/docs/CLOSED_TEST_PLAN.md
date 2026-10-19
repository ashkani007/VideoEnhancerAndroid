# Closed testing and production acceptance

Prepared 18 October 2026. **Track configuration, rollout, opt-in count and test start date are unverified; no invitations were sent.**

## Configure when Console access is restored

1. Complete app setup, policy/listing assets and required declarations with owner approval for final attestations. Inspect the existing bundle; do not recreate the app or change `com.lensprompt.app`.
2. Use the initial closed track, or a clearly named track such as “LensPrompt closed beta.” Reuse the existing uploaded AAB if it is appropriate for the test; do not upload a duplicate. Required code fixes need a tested, signed update with a strictly higher version code, not a duplicate code 1.
3. Create/select an email list containing consenting real testers, or a real Google Group. Save and re-open the tester configuration to verify. Set feedback contact to the verified owner email or an owner-approved channel. Use actual tester locations for country availability; do not change all tracks' geography without checking scope.
4. Copy the exact closed-track opt-in link from Console. No closed-track link was verified here. Prepare a draft release and present any final review/attestation action to the owner before submitting.
5. Recruit at least 12 real testers, preferably with some buffer for dropouts. Each must opt in using their eligible Google account and remain opted in for **14 consecutive days**. Internal-test time does not count. A person in the internal test must opt out of it before joining closed testing; verify the correct opt-in state. Do not remove the internal test globally.
6. Confirm availability/installation and capture truthful engagement, feedback and defect records. The qualifying period begins with the real eligible closed-test state, not creation of an email list or this document. Do not pre-fill completed days or invent usage. Apply for production access only after eligibility is visible; Google also reviews engagement, feedback and readiness.

## Invitation draft — owner sends after links are verified

Subject: Help test LensPrompt on Android

I'm preparing LensPrompt, a floating teleprompter with speech-assisted scrolling and an optional built-in recorder. Please use the Google account you provided for testing, join through [COPY THE VERIFIED CLOSED-TRACK OPT-IN LINK], and install the test version from Google Play. If you are in LensPrompt's internal test, first opt out of that track and then join this closed test.

Please remain opted in for at least 14 consecutive days and try the features below on several occasions. Report what worked and what failed; no positive review is requested. Keep a copy of important scripts and recordings before any uninstall or data clearing. An external camera recording sound can take the microphone, so floating Smart Follow may use manual scrolling in that case. Speech-provider processing and SDK diagnostics are described at https://lensprompt-privacy.ideal-jam-4118.chatgpt.site . Send feedback through Google Play's private test feedback or abbasian7iraj@gmail.com. Never send private recordings or scripts without checking their contents.

## Device matrix

- Android 15 / API 35: physical phone and prepared emulator QA.
- Android 16 / API 36: physical phone and prepared emulator QA.
- The owner's current phone/OS must be read from the device, not inferred from prior chat metadata; test it separately if newer than Android 16.
- At least one Samsung device with its stock camera and one other maker if available.
- An older supported Android 8–9 device for app-private recording/uninstall/storage behavior, and an API 29+ device for shared media behavior.
- Both a device with working on-device speech and one exercising the default system recognizer, with EN/NL/FA and at least one other supported language.

## Acceptance cases — all pending a fresh run

| ID | Procedure | Pass evidence |
|---|---|---|
| O1 | Start overlay from a script; move, resize, rotate, change opacity/font/line spacing, mirror and lock | Text remains reachable/in bounds; no overlay trap; settings persist sensibly |
| O2 | Close via ×, locked-strip exit, notification Stop and in-app Stop; reopen | Overlay and service disappear, microphone stops, every exit remains accessible |
| S1 | Read a 60–120 second script, pause 2/5/10 seconds, speed up, repeat a phrase, skip a sentence | Word-driven motion when recognition works; no sustained runaway on silence; recovery without large unexplained jumps |
| S2 | Deny/revoke microphone access before and during use | Clear explanation and usable manual mode; no crash/restart loop or hidden listening |
| S3 | Test offline pack, Automatic and System routes; disconnect network; force an unavailable language/model | Route/failure/fallback is honest; no claim of strict offline mode; actual behavior matches policy |
| C1 | Built-in camera, front/back, portrait/rotation; record 30/120 seconds with audio on/off | Saved playable files, correct orientation, no lost video, visible sound failure if muxing fails |
| C2 | While recording with sound, read with an offline pack and with system recognition; clap at start/end | Smart Follow and A/V sync assessed on real hardware; report measurable drift or fallback |
| M1 | Float above stock camera with sound ON and OFF | Record which app owns mic; manual fallback is signaled when speech audio is silenced; resumes when available |
| L1 | Switch recognition and script languages EN/NL/FA; Persian RTL and mixed numbers | Readable editing/prompting, correct direction, model selection and supported-language behavior |
| U1 | Manual speed, finger drag, pause/resume, countdown and restart | Full script reachable; stable position and no unintended recognition |
| B1 | Home/background, incoming-call interruption, screen lock/unlock and app resume during prompting/recording | Built-in capture stops as intended; user-started overlay lifecycle/notifications remain correct; no unauthorized background restart |
| P1 | Overlay denied/revoked; camera denied; notifications denied; mic one-time permission | No crash or blocked exit; clear recovery; manual mode where possible |
| D1 | Create/edit/duplicate/delete scripts, restart, long Unicode text, backup/device restore | No silent data loss; settings/backup behavior matches disclosure |
| D2 | Download/cancel/delete/import a model, no-network/low-storage/bad ZIP | Accurate progress/error; no corrupted existing model or stuck state |
| Q1 | 30-minute use, rotations, repeated open/close and interruptions on API 35/36 | No crash, ANR, unbounded memory/thermal problem or leaked mic/service |
| A1 | Large font, TalkBack and bright camera background | Essential controls labeled, legible and reachable; close never hidden permanently |
| V1 | Install/update through Play on an eligible account, preserving existing data | Correct package/version/installer; no unsupported signer/downgrade workaround |
| R1 | Compare actual binary permissions, build flags, native 16 KB alignment, collected-data paths and policy link | Release evidence matches declarations and public policy; no secrets in logs or artifacts |

StoreScreenshotTest captures actual paused UI only; it does not prove microphone, camera or speech synchronization. Historical API 34 CI (10 passing tests) is baseline evidence, not a pass for this matrix.

## Feedback and defect handling

Record tester, consented contact/account identifier, device/model/API, installed version, date, test case, steps, expected/actual result, reproducibility and severity. Keep this roster private; do not publish tester emails in GitHub or public artifacts. Redact scripts, speech excerpts and unrelated information from shared evidence.

Block production for crashes/ANRs, script loss, recordings silently lost, incorrect privacy notices, unexpected remote processing relative to disclosures, unusable close controls or broken Play installation. Record microphone exclusivity as a compatibility limitation when the UI and listing correctly explain fallback, rather than promising a universal fix.

Create a separate fix branch/PR for reproduced critical defects, add a meaningful regression where practical, run affected checks, and retest on the failing device. Do not merge or roll out production without the owner's required approval.

## Production-access answers after actual testing

Summarize how testers were recruited, which functions they actually used, real feedback, changes made and the evidence for readiness. Estimate audience/install expectations honestly with owner input. These responses must remain blank until supported by the completed test record.

Official requirements checked: https://support.google.com/googleplay/android-developer/answer/14151465?hl=en and https://support.google.com/googleplay/android-developer/answer/9845334?hl=en .

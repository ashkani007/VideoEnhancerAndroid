# Internal testing — “Item not found” diagnosis

18 October 2026. **Current installation success is not verified.** Console, tester account identity on the phone and the phone's package/signature state were unavailable. No app was uninstalled, app data cleared, release replaced or package name changed.

User-reported state: internal release 1.0.0 active, Available on Play 100%, tester list Iraj enabled, prior opt-in successful, package shown as unreviewed, and a sideloaded APK previously installed. These reports narrow the investigation but do not prove that today's store request uses the same account or that installation succeeds.

| Check | Evidence now | Next observation needed |
|---|---|---|
| Track release | User reports active/100%; not reverified | Console internal release: exact version code, availability and pending changes |
| Tester eligibility | User reports Iraj list enabled and opt-in confirmed | Read saved list and compare exact Google identity used by browser opt-in and Play Store |
| Store account matching | Not observed | On phone, verify Play account for the store request equals the eligible opt-in account; multiple Google accounts are a common distinct source of mismatch |
| Propagation | Unknown time since last change | Google says initial test links/updates can take hours. Do not repeatedly rebuild while waiting. |
| “unreviewed” package title | Expected for an app before its first review | Google explicitly allows internal tests before app setup is complete. This label alone does not prove an installation blocker or a broken bundle. |
| Device compatibility | Source supports API 26+, optional camera/mic, ARM64/ARMv7/x86_64; uploaded artifact unverified | Inspect uploaded AAB supported ABIs/SDK/manifest and Play's result for the actual device; source alone cannot certify compatibility |
| Countries/exclusions | No evidence of a country blocker | Google's internal-track documentation says country distribution and device exclusion rules do not apply to internal testers in the usual way. Do not diagnose this solely from closed/production country settings. |
| Prior sideload | Signing identity unknown | Compare installed APK signer/version with Play-distributed app signing certificate, not only the upload-key certificate |
| Install from Play | Not attempted/observed this session | Eligible opted-in tester opens the Console-provided link and installs/updates; verify app version and installer afterward |

**A signature mismatch can block an update after Play offers the package. It does not, by itself, explain a catalogue page displaying “Item not found.”** Investigate eligibility/account/propagation separately from update-signature or downgrade errors. A matching package name does not imply matching signing certificates; Play App Signing may distribute an app signed differently from a debug or manually signed APK.

If an installed sideloaded build has a higher version code, Play may not offer a downgrade. Compare versions before considering any replacement. Do not upload a new bundle merely to change the catalogue page.

**Preserve local content:** never recommend or perform uninstall or Clear storage as the first step. Scripts/settings and Android 8–9 private recordings can be lost. Verify a usable export/copy of scripts, settings and private videos first; the current app has no general script-export button. Clipboard copy from the editor or an authorized app-data extraction may be needed. Android backup being enabled is not proof of a recoverable current backup. If replacement still requires uninstall, warn the owner and obtain their decision first.

An authorized USB-device investigation can use read-only `adb shell dumpsys package com.lensprompt.app`, installed APK certificate inspection and `adb shell pm list packages -i` to verify version/signing/installer. No phone was connected here. Do not collect or publish unrelated device/account information.

Official reference: https://support.google.com/googleplay/android-developer/answer/9845334?hl=en . No statement in this document claims the prior problem is now fixed.

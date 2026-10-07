# Google Play Console: tasks and draft texts for LensPrompt 1.0

Package: **`com.lensprompt.app`** (permanent; never change without the owner's approval).

## A. Account and app setup (owner)

1. Create the developer account, or use an existing one. Complete identity verification. A new personal account must run a **closed test with testers for 14 days** before production access. Check the current requirement in Play Console.
2. Create the app "LensPrompt" with default language, app type **App**, **Free** (Pro is in-app).
3. Turn on **Play App Signing**. Create the upload key and add it to GitHub secrets (`docs/RELEASE_SIGNING.md`).
4. Upload the signed AAB to **Internal testing**, then to Closed testing.

## B. Policy declarations (App content)

| Item | What to enter |
|---|---|
| Privacy policy URL | The hosted version of `docs/PRIVACY_POLICY.md`, with `[[OWNER]]` items completed |
| Ads | No ads |
| App access | All features are available without login. No credentials are needed. |
| Content rating | Questionnaire: utility/productivity, no user-generated content shared with others |
| Target audience | Adults / 16+ or 18+ (owner decision; not designed for children) |
| Data safety | Use `docs/DATA_MAP.md` §4. **First check ML Kit's current data disclosure.** |
| Government apps / financial / health | No |
| **Foreground service: `specialUse`** | See text C1, plus a demo video |
| **Foreground service: `microphone`** | See text C2 (same video) |
| Permissions: camera, microphone | Explained in the listing and in the app |

## C. Draft declaration texts

**C1 – specialUse foreground service**

> LensPrompt shows a floating teleprompter window (SYSTEM_ALERT_WINDOW) over the user's camera app, so they can read their script while recording with the camera app they already use. The foreground service keeps this user-started window alive while another app is in front. It always shows a notification with a "Stop teleprompter" action, and the user can close it at any time with ✕ on the window or "Stop floating mode" in LensPrompt. It runs only while the floating teleprompter is open.

**C2 – microphone foreground service**

> While the floating teleprompter is open, its "Smart Follow" feature listens to the user reading their script and scrolls the text along with their voice. Audio is processed on the device (offline speech packs) or by the device's speech recognition service, and is not stored or uploaded by LensPrompt. Listening starts only when the user presses Play with Smart Follow on, and stops when they pause, switch to manual or close the window.

**Demo video (record on a real device, 30–60 s):**

1. Open LensPrompt and choose a script.
2. Tap "Use with phone camera" and grant permissions.
3. The overlay appears over the camera app; tap ▶ with AUTO on and read.
4. Show the text following the voice.
5. Show the notification with "Stop teleprompter" and tap it.

## D. Store listing drafts

**App name (≤30):** `LensPrompt – Teleprompter`

**Short description (≤80):** `A teleprompter that works over the camera you already use, and follows your voice.`

**Full description (draft):**

> LensPrompt is a teleprompter for creators, presenters, teachers and anyone who records scripted video.
>
> • **Works over your camera app.** A floating, resizable teleprompter stays on top of Samsung Camera, Google Camera, Instagram, TikTok or any camera app. Place it right next to your selfie camera.
> • **Smart Follow.** LensPrompt listens as you read and scrolls with you: it slows when you slow down, waits when you pause and finds its place again if you skip ahead. Prefer a fixed speed? Use manual scrolling.
> • **Offline speech.** Optional offline speech packs (English, Dutch, Persian, German, French, Spanish) keep recognition on your phone.
> • **Built-in camera.** Record directly in LensPrompt, with the script in front of the lens and sound recorded alongside.
> • **Made for reading.** Adjustable text size, line spacing, transparency, alignment and mirror mode, a lock mode and a reading marker.
> • **Private by design.** No account, no ads, no analytics. Your scripts stay on your device.

**Graphics needed (owner/designer):**

- 512×512 icon. Derive it from `res/drawable/ic_launcher_foreground.xml`.
- 1024×500 feature graphic.
- At least 2 phone screenshots, ideally 6 to 8:
  - library;
  - floating teleprompter over a camera app;
  - Smart Follow in action;
  - the settings panel;
  - offline speech packs;
  - built-in camera.

**Category:** Video Players & Editors, or Productivity (owner decision).

## E. Before production

- [ ] Physical-device test pass (see the RC report).
- [ ] Privacy policy hosted, and the URL set in the build (`-Plensprompt.privacyPolicyUrl=…`). Set the support e-mail (`-Plensprompt.supportEmail=…`).
- [ ] Data safety submitted.
- [ ] Foreground-service declarations approved.
- [ ] Closed testing period completed (if required for the account).
- [ ] Pro: keep billing off for 1.0, or follow `docs/MONETIZATION.md`.

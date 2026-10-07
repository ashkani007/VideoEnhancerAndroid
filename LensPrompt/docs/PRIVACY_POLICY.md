# LensPrompt Privacy Policy (DRAFT)

> **Draft for owner review. Not yet published.**
> Fill in every `[[OWNER: …]]` before publishing, and host the final version at a public HTTPS URL.
> Then build with `-Plensprompt.privacyPolicyUrl=<url>` so the app links to it.
> Every statement is based on the app's code at the time of writing (see `docs/DATA_MAP.md`).
> Items marked **[VERIFY]** depend on third-party software and must be checked before publishing.

**Effective date:** [[OWNER: date]]
**Developer / data controller:** [[OWNER: legal name and address]]
**Contact:** [[OWNER: support e-mail]]

## Summary

- LensPrompt has **no account, no ads and no analytics**. It does **not upload** your scripts, recordings or audio to any server operated by us. We do not operate any server for the app.
- Your scripts, settings and videos are stored **on your device**.
- Speech recognition happens on your device when you use an **offline speech pack**. Without one, your device's own speech recognition service (for example from Google or Samsung) does it, under that provider's privacy policy.

## 1. Information stored on your device

- **Scripts and settings.** The text you write or paste, and your app settings, are stored in LensPrompt's private storage on your device. If Android backup or device transfer is turned on in your phone settings, Android may include them in your device backup (for example your Google account backup) or copy them to a new phone. Offline speech packs and videos are excluded from these backups.
- **Videos you record.** When you record in LensPrompt, the video (and sound, if "Record audio with video" is on) is saved on your device:
  - Android 10 and newer: in **Movies/LensPrompt**;
  - Android 8–9: in LensPrompt's own media folder.

  Other apps you allow to access your media can read videos in shared storage. Temporary files used while saving a video are deleted after saving.
- **Offline speech packs.** Speech models you choose to download are stored in LensPrompt's private storage until you delete them.

## 2. Microphone

LensPrompt uses the microphone only:

- while **Smart Follow** is running (a microphone indicator is shown in the app);
- while **recording a video with sound**;
- while the **floating teleprompter** follows your voice.

How your speech is turned into text:

- **With an offline speech pack:** recognition runs **inside LensPrompt on your device**. The audio and the recognized words are not sent anywhere and are not stored, except as the soundtrack of a video you choose to record.
- **Without an offline speech pack:** LensPrompt asks your device's **speech recognition service** (chosen in your phone's settings, for example Google or Samsung) to recognize speech. That service receives the audio and may process it on its servers under its provider's privacy policy. LensPrompt receives only the recognized text. If you turn on "Prefer on-device recognition", LensPrompt asks the service to stay on the device, but the service decides.
- While another app (for example your camera app) records sound, Android may give LensPrompt silence instead of microphone audio.

## 3. Camera

The camera is used for the preview behind the script and for recording videos. If **Lip tracking** is on, the front-camera image is analysed **on your device** by Google ML Kit face detection to tell whether you are speaking; images are not stored or sent by LensPrompt. **[VERIFY]** According to Google's documentation, ML Kit may send limited usage and diagnostic information (such as device model, app version and performance metrics) to Google. Confirm the current ML Kit data disclosure and describe it here.

## 4. Network use

LensPrompt connects to the internet only:

- **when you download an offline speech pack.** The file is downloaded over HTTPS from **alphacephei.com** (the Vosk project). As with any download, that server receives your IP address and basic request information. No personal data from LensPrompt is sent;
- **[When LensPrompt Pro is launched]** to Google Play for purchases (see section 6);
- by the third-party components described in sections 2 and 3.

## 5. Diagnostics

If you turn on **Diagnostics overlay**, LensPrompt shows technical details on screen and writes them to the device log. These include up to 60 characters of the most recently recognized speech. Only you can share them, using "Copy diagnostics". Nothing is sent automatically.

## 6. Purchases (LensPrompt Pro)

[[OWNER: keep this section once Pro is launched.]] Purchases and subscriptions are processed by **Google Play** under Google's terms and privacy policy. LensPrompt receives only the information needed to unlock Pro (product and purchase identifiers). We do not receive your payment details. You manage or cancel subscriptions in Google Play.

## 7. Children

LensPrompt is not directed to children under [[OWNER: 13 / 16 depending on target markets]].

## 8. Your choices and deletion

- Delete scripts in the app, delete speech packs in Settings → Offline speech, and delete videos in your gallery.
- Uninstalling LensPrompt removes its private data (scripts, settings, speech packs). It also removes Android 8–9 recordings stored in its own media folder. Videos in Movies/LensPrompt (Android 10+) stay until you delete them.
- You can revoke microphone, camera, overlay and notification permissions at any time in Android settings.

## 9. Data sharing and sale

We do not sell personal data and do not share it with advertisers or data brokers. Third-party services you use through LensPrompt are described above.

## 10. Changes

We will update this policy when the app's data practices change and show the new effective date.

## 11. Contact

[[OWNER: contact e-mail and postal address; EU/UK representative if required]]

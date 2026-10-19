# LensPrompt Privacy Policy

Last updated: 19 October 2026

LensPrompt (Android package `com.lensprompt.app`) is published by **Supernova studio**. This policy explains how LensPrompt handles information when you write scripts, use the floating teleprompter or Smart Follow, and record video.

**Privacy and support contact:** [abbasian7iraj@gmail.com](mailto:abbasian7iraj@gmail.com). Include “LensPrompt privacy” in your subject for privacy requests. You do not need a LensPrompt account to use the app.

## 1. What LensPrompt does

LensPrompt displays scripts, scrolls them manually or with speech assistance, shows a floating window over other apps, and offers an optional built-in camera. Supernova studio does not operate an app server that receives your scripts or recordings. However, this does **not** mean that every feature is offline: your Android speech recognition provider may process audio online; Google ML Kit sends technical metrics; speech pack downloads and Android backup involve other providers.

LensPrompt contains no advertising SDK, advertising placements or separate marketing analytics SDK. The technical usage analytics described under ML Kit still apply.

## 2. Scripts, settings and clipboard

Script titles, text, creation and editing times, and your most recent opening time are saved in private app storage. Display preferences, selected recognition language, speech engine choices and floating-window settings are saved on your device. LensPrompt reads clipboard text when you choose to create a script from the clipboard; it does not continuously monitor the clipboard.

LensPrompt does not upload scripts to Supernova studio, publish them to other users, or provide a cloud script account. Android backup and device transfer can copy app data, including scripts and settings, to your backup provider or another device when enabled in your device settings. Downloaded speech packs and per-device speech-service compatibility records are excluded by the app's backup rules. Device makers and Android versions control the backup and transfer service. Copies already present in backups may remain until that service replaces or deletes them.

## 3. Microphone and Smart Follow

With microphone permission, LensPrompt listens while a Smart Follow session is running, including in the floating window, and while you record a video with sound. Pausing or stopping Smart Follow stops that recognition session; if a video with sound is still recording, microphone capture continues for the recording. Closing floating mode stops its listening service.

**Offline speech packs.** When the Vosk offline engine is the active recognition route, LensPrompt processes microphone samples and recognized words on the device. These samples are not uploaded to a speech server by Vosk. An installed pack alone does not force all sessions offline: Automatic mode may use the system recognizer, and recognition failures can cause a fallback to that service. The engine and its availability depend on your settings, selected language and whether you are recording.

**Android speech recognition.** LensPrompt can ask the speech recognition service installed or selected on your phone, such as a Google or Samsung service, to recognize your speech. The service receives microphone audio, the language and recognition configuration, and the calling app identity. On supported Android versions it may instead receive an audio stream captured by LensPrompt. It can send audio and related data to its provider's servers and generate transcripts under that provider's terms, retention rules and privacy policy. LensPrompt receives recognized text for aligning and scrolling your script; it does not send the stored script as a recognition prompt.

“Prefer on-device recognition” is a request to the provider, not a guarantee. The current app may fall back to the default service if a local route or language is unavailable. For a session that must stay offline, select an installed offline pack and verify operation with network connectivity disabled. You can use manual scrolling without speech recognition.

Android may silence LensPrompt when another app owns the microphone, particularly while an external camera records sound. Floating mode can then use fixed-speed scrolling. Lip-movement assistance in the built-in camera is not speech-to-text or a way to transcribe words without microphone access.

## 4. Camera, lip movement and Google ML Kit

Camera permission enables the built-in preview and video recording. Optional lip-movement assistance analyses camera frames with the bundled Google ML Kit Face Detection SDK to estimate mouth movement. Frames and face contours are processed on the device. They are not sent to Google for face analysis, and LensPrompt does not use them to identify a person or create a face identity database. Analysis frames and mouth measurements are not separately saved by LensPrompt; camera content is saved if you choose to record a video.

**ML Kit technical collection.** Google's documentation states that its SDK collects device manufacturer/model, operating system/build and available machine-learning hardware; app package and version; a per-installation identifier for bundled features; performance metrics; API configuration such as image format/resolution; input/output sizes; feature versions; event types and error codes. Google uses this information for diagnostics and usage analytics, including maintaining and improving its APIs and detecting misuse. This is technical collection even though camera analysis itself stays on the device. Google states that these transmissions use HTTPS and that the listed metrics are not transferred onward to third parties by ML Kit.

Turning off lip assistance prevents that camera analysis; SDK initialization and technical reporting may still occur. LensPrompt does not provide a separate SDK-metrics opt-out switch. See [ML Kit privacy](https://developers.google.com/ml-kit/terms), [ML Kit data disclosures](https://developers.google.com/ml-kit/android-data-disclosure), and [Google's Privacy Policy](https://policies.google.com/privacy).

## 5. Video and audio files

Recording starts when you choose Record. With sound enabled, LensPrompt captures audio and video separately, temporarily stores the data in app cache, and combines them into a video. Normal completion deletes the temporary files. If recording or saving is interrupted, temporary files may remain until app storage is cleared, the app is uninstalled, or Android clears its cache. A save failure may result in a video without sound; the app reports that condition.

On Android 10 and later, finished recordings are normally saved to `Movies/LensPrompt` in shared media storage. On Android 8–9, they are normally saved in the app-specific Movies directory. Private internal storage can be used if an external app directory is unavailable. Android backup or device transfer may handle private files according to the installed app version and device's rules. Apps you permit to access your media, and gallery or photo-backup services you enable, may access or sync shared videos under their own policies. LensPrompt itself does not upload finished videos to Supernova studio.

When you use LensPrompt over an external camera app, that app controls its own camera, recordings, media backup and privacy practices. LensPrompt does not receive the external app's recorded video.

## 6. Offline model downloads and imports

Speech packs are optional, user-requested downloads from `https://alphacephei.com/vosk/models/`. A request exposes the IP address, requested model/file, request time and normal network request information to the host and its delivery providers. LensPrompt does not attach your script, microphone recording or account details to the request. Packs are approximately 39–53 MB; sizes and availability can vary.

You can also import a Vosk model ZIP using Android's file picker. The selected file or document provider supplies its contents to LensPrompt. That provider may be a local or cloud-storage app; its own policies apply. Installed packs are stored privately until deleted in Settings or removed with app data. LensPrompt does not upload an imported pack.

## 7. Diagnostics

LensPrompt maintains recognition and audio-route diagnostics such as error codes, timing, sample rate, microphone status and recognition-service identity. A short excerpt of the most recent recognized speech can appear in the optional diagnostic view and an export you choose to copy. Some internal builds also include it in local device logs. These records are not automatically sent to Supernova studio. Review copied diagnostics before sharing them; they may contain spoken text or other contextual information. Clipboard and device-log retention are controlled by Android and any tools you use to access them.

## 8. Permissions and background operation

- **Microphone:** Smart Follow and sound in recordings.
- **Camera:** preview, recording and optional lip-movement analysis.
- **Display over other apps:** the movable, resizable floating teleprompter. This does not grant LensPrompt permission to read another app's screen or files.
- **Foreground service, special use and microphone:** keep the user-started floating window available and support its listening session while another app is in front. The service has a notification with a Stop action and can also be closed from the window or the app.
- **Notifications:** controls and status for floating mode, subject to Android notification settings.
- **Internet:** model downloads and the third-party service/SDK network activity described above.

LensPrompt does not request location, contacts, SMS, call-log, broad photo-library or accessibility-service access. You can revoke runtime and special permissions in Android settings. Features requiring a permission may then be unavailable; manual prompting does not require camera or microphone permission.

## 9. Billing, advertising and third-party platforms

The standard 1.0.0 configuration has LensPrompt Pro billing disabled. Although the Google Play Billing library is included, the disabled configuration does not open a billing connection or offer purchases. Supernova studio does not receive payment-card details. If purchases are activated in a future release, the applicable disclosures will be updated before launch.

Google Play and Android may separately collect store, installation, crash, performance and backup information under their own settings and policies. This is distinct from a developer-operated crash-reporting service; none is integrated in the audited app. Your speech provider, file provider, gallery and external camera are separate services.

## 10. Purposes, legal bases and international processing

Information used locally supports the functions you request: storing and displaying scripts, aligning speech, recording video and remembering settings. Permissions and feature choices control access. Where applicable, processing needed to provide the requested service relies on that necessity; optional access relies on your permission or consent where required. Support handling and essential maintenance rely on providing the requested assistance and legitimate interests, subject to applicable law. This policy is a notice, not a substitute for consent where consent is legally required.

Third-party providers may process network requests, speech or technical metrics outside your country, including outside the EEA, under their own privacy notices and applicable safeguards. Supernova studio does not control those providers' full retention periods or claim that all third-party processing is temporary. We do not sell personal data or provide it to advertising brokers.

## 11. Retention, deletion and your controls

Scripts and settings remain in app storage until you edit/delete them, clear storage or uninstall. Speech packs remain until deleted or app data is removed. Recordings remain until you delete them in the relevant gallery or storage location; shared recordings normally survive uninstall, whereas app-specific recordings can be removed with the app. Save a copy of anything important before uninstalling or clearing storage.

You can delete scripts in the library, delete downloaded packs in Settings, turn off camera/lip assistance or Smart Follow, switch to manual scrolling, and manage permissions and backups through Android. Deleting local data does not necessarily delete an earlier Android or gallery backup. Manage those copies with the provider that holds them.

There is no LensPrompt user account to delete and no developer-held cloud script library. If you contact support, we receive what you send, such as your email address, message and attachments. We use correspondence to answer the request and retain it only as needed to handle the matter, comply with legal duties or resolve related disputes. Do not send passwords, signing keys or private recordings unless necessary for your request. You may ask us to delete support correspondence, subject to lawful retention requirements.

Depending on applicable law, including the GDPR in the EEA, you may have rights of access, correction, deletion, restriction, portability, objection and withdrawal of consent, and a right to complain to a data-protection authority. Contact the email above for data Supernova studio holds; manage local data on your phone and contact the relevant provider for its own records. Withdrawal does not affect earlier lawful processing.

## 12. Teen users and children

LensPrompt is intended for teenagers aged 13 and above and adults. It is not directed to children under 13. LensPrompt does not ask for a date of birth and does not create user accounts. The data practices described above, including third-party speech processing and ML Kit technical collection, also apply to teen users. If you believe a child under 13 has provided personal information to our support contact, contact us to request review and deletion.

## 13. This webpage and policy changes

This public policy page is hosted on GitHub Pages by GitHub and its hosting providers. Delivering the page can involve normal web-server information such as IP address and request headers under the providers' policies. The page itself has no sign-in, advertising scripts or analytics code added by Supernova studio. Opening external links or sending email involves the service you choose.

We will update this policy when practices change and show the new revision date. A change to advertising, billing, recognition providers or data collection requires corresponding updates to the app disclosures and store declarations. For questions, contact **Supernova studio** at **abbasian7iraj@gmail.com**.

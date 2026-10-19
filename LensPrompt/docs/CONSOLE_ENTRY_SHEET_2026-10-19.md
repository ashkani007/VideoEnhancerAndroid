# LensPrompt — source-backed Console entry sheet

Updated 19 October 2026, Europe/Brussels. Prepared for package `com.lensprompt.app`, Supernova studio. **These are drafts, not saved Console declarations.** The official Console route now opens Google's sign-in page. The secure authentication request timed out; successful sign-in has not been observed. The active Play AAB has not been matched to source; no new release was uploaded.

## Entries ready for exact-form review

| Section | Prepared English answer | Evidence / limit |
|---|---|---|
| Privacy policy | https://ashkani007.github.io/VideoEnhancerAndroid/ | Verified public HTML, anonymous HTTPS 200; Pages deployment succeeded. Owner reports it saved in Console. |
| App access | No sign-in or reviewer credentials required. | No app authentication, account or backend. `ProPolicy.PRO_ONLY` is empty in the inspected source. Android permission prompts are normal feature permissions. |
| Ads | No, the app does not contain ads. | No ad placements, ad SDK or advertising-ID permission found. SDK technical analytics still exist and belong in Data safety. |
| Content rating | Utility/teleprompter; no app-supplied violence, sexual content, gambling, controlled-substance content or public user-to-user communication. | Answer exact IARC questions, then let IARC generate the rating. Users can create private scripts; do not answer a general “can users create content?” question as No. No public content exchange is implemented. |
| Government apps | No government affiliation or government service functionality is represented by the inspected app. | Independent teleprompter; do not invent an official relationship. |
| Financial features | No financial features. | No banking, lending, investing or cryptocurrency service. A bundled, disabled billing library is not a financial-services feature. |
| Health declaration | No health features. | Lip movement estimates speaking activity; it is not diagnosis, medical assessment or fitness tracking. |
| App category | App → Video Players & Editors | Accurate category for prompting/recording. Use only available tags that match the real app. |
| Listing contact | abbasian7iraj@gmail.com | Previously verified owner contact, already public in the policy. Do not invent phone, business identifiers, address, trader status or account verification details. |
| Target audience | **Ages 13–15, 16–17, and 18 and over.** Exclude all groups under 13. | Explicitly confirmed by the owner on 19 October 2026; the privacy policy now describes teens aged 13+ and adults. Verify exact form options before saving. This is a targeting decision, not an IARC rating or a declaration that all teens are legal adults. |

## Reviewer instructions

The target audience is confirmed, but the Console selection is still pending sign-in. Google notes that teen groups may include children under local law. Review the applicable Families/User Data requirements, system speech provider terms and any required disclosure/consent before final submission. Excluding users under 13 does not establish that every minor-related obligation is resolved. Reference: https://support.google.com/googleplay/android-developer/answer/9867159?hl=en .

LensPrompt does not require an account or login. Open the welcome script and use Prompt to read it. Manual scrolling works without speech recognition. For Smart Follow, grant microphone access and use a supported system recognizer or an installed Vosk pack. Automatic mode and failure fallback can use a system provider that processes audio online.

For floating mode, choose Use with phone camera, allow Display over other apps in Android Settings, and return. Close from the overlay ×, notification Stop, or Stop floating mode in LensPrompt. The built-in camera requires camera permission; recording sound requires microphone permission. An external camera recording sound can take the microphone and cause fixed-speed fallback. Optional speech packs download from alphacephei.com or import through the Android file picker.

## Data safety — verified facts and pending decisions

**Overall data collection: Yes.** ML Kit technical collection prevents a truthful “no data collected” answer, even though scripts, recordings and camera analysis are local in the app's own code.

| Type / question | Working answer | Why it is not a final attestation |
|---|---|---|
| Device or other IDs | Collected: Yes; SDK installation identifier; analytics/diagnostics. | No global metrics opt-out is established; do not claim optional collection just because lip analysis can be disabled. |
| App info and performance → Diagnostics | Collected: Yes; SDK configuration, latency and technical/error records. | Do not claim developer crash-reporting or Firebase Analytics/Crashlytics; neither is integrated. |
| App activity → App interactions | Review SDK initialization/detection/release events against the form's definition. | SDK usage events exist; this is not evidence of tracking every screen/tap. |
| Voice or sound recordings | Online system recognition must be accounted for; speech assistance is optional because manual prompting remains usable. | Selected providers can process audio remotely. Retention, the applicable sharing exception and provider-specific security are not established globally. |
| Script/transcript text | No stored-script prompt or finished transcript upload by LensPrompt found. | Remote speech processing can derive transcripts from audio. Do not invent direct script uploads, or promise provider deletion/retention. |
| Videos/photos | No app upload found for finished video or camera analysis. | Shared-media/gallery backup and Android transfer are separate paths; disclose them accurately. |
| Location | No location permission or location API use found. | Do not equate a network host seeing an IP address with verified location use or claim all providers avoid deriving location. |
| Purchases | Default build has billing disabled; no billing connection. | Confirm actual active-AAB flags before submitting. No access to payment-card details is implemented. |
| Shared with third parties | Do not submit a blanket No. | Google documents SDK metrics and no onward transfer by ML Kit; LensPrompt's transfer to Google and a selected speech service still require classification under Play's exceptions. |
| Encryption in transit | ML Kit documents HTTPS; app endpoints are HTTPS and app cleartext is disabled. | Another app's speech service is outside this manifest's control. Do not attest that all paths are encrypted without provider evidence. |
| Ephemeral processing | Do not claim ephemeral by assumption. | Real-time use does not establish in-memory-only provider processing or retention. |
| Data deletion | Local scripts/packs can be deleted; videos can be removed in storage/gallery; support accepts privacy requests. No LensPrompt account exists. | Do not promise remote deletion of every provider metric, transcript or prior backup. Answer the exact form wording after scope is resolved. |

Google's public guidance includes SDK transfers and does not exempt data simply because the developer has no server. Its sharing exceptions are conditional. Android's SpeechRecognizer documentation explicitly warns that recognition may stream audio to remote servers. A privacy-policy link alone does not establish a required in-app disclosure/affirmative-consent flow.

Primary references checked on 18 October UTC / 19 October Brussels:

- https://developers.google.com/ml-kit/android-data-disclosure
- https://developers.google.com/ml-kit/terms
- https://developers.google.com/ml-kit/vision/face-detection/android — bundled 16.1.7 matches the dependency.
- https://developer.android.com/reference/android/speech/SpeechRecognizer
- https://support.google.com/googleplay/android-developer/answer/10787469?hl=en

## Listing and assets

Title: **LensPrompt - Teleprompter** (25/30 characters)

Short description: **Floating teleprompter with Smart Follow and built-in video recording** (68/80)

Full description: `store/en-US/full-description.txt` (2,960/4,000 excluding the final newline). It discloses system speech, SDK diagnostics and external-camera microphone limits. Icon: 512×512 PNG; feature graphic: 1024×500 PNG. Actual screenshots must be visually reviewed and matched to the intended release before upload; a PR debug build is not proof of the installed Play binary.

## Foreground services

Use the `specialUse` and `microphone` drafts in `docs/PLAY_CONSOLE.md`. A real-device demonstration must show user initiation, permissions, visible overlay, the supported speech route, pause, notification Stop and closure. Do not claim simultaneous external-camera audio access on every phone. No demonstration video has been fabricated or submitted.

## Closed testing and approvals

The reported gate matches current official guidance for applicable new personal accounts: 12 real closed testers opted in continuously for 14 days, followed by the production-access application. Internal testing does not establish this period. Keep tester identities private; record genuine engagement and feedback. Source: https://support.google.com/googleplay/android-developer/answer/14151465?hl=en .

The test plan is prepared; no closed track, roster, opt-in link, tester count or start date has been verified. No invitations have been sent. Merge, any necessary higher-version signed Play update, invitations, final attestations/review submission and production publication require the owner's separate approval.

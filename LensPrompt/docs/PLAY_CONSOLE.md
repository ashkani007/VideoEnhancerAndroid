# LensPrompt — Play Console worksheet

Prepared 18 October 2026. **No section was saved, submitted or verified in Console during this session.** See `DATA_MAP.md` and `PUBLISHING_STATUS_2026-10-18.md` for evidence and limits.

## App setup answers ready for entry

| Section | Prepared answer | Evidence / review requirement |
|---|---|---|
| Privacy policy | `https://ashkani007.github.io/VideoEnhancerAndroid/` | Pages deployment succeeded; anonymous HTTPS 200 verified on 18 October 2026 UTC / 19 October Brussels. Owner reports URL saved in Console; Console state remains inaccessible to the agent. |
| App access | All features available without login; no test credentials needed | Source has no authentication. Normal Android permission prompts are not account access restrictions. |
| Ads | **No** | No advertising placements or advertising SDK in source or resolved debug dependencies. ML Kit metrics are not advertising. |
| Content rating | App/utility questionnaire: no built-in mature, violent, gambling or sexual content; no public user exchange/social features | Do not invent an IARC rating. Review exact questions/attestations. Private script editing is not a public UGC service. |
| Target audience | Proposed **18 and over**, adult creators and presenters; not directed at children | Product targeting choice for owner review, distinct from content rating. |
| Data safety | **Collects data: Yes. Per-type answers require resolution below.** | ML Kit metrics/installation ID alone rule out “no data.” |
| Government apps | **No** | Independent teleprompter, no government services or affiliation. |
| Financial features | **No financial features** | No lending, banking, investing, crypto or financial service. Disabled in-app billing is not a financial-services feature. |
| Health apps | **No health features** | No medical or fitness functionality. Mouth movement estimates speaking, not health. |
| Category | App → **Video Players & Editors** | Select only tags that are available and accurate. |
| Developer contact | **abbasian7iraj@gmail.com**; website may be the public policy page | Email retrieved from authenticated GitHub profile. Do not fabricate phone, legal address, trader status or business identifiers. Existing account details need Console verification. |
| Main store listing | `store/en-US/` and `store/graphics/` | Title 25, short 68, full 2964 characters excluding final newline. Actual screenshots pending. |

Reviewer access instructions:

1. Open LensPrompt; no sign-in is required. Use the welcome script.
2. Tap a script to edit or its play button to prompt. Manual mode works without recognition.
3. Smart Follow needs microphone permission and a functioning system speech provider or installed offline model. The system route may process audio online.
4. For floating mode, choose Use with phone camera, allow Android Display over other apps, and return. Close using the window ×, notification Stop or Stop floating mode in LensPrompt.
5. Built-in preview/recording needs camera access; sound needs microphone permission. Optional packs download over internet or import through the Android file picker.

## Data safety worksheet — not ready for final submission

Google's form covers SDK collection even when it goes to Google instead of the developer, and remote ephemeral processing. The exact uploaded AAB/build flags were not matched to source. “We have no server” is not a reason to answer No.

| Data type | Working treatment | Purpose and unresolved details |
|---|---|---|
| Device or other IDs | **Collected: Yes** for ML Kit installation identifier | Analytics/technical diagnostics. Treat as required until a genuine global opt-out is verified; the lip toggle does not prove initialization telemetry stops. |
| App info and performance → Diagnostics | **Collected: Yes** for SDK technical/error/performance information | Analytics and technical maintenance. Device/OS and API configuration are technical records. Do not invent crash-log collection. |
| App activity → App interactions | Candidate **Collected: Yes** for ML Kit initialization/detection/release events | Analytics. Map SDK event semantics to the form; do not claim all navigation is tracked. |
| Audio → Voice or sound recordings | **Submission blocker:** assess system speech transmission; do not answer No because Vosk is local | Optional feature, app functionality. Provider can receive audio online; establish its role, disclosures/consent and any sharing exception. |
| Transcripts / other user-generated content | Review provider transcript handling as a separate category | No stored script prompt is sent. Do not invent direct script uploads; the provider can derive text from audio. |
| Local scripts / video files | No app upload found for stored files | Android/gallery backups and explicit transfers need policy disclosure; distinguish them from a developer backend. |
| Approximate location | No location API access found; do not infer this automatically from IP requests | Download hosts see an IP. Location derivation/use by providers needs evidence. |
| Purchases / financial information | No default purchase collection found | Fresh local debug BuildConfig verifies `BILLING_ENABLED=false`; still match the actual active AAB. |

**Sharing:** ML Kit says it does not onward-share its listed metrics. This does not automatically establish that LensPrompt's transfer to Google is exempt from the form's sharing definition. Assess Google's applicable SDK/service-provider role and the form's user-initiated/disclosure exemptions. Assess system speech separately. Neither “shared: No” nor an expansive unsupported answer should be presented as verified fact.

**Ephemeral:** Do not select ephemeral unless a provider establishes that off-device data stays only in memory for the real-time request. That is not established for all recognition services or SDK metrics here.

**Encryption:** ML Kit documents HTTPS, and model endpoints start with HTTPS. The prepared manifest disables app cleartext traffic. This does not control another app's speech service. Do not attest that all collected data paths are encrypted before resolving provider behavior.

**Deletion:** Users can delete local scripts/packs and media recordings. There is no LensPrompt account. Do not claim LensPrompt remotely deletes every provider's metrics, transcripts or backups. The policy supplies a support/rights contact. Read the exact Console deletion question before selecting an option.

If speech-provider handling cannot be resolved, leave the form unfinished or implement and test a constrained local-only route in a later release. Public notice is not a substitute for an in-app disclosure and affirmative consent where required.

## Foreground-service declaration drafts

**specialUse:** LensPrompt displays a movable teleprompter over a compatible camera app after the user starts floating mode. The foreground service keeps the visible script and controls available while the camera app is in front. It ends when the user closes the overlay, chooses notification Stop, or stops floating mode in LensPrompt. It does not start at boot or run as a background video recorder.

**microphone:** When the user presses Play with Smart Follow enabled in floating mode, microphone input aligns and scrolls the script. The active engine can be an on-device Vosk pack or the user's system recognition provider, which may process audio online. Pause, manual mode and closing the overlay stop its listening session. Another recording app may take the microphone, causing manual-speed fallback. The service starts from the visible app after microphone permission is granted.

A real-device demo is pending. Show start, permissions, visible overlay over camera, speech following while the mic is available, pause, notification Stop and disappearance. Demonstrate sound-recording conflicts honestly. Verify notification denial and lock-screen behavior separately. This draft is not a submitted declaration.

## Save and approval process

When access is restored, enter and save reversible draft changes, then record each resulting complete/draft status. Stop before final legal attestations, binding acceptance, review submission or production rollout and present the concrete pending action to the owner. A prepared worksheet does not mean a Console section is complete.

See `CLOSED_TEST_PLAN.md` and `INTERNAL_TESTING_DIAGNOSIS.md` for testing.

Local artifact follow-up: the fresh merged debug manifest contains no advertising-ID permission. It contains Billing and ACCESS_NETWORK_STATE from dependencies plus an internal AndroidX signature permission. Do not confuse an unused Billing permission with an active purchase flow. The uploaded AAB remains unverified.

Fresh validation: 75 unit tests passed (66 core, 9 app); debug and minified QA APKs built, the instrumentation source compiled, and native/ZIP alignment checks passed. None of these results resolves provider-specific Data safety questions or means a Console section has been saved. See `ANDROID_BUILD_RESULTS_2026-10-18.md`.

# Store materials

English title, short description and full description are in `en-US/`. Category: **Video Players & Editors**. Natural search terms included in the copy: teleprompter, floating teleprompter, Smart Follow, speech-assisted scrolling, video recording, offline speech, multilingual scripts. Google Play has no separate keyword field; do not paste a keyword list into the listing.

`graphics/` contains a 512×512 RGBA PNG icon, derived from the existing launcher vector, and a 1024×500 RGB PNG feature graphic. Run `python tools/build_store_assets.py` from LensPrompt to regenerate them. They are branding assets, not screenshots or evidence that a feature passed testing.

**Actual app screenshots are still pending.** `StoreScreenshotTest` captures the real app library, editor, paused manual prompter, settings, About and floating window without simulated speech or generated camera imagery. The publication QA workflow renders the emulator at 1080×1920. It must run after GitHub write access is restored. Review and convert the resulting PNGs to RGB for upload; do not invent a camera image or imply that the paused prompter demonstrates live Smart Follow.

Capture an additional real-phone video/frames showing voice synchronization, an actual camera recording with sound, and the floating overlay over the chosen camera app. Do not claim every camera app permits overlays or simultaneous microphone access. A foreground-service declaration demo is separate from store screenshots.

The copy is based on inspected source; camera, live microphone and Android 15/16 behavior require the physical-device acceptance plan in `docs/CLOSED_TEST_PLAN.md` before production. No store listing has been saved to Play Console in this session.

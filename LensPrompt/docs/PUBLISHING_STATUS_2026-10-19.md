# LensPrompt publication readiness — 19 October 2026 (Brussels)

This report supersedes the current-status statements in `PUBLISHING_STATUS_2026-10-18.md`; retain the earlier report as the historical audit and delivery record.

## Verified access and privacy policy

- Draft PR #4 remains open, unmerged and targeted at `claude/lensprompt-android-dev-s2ojat`: https://github.com/ashkani007/VideoEnhancerAndroid/pull/4 . The development branch remains at `b255abee786d447f6cc8aba6e3cf3532c563e4b3`.
- GitHub Pages deployment run **39161886722**, latest attempt, succeeded at **2026-10-18 21:54 UTC**. The emitted URL is **https://ashkani007.github.io/VideoEnhancerAndroid/**. A fresh anonymous HTTPS request returned **200**, HTML, 18,772 bytes, SHA-256 `bd6fe6ba76357341e7d8de575b75c3fb248466fc7188466e6695c907e46b4dd0`. It identifies LensPrompt, its package, Supernova studio, the verified support email, all 13 policy sections and GitHub hosting.
- The owner reports this URL saved in Play Console, internal release 1.0.0/code 1 active, and 1/11 setup tasks complete. These Console states have not been independently observed.
- The exact authorized navigation to `https://play.google.com/console/` was rejected **before page observation** by automatic browser review. Its stated reason refers to the different origin `https://google.play` and an obsolete authentication restriction. No Google login wall or CAPTCHA was observed. No bypass, alternate browser, authentication attempt or Console mutation followed.

## Completed CI on PR head e6171c6

| Evidence | Actual result |
|---|---|
| Build and API 34 workflow, run 39162322936 | Success, including unit tests, debug/release artifact builds, 64-bit 16 KB check and the instrumented emulator job. Upload steps are GitHub artifacts, not Google Play uploads. |
| API 36 publication QA, run 39162322933 | Success: 8 instrumented tests, 0 failures/errors/skips; unit tests, full debug lint and minified QA build also passed. |
| API 35 publication QA, same run | 8 instrumented tests, 1 failure, 0 errors/skips. `everyExitPathClosesTheOverlayAndItRestarts` failed with `AssertionError: no controls handle`, at the first close/reveal path. The other 7 tests passed. |
| Screenshot evidence | Screenshot instrumentation passed on both APIs, but **no PNG files were present in either downloaded artifact**. Do not treat an instrumentation pass as delivered screenshot evidence. |

Artifacts were downloaded and their SHA-256 hashes matched GitHub's metadata:

- API 35, artifact 12149761098: `cb2f6849ea4b0f2ccb948a417d3a167a7736cae1c71cf74229b72840f3ac5133`.
- API 36, artifact 12149477609: `dc2daf721f9075d791c22328785a6f711410e30bd646988d3f274628d765fef3`.

## Follow-up changes prepared for validation

The collapsed floating controls handle had only a touch listener. It lacked an accessibility click listener, so `ACTION_CLICK` could not reveal the toolbar. It now has an explicit click action; normal short taps dispatch through `performClick()` and dragging still moves the window. An additional instrumented regression waits for auto-hide, reveals the controls through accessibility, and closes the window. Existing exit-path assertions remain. The test searches actual content descriptions in the window tree and retries unsuccessful actions instead of depending on text-search matching or returning immediately on a transient failure.

Screenshot files were kept only under app storage, which can be removed when AGP finishes its install/test/uninstall lifecycle. Instrumentation now preserves each capture in the disposable emulator's shell-owned temporary directory before teardown. The workflow checks that all six PNGs exist and then pulls that directory. No generated interface or camera image is used. Fresh screenshots and the new regression are **pending the follow-up CI**, not yet claimed as passes.

The proposed app policy default and store copy now use the verified GitHub Pages URL. These are proposed code changes; an installed binary is not altered by a Console metadata edit or by this PR.

The current workspace initially contained an older local checkpoint. Review work uses a separate worktree and branch, reconstructed from the exact remote PR snapshot with verified Git tree `b756933d57a78d8dc5c4132b127cba2b6b849eab`. The pre-existing local branch was not reset or rewritten. The remote copies and their original-local-commit provenance remain intact.

## Console draft answers and unresolved decisions

`PLAY_CONSOLE.md` contains source-backed draft answers for app access, ads, government affiliation, financial/health features, category/contact, rating facts, foreground services and Data safety. **No new Console section has been saved or marked complete by the agent.**

Data safety is still blocked by provider-specific system speech handling, ML Kit collection/sharing classification, security/retention answers and any necessary in-app disclosure/consent. The app can send speech through a selected system provider, ML Kit collects documented technical information, and Android backup/transfer can copy local data. Do not answer “no data collected.” Billing is disabled in the audited default configuration; the exact active AAB has not been matched to that configuration.

The adult-only target audience in the policy/worksheet remains a product decision for the owner to confirm. Content rating must be generated by the actual IARC questionnaire; do not invent a rating or treat private scripts as a public UGC exchange service.

The listing copy and branding assets are prepared. Screenshots of a proposed debug build must be reviewed and matched to the actual published binary before store use. An emulator speech simulator is a UI smoke check; it does not prove live speech accuracy, concurrent external-camera microphone access, or physical-device recording behavior.

## Release and testing boundaries

- No merge, new Play upload, review submission, production rollout, payment/account change or external tester invitation is authorized or performed.
- The existing internal release's active AAB, signer, device distribution, Google-account eligibility and installation remain unverified. Do not uninstall or clear storage without preserving scripts, settings and app-specific media.
- The account-reported production gate is at least **12 real opted-in closed testers continuously for 14 days**, plus the production-access application and genuine test feedback. No roster, eligible count, start date or elapsed test period is verified. See `CLOSED_TEST_PLAN.md`.
- A real-device foreground-service demo and Android 15/16 speech/camera/notification/permission acceptance remain required. Production readiness is **not yet established**.

Owner decisions still needed: confirm intended age groups; approve any necessary new signed release only after the PR and fresh tests are reviewed; authorize real tester invitations separately; approve final attestations, review submission and production publication only when the setup is complete.

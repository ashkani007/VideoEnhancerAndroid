> Historical proposal. Use the actual draft PR #4 description and PUBLISHING_STATUS_2026-10-19.md for current results.

# Prepare LensPrompt privacy disclosures and publication QA

The default build hides its Privacy policy and Contact support buttons because their values are empty. Its privacy summary omits ML Kit technical collection, and routine diagnostics can log recognized speech.

This change sets the verified public policy/contact defaults, corrects English/Persian/Dutch disclosures, redacts speech from routine logs while preserving explicit exports, and disables cleartext app traffic. It also declares the Android 13+ contract on the recognizer audio pipe and uses the microphone foreground-service type only from Android 11, its actual introduction, rather than Android 10. Package identity, version and default disabled billing behavior are preserved. It adds a diagnostic privacy regression, actual-interface screenshot capture, Android 15/16 QA and a policy-only GitHub Pages workflow. Store branding/copy, the source data map and test/declaration worksheets accompany the implementation.

Validation: **75 fresh unit tests passed** (66 core and 9 app); full debug lint passed with 0 errors and 20 recorded non-blocking warnings; debug and R8-minified/resource-shrunk QA APKs built; instrumentation code compiled. All 12 64-bit native libraries and official `zipalign -c -P 16 -v 4` checks passed in both APK variants. Merged permissions/resolved SDK dependencies, policy packaging, XML/YAML, shell syntax, diff whitespace, listing limits and asset dimensions were checked. Public policy was displayed anonymously in Cloud Browser over HTTPS. See `docs/ANDROID_BUILD_RESULTS_2026-10-18.md` for scope and hashes.

An API 35 software emulator booted, but a basic setup command timed out before app installation/instrumentation. No app runtime failure or screenshot success is inferred.

Pending review: actual UI screenshots and physical-device microphone/camera/overlay behavior; API 35/36 runtime checks; matching the active AAB to source/build flags; provider-specific Data safety and consent answers. Local debug/QA alignment does not certify Play-delivered AAB splits. No Console changes, release uploads, review submissions or tester invitations were made.

PR base: `claude/lensprompt-android-dev-s2ojat`. Prepared branch: `codex/lensprompt-play-readiness-20261018`. Do not merge into the unrelated old default-branch project without a separate review. Draft PR #4 is open: https://github.com/ashkani007/VideoEnhancerAndroid/pull/4 . Connector writes are now working; copied GitHub trees match the three preserved local commits.

The public Sites policy remains the app default until the prepared Pages workflow is deployed and its returned URL is verified. Pages packaging passed in run 39161886722; deployment stopped at configure-pages with 404 because repository Pages needs administrator enablement for GitHub Actions. Pages settings have not been changed.

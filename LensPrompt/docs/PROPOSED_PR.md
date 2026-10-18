# Prepare LensPrompt privacy disclosures and publication QA

The standard build hides its Privacy policy and Contact support buttons because both defaults are empty. The app also describes itself as having no analytics even though bundled ML Kit collects technical metrics, and routine diagnostics can log recognized speech.

This change sets the verified public policy/contact defaults, corrects English/Persian/Dutch disclosures, redacts speech from routine logs while preserving explicit support exports, and disables cleartext app traffic. It preserves package identity and billing behavior. It adds a meaningful diagnostic privacy regression and actual-interface screenshot capture plus Android 15/16 QA. Store text/branding, a source data map and test/declaration worksheets accompany the change.

Validation: XML and YAML parsing, shell syntax, diff whitespace checks, listing character limits, icon/feature dimensions and visual graphic inspection. Public policy served anonymously over HTTPS with HTTP 200. New Gradle tests/compile were blocked by the local network/SDK environment; the new CI workflow has not run because GitHub writes return 403. Historical API 34 CI on the base source reports 10 passing instrumentation tests and is not validation of this patch.

Review before merge: compile/unit/UI checks, actual screenshots, uploaded-AAB source/build-flag matching and final provider-specific Data safety answers. No Console changes, review submissions or app releases were made. No remote PR was created in this session.

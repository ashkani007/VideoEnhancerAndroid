# GitHub Pages policy publication

The policy is already publicly available at https://lensprompt-privacy.ideal-jam-4118.chatgpt.site . Keep that working app/store URL until a GitHub Pages deployment is confirmed. There is **no verified GitHub Pages URL yet**.

The `LensPrompt public privacy policy` workflow publishes only `index.html` and `.nojekyll` from a generated policy folder. It does not publish the repository tree, Android artifacts, reports, tester data or signing material. The packaging script changes the hosting disclosure specifically for the GitHub-hosted copy; it preserves the app data disclosures. The existing Sites copy remains accurate for its own host.

Prerequisites:

1. A GitHub connection capable of creating repository branches and commits and opening pull requests. Current branch-create requests return 403; a plain Git push also failed because this environment has no GitHub credentials. The user's authorization in chat does not change the app's OAuth/installation permissions.
2. An authenticated repository administrator opens repository Settings → Pages and selects GitHub Actions under Build and deployment → Source. This repository was public and had `has_pages=false` at the last read.
3. The `github-pages` environment permits the branch being published. Keep its protections; do not disable them to make an arbitrary workflow pass. If a deployment needs owner approval, the owner approves that concrete policy deployment.
4. Push the separate readiness branch and review its PR. The policy workflow can run on the prepared branch or after a reviewed merge. GitHub's workflow-dispatch UI normally requires the workflow on the default branch, so do not rely on a not-yet-visible Run workflow button for the first deployment.

Verification after deployment:

- Read the actual `deploy-pages` result and use its returned `page_url` rather than guessing a URL.
- Open that URL without signing in; confirm HTTP 200, mobile layout, policy title, package, developer and support contact.
- Confirm the content covers system speech, ML Kit metrics/installation identifiers, backup, downloads, diagnostics and deletion. Do not replace it with “no data collected.”
- Only then update the in-app/default policy URL and Console field, save, and verify. A necessary app update must use a higher version code than the installed Play release.

Local packaging check:

```bash
python3 LensPrompt/tools/prepare_privacy_pages.py --output /tmp/lensprompt-policy-pages
```

Official workflow requirements were checked against https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages . The workflow has not run and Pages has not been enabled in this session.

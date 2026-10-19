# LensPrompt policy on GitHub Pages

**Deployed and verified:** https://ashkani007.github.io/VideoEnhancerAndroid/

The latest attempt of run **39161886722** completed successfully at 21:54 UTC on 18 October 2026. It emitted this actual URL; it was not guessed. An anonymous HTTPS request returned 200, HTML, correct identity/contact and all 13 policy sections. Responsive CSS/mobile metadata are present; an actual mobile-browser rendering has not been inspected. The earlier 404 was resolved by repository setup and rerun; do not tell the owner to enable Pages again.

The workflow publishes only the generated `index.html` and `.nojekyll`. It does not publish the repository, Android outputs, reports, tester records or signing material. `prepare_privacy_pages.py` changes the hosting paragraph for the GitHub copy; the source HTML also supports the previously deployed Sites copy. The public GitHub page correctly names GitHub hosting. The Markdown policy mirrors the GitHub-hosted wording.

The proposed app default and English listing use the verified Pages URL. The owner reports the URL saved in Play Console, but the agent has not observed Console. Updating metadata does not update an installed binary.

For future policy changes, review the source and package it with:

```bash
python3 LensPrompt/tools/prepare_privacy_pages.py --output /tmp/lensprompt-policy-pages
```

Keep the repository's Pages/environment protections. Review any binding acceptance or owner-approval gate rather than weakening protection. After a deployment, inspect its emitted URL, anonymously verify status/content and check disclosures before changing app/store references.

Deployment: https://github.com/ashkani007/VideoEnhancerAndroid/actions/runs/39161886722

Workflow guidance: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

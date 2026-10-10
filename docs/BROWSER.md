# Integrated VR web browser

The Browser tab finds videos on the web and hands compatible ones to VRVision's existing VR
player and enhancement pipeline. It is built on Android WebView with a Compose UI.

## Components

| Piece | Where | Role |
|---|---|---|
| `UrlPolicy`, `TabManager`, `MediaDetector`, `DownloadPolicy`, `VrPointer`, `DwellClicker`, `ControllerMap` | `android/core/.../browser` | Pure, JVM-tested rules: address parsing, HTTPS-first, scheme allow/deny, tabs, media classification and play/enhance assessment, download authorization, gaze hit-testing, dwell clicks, gamepad mapping |
| `BrowserController` | `app/.../browser` | Owns tabs and their WebViews; WebViewClient/WebChromeClient; prompts; fullscreen; history; session restore; clear data |
| `WebViewSecurity` | `app/.../browser` | The single place where WebView settings are hardened (asserted by an instrumented test) |
| `BrowserDownloads` | `app/.../browser` | User-confirmed downloads via DownloadManager into private storage; import into the library |
| `CaptureLayout` | `app/.../browser` | Hosts the WebView at 1280×720 and draws it into the VR renderer's surface |
| `BrowserDatabase` (`browser.db`) | `app/.../browser` | Bookmarks, history, session tabs (URL + title), download records — separate from the video library |
| `BrowserScreen`, `BrowserPanels`, `VrBrowserView` | `app/.../ui/screens` | Normal browser, tabs/bookmarks/history/downloads/media panels, dialogs, VR mode |

## Flows

**Open in VRVision Player.** On page load (and on demand) a read-only script, run with
`evaluateJavascript`, lists `<video>`/`<source>` URLs, links to `.mp4/.webm/.m3u8/.mpd`, the page
title and whether a video has Encrypted Media Extensions keys (DRM). Request URLs that look like
media are also observed (never modified) in `shouldInterceptRequest`. `MediaDetector.assess`
decides per source: HTTPS MP4/WebM/HLS/DASH without DRM can be played; blob: streams, DRM,
plain-HTTP and unknown formats can't, each with a stated reason. The user confirms projection
(flat/VR180/VR360) and stereo layout (mono/SBS/TB, eye swap) — pre-filled from name/title hints
— and the URL plays in the existing `VrPlayback` with Media3 (HLS and DASH modules included) and
the right MIME type. No cookies or credentials are passed to the player.

**Enhance Video.** Only for progressive files (MP4/WebM). The user confirms a download
(DownloadPolicy: never automatic, no executables, size limit, safe file name); the file goes to
app-private storage; when complete it is imported into the library with the chosen format and
the existing flow opens: analysis (size, codec limits, storage, battery, thermal, estimated
output size) → recommendation (local/cloud with reasons and time estimates) → explicit cloud
consent if chosen → 10-second preview → before/after comparison → full processing → play in VR.
HLS/DASH, DRM, blob and login-only sources explain why enhancement is unavailable.

**VR browser mode.** The active tab's WebView is moved into `CaptureLayout`, which renders it
into the `SurfaceTexture` of a `VrRenderer`. The page is shown as a flat virtual screen
(adjustable distance/width) through the same per-eye framebuffers, off-axis projection and
radial lens pre-distortion as videos, using the active headset calibration profile and head
tracking (with recenter). Interaction:

- gaze reticle at each lens center, dwell 1.5 s to click (toggle);
- a tap anywhere on the phone screen (passive-headset button) clicks at the reticle;
- Bluetooth gamepad/remote/keyboard: A/Enter/D-pad center = click, B/Back/Esc = page back,
  D-pad = scroll, Y = recenter, X = toggle dwell, Start/Space/Play = play/pause page video;
- double tap or system Back opens the panel (distance, size, dwell, recenter, exit).

Clicks are delivered as touch events at the page coordinates computed by `VrPointer.hit`.

## Security and privacy

| Requirement | Implementation |
|---|---|
| HTTPS-first | Typed hosts become `https://`; `http://` navigations are upgraded; if HTTPS fails the page is not loaded over HTTP (explained to the user) |
| Safe Browsing | `safeBrowsingEnabled = true` |
| Mixed content | `MIXED_CONTENT_NEVER_ALLOW` |
| No unrestricted JS bridges | No `addJavascriptInterface` anywhere; only fixed read-only scripts via `evaluateJavascript` (media listing, scrolling, play/pause) |
| No arbitrary file access | `allowFileAccess`, `allowContentAccess`, file-URL access all off; `file:`/`content:` URLs blocked |
| External schemes | Only `tel`, `mailto`, `sms`, `geo`, `market` — and only after confirmation and a user gesture in the main frame; `intent:`, `javascript:`, `data:` top-level, `chrome:` blocked |
| SSL errors | Always `cancel()`; never proceed |
| Permissions | Camera, microphone, MIDI, geolocation denied; protected-media (DRM) playback inside the page asked per request |
| Downloads | Confirmation dialog for every download; executables/installers blocked; no cookies sent; private storage |
| Pop-ups | No automatic windows; multiple windows disabled |
| Cookies/tokens | Never logged (the browser code has no logging of URLs, cookies or headers); third-party cookies off |
| Private data | Browser DB, cookies and site storage are app-private and excluded from backup/transfer; *Clear browsing data* removes cookies, site storage, cache, history, saved session, form and HTTP-auth data |
| Renderer crash | `onRenderProcessGone` handled: the tab's WebView is dropped and recreated, the app keeps running |

# Production cost: Napoleon 2D Animation POC

## Tools used (all free / open source)
| Tool | Use | Licence |
|---|---|---|
| Python 3.13 | Animation code | PSF |
| skia-python 144.1 | Vector rendering (anti-aliased paths, gradients, path booleans) | BSD-3 |
| NumPy, OpenCV | Frame buffers, vignette, whip-pan blur, frame checks | BSD / Apache-2.0 |
| FFmpeg (libx264) | H.264 encoding, probing, decode check | LGPL/GPL |

Not used: Blender, AI image generation, AI video, ElevenLabs or any other paid API. No narration in this POC.

## Where it ran
Every step ran **locally in the Claude Code cloud container** (4 vCPU, no GPU): character and set drawing, animation,
rendering, encoding and frame inspection. The same scripts run on the client's Windows 11 PC (Ryzen 5 4500,
RTX 4060), where FFmpeg's `h264_nvenc` is used automatically when available.

## Measured render times (cloud container, 3 worker processes)
| Output | Wall time |
|---|---|
| 540×960 preview, 12 s | 14 s |
| 1080×1920 final, 12 s (360 frames) | 39 s |

## Paid usage
- **Paid API calls: none.** ElevenLabs: none. Image or video generation services: none.
- **Claude usage (session meter, API-equivalent, not an invoice):** this long-running session shows **$93.12**
  cumulative. It was $74.50 before the previous v3 proof of concept, so v3 plus this POC together used about **$18.6**.
  The two are not metered separately, so a split would be a guess. On a Claude subscription this counts against plan
  usage limits rather than being billed separately.

## Estimated cost per 45-second reel (estimates, not measured)
| Item | Estimate | Basis |
|---|---|---|
| Rendering | about 2.5 min of CPU per reel; electricity well under €0.01 | 39 s per 12 s measured, ×3.75 |
| Narration (when added) | about 600–700 ElevenLabs credits, about $0.12–0.14 | Ep02: 838 credits = $0.168 at the connector price; 45 s ≈ 650 characters with the approved voice |
| Software | €0 | Free tools |
| **Variable cash cost** | **about €0.13 per reel** | Mostly narration |
| Claude authoring time | the real cost | Each reel needs a storyboard, acting keyframes and any new characters or sets. With a reusable library, roughly $10–25 API-equivalent per reel is a plausible range, extrapolated from this POC; to be measured on the first full reel |

## Can it scale to 30–60 reels per month?
- **Rendering: yes.** Minutes per reel on a normal CPU, so 60 reels is about 2–3 hours of rendering a month.
- **Authoring is the bottleneck.** Every new historical figure, costume, set and action currently needs code. To reach
  30 reels/month it needs:
  1. a **character template library** (male/female bodies, costume kits by era, face presets) built on this rig;
  2. a **set kit** (interiors, landscapes, battle elements) and an **action library** (walk, point, talk, nod, sit, ride);
  3. a **storyboard → keyframe JSON** format so a reel is assembled from library pieces instead of new code;
  4. phoneme-driven mouth shapes from the narration;
  5. human review of every reel before publishing.
- **Assessment:** 30/month looks achievable once items 1–4 exist (several focused build sessions). 60/month is not proven
  and probably needs more templating plus a review workflow. Claude usage limits on the client's plan must also be
  checked against the per-reel authoring effort.

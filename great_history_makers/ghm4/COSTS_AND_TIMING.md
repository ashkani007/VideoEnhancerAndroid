# Time and cost per video (2026-10-25)

**Measured** = measured in the cloud container: 4 vCPU, no GPU.
**Estimate** = not yet measurable; it will be replaced by the numbers the PC worker writes into every result manifest.

## Per 60-second Short (about 10 illustrations, 2 maps, 1080×1920)
| Stage | Where | Time | Basis |
|---|---|---|---|
| Illustration candidates: 10 shots × 4 seeds, SDXL + IP-Adapter, 768×1344 + 1.5× hires | PC GPU | ≈ 20–40 min | **Estimate**: 30–60 s per image on an RTX 4060 |
| 2× upscale of the 10 picks | PC GPU | ≈ 2–4 min | **Estimate** |
| Plates: automatic metadata + matte | Cloud CPU | ≈ 2–4 min | **Measured**: 8–30 s per plate |
| Picture render 720p preview | Cloud CPU | ≈ 6.5 min | **Measured**: 115 s per 18.2 s of video |
| Picture render 1080p final | Cloud CPU | ≈ 16 min | **Measured**: 282 s per 18.2 s (3 workers) |
| Narration mix + captions 1080p | Cloud CPU | ≈ 5 min | **Measured**: 95 s per 18.2 s |
| Verification + branding | Cloud CPU | ≈ 1 min | **Measured** |
| **Total machine time** | | **≈ 55–75 min**, of which 25–45 min on the PC GPU | |

The automated pipeline test (`ghm4/tests/test_episode.py`) runs the whole chain in about 70 s with stand-in plates.

## Money per video
| Item | Cost | Basis |
|---|---|---|
| Image generation | €0 per image (local) + electricity ≈ **€0.03** | ≈ 0.2 kW for ≈ 0.5 h at ≈ €0.30/kWh (assumed household price; adjust to your tariff) |
| Rendering, maps, mattes, captions | €0 | Runs in the Claude Code container; no paid service |
| Music + sound effects | €0 | Procedurally synthesised (`mosaic/audio.py`), no licences |
| Narration, ElevenLabs (only with approval) | ≈ **840 credits per take** | **Measured** on Ep02: 1,676 credits for 2 takes of a 68 s script. Euros = credits × your plan's price per credit |
| Narration, your own voice file | €0 | |
| **Variable cost** | **≈ €0.03 + narration** | Below the €0.50 target with one ElevenLabs take on typical plans |

At 30–60 Shorts a month:
- electricity ≈ €1–2;
- ElevenLabs ≈ 25,000–50,000 credits (one take each). The current inactive budget file caps it at 25,000 a month (`autopilot/BUDGET.json`).

Fixed costs are the subscriptions you already have: the Claude plan and the ElevenLabs plan.

## The real constraint: Claude-dependent steps
Rendering costs no Claude usage. These steps do (per 60 s video, counted as image reads):

| Step | Before automation | With `ghm4/episode.py` + presets |
|---|---|---|
| Storyboard and prompt writing | Text | Text: one `episode.json` |
| Plate metadata (flags, smoke, sky, ranks, wind, matte hint) | ≈ 20–30 image reads | **≈ 0**: automatic (flags verified on the approved image: 3/3 found, 0 false) |
| Eye outline for the blink, hand pivot | Included above | ≈ 1–2 grid reads per close-up (only portraits) |
| Candidate review | ≈ 30–40 reads | ≈ 10: one contact sheet per job + the picks |
| Render QA | ≈ 10–15 | ≈ 5: contact sheet + verification report |

Next reductions (not built):
- automatic eye localisation on illustrated faces;
- a trained character LoRA, so fewer candidates are rejected;
- batching several episodes per worker run.

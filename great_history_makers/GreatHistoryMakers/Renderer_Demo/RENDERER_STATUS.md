# ghm4 renderer: status report (2026-10-25)

## 1. The demo short
`output/renderer_demo_napoleon_720x1280_final.mp4`: 18.2 s, 720×1280, H.264 + AAC 48 kHz, unbranded preview.

| Time | Shot | Plate (separate file, own metadata) | Motion | Text |
|---|---|---|---|---|
| 0–4.95 | Wide establishing | `p1_wide.png` 941×1672, **auto matte** | Parallax pull-back, flags, smoke, ranks, clouds | "1769 – 1821 / NAPOLEON" |
| 4.95–10.25 | Portrait | `p2_portrait.png` 1000×1780, **auto matte** | Push-in, **one blink** at 7.55 s | "1804 / CORONATION" |
| 10.25–15.74 | Map | `ghm4/data/maps/victories_1805_1811.json` | Arrow Paris → Austerlitz; Austerlitz, Jena, Friedland and Wagram stars; the 1811 empire spreads from Paris | Date ticker 1805 → 1811, labels, legend |
| 15.74–18.2 | Battlefield | `p4_battle.png` 491×840 (not 9:16), **matte rejected → single layer** | Flags ×2, ranks, battle smoke, 2 cannon puffs, haze | — |

- Transitions: whip-zoom, painted ink wipe, flash with cross-zoom, fade.
- Narration: the **already approved and paid Ep02 ElevenLabs take**, first four sentences. The file is unchanged and no new credits were spent.
- Shot cuts are re-timed to the aligned words ("He rose…", "Napoleon Bonaparte crowned himself…", "His armies won…", "But Napoleon wanted more").
- Captions burned at y 1410/1920.
- **Honest limit:** this container cannot generate illustrations, so the three test plates are different files cut from the one approved image. They prove the assembly path (any number of plates, any size or aspect ratio, each with its own metadata and matte decision), not illustration variety. Real variety arrives with the ComfyUI plates.

## 2. Verification (measured)
| Check | Result |
|---|---|
| `tools/verify_delivery.py --excerpt --no-logo` (720p and 1080p) | **PASS**: narration correlation 0.977, offset 0 ms, speech −20.4 dBFS; 7/7 captions present on their aligned cues, start error 0 ms, wording matches the transcript |
| Regression suite `python -m ghm4.tests.run_all` | **7/7 PASS** in 117 s (golden frames, plate sizes, robustness, transitions, narration, masks, worker) |
| Golden frames | 13 key frames (approved POC port + this demo) bit-identical (PSNR 99 dB; threshold 40 dB) |
| Parallax stress (zoom 1.0 → 1.45, parallax 0.25, far stronger than any shot uses) | No tearing at the coat edge; crate, map and spyglass stay whole (`parallax_stress_test.jpg`) |

### Automatic masks (`ghm4/masks.py`, `ghm4/tests/test_masks.py`)
Ground truth: the hand-checked matte of the approved plate, split into named regions.
- Figure parts (hat, face, hair, epaulette, collar, coat, torso, legs) must keep ≥ 95 %.
- Background regions (sky, sun, town, midground flags, rider, ranks) must lose ≤ 3 %.

| Method | Full plate | Portrait crop | Battlefield crop (figure is a sliver at the edge) |
|---|---|---|---|
| **hybrid** (BiRefNet + hint outline + QA), **production** | **PASS**: figure ≥ 0.976, background leak 0.000 | **PASS**: ≥ 0.991, 0.000 | **PASS via safe fallback**: QA rejects, shot renders as one layer |
| BiRefNet alone | PASS | PASS | **FAIL**: picks the rider as the subject (rider 50 % and ranks 31 % pulled into the foreground) |
| GrabCut from hints alone | PASS (leak 0.028) | PASS | **FAIL**: legs 67 %, sky leak 6 % |

- **Rule:** a wrong matte is worse than none. If QA fails (empty, fragmented, or edges not following the image), no matte is used and only parallax is lost.
- **Props** such as the crate, map, spyglass and draped flag are not "figure" to the model. Add them with an `include` polygon; this is done for `p1`.
- **The reference matte itself was imprecise:** it included up to ~30 px of sky at the left frame edge. BiRefNet was right there.

## 3. Component status
| Status | Component |
|---|---|
| **Complete, tested** | Storyboard renderer: plates of any size or aspect ratio, cover fit, working resolution per shot, camera, parallax, transitions (whip, ink, flash, dissolve, cut), fade, grain, vignette |
| **Complete, tested** | Limited motion: blink, flags, marching bob, smoke, smoke column, cannon puffs, wind ripples, cloud drift, lens haze |
| **Complete, tested** | Typography presets (titles, lower thirds, dates, rules, bars); caption-band collision check |
| **Complete, tested** | Map module: routes with moving arrows, dots, rings, stars, labels, date ticker, legend, camera spline, territory reveals, Natural Earth coastline |
| **Complete, tested** | Narration stage: re-timing to aligned words, ducked mix, burned captions, delivery verification |
| **Complete, tested** | Regression suite with golden frames |
| **Complete, tested** | Job-queue worker plumbing (mock ComfyUI and temporary git remote) |
| **Experimental** | Automatic mattes (hybrid): validated on the approved image and two crops only; generated plates still need checking (review sheet per plate) |
| **Experimental** | 1811 territory polygons: simplified, hand-traced; good enough for a gesture, not for borders shown up close |
| **Experimental** | Plate metadata authoring (eyes, flag poles, smoke bands, hints) is manual; see section 5 |
| **Experimental** | ComfyUI workflows and prompts: graph structure tested, never run on a GPU; IP-Adapter weight and hires settings untuned |
| **Needs external tools** | Illustrations: ComfyUI on your RTX 4060 (the cloud has no GPU and cannot reach model hosts) |
| **Needs external tools** | Character consistency LoRA: training on your PC after about 20 approved images |
| **Needs external tools** | New narration: your voice file, or ElevenLabs with explicit approval each time |
| **Needs external tools** | Large-volume storage: Git LFS or a private bucket |
| **Not set up (by request)** | Publishing and daily scheduling |

**Bugs found and fixed by the new tests:**
- metadata regions outside a cropped plate crashed the loader;
- a camera keyframe without `focus` crashed;
- a missing matte file crashed (it now falls back to one layer);
- map frames with many stars or territories took up to 9 s; now < 1 s, by blending only inside each element's box, precomputing the hatch and using OpenCV blends.

## 4. Rendering time (cloud container, 4 vCPU, no GPU)
| Step | Time |
|---|---|
| Picture 720p, 18.2 s, 4 workers | **115 s** (≈ 6.3 s per second of video) |
| Picture 1080p, 18.2 s, 3 workers | **282 s** (≈ 15.5 s per second of video) |
| Narration mix + captions | 33 s (720p), 95 s (1080p; single-threaded, could be parallelised) |
| One 1080p frame by plate size | 768×1344: 0.26 s · 1152×2016: 0.32 s · 2304×4032: 0.51 s (rendered at 1935×3387 working size) |
| Map frame (720p) | 0.2–1.0 s; plus about 10 s one-time map build per worker |
| Auto matte per plate | 8 s (BiRefNet on CPU) to 30 s (hybrid with hints); 224 MB model downloaded once |
| Regression suite | 117 s |
| **Estimate, 60 s episode** (10 plates, 2 maps, 1080p) | Mattes ≈ 3 min + picture ≈ 16 min + narration ≈ 5 min = **≈ 25 min of CPU**, no paid service |
| Illustrations on your PC | Not measured yet; estimate 30–60 s per image (the manifest records the real number) |

## 5. Claude-dependent steps (where the cost is)
These need Claude to read text or **look at images**. Rendering itself is plain CPU work and costs no Claude usage while it runs.
I cannot read my own token meter, so the counts below are image reads per 60 s episode, not measured tokens.

| Step | Per episode | Cost |
|---|---|---|
| Script, history check, storyboard, prompt specs | Text only | Moderate |
| Candidate review: contact sheet + full views of the picks, per shot | ≈ 30–40 image reads (more if candidates are rejected) | **High** |
| Plate metadata: eye outline (close-ups only), flag poles, smoke bands, mask hint, via grid overlays | ≈ 20–30 image reads | **Highest, and the most error-prone** |
| Render QA: contact sheet + 5–10 stills | ≈ 10–15 image reads | Moderate |
| Fix loops after QA | Varies | Varies |

**Ways to cut it** (not built yet; ordered by value):
1. Detect French tricolour flags and the sky line automatically and propose metadata.
2. Use a fixed effect preset per shot type (battle, portrait, landscape).
3. Request a depth map from ComfyUI with each plate (Depth Anything V2 Small, Apache-2.0) for automatic layers.
4. Animate eyes only in hero close-ups (1–2 per episode).
5. Review candidates as one contact sheet per job rather than single images.

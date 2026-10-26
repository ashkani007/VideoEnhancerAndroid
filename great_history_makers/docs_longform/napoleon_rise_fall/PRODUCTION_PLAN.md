# Production plan and audit: *Napoleon: The Rise and Fall of an Emperor* (2026-10-26)

## 1. Audit (what exists, what works, what is missing)
| Area | Finding | Status |
|---|---|---|
| Renderer (`ghm4`) | Was built for 9:16 Shorts only | **Fixed today:** `"format": "landscape"` gives 1920×1080 (1280×720 preview), with a 1280×720 design space for text, maps, subtitles (y 975/1080), the QC stage and the delivery verifier. The vertical pipeline is unchanged: 6/6 regression tests pass, golden frames identical |
| Map system | Approved parchment campaign style; routes, rings, stars, territory reveals, date ticker; safe-label layout; QC label checks | **Corrected after client feedback:** the ORIGINAL approved map style is restored and **locked** (`ghm4/map_style.py`; see `poc/MAP_STYLE_RESTORATION.md`). 16:9 output keeps the approved graphics size; unit blocks and other new map elements are refused without approval. **Ulm–Austerlitz sample in the original style rendered (16.5 s, 1080p).** |
| Painted plates | Only one approved illustration exists, in the earlier flat cinematic style. It does **not** match the new realistic direction and is not used. The minimalist stand-ins are retired | **Missing:** every painted plate must be generated |
| Image generation in this cloud session | No GPU (4 vCPU); Hugging Face, Civitai, Wikimedia and museum image hosts are blocked; no image-generation tool or connector (the ElevenLabs connector here is voice-only) | **Not possible here** |
| Local GPU (client's RTX 4060) | ComfyUI is not installed. The reviewed, hash-locked installer waits for approval (`comfyui/windows/LOCAL_INSTALL_PLAN.md`); the Hugging Face checksums are resolved on the PC (`-ResolveLock`). No local session is reachable from here | **Not verified, waiting for the client** |
| Generation jobs | Queued: `jobs/queue/napoleon_longform_poc_v1.json`<br>• 7 shots × 4 seeds = 28 images, 16:9 (1344×768 → 2016×1152 hires)<br>• style `ghm_painterly_v2`; workflow `sdxl_hires`, which needs no reference images<br>• includes Napoleon references for 1796 / 1805 / 1812 / 1815 and the three POC plates | Ready for the PC worker |
| Narration | Approved ElevenLabs voice Max (`Gfpl8Yo74Is0W6cPUWWT`) | POC text frozen (`poc/NARRATION_POC.txt`, 166 words). **Estimate (nothing generated): 944 credits ≈ $0.19 per take** |
| Music and sound effects | Procedural (`mosaic.audio`): no licences, no cost | Ready |
| QC | `ghm4.qc` (black / frozen / washout, plate enlargement, title contrast, subtitle background, map label clipping, overlap and subtitle collisions), regression suite, delivery verifier | Ready, landscape-aware |

## 2. Why the 60–90 s POC is not delivered complete yet
The POC needs three painted scenes in the new realistic style:
- the Napoleon character scene;
- the battlefield;
- the Russian retreat.

Nothing in this session can generate them, and the brief rules out placeholders. Everything else is done, and the POC is assembled automatically as soon as the plates and the narration exist:
- the map scene;
- script, narration text, storyboard, style, characters, jobs;
- music and sound effects.

## 3. Decisions needed from the client
| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | **How the paintings are generated** | **A. Local PC (ComfyUI, RTX 4060):** run phases 1–4 of `LOCAL_INSTALL_PLAN.md` in your Windows Claude session (inspect → plan → resolve the lock → approve the fingerprint → install, about 21 GB), then `run_worker_once.bat`<br>**B. Paid hosted image generation** through a connector you add (for example the full ElevenLabs connector, which has image models). Needs your budget approval; the price is checked with an estimate first<br>**C. You supply licensed images** | **A** for the full film (lowest running cost, full control). B is acceptable for the POC only if you want it faster |
| D2 | Image model for realism (option A) | SDXL base 1.0 (already in the hash lock); or an added realism checkpoint (a licence-checked SDXL fine-tune) or FLUX.1 [schnell] GGUF (Apache-2.0, strong anatomy and composition, about 7–12 GB extra) | Start with SDXL base; A/B FLUX.1 [schnell] on the POC shots if the realism is not enough. Any added model goes through the same lock + fingerprint approval |
| D3 | POC narration | ElevenLabs, voice Max, one take of `poc/NARRATION_POC.txt` | Approve **944 credits (≈ $0.19)** |
| D4 | Script | `SCRIPT.md` draft 1 (about 2,200 words, about 17–18 min) | Review facts, tone and length before the full narration (about 13,000–14,000 credits ≈ $2.70 per take) |

## 4. Pipeline after approval (gates in bold)
1. **Look development:** the PC worker generates the 28 images of `napoleon_longform_poc_v1`. I review the contact sheet, rank candidates, and send you the picks.
   - **Gate:** you approve one Napoleon reference per age and the POC plates.
2. **POC assembly** (cloud, about 20–30 min):
   - 2× upscale (PC worker), plate metadata and automatic mattes;
   - narration (one take) → forced alignment → `poc/storyboard_poc.json` retimed;
   - 1080p render, subtitles, mix, QC, verification.
   - **Gate:** you approve the visual style.
3. **Full narration:** script frozen as `NARRATION.txt` → 2 takes → you pick → alignment.
4. **Plates:** 52 paintings in chapter batches (at most 40 images per job, about 13 jobs). Each batch: generate → review → upscale → plate metadata → QC. Character LoRA after about 20 approved Napoleon plates.
5. **Maps:** 12 map shots (5 adapted from existing data, 7 new). New year-accurate borders are digitised from a cited atlas; every route simplification is noted.
6. **Render:** chapter by chapter at 1080p, then assembly. Defective shots are re-rendered with `--patch`; the final assembly is one clean render.
7. **QC and review:**
   - QC stage, delivery verifier and visual review of every shot;
   - history check against the claim table;
   - branding.
   - **Gate:** you approve the final cut. **No publishing or scheduling by the pipeline.**

## 5. Time and cost
| Item | Actual so far | Estimate | Basis |
|---|---|---|---|
| Engineering, map, script, bible, plan (this session) | **$0** (no paid service) | – | – |
| POC images (28) on the PC | – | about 15–30 min GPU, electricity ≈ €0.01–0.03 | 30–60 s per image on an RTX 4060 (estimate until the first manifest reports real numbers) |
| POC narration | – | **944 credits ≈ $0.19** | ElevenLabs estimate (nothing generated) |
| Full-film images (52 plates × 4 seeds ≈ 210 images + upscales) | – | about 2–4 h GPU, electricity ≈ €0.10–0.20 | Same per-image estimate |
| Full narration, 2 takes | – | about 27,000 credits ≈ $5.40 | 944 credits per 946 characters, script about 13,500 characters |
| Cloud rendering, 17.3 min at 1080p (about 31,000 frames) | – | about 6–10 h machine time, $0 | Measured: map frames about 0.85 s each at 1080p with 3 workers; plate frames are cheaper |
| Music and sound effects | – | $0 | Procedural |
| Hosted image generation (only if you choose option B) | – | To be quoted with an estimate before any spend | – |

## 6. Files
- `SCRIPT.md`: documentary script with the claim-check table and sources.
- `STYLE_BIBLE.md`: visual language (machine version `comfyui/bible/style_ghm_painterly_v2.json`).
- `CHARACTERS.md`: Napoleon by age and the supporting cast (machine version `comfyui/bible/characters/napoleon.json`).
- `SCENE_LIST.md`: 74 shots, 12 maps, timings.
- `poc/`: map storyboard and render, `NARRATION_POC.txt`, `storyboard_poc.json` (assembly template), POC job spec `jobs/specs/napoleon_longform_poc_v1.json`.

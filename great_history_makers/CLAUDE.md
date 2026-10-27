# Great History Makers: production instructions for Claude

Read this file first in every session. Then read, in order: `STYLE_BIBLE.md`,
`LESSONS_LEARNED.md`, `FAILED_EXPERIMENTS.md`, `QUALITY_RUBRIC.md`, `EPISODE_HISTORY.json`
and `PROMPT_LIBRARY/`. Only what is written in these files is remembered between sessions.
Never claim to remember anything else.

## What this project is
A local Python + FFmpeg pipeline (`mosaic/`, `produce.py`, `tools/`). It makes 9:16 history
Shorts in a vibrant ancient-mosaic style for the channel **great_history_makers_en**.
Episodes live in `episodes/<id>/`: `episode.json` (timeline, captions, audio cues) and
`scenes.py` (shot builders). Outputs go to `output/<id>/`.

## Non-negotiables
- **Brand:** use the original gold emblem `assets/brand/Great_History_Makers_Logo_Transparent.png`
  (extracted from the channel screenshot). Never invent or redraw it. Apply it with
  `tools/brand.py`: an upper-left watermark (155 px, 60 %) and a 3 s end signature with the handle.
- **Format:** 1080×1920, 30 fps, H.264 High yuv420p, AAC 48 kHz. Upload encode about 13 Mbps 2-pass (under 100 MB for git).
- **Narration:** the client's voice file is never regenerated, edited or time-stretched. Only one overall gain is allowed.
  Paid generation (ElevenLabs, Runway, Kling, Artlist and so on) needs explicit approval every time.
- **Generated narration (ElevenLabs):** send the approved `NARRATION.txt` unchanged with the approved voice
  (`episode.json` → `tts.voice_id`; Ep02: `Gfpl8Yo74Is0W6cPUWWT`, Max). Price it first (estimate / dry run), then
  generate once, then put the chosen take at `audio/narration.mp3`, align it, and re-time shots, titles and SFX to the real lines.
  Once chosen, that take is treated like a client file: no edits or time-stretch. Use the ElevenLabs connector when the session has it;
  otherwise `tools/tts_elevenlabs.py`, which reads the key only from the `ELEVENLABS_API_KEY` environment variable.
  Never put an API key in code, chat, git or logs.
- **Subtitles:** timing comes from forced alignment of the real audio (`tools/align_narration.py`). Never estimate it.
  Wording must match the narration exactly. One lower-middle position (y = 1410/1920), at most two lines,
  ivory text with an outline, no box. Never in the top of the frame; keep faces out of the caption band.
- **History:** fill in the episode's `HISTORY.md` with four categories: established, propaganda, disputed,
  reconstruction. No invented quotes. Label reconstructions on screen.
- **No templates:** every episode gets an original script, a topic-specific storyboard and unique compositions.
  Never re-skin a previous episode. Nothing is published without human approval.
- **Style changes:** never roll out an unapproved style change across an episode. Test it first as an A/B on one shot.

## v4 direction: APPROVED by the client 2026-10-25 (use for all new episodes)
The look of `GreatHistoryMakers/Napoleon_20s_POC`: a new illustration for each narrative beat, motion graphics
(animated maps with moving arrows, cinematic typography, transitions), sound design, and **limited** character motion
(a visible blink in close-ups; flags, smoke, marching ranks, clouds). No complex character animation, no paid
image-to-video. Pipeline: `ghm4/` (see `ghm4/README.md`). Illustrations come from ComfyUI on the client's RTX 4060
through the git job queue (`jobs/README.md`, `comfyui/SETUP_WINDOWS_RTX4060.md`); prompts are built from
`comfyui/bible/` (style + characters). The cloud container cannot generate images itself: never substitute
code-drawn characters for missing illustrations. Narrated episodes: titles stay out of the caption band (design y 900–990).
Daily scheduling and publishing stay off until the client authorises them. The current GitHub repository (LensPrompt)
is public: the client prefers a NEW dedicated private repository (`tools/export_ghm_repo.sh`), not changing LensPrompt.
Windows install: only via the reviewed, hash-locked installer and `comfyui/windows/LOCAL_INSTALL_PLAN.md` gates
(inspect → plan → resolve lock → client approves fingerprint → install). Never run the install, large downloads,
firewall or scheduled-task changes without that explicit approval. Never ask for or print tokens.
Client's final direction (2026-10-25): cinematic AI illustrations, a new one at each topic change; simple character
motion only (blink, subtle hand `sway`, cloth `wind`); maps, timelines, arrows, dates, typography, camera moves,
transitions, atmosphere, sound. No 2.5D/3D character animation, no paid image-to-video. New episodes are specs in
`episodes_v4/<id>/episode.json`, produced with `python -m ghm4.episode run`. Local generation is NOT confirmed working
until the client's PC returns a manifest (`jobs/results/<id>/manifest.json`).

## Long-form documentary direction (client brief 2026-10-26): *Napoleon: The Rise and Fall of an Emperor*
16:9 1920×1080, 15–20 min, English. Project folder `docs_longform/napoleon_rise_fall/` (script with citations, style bible,
characters, scene list, production plan, POC). **The client rejected the minimalist stand-in look** (flat vector church,
simplified Moscow skyline, empty snowfields): never use code-drawn or minimalist environments or placeholder art in a video
again. New look: cinematic historical digital paintings with realistic proportions and rich detail (`style_ghm_painterly_v2`),
consistent Napoleon references per age (`napoleon.json` variants), subtle motion and atmosphere, and **maps as a major
storytelling element** (moving army positions, routes, dates, territorial change). Renderer: storyboard `"format": "landscape"`.
**MAP STYLE IS LOCKED (client correction 2026-10-26):** the animated maps of the original Napoleon Short (Ep01) and the
20s POC campaign map are the approved reference. Never redesign them (no new zoom scale, unit blocks, legend position,
river style or fading behaviour) without the client's explicit approval; `ghm4/map_style.py` refuses non-original
features and QC checks the graphics scale. The locked, reusable preset for ALL future documentaries is
`ghm4/data/map_presets/ghm_original_v1.json` (measured ranges, label rules, Ep01 reference frames, code fingerprint
checked by the `map_lock` test). Compare new maps against actual Ep01 frames with `tools/map_compare_sheet.py`,
never against a verbal description. The painterly illustration style applies to non-map scenes only.
Do not assume a new style is better because it looks more cinematic.
Deliver a 60–90 s POC for approval before producing the full film; no publishing.

## v2 direction (client decision 2026-10-23, superseded by v4 for new work)
New episodes use **illustration plates + limited 2D animation + motion graphics** (`ghm2/`, see
`ghm2/MIGRATION_PLAN.md`). Do not build new 2.5D rigs or per-shot procedural scenes; the v1 engine stays in the
repo for reference and for Episode 01/02. 8–12 compositions per 60 s, one motivated camera move each, cuts in
narration pauses, limited character motion (blink, head turn, gesture, breathe) only where it serves the story.
The exact v2 look (including whether a mosaic filter is kept) still needs client approval.
Variable cost target < €0.50 per video: measure it, log credits in `autopilot/LEDGER.json`.

## v3 visual identity PROPOSAL (client brief 2026-10-23, superseded by v4)
"Cinematic Living Illustration": painterly, character-driven, every shot a narrative action, believable acting
(eyes lead, head follows, face sets), cinematic shot grammar and motivated light. No mosaic, stained glass,
paper-cut puppets, zoom-and-pan slideshows or permanent infographics. See `ghm3/VISUAL_IDENTITY.md` and
`ghm3/POC_EVALUATION.md`. Do not produce full episodes in v3 until the client approves the proof of concept.

## Episode loop (follow every time)
1. **Review:** read the memory files and list the strongest techniques and the open weaknesses.
2. **Goals:** pick 2–3 concrete improvements. Write them into `EPISODE_HISTORY.json` before producing.
3. **Produce:** script, then storyboard, then shots, then a 720p preview, then human review, then the 1080p final, then branding.
4. **Evaluate:** score with `QUALITY_RUBRIC.md` using observable evidence (frames, crops, ffprobe, measurements).
5. **Compare:** set the scores against the previous approved episode. List regressions as well as gains.
6. **Learn:** append to `LESSONS_LEARNED.md` / `FAILED_EXPERIMENTS.md`. Change `STYLE_BIBLE.md` only after approval.
7. **Apply:** carry the lessons into the next episode's goals.

## Commands
```
py produce.py episodes/<id>                         # 720p preview + QC
py produce.py episodes/<id> --quality final --workers 3
py produce.py episodes/<id> --still 12.5
py tools/brand.py master.mp4 audio_src.mp4 out.mp4 endcard.png
py tools/shot_sheet.py episodes/<id> video.mp4 sheet.png
py tools/tts_elevenlabs.py episodes/<id> [--confirm]  # narration via API (dry run without --confirm)
py -m ghm2.render <v2 episode dir> [--final|--still T]  # v2 illustration pipeline (540x960 preview / 1080x1920)
py tools/verify_delivery.py video.mp4 <episode dir> [--no-endcard]  # narration sync, captions, logo (v1-v3)
py -m ghm3.render_poc [--final]                     # v3 Cinematic Living Illustration proof of concept
py tools/character_sheet.py out.png                 # character turnaround sheet (rig views + profiles)
py experiments/ab_2p5d/render_ab.py                 # style A/B (A vs B)
py experiments/ab_2p5d/render_c.py                  # Version C + B/C comparison + metrics
py experiments/ab_2p5d/render_d.py                  # Version D (turning gate entry) + C/D comparison + metrics
py -m ghm4.illustrate job jobs/specs/<id>.json      # illustration job for the local ComfyUI worker (then: status / pick / place)
py comfyui/worker/test_worker.py                     # worker plumbing test (mock ComfyUI + temp git remote)
py -m ghm4.render <storyboard.json> [--final|--still T|--sheet]   # v4 picture render (+ music/SFX preview)
py -m ghm4.narrate <storyboard.json> check|align|retime|finish <picture.mp4>   # v4 narration + captions stage
py -m ghm4.plate_tool overlay <plate.png> <plate.json>          # draw plate metadata regions for checking
py -m ghm4.masks make <plate.png> <plate.json>                  # automatic matte (hybrid) + QA; rejected -> one layer
py -m ghm4.tests.run_all [--quick|--update-golden]              # v4 regression suite (golden frames, masks, worker, episode...)
py -m ghm4.episode run|jobs|status|pick|plates|sheet|storyboard|render episodes_v4/<id>   # automated episode pipeline
```

## Environment gotchas (verified)
- 1080p renders need about 2.5 GB RAM per worker. Use `--workers 3` on 16 GB.
- Never `pkill -f <pattern>` with a pattern that also appears in the command itself: it kills the shell.
  Use `pgrep -f "[p]attern"`.
- In the cloud container: no GPU, and Hugging Face and model hosts are blocked (403). PocketSphinx from PyPI works offline.

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
- **Subtitles:** timing comes from forced alignment of the real audio (`tools/align_narration.py`). Never estimate it.
  Wording must match the narration exactly. One lower-middle position (y = 1410/1920), at most two lines,
  ivory text with an outline, no box. Never in the top of the frame; keep faces out of the caption band.
- **History:** fill in the episode's `HISTORY.md` with four categories: established, propaganda, disputed,
  reconstruction. No invented quotes. Label reconstructions on screen.
- **No templates:** every episode gets an original script, a topic-specific storyboard and unique compositions.
  Never re-skin a previous episode. Nothing is published without human approval.
- **Style changes:** never roll out an unapproved style change across an episode. Test it first as an A/B on one shot.

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
py tools/character_sheet.py out.png                 # character turnaround sheet (rig views + profiles)
py experiments/ab_2p5d/render_ab.py                 # style A/B (A vs B)
py experiments/ab_2p5d/render_c.py                  # Version C + B/C comparison + metrics
py experiments/ab_2p5d/render_d.py                  # Version D (turning gate entry) + C/D comparison + metrics
```

## Environment gotchas (verified)
- 1080p renders need about 2.5 GB RAM per worker. Use `--workers 3` on 16 GB.
- Never `pkill -f <pattern>` with a pattern that also appears in the command itself: it kills the shell.
  Use `pgrep -f "[p]attern"`.
- In the cloud container: no GPU, and Hugging Face and model hosts are blocked (403). PocketSphinx from PyPI works offline.

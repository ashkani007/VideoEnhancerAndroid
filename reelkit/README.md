# ReelKit — autonomous storytelling Shorts

ReelKit turns an openly licensed film into a 45–60 s narrated vertical Short. It finds the film, analyses the footage, writes and voices the narration, edits, reframes, captions and mixes, then runs QC. A human approves the 480p preview before the 1440×2560 render.

```
discover ─► acquire ─► analyze ─► write (story.json) ─► voice ─► timeline ─► preview + QC ─► approve ─► final
 cached      licence    cached     LLM or operator       local     saliency     480x854         gate      1440x2560
             gate       per film                          TTS       reframe                               NVENC
```

| Module | Does | Cost |
|---|---|---|
| `discovery.py` | Curated open-movie catalogue + Internet Archive + Wikimedia Commons + YouTube (CC-BY only, via yt-dlp metadata). Rejects NC/ND/standard licences. Cached 7 days. | free |
| `__main__ acquire` | Direct download for file URLs; yt-dlp only when the platform itself reports a CC licence. Never touches DRM. Writes a `.source.json` licence record with sha256. | free |
| `analyze.py` | One low-res decode pass: shot cuts, brightness, motion, saliency track; keyframes and labelled contact sheets. Cached by file hash, so each film is analysed once for every Short cut from it. | ~30 s CPU per 15-min film |
| `llm.py` | Optional: Claude reads contact sheets, ranks candidates and drafts `story.json`. Without credentials it writes the prompt next to the expected answer file and waits. | ~$0.10–0.25 per Short on the default model; set `llm.model` lower to cut it |
| `tts.py` | Kokoro-82M (int8 ONNX, 92 MB, Apache-2.0), local, per-sentence cache, estimated word timings. | free |
| `edit.py` | Timeline from narration windows; hybrid 9:16 reframe (saliency-tracked square crop over a blurred fill, slow push-in on static shots, gamma lift on dark shots); ASS captions with active-word highlight; source-audio bed per cut, ducked under the voice; synthesised SFX; −14 LUFS master. | — |
| `qc.py` | Duration, hook timing, beat timing, pace, shot lengths, cut overruns, reused footage, black frames, loudness, source resolution, licence record. | — |
| `produce.py` | Orchestration, deliverable docs, and the approval gate (final render requires an approval matching the preview's sha256 and a ≥1080p master). | — |

## Setup (RTX 4060 workstation)

```bash
pip install -r reelkit/requirements.txt          # kokoro-onnx, soundfile, numpy, pillow, requests, yt-dlp
export REELKIT_WORKSPACE=~/reelkit_media         # sources/, cache/, models/, productions/
python -m reelkit discover "short film twist ending"
python -m reelkit acquire <file-url> --license CC-BY-3.0 --name film.mp4
python -m reelkit analyze sources/film.mp4       # contact sheets for the writer step
# write productions/<slug>/story.json (or let llm.py draft it)
python -m reelkit produce <slug>                 # preview + script/sources/timeline/QC docs
python -m reelkit approve <slug>
python -m reelkit final <slug> --master sources/film_1080p.mp4
```

NVENC is detected with a real 1-frame test encode. Without a working NVIDIA driver ReelKit falls back to libx264.

## Throughput for 30–60 Shorts/month

- One film usually yields several Shorts (different characters or arcs), and analysis is paid once per film.
- Voice, LLM answers, discovery results and analysis are all cached on disk. Re-rendering after a script tweak re-synthesises only the changed sentences.
- On a 4-core CPU with no GPU, the full preview pipeline takes about 50 s. Final 1440×2560 renders are the only heavy step, and NVENC handles those.

## Known limitations

- Caption word timing is estimated, not forced-aligned (±0.1–0.2 s).
- Saliency comes from edges and motion, not face detection. Shots with off-centre faces may need `"frame": "wide"` or `"tight"` in `story.json`.
- The writer step needs either Claude API credentials or an operator/agent to supply `story.json`.

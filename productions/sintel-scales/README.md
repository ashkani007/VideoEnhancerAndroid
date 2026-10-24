# Production test #1 — "She hunted this dragon for years" (Sintel)

Status: **480p preview rendered — waiting for approval.** The final 1440×2560 render has not been made.

| Deliverable | File |
|---|---|
| 1. Narration script | [script.md](script.md) |
| 2. Sources and licences | [sources.md](sources.md) |
| 3. Shot-by-shot timeline | [timeline.md](timeline.md) (machine-readable: `timeline.json`) |
| 4. 480p preview | [sintel-scales_preview_480p.mp4](sintel-scales_preview_480p.mp4) |
| 5. QC report | [qc_preview.md](qc_preview.md) and the notes below |

## Reference video (youtube.com/shorts/5V5KalgmlUI)

**Not analysed.** This run's network blocks youtube.com: the proxy refused the connection, and server-side fetch failed DNS. A web search returned nothing about that video ID. So nothing here is modelled on that Short. The pacing choices below are general storytelling-Short conventions and not an analysis of it: a hook question in the first 3 s, cuts every 1–2.5 s, 2–3 word captions with the active word highlighted, and the film's own score kept under the narration.

## Phase 1 — candidate ranking

13 openly licensed narrative films were scored on a 5×5 rubric (hook, conflict, visual clarity, payoff, 60-second fit). Full data: [`../_discovery/discovery.json`](../_discovery/discovery.json). In this run the Internet Archive, Wikimedia Commons and YouTube-CC providers were attempted but blocked by the network or missing `yt-dlp`, so ranking came from the curated catalogue plus web search.

| Rank | Film | Score /25 | Licence | Why |
|---|---|---|---|---|
| 1 | **Sintel** (2010) | 24 | CC BY 3.0 | Full arc fits in 60 s and ends on a true twist (she kills the dragon she raised). Footage was verified shot by shot. |
| 2 | Night of the Living Dead (1968) | 23 | Public domain (US) | Bleak twist ending. Black and white, and only original-print scans are safe to use. archive.org is unreachable here. |
| 3 | Sprite Fright (2021) | 21 | CC BY 4.0 (studio-wide policy; per-film page not checked) | Strong horror-comedy hook, 4K source. Not reachable here. |
| — | Cosmos Laundromat 21 · Tears of Steel 17 · Charge 18 · Caminandes 3 18 · Spring 17 · Agent 327 17 · Big Buck Bunny 17 · Glass Half 16 · Coffee Run 15 · Elephants Dream 10 | | | |

## QC summary (preview)

- 58.3 s total. Hook line ends at 2.4 s. 159 words at 3.2 words/s, with 41 cuts averaging 1.4 s.
- No reused footage, no clip runs past a source cut, no black gaps. Loudness is −15.1 LUFS integrated (target −14) with a −1.2 dBFS peak.
- **Warn:** the ending beat starts at 50.3 s, against a 55 s target. The narration is 3 s shorter than the template, so the whole arc runs slightly early.
- **Limitation, source resolution:** the only copy of Sintel reachable from this network is a 512×292 re-encode. The preview is soft (×1.64 upscale of the foreground). The final render refuses sources under 1080p. Download the official 1080p file (durian.blender.org or archive.org/details/Sintel) and run `final --master`.
- **Limitation, caption timing:** word times are estimated from pauses in the TTS audio and syllable counts, not forced-aligned. Expect ±0.1–0.2 s per word.
- **Limitation, hardware:** this container has no GPU. The preview was encoded with libx264. On the RTX 4060 machine ReelKit detects and uses `h264_nvenc` automatically.
- Narration is faithful to the film's plot as published (Wikipedia, IMDb). "Years" is used because the film says "many years" and gives no number.

## To approve and render the final

```bash
export REELKIT_WORKSPACE=~/reelkit_media
python -m reelkit approve sintel-scales --note "approved"
python -m reelkit final sintel-scales --master ~/reelkit_media/sources/Sintel.2010.1080p.mp4
```

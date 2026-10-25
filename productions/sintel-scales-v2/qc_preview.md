# QC report (preview, v2)

Overall: **WARN** — 58.98 s, encoder `libx264`.

| Check | Status | Detail |
|---|---|---|
| duration 45-60 s | pass | 58.98 s |
| resolution | pass | 480x854 |
| hook line lands inside 3 s | pass | first line ends at 2.01 s |
| beat 'hook' timing | pass | 0.1-3.5 s (target 0-3 s) |
| beat 'setup' timing | pass | 4.0-13.2 s (target 3-15 s) |
| beat 'rising' timing | pass | 13.6-36.0 s (target 15-40 s) |
| beat 'climax' timing | warn | 36.4-48.6 s (target 40-55 s) |
| beat 'ending' timing | warn | 49.1-56.1 s (target 55-60 s) |
| narration pace 2.2-3.3 words/s | pass | 159 words, 3.21 words/s |
| shot lengths | pass | 40 cuts, min 0.51 s, max 2.64 s, mean 1.47 s |
| no clip runs past its source cut | pass | none |
| no repeated footage | pass | none |
| no black gaps | pass | none |
| loudness ~ -14 LUFS | pass | {'integrated_lufs': -14.3, 'true_peak_dbfs': -1.2} |
| source resolution | pass | source 512x292, foreground upscale x1.64 |
| faces never cut off | pass | min face coverage 100% |
| subjects kept in frame | pass | min subject coverage 100% |
| no excessive zoom (≤ ×2.2) | pass | max ×2.20 |
| picture fills the frame | pass | picture covers 47% of frame height on average; modes {'full-frame': 17, 'subject-crop': 23} |
| captions inside Shorts safe area | pass | caption block x 13%–81%, y 67%–73% (UI-free zone x 4–86%, y 15–78%) |
| captions never cover a face | pass | 0 clip samples with a face under the captions |
| music changes land on story lines | pass | 13 cues: mystery → tender → wonder → tension → journey → mystery → dread → action → silence → action → dread → mystery → grief |
| licence + credit recorded | pass | CC BY 3.0 |

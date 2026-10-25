# Sintel — improved preview (v2)

Status: **480p preview rendered — waiting for your approval.** No 2K render has been made. The original version is unchanged in [`../sintel-scales/`](../sintel-scales/).

| | File |
|---|---|
| Preview (59 s, 480×854) | [sintel-scales-v2_preview_480p.mp4](sintel-scales-v2_preview_480p.mp4) |
| Voice comparison | [voice_comparison.mp3](voice_comparison.mp3) |
| Score only (no voice) | [score_only.mp3](score_only.mp3) |
| v1 vs v2 frames | [v1_vs_v2_frames.jpg](v1_vs_v2_frames.jpg) (top v1, bottom v2) |
| Script with music moods | [script.md](script.md) |
| Timeline, framing per clip, music cue sheet | [timeline.md](timeline.md) |
| Sources and licences | [sources.md](sources.md) |
| QC | [qc_preview.md](qc_preview.md) |

## What changed vs v1

| Problem | v1 | v2 |
|---|---|---|
| Narration | Kokoro `am_onyx`, deep and flat, uniform pace | Kokoro `af_heart` (Kokoro's top-graded voice) locked as ReelKit's narrator. Per-beat pacing (climax 0.93×, ending 0.88×) and longer dramatic pauses. Still local and free; ElevenLabs declined. |
| Softness | Every clip from the 512×292 copy; fixed square crop up to ×1.64; unsharp mask | Best available copy per clip (the 720-wide excerpt for 4 rooftop/hut clips, auto-aligned). Zoom capped at ×2.2 (median ×1.3). No sharpening. |
| Composition | Fixed square crop from edge/motion saliency, which cut heads and action | Faces (YuNet), characters and animals (YOLOX) and saliency detected on real frames. Subject crop, or the full frame when the action spans the shot. Height never cropped. 23 subject crops and 17 full frames, with every face and subject fully in frame. |
| Captions | Centred at 73% height | 47% across × 70% down, inside the Shorts UI-free zone; checked not to cover faces |
| Music | The film's own mixed audio chopped at every cut | Original ReelKit score with 13 cues that follow the story's moods. It goes silent on "It hesitated.", with braams on the hook, the attack, "She didn't." and "It was Scales." It ducks 17 dB under the voice. |

## Honest limitations

- **Source resolution is still the main ceiling.** No 1080p+ copy of Sintel is reachable from this network: blender.org, archive.org, wikimedia.org and xiph.org are all blocked. The final 2K render is still blocked until a ≥1080p master is registered. On your RTX 4060 machine: download the official 1080p file, then `python -m reelkit register-rendition sintel.mp4 Sintel.2010.1080p.mp4 --license "CC BY 3.0" --url <url>`. It's aligned automatically and used for every clip.
- **The score is synthesised.** It's original and needs no licence, but it uses simple synthesised instruments rather than recorded orchestra. Please judge it from `score_only.mp3`. If you'd rather use licensed library tracks, the cue sheet (mood × start/end) is the brief to pick them against.
- **The narrator is free local TTS.** It's warmer than v1 but still a 82M-parameter model. Switching to an ElevenLabs voice later costs about 873 credits (~$0.17) per Short and needs your approval.
- **Beat timing:** the climax starts at 36 s against a 40 s target. The story's front half is denser than the template.
- Shot-level dragon detection relies on saliency, because dragons are not one of the detector's classes.

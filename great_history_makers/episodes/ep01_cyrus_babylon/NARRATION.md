# Narration — Episode 1 (English, ~20 s)

Tone: calm documentary, warm and clear, not dramatic. Target pace ≈ 150 wpm (2.5 words/s).

| Time | Scene | Line (on screen) | Spoken form | Words |
|---|---|---|---|---|
| 0.4–4.9 | 1 · Overlook | In 539 BCE, Cyrus the Great of Persia set his sights on Babylon. | "In five thirty-nine B.C.E., Cyrus the Great of Persia set his sights on Babylon." | 13 |
| 5.2–9.9 | 2 · Gate | A Babylonian chronicle records that his army entered the city without a battle. | (same) | 13 |
| 10.2–14.9 | 3 · Court | Temple rites went on, and Cyrus proclaimed that Babylon's own god had chosen him. | (same) | 14 |
| 15.3–19.4 | 4 · Sunset | One of the greatest cities of the ancient world now had a new ruler. | (same) | 13 |

Total: 53 words in about 18.5 s of speech. If the chosen voice runs long, use these approved shorter alternatives:
- L1: "In 539 BCE, Cyrus of Persia turned toward Babylon."
- L3: "Temple rites went on — and Cyrus claimed Babylon's god had chosen him."

## Recording / ElevenLabs workflow
1. Generate each line as its own clip (gives timing control). Suggested settings: model `eleven_multilingual_v2`, stability ≈ 0.5, similarity ≈ 0.75, style ≈ 0.15.
2. Place the clips at the start times above in one 20 s, 48 kHz WAV and save it as `episodes/ep01_cyrus_babylon/audio/narration.wav`.
3. Adjust the `subtitles` start/end times in `episode.json` to the real speech if needed.
4. Run `python produce.py episodes/ep01_cyrus_babylon`. The mixer finds the narration and ducks the music under the voice automatically.

No synthetic voice has been generated yet: the preview has subtitles, music and SFX only, until a voice is chosen and the spend is approved.

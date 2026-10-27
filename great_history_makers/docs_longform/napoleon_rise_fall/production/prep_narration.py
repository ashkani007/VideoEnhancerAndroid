"""Place an approved narration take for one chapter: pad it with the chapter's lead-in silence (the chapter card),
so the storyboard, the alignment and the captions all run in chapter time.

    py docs_longform/napoleon_rise_fall/production/prep_narration.py ch3 path/to/take.mp3

Writes chapters/<ch>/audio/narration.mp3 (the take itself is never edited or time-stretched; only silence is added
before it). Then: py -m ghm4.narrate chapters/<ch>/storyboard.json align -> build.py -> render -> finish.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ch, take = sys.argv[1], sys.argv[2]
    d = os.path.join(HERE, "chapters", ch)
    lead = json.load(open(os.path.join(d, "storyboard.json")))["audio"]["narration_lead_in"]
    out = os.path.join(d, "audio", "narration.mp3")
    ms = int(round(lead * 1000))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", take, "-af", f"adelay={ms}:all=1", "-c:a", "libmp3lame", "-q:a", "0", out], check=True)
    print(f"{out}: {lead:.2f}s lead-in + take")


if __name__ == "__main__":
    main()

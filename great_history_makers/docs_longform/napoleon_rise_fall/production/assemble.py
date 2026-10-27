"""Final assembly of *Napoleon: The Rise and Fall of an Emperor* from the seven finished chapter videos.

    py docs_longform/napoleon_rise_fall/production/assemble.py [--check]

Expects, per chapter, the finished video written by `ghm4.narrate finish` (picture + ducked narration mix + burned
captions): chapters/<ch>/output/napoleon_doc_<ch>_1920x1080_final.mp4, and the aligned words used for its captions.
Writes to output/:
- Napoleon_The_Rise_and_Fall_of_an_Emperor_1080p.mp4   (lossless concat of the chapter finals, then the 2-pass delivery encode)
- Napoleon_The_Rise_and_Fall_of_an_Emperor.en.srt      (subtitles from the same caption cues, offset per chapter)
- CHAPTER_TIMESTAMPS.txt                                (from the real chapter lengths)
--check only reports what is missing. Nothing is uploaded or published.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, GHM)
sys.path.insert(0, HERE)

from ghm4 import narrate  # noqa: E402
from shots import CHAPTERS  # noqa: E402

TITLE = "Napoleon_The_Rise_and_Fall_of_an_Emperor"


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    finals, missing = [], []
    for ch in CHAPTERS:
        d = os.path.join(HERE, "chapters", ch["id"])
        f = os.path.join(d, "output", f"napoleon_doc_{ch['id']}_1920x1080_final.mp4")
        w = os.path.join(d, "audio", "words_aligned.json")
        for p in (f, w):
            if not os.path.exists(p):
                missing.append(os.path.relpath(p, HERE))
        finals.append((ch, d, f))
    if missing or a.check:
        print("missing:" if missing else "all chapter finals present", *missing, sep="\n  ")
        sys.exit(1 if missing else 0)
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    lst = os.path.join(out, "concat.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for _, _, f in finals))
    master = os.path.join(out, f"{TITLE}_master.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", master], check=True)
    srt, ts, t0, n = [], [], 0.0, 1
    for ch, d, f in finals:
        sb = json.load(open(os.path.join(d, "storyboard.json"), encoding="utf-8"))
        ts.append(f"{int(t0 // 60)}:{int(t0 % 60):02d} {ch['title']}")
        for c in narrate.cues_for(sb, d):
            srt.append(f"{n}\n{srt_time(t0 + c['start'])} --> {srt_time(t0 + c['end'])}\n{c['text'].replace(' / ', chr(10))}\n")
            n += 1
        t0 += duration(f)
    open(os.path.join(out, f"{TITLE}.en.srt"), "w", encoding="utf-8").write("\n".join(srt))
    open(os.path.join(out, "CHAPTER_TIMESTAMPS.txt"), "w", encoding="utf-8").write("\n".join(ts) + "\n")
    final = os.path.join(out, f"{TITLE}_1080p.mp4")
    subprocess.run(["sh", os.path.join(HERE, "encode_delivery.sh"), master, final], check=True)
    print(f"{final}: {duration(final) / 60:.2f} min, {n - 1} subtitles; timestamps in output/CHAPTER_TIMESTAMPS.txt")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build autopilot/selftest_cyrus: an end-to-end pipeline test that spends no credits.

It reuses Episode 01 (Cyrus V3) read-only: its scenes module, its client narration file and its
caption groups. Only the shot cut points are re-derived (from word indices, as a daily episode
does), so the test exercises align -> timeline -> render -> brand -> verify for real.

  python autopilot/make_selftest.py && python autopilot/pipeline.py all autopilot/selftest_cyrus
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from mosaic import captions  # noqa: E402

SRC = os.path.join(ROOT, "episodes", "ep01c_cyrus_v3")
DST = os.path.join(HERE, "selftest_cyrus")


def main():
    c = json.load(open(os.path.join(SRC, "episode.json"), encoding="utf-8"))
    os.makedirs(os.path.join(DST, "audio"), exist_ok=True)
    text = open(os.path.join(SRC, "audio", "transcript.txt"), encoding="utf-8").read().strip()
    shutil.copy(os.path.join(SRC, "audio", "transcript.txt"), os.path.join(DST, "audio", "transcript.txt"))
    lines = [s.strip() for s in re.split(r"(?<=[.])\s+", text) if s.strip()]
    open(os.path.join(DST, "NARRATION.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    # shot k starts at the first word that the original cut preceded (derived from the V3 alignment)
    words = captions.map_words(text, json.load(open(os.path.join(SRC, "audio", "words_aligned.json"))))
    shots = []
    for s in c["scenes"]:
        j = next((i for i, w in enumerate(words) if w["start"] >= s["start"] - 0.05), len(words) - 1)
        shots.append(dict(id=s["id"], at_word=0 if s["start"] == 0 else j))
    rel = os.path.relpath(SRC, DST)
    c["scenes_module"] = os.path.join(rel, c.get("scenes_module", "scenes.py"))
    c["audio"]["narration_file"] = os.path.join(rel, c["audio"]["narration_file"])
    c["captions"]["transcript"] = "audio/transcript.txt"
    c["captions"]["words"] = "audio/words_aligned.json"
    c["shots"] = shots
    c["tts"] = {"voice_id": None, "note": "self-test uses the existing Episode 01 client narration; no TTS call"}
    c["selftest_reference_starts"] = [s["start"] for s in c["scenes"]]
    json.dump(c, open(os.path.join(DST, "episode.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"wrote {DST} ({len(lines)} lines, {len(shots)} shots)")


if __name__ == "__main__":
    main()

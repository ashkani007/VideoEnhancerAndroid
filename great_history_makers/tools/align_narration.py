#!/usr/bin/env python3
"""Word-level timestamps for a narration file by forced alignment (fully offline).

  python tools/align_narration.py narration.mp3 transcript_align.txt words_aligned.json

Uses PocketSphinx (pip install pocketsphinx; its English model ships inside the
wheel). transcript_align.txt is the verified transcript in lowercase spoken form
(numbers spelled out). Words missing from CMUdict can be added in EXTRA_PRON.
Workflow used for Episode 1b: rough ASR pass -> candidate wordings checked by
constrained decoding and acoustic scores -> forced alignment -> cross-check
against ffmpeg silencedetect.
"""
import json
import os
import subprocess
import sys
import tempfile

EXTRA_PRON = {"opis": "OW P IH S", "marduk": "M AA R D UH K", "citys": "S IH T IY Z", "elba": "EH L B AH"}


def main(audio, text_path, out_path):
    import pocketsphinx
    from pocketsphinx import Decoder
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    base = os.path.join(pocketsphinx.get_model_path(), "en-us", "cmudict-en-us.dict")
    have = set(line.split(" ", 1)[0] for line in open(base, encoding="utf-8"))
    d_path = os.path.join(tempfile.mkdtemp(), "custom.dict")
    with open(d_path, "w") as f:
        f.write(open(base, encoding="utf-8").read())
        for w, p in EXTRA_PRON.items():
            if w not in have:
                f.write(f"{w} {p}\n")
    d = Decoder(samprate=16000, dict=d_path)
    d.set_align_text(open(text_path).read().strip())
    d.start_utt()
    d.process_raw(raw, full_utt=True)
    d.end_utt()
    segs = [dict(word=s.word, start=round(s.start_frame / 100, 2), end=round((s.end_frame + 1) / 100, 2))
            for s in d.seg()]
    json.dump(segs, open(out_path, "w"), indent=0)
    print(f"{len(segs)} segments -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])

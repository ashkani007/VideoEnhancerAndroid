#!/usr/bin/env python3
"""ghm4 narration + subtitle stage (separate from the picture render).

  python -m ghm4.narrate <storyboard.json> check                 # what is present / missing, caption-band conflicts
  python -m ghm4.narrate <storyboard.json> tts [--confirm]       # ElevenLabs (PAID: only with explicit client approval)
  python -m ghm4.narrate <storyboard.json> align                 # forced alignment -> captions.words (offline)
  python -m ghm4.narrate <storyboard.json> retime                # shots with "cue" start on their narration phrase
  python -m ghm4.narrate <storyboard.json> finish <picture.mp4>  # ducked mix + burned captions -> *_final.mp4

Order: write NARRATION.txt -> client voice file or approved TTS -> align -> retime -> render the picture
(python -m ghm4.render <storyboard>.timed.json --final) -> finish -> tools/verify_delivery.py -> tools/brand.py.

storyboard.json keys used here (compatible with tools/verify_delivery.py):
  "audio": {"narration_file": "audio/narration.mp3", "bed_under_voice_db": 20, "bed_in_pauses_db": 11, music, sfx}
  "captions": {"transcript": "audio/transcript.txt", "transcript_align": "audio/transcript_align.txt",
               "words": "audio/words_aligned.json", "groups": ["line one / line two", ...], "spoken": {...},
               "y": 1410, "size": 60}                       (y and size in 1080x1920 pixels, CLAUDE.md caption rule)
  shot "cue": "exact transcript words"                     (the shot starts 0.15 s before the first of those words)
  "excerpt": true                                          (tests: the video covers only the opening of the narration)
Timing always comes from the aligned words of the real audio; nothing is estimated.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

from . import text as T

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GHM)
from mosaic import captions  # noqa: E402

IVORY = (242, 230, 200)
OUTLINE = (14, 16, 24)
CAPTION_BAND = (900, 990)          # design units (720x1280) around y = 1410/1920


def load(sb_path):
    return json.load(open(sb_path, encoding="utf-8")), os.path.dirname(os.path.abspath(sb_path))


def words_for(sb, d):
    cc = sb["captions"]
    tr = open(os.path.join(d, cc["transcript"]), encoding="utf-8").read().strip()
    return captions.map_words(tr, json.load(open(os.path.join(d, cc["words"]))), cc.get("spoken"))


def cues_for(sb, d):
    cc = sb["captions"]
    tp, wp = os.path.join(d, cc["transcript"]), os.path.join(d, cc["words"])
    if cc.get("groups"):
        return captions.build_groups(cc["groups"], tp, wp, spoken=cc.get("spoken"))
    return captions.build(tp, wp)


def text_conflicts(sb, cues):
    """Typography inside the caption band while a caption is on screen (would collide)."""
    out = []
    for sh in sb["shots"]:
        for it in sh.get("text", []):
            y = it.get("y")
            if y is None or not CAPTION_BAND[0] - 40 <= y <= CAPTION_BAND[1] + 40:
                continue
            t0 = sh["start"] + it.get("at", 0)
            t1 = sh["start"] + (it["out"][1] if "out" in it else sh["end"] - sh["start"])
            for c in cues:
                if c["start"] < t1 and c["end"] > t0:
                    out.append(f"{sh.get('id', sh['start'])}: '{it.get('text', 'graphic')}' (y {y}) overlaps caption "
                               f"'{c['text'][:30]}' at {c['start']:.2f}s; move the title above y 840 or out of the cue")
                    break
    return out


def cmd_check(a):
    sb, d = load(a.storyboard)
    au, cc = sb.get("audio", {}), sb.get("captions")
    narr = os.path.join(d, au.get("narration_file", "audio/narration.mp3"))
    print(f"narration audio: {'ok ' + narr if os.path.exists(narr) else 'missing (client voice file, or approved TTS)'}")
    if not cc:
        print("captions: no 'captions' section in the storyboard")
        return
    for k in ("transcript", "transcript_align", "words"):
        p = os.path.join(d, cc.get(k, ""))
        print(f"{k}: {'ok' if cc.get(k) and os.path.exists(p) else 'missing'}")
    if os.path.exists(os.path.join(d, cc.get("words", "__"))):
        cues = cues_for(sb, d)
        print(f"{len(cues)} caption cues, {cues[0]['start']:.2f}-{cues[-1]['end']:.2f}s")
        for c in text_conflicts(sb, cues):
            print("CONFLICT:", c)


def cmd_tts(a):
    sb, d = load(a.storyboard)
    args = [sys.executable, os.path.join(GHM, "tools", "tts_elevenlabs.py"), d]
    if a.confirm:
        print("PAID generation: run only with explicit client approval for this episode.")
        args.append("--confirm")
    if not os.path.exists(os.path.join(d, "episode.json")):
        sys.exit("tts_elevenlabs.py reads episode.json (tts.voice_id) and NARRATION.txt in the storyboard folder")
    sys.exit(subprocess.call(args))


def cmd_align(a):
    from tools.align_narration import Aligner
    sb, d = load(a.storyboard)
    cc = sb["captions"]
    audio = os.path.join(d, sb["audio"]["narration_file"])
    text = open(os.path.join(d, cc["transcript_align"]), encoding="utf-8").read()
    segs, score = Aligner(audio).run(text)
    if segs is None:
        sys.exit("alignment failed: the spoken-form transcript does not match the audio")
    json.dump(segs, open(os.path.join(d, cc["words"]), "w"), indent=0)
    print(f"{len(segs)} segments -> {cc['words']} (score {score})")


def cmd_retime(a):
    sb, d = load(a.storyboard)
    words = words_for(sb, d)
    toks = [w["text"].lower().strip(".,:;!?\"'") for w in words]
    shots = sorted(sb["shots"], key=lambda s: s["start"])
    old = [s["start"] for s in shots]
    for s in shots:
        if not s.get("cue"):
            continue
        q = [x.lower().strip(".,:;!?\"'") for x in s["cue"].split()]
        hit = [i for i in range(len(toks) - len(q) + 1) if toks[i:i + len(q)] == q]
        if len(hit) != 1:
            sys.exit(f"cue {s['cue']!r} found {len(hit)} times in the transcript; make it unique")
        s["start"] = round(max(0.0, words[hit[0]]["start"] - a.lead), 3)
    shots[0]["start"] = 0.0
    if not sb.get("excerpt"):                                       # excerpt: keep the storyboard's own duration
        sb["duration"] = round(max(sb["duration"], words[-1]["end"] + a.tail), 3)
    for s, n in zip(shots, shots[1:] + [None]):
        s["end"] = n["start"] if n else sb["duration"]
        if s["end"] - s["start"] < 1.0:
            sys.exit(f"shot at {s['start']}s would last {s['end'] - s['start']:.2f}s; check the cues")
    remap = dict(zip([round(x, 3) for x in old], [s["start"] for s in shots]))
    for tr in sb.get("transitions", []):
        tr["at"] = remap.get(round(tr["at"], 3), tr["at"])
    out = os.path.splitext(a.storyboard)[0] + ".timed.json"
    json.dump(sb, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for s in shots:
        print(f"{s['start']:6.2f}-{s['end']:6.2f}  {s.get('cue', '')}")
    print(f"-> {out} (duration {sb['duration']}s)")


def caption_image(text, W, H, y, size):
    """Ivory text with a dark outline, centred on y, at most two lines (CLAUDE.md caption rule)."""
    U = W / 1080.0
    fnt = T.font("Bold", int(size * U))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lines = text.split("\n")[:2]
    lh = int(size * U * 1.22)
    y0 = y * H / 1920 - lh * (len(lines) - 1) / 2
    for i, ln in enumerate(lines):
        d.text((W / 2, y0 + i * lh), ln, font=fnt, fill=IVORY + (255,), anchor="mm", stroke_width=max(2, int(5 * U)),
               stroke_fill=OUTLINE + (255,))
    return np.asarray(im, np.float32) / 255


def cmd_finish(a):
    from mosaic.audio import build_mix
    sb, d = load(a.storyboard)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height,r_frame_rate,nb_frames", "-of", "json", a.picture],
                                      capture_output=True, check=True).stdout)["streams"][0]
    W, H = probe["width"], probe["height"]
    fps = eval(probe["r_frame_rate"])
    cc = sb["captions"]
    cues = cues_for(sb, d)
    for c in text_conflicts(sb, cues):
        print("WARNING:", c)
    imgs = [caption_image(c["text"], W, H, cc.get("y", 1410), cc.get("size", 60)) for c in cues]
    out_dir = os.path.dirname(os.path.abspath(a.picture))
    wav = os.path.join(out_dir, f"{sb['id']}_mix.wav")
    has_voice = build_mix(d, {"duration": sb["duration"], "audio": sb["audio"]}, wav)
    if not has_voice:
        sys.exit(f"narration file {sb['audio'].get('narration_file')} not found")
    out = a.out or os.path.join(out_dir, f"{sb['id']}_{W}x{H}_final.mp4")
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.picture, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", probe["r_frame_rate"],
                            "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    n, fb = 0, W * H * 3
    while True:
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        t = n / fps
        frame = None
        for c, im in zip(cues, imgs):
            if c["start"] <= t < c["end"]:
                a_ = min(1.0, (t - c["start"]) / 0.08, (c["end"] - t) / 0.08)
                frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32) / 255 if frame is None else frame
                al = im[..., 3:4] * a_
                frame = frame * (1 - al) + im[..., :3] * al
        enc.stdin.write(buf if frame is None else (frame * 255 + 0.5).astype(np.uint8).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    os.remove(wav)
    print(f"{out}: {n} frames, {len(cues)} captions, narration mixed with ducking")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check")
    t = sp.add_parser("tts")
    t.add_argument("--confirm", action="store_true")
    sp.add_parser("align")
    r = sp.add_parser("retime")
    r.add_argument("--lead", type=float, default=0.15)
    r.add_argument("--tail", type=float, default=1.2)
    f = sp.add_parser("finish")
    f.add_argument("picture")
    f.add_argument("--out")
    a = ap.parse_args()
    {"check": cmd_check, "tts": cmd_tts, "align": cmd_align, "retime": cmd_retime, "finish": cmd_finish}[a.cmd](a)


if __name__ == "__main__":
    main()

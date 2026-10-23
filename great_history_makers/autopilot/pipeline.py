#!/usr/bin/env python3
"""Daily-episode pipeline (everything after the narration exists). No paid calls happen here.

  python autopilot/pipeline.py check    episodes/<id>             # script length, credit estimate, files
  python autopilot/pipeline.py align    episodes/<id>             # forced alignment + silence cross-check
  python autopilot/pipeline.py timeline episodes/<id>             # shot starts from aligned words
  python autopilot/pipeline.py render   episodes/<id> [--final] [--out DIR]
  python autopilot/pipeline.py brand    episodes/<id> [--final] [--out DIR]
  python autopilot/pipeline.py verify   episodes/<id> [--final] [--out DIR]
  python autopilot/pipeline.py all      episodes/<id> [--final] [--out DIR]   # align..verify

Narration is produced BEFORE this script by Claude through the ElevenLabs connector (or
tools/tts_elevenlabs.py --confirm) and saved where episode.json audio.narration_file points.
Episode layout extras used here:
  NARRATION.txt           approved script, one spoken line per row
  episode.json "shots"    optional [{"id", "at_word"}]: the shot starts at that word (0-based index
                          into the transcript words); cuts land in the pause before the word.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from mosaic import captions  # noqa: E402

CREDITS_PER_CHAR = 1.0          # eleven_v4, measured on Ep02 (838 chars -> 838 credits)
WORDS_PER_SEC = 2.07            # Max voice incl. line pauses, measured on Ep02 (137 words / 66.0 s)


def cfg_of(ep):
    return json.load(open(os.path.join(ep, "episode.json"), encoding="utf-8"))


def save_cfg(ep, c):
    with open(os.path.join(ep, "episode.json"), "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1, ensure_ascii=False)


def rel(ep, p):
    return os.path.normpath(os.path.join(ep, p))


def script_lines(ep):
    return [ln.strip() for ln in open(os.path.join(ep, "NARRATION.txt"), encoding="utf-8") if ln.strip()]


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
       "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _two(n):
    return [ONES[n]] if n < 20 else [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])


def cardinal(n, use_and=False):
    out = []
    if n >= 1000:
        out += _two(n // 1000) + ["thousand"]
        n %= 1000
    if n >= 100:
        out += [ONES[n // 100], "hundred"]
        n %= 100
        if n and use_and:
            out.append("and")
    if n or not out:
        out += _two(n)
    return out


def number_candidates(tok):
    """Ways a narrator reads a number: 1812 -> eighteen twelve / one thousand eight hundred twelve ..."""
    n = int(tok.replace(",", ""))
    c = [cardinal(n), cardinal(n, True)]
    hi, lo = divmod(n, 100)
    if 1000 <= n <= 2099 or 100 <= n <= 999:
        head = _two(hi)
        c.append(head + (["hundred"] if lo == 0 else ["oh", ONES[lo]] if lo < 10 else _two(lo)))
    out = []
    for x in c:
        if x not in out:
            out.append(x)
    return out


def spoken_tokens(text, table):
    out = []
    for tok in text.split():
        core = re.sub(r"[^\w'-]", "", tok)
        out += table.get(core) or [t for t in captions.fold(core).lower().replace("'", "").split("-") if t]
    return out


def spoken(text, table=None):
    """Lower-case spoken form for PocketSphinx: numbers via the table, no punctuation or accents."""
    return " ".join(spoken_tokens(text, dict(captions.SPOKEN, **(table or {}))))


def check(ep, a):
    c = cfg_of(ep)
    lines = script_lines(ep)
    text = " ".join(lines)
    words = len(text.split())
    est = words / WORDS_PER_SEC
    res = dict(lines=len(lines), words=words, chars=len(text), est_seconds=round(est, 1),
               credits_one_take=round(len(text) * CREDITS_PER_CHAR),
               voice_id=c.get("tts", {}).get("voice_id"), model_id=c.get("tts", {}).get("model_id"),
               narration_present=os.path.exists(rel(ep, c.get("audio", {}).get("narration_file", "audio/narration.mp3"))))
    import align_narration as an
    vocab = set(line.split(" ", 1)[0] for line in open(os.path.join(
        __import__("pocketsphinx").get_model_path(), "en-us", "cmudict-en-us.dict"), encoding="utf-8"))
    vocab |= set(an.EXTRA_PRON) | set(c.get("captions", {}).get("pron", {}))
    nums = [t for t in re.findall(r"\b\d[\d,]*\b", text)]
    words = [w for w in spoken(re.sub(r"\b\d[\d,]*\b", " ", text), c.get("captions", {}).get("spoken")).split()]
    unknown = sorted(set(w for w in words if w not in vocab))
    res["numbers"] = nums
    res["words_missing_pronunciation"] = unknown
    res["ok"] = 50 <= est <= 63 and not unknown and bool(res["voice_id"])
    print(json.dumps(res, indent=1))
    return res


def silence_ends(audio, db=-38, dur=0.3):
    log = subprocess.run(["ffmpeg", "-i", audio, "-af", f"silencedetect=n={db}dB:d={dur}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]


def words_of(ep, c=None):
    c = c or cfg_of(ep)
    cc = c["captions"]
    tr = open(rel(ep, cc["transcript"]), encoding="utf-8").read().strip()
    return captions.map_words(tr, json.load(open(rel(ep, cc["words"]))), cc.get("spoken"))


def align(ep, a):
    c = cfg_of(ep)
    cc = c.setdefault("captions", {})
    cc.setdefault("transcript", "audio/transcript.txt")
    cc.setdefault("words", "audio/words_aligned.json")
    lines = script_lines(ep)
    tr = rel(ep, cc["transcript"])
    os.makedirs(os.path.dirname(tr), exist_ok=True)
    if not os.path.exists(tr):
        open(tr, "w", encoding="utf-8").write(" ".join(lines) + "\n")
    import align_narration as an
    narr = rel(ep, c["audio"]["narration_file"])
    aligner = an.Aligner(narr, cc.get("pron"))
    text = open(tr, encoding="utf-8").read().strip()
    table = dict(cc.get("spoken", {}))
    # pick, number by number, the spoken form that the audio actually contains
    for tok in dict.fromkeys(re.findall(r"\b\d+\b", text)):
        if tok in table:
            continue
        best = None
        for cand in number_candidates(tok):
            trial = dict(table, **{tok: cand})
            segs, score = aligner.run(spoken(text, trial))
            if segs is not None and (best is None or score > best[1]):
                best = (cand, score)
        if best is None:
            sys.exit(f"no spoken form of {tok!r} aligns; add it to captions.spoken in episode.json")
        table[tok] = best[0]
    cc["spoken"] = table
    al = os.path.join(os.path.dirname(rel(ep, cc["words"])), "transcript_align.txt")
    open(al, "w").write(spoken(text, table) + "\n")
    segs, _ = aligner.run(spoken(text, table))
    if segs is None:
        sys.exit("forced alignment failed: the audio does not match the approved script")
    json.dump(segs, open(rel(ep, cc["words"]), "w"), indent=0)
    save_cfg(ep, c)
    w = words_of(ep, c)
    starts, i = [], 0
    for ln in lines:
        starts.append(w[i]["start"])
        i += len(ln.split())
    sil = silence_ends(narr)
    errs = [min(abs(s - x) for x in sil) for s in starts[1:]] if sil else []
    rep = dict(words=len(w), narration_s=round(w[-1]["end"], 2), line_starts=starts,
               max_line_start_vs_silence_s=round(max(errs), 3) if errs else None)
    rep["ok"] = rep["max_line_start_vs_silence_s"] is not None and rep["max_line_start_vs_silence_s"] < 0.15
    if not cc.get("groups"):
        cc["groups"] = [g["text"].replace("\n", " / ") for g in captions.group(w)]
    save_cfg(ep, c)
    print(json.dumps(rep, indent=1))
    return rep


def timeline(ep, a, tail=2.3):
    """Shot starts from 'shots[].at_word'; the cut sits in the middle of the pause before that word."""
    c = cfg_of(ep)
    shots = c.get("shots")
    if not shots:
        print("no 'shots' in episode.json; keeping existing scene starts")
        return None
    w = words_of(ep, c)
    cuts = []
    for k, s in enumerate(shots):
        j = s["at_word"]
        if j == 0:
            cuts.append(0.0)
            continue
        gap0, gap1 = w[j - 1]["end"], w[j]["start"]
        cuts.append(round((gap0 + gap1) / 2 if gap1 - gap0 > 0.12 else max(gap1 - 0.06, 0.0), 3))
    dur = round(w[-1]["end"] + tail, 2)
    old = {s["id"]: s for s in c["scenes"]}
    scenes = []
    for k, s in enumerate(shots):
        end = cuts[k + 1] if k + 1 < len(cuts) else dur
        sc = dict(old.get(s["id"], {}), id=s["id"], start=cuts[k], duration=round(end - cuts[k], 3))
        scenes.append(sc)
    # transitions belong to cuts: move each one with the cut it sat on
    moved = {round(old[s["id"]]["start"], 3): s["start"] for s in scenes if s["id"] in old and "start" in old[s["id"]]}
    for tr in c.get("transitions", []):
        near = min(moved, key=lambda t0: abs(t0 - tr["at"]), default=None)
        if near is not None and abs(near - tr["at"]) <= 0.3:
            tr["at"] = moved[near]
    c["scenes"], c["duration"] = scenes, dur
    save_cfg(ep, c)
    print(json.dumps([(s["id"], s["start"], s["duration"]) for s in scenes]))
    return scenes


def paths(ep, a):
    name = os.path.basename(os.path.abspath(ep).rstrip("/"))
    out = a.out or os.path.join(ROOT, "output", name)
    q = "final" if a.final else "preview"
    w, h = (1080, 1920) if a.final else (720, 1280)
    return name, out, os.path.join(out, f"{name}_{q}_{w}x{h}.mp4"), os.path.join(out, f"{name}_{q}_{w}x{h}_branded.mp4")


def render(ep, a):
    name, out, master, _ = paths(ep, a)
    cmd = [sys.executable, os.path.join(ROOT, "produce.py"), ep, "--out", out]
    if a.final:
        cmd += ["--quality", "final", "--workers", "3"]
    subprocess.run(cmd, check=True)
    q = json.load(open(master[:-4] + "_qc.json"))
    if not q["passed"]:
        failed = [k for k, v in q["checks"].items() if not v]
        sys.exit(f"QC flagged {failed} (flicker at {q.get('flicker_spikes_s')}); inspect those frames before branding")
    return master


def brand(ep, a):
    name, out, master, branded = paths(ep, a)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "brand.py"), master, master, branded,
                    os.path.join(out, f"{name}_endcard.png")], check=True)
    return branded


def verify(ep, a):
    name, out, master, branded = paths(ep, a)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_delivery.py"), branded, ep,
                        "--report", os.path.join(out, f"{name}_verify.json")])
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["check", "align", "timeline", "render", "brand", "verify", "all"])
    ap.add_argument("episode")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    ep = os.path.abspath(a.episode)
    if a.stage == "all":
        if not align(ep, a)["ok"]:
            sys.exit("alignment cross-check failed; stop and review")
        timeline(ep, a)
        render(ep, a)
        brand(ep, a)
        sys.exit(0 if verify(ep, a) else 1)
    r = globals()[a.stage](ep, a)
    if a.stage == "verify" and not r:
        sys.exit(1)


if __name__ == "__main__":
    main()

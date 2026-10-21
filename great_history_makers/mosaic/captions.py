"""Build subtitle cues from forced-alignment word timestamps (never invented timing).

words_aligned.json comes from tools/align_narration.py (PocketSphinx forced alignment
of the verified transcript). Display words are mapped back onto the spoken tokens,
grouped into short phrases (max 2 lines, ~30 characters per line), and each cue
starts at its first word and ends at its last word (+ a short hold, never
overlapping the next cue)."""
import json
import re

SPOKEN = {"539": ["five", "thirty", "nine"], "BCE": ["b", "c", "e"], "twenty-five": ["twenty", "five"]}


def _norm(tok):
    return re.sub(r"\(\d+\)$", "", tok.lower())


def map_words(transcript, aligned):
    spoken = [w for w in aligned if w["word"] not in ("<sil>", "<s>", "</s>")]
    out, i = [], 0
    for disp in transcript.split():
        core = re.sub(r"[^\w'-]", "", disp)
        toks = SPOKEN.get(core) or [core.lower().replace("'", "")]
        n = len(toks)
        seg = spoken[i:i + n]
        got = [_norm(s["word"]) for s in seg]
        if got != toks:
            raise ValueError(f"alignment mismatch at {disp!r}: expected {toks}, got {got}")
        out.append(dict(text=disp, start=seg[0]["start"], end=seg[-1]["end"]))
        i += n
    return out


def group(words, max_line=30, max_gap=0.45, max_dur=3.4):
    cues, cur = [], []

    def flush():
        if cur:
            cues.append(cur[:])
            cur.clear()
    for k, w in enumerate(words):
        if cur:
            gap = w["start"] - cur[-1]["end"]
            text_len = len(" ".join(x["text"] for x in cur + [w]))
            if gap > max_gap or text_len > 2 * max_line or w["end"] - cur[0]["start"] > max_dur:
                flush()
        cur.append(w)
        if re.search(r"[.,;:]$", w["text"]) and len(" ".join(x["text"] for x in cur)) > 14:
            flush()
    flush()
    result = []
    for i, c in enumerate(cues):
        text = " ".join(x["text"] for x in c)
        lines = _wrap(text, max_line)
        start = c[0]["start"]
        end = c[-1]["end"] + 0.25
        if i + 1 < len(cues):
            end = min(end, cues[i + 1][0]["start"] - 0.02)
        result.append(dict(start=round(start, 3), end=round(end, 3), text="\n".join(lines)))
    return result


def _wrap(text, max_line):
    words = text.split()
    if len(text) <= max_line:
        return [text]
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        score = max(len(a), len(b))
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1]


def build(transcript_path, aligned_path):
    with open(transcript_path, encoding="utf-8") as f:
        transcript = f.read().strip()
    with open(aligned_path) as f:
        aligned = json.load(f)
    return group(map_words(transcript, aligned))


def build_groups(groups, transcript_path, aligned_path, hold=0.3):
    """Editorial phrase groups ("line one / line two"); timing comes only from the words."""
    with open(transcript_path, encoding="utf-8") as f:
        transcript = f.read().strip()
    with open(aligned_path) as f:
        words = map_words(transcript, json.load(f))
    cues, i = [], 0
    for g in groups:
        lines = [ln.strip() for ln in g.split("/")]
        n = sum(len(ln.split()) for ln in lines)
        chunk = words[i:i + n]
        if " ".join(w["text"] for w in chunk) != " ".join(" ".join(lines).split()):
            raise ValueError(f"group {g!r} does not match transcript words {[w['text'] for w in chunk]}")
        cues.append(dict(start=chunk[0]["start"], end=chunk[-1]["end"] + hold, text="\n".join(lines)))
        i += n
    if i != len(words):
        raise ValueError("caption groups do not cover the whole transcript")
    for a, b in zip(cues, cues[1:]):
        a["end"] = min(a["end"], b["start"] - 0.03)
    return [dict(start=round(c["start"], 3), end=round(c["end"], 3), text=c["text"]) for c in cues]

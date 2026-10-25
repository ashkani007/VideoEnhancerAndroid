"""Timeline building, 9:16 reframing, subtitles, audio mix and rendering."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from .tts import SR as TTS_SR, Voice, word_timings
from .util import Config, detect_video_encoder, run, write_json

AR = 48000
LEAD = 0.12          # picture cuts lead the narration slightly (J-cut feel)
VOICE_START = 0.10
GAP = 0.16           # default gap between sentences


# ------------------------------------------------------------------ voice + timeline


def build_voice(cfg: Config, story: dict) -> list[dict]:
    v = Voice(cfg, story.get("voice", {}).get("voice"), story.get("voice", {}).get("speed"))
    beat_speed = cfg.get("voice.beat_speed", {}) if story.get("pipeline", 1) >= 2 else {}
    t = VOICE_START
    lines = []
    for i, s in enumerate(story["sentences"]):
        speed = s.get("speed") or (v.speed * beat_speed.get(s["beat"], 1.0))
        path, audio = v.say(s["text"], speed)
        dur = len(audio) / TTS_SR
        words = [w | {"start": round(w["start"] + t, 3), "end": round(w["end"] + t, 3)}
                 for w in word_timings(s["text"], audio)]
        lines.append({"i": i, "beat": s["beat"], "text": s["text"], "wav": str(path),
                      "start": round(t, 3), "end": round(t + dur, 3), "words": words})
        t += dur + s.get("pause_after", GAP)
    return lines


def _clip_range(shot: dict, want: float, at: float | None) -> tuple[float, float]:
    """Pick [in, out) inside a shot; centred on the shot unless `at` is given."""
    s0, s1 = shot["start"] + 0.06, shot["end"] - 0.06
    if at is not None:
        a = max(s0, min(at, s1 - 0.2))
    else:
        a = max(s0, (s0 + s1) / 2 - want / 2)
    return a, min(s1, a + want)


def build_timeline(cfg: Config, story: dict, analysis: dict, lines: list[dict]) -> list[dict]:
    shots = {s["id"]: s for s in analysis["shots"]}
    min_shot, max_shot = cfg.get("edit.min_shot"), cfg.get("edit.max_shot")
    windows = []
    for k, (s, ln) in enumerate(zip(story["sentences"], lines)):
        w0 = 0.0 if k == 0 else ln["start"] - LEAD
        w1 = lines[k + 1]["start"] - LEAD if k + 1 < len(lines) else ln["end"] + 0.25
        windows.append((s["clips"], w0, w1, k))
    tail = story.get("tail")
    if tail:
        w0 = windows[-1][2]
        windows.append((tail["clips"], w0, w0 + tail["seconds"], None))

    timeline = []
    for clips, w0, w1, k in windows:
        span = w1 - w0
        # drop the weakest picks until every cut can hold min_shot, unless the
        # sentence is marked fast (action beats may cut quicker)
        fast = k is not None and story["sentences"][k].get("fast", False)
        floor = 0.45 if fast else min_shot
        def room_in(c):
            sh = shots[c["shot"]]
            return max(0.3, sh["end"] - 0.06 - c.get("at", sh["start"] + 0.06))

        clips = list(clips)
        while len(clips) > 1 and span / len(clips) < floor:
            j = min(range(len(clips)), key=lambda i: room_in(clips[i]))
            rest = clips[:j] + clips[j + 1:]
            if sum(room_in(c) for c in rest) < span:
                break  # dropping would force a clip past its cut; keep the quicker cut
            clips = rest
        n = len(clips)
        # equal split, then let short source shots give their slack to the others
        avail = [room_in(c) for c in clips]
        share = [span / n] * n
        for _ in range(3):
            over = sum(max(0, share[i] - avail[i]) for i in range(n))
            if over <= 1e-3:
                break
            room = [i for i in range(n) if share[i] < avail[i]]
            share = [min(share[i], avail[i]) for i in range(n)]
            if not room:
                # every source shot is too short: the longest one overruns (QC flags it)
                j = max(range(n), key=lambda i: avail[i])
                share[j] += over
                break
            for i in room:
                share[i] += over / len(room)
        t = w0
        for c, d in zip(clips, share):
            sh = shots[c["shot"]]
            a, b = _clip_range(sh, d, c.get("at"))
            # if the source shot is too short we hold the cut a little longer by
            # slowing nothing — just extend into the shot's tail; QC flags it
            if b - a < d - 0.02:
                b = a + d
            timeline.append({
                "t0": round(t, 3), "t1": round(t + d, 3), "dur": round(d, 3),
                "shot": sh["id"], "src_in": round(a, 3), "src_out": round(a + d, 3),
                "sentence": k, "overruns_shot": (a + d) > sh["end"] + 0.01,
                "frame": c.get("frame", "hybrid"),
            })
            t += d
    _attach_reframe(timeline, shots, analysis)
    return timeline


def _attach_reframe(timeline: list[dict], shots: dict, analysis: dict) -> None:
    for seg in timeline:
        sh = shots[seg["shot"]]
        tr = sh["saliency_track"] or [sh["saliency_x"]]
        step = max(sh["duration"] / len(tr), 1e-3)
        i0 = int((seg["src_in"] - sh["start"]) / step)
        i1 = int((seg["src_out"] - sh["start"]) / step)
        i0, i1 = max(0, min(i0, len(tr) - 1)), max(0, min(i1, len(tr) - 1))
        # blend tracked centre with whole-shot centre to keep motion calm
        x0 = 0.6 * tr[i0] + 0.4 * sh["saliency_x"]
        x1 = 0.6 * tr[i1] + 0.4 * sh["saliency_x"]
        # cap pan speed at 6% of frame width per second
        maxd = 0.06 * seg["dur"]
        x1 = x0 + max(-maxd, min(maxd, x1 - x0))
        seg["cx0"], seg["cx1"] = round(x0, 3), round(x1, 3)
        seg["push_in"] = sh["motion"] < 4.0
        seg["brightness"] = sh["brightness"]


# ------------------------------------------------------------------ render video


def _segment_filter(seg: dict, W: int, H: int, sw: int, sh: int, fg_aspect: float) -> str:
    d = seg["dur"]
    # background: cover-scaled, blurred, darkened
    bg = (f"[0:v]scale=-2:{H},crop={W}:{H},gblur=sigma={max(8, W // 24)},"
          f"eq=brightness=-0.10:saturation=0.75[bg]")
    if seg["frame"] == "tight":
        fg_aspect = W / H
    elif seg["frame"] == "wide":
        fg_aspect = sw / sh
    cw = min(sw, int(round(sh * fg_aspect / 2) * 2))
    span = sw - cw
    x_expr = f"max(0,min({span},({seg['cx0']}+({seg['cx1']}-{seg['cx0']})*t/{d:.3f})*{sw}-{cw}/2))"
    fgw = W
    fgh = int(round(W * sh / cw / 2) * 2)
    zoom = (f",scale=w='trunc({fgw}*(1+0.045*t/{d:.3f})/2)*2':h=-2:eval=frame,"
            f"crop={fgw}:{fgh}") if seg["push_in"] else ""
    # lift very dark shots so they survive phone screens and YouTube's encoder
    lift = ",eq=gamma=1.35:contrast=1.06" if seg.get("brightness", 99) < 35 else ""
    fg = (f"[0:v]crop={cw}:{sh}:x='{x_expr}':y=0,scale={fgw}:{fgh}:flags=lanczos{zoom},"
          f"unsharp=5:5:0.6{lift}[fg]")
    y = int(H * 0.40 - fgh / 2)
    return f"{bg};{fg};[bg][fg]overlay=0:{max(0, y)},setsar=1,format=yuv420p[v]"


def _framed_filter(seg: dict, plan: dict, W: int, H: int, max_up: float) -> str:
    """Pipeline-2 layout: shot-aware crop (never crops height), complete
    composition for wide shots, blurred same-shot background, no sharpening."""
    d = seg["dur"]
    sw, sh, cw, fh = plan["rend_w"], plan["rend_h"], plan["crop_w"], min(plan["fg_h"], H)
    bg = (f"[0:v]scale=-2:{H},crop={W}:{H},gblur=sigma={max(10, W // 18)},"
          f"eq=brightness=-0.16:saturation=0.65,vignette=PI/4.5[bg]")
    span = sw - cw
    x_expr = f"max(0,min({span},({plan['cx0']}+({plan['cx1']}-{plan['cx0']})*t/{d:.3f})*{sw}-{cw}/2))"
    push = seg.get("push_in") and plan["upscale"] * 1.03 <= max_up and plan["mode"] != "full-frame"
    zoom = (f",scale=w='trunc({W}*(1+0.03*t/{d:.3f})/2)*2':h=-2:eval=frame,crop={W}:{fh}"
            if push else "")
    lift = ",eq=gamma=1.22:contrast=1.04" if seg.get("brightness", 99) < 35 else ""
    fg = f"[0:v]crop={cw}:{sh}:x='{x_expr}':y=0,scale={W}:{fh}:flags=lanczos{zoom}{lift}[fg]"
    y = 0 if fh >= H - 2 else int(np.clip(H * 0.42 - fh / 2, H * 0.06, H - fh))
    plan["fg_y"] = y
    return f"{bg};{fg};[bg][fg]overlay=0:{y},setsar=1,format=yuv420p[v]"


def render_video(cfg: Config, src: Path, analysis: dict, timeline: list[dict], out: Path,
                 profile: str, story: dict | None = None) -> dict:
    W, H = cfg.get(f"render.{profile}.width"), cfg.get(f"render.{profile}.height")
    fps = cfg.get(f"render.{profile}.fps")
    enc = detect_video_encoder()
    seg_dir = out.parent / f"segments_{profile}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    sw, sh = analysis["width"], analysis["height"]
    v2 = (story or {}).get("pipeline", 1) >= 2
    if v2:
        from .framing import Detector, plan_clip
        from .renditions import choose
        det = Detector(cfg)
        max_up = cfg.get(f"render.{profile}.max_upscale", 2.2)
    listing = []
    for i, seg in enumerate(timeline):
        p = seg_dir / f"seg_{i:03d}.mp4"
        nframes = max(1, round(seg["t1"] * fps) - round(seg["t0"] * fps))
        if v2:
            rend = choose(cfg, src, analysis, seg["src_in"], seg["src_out"])
            plan = plan_clip(cfg, det, rend, seg["src_in"], seg["src_out"], W, H, max_up,
                             seg.get("frame") if seg.get("frame") in ("wide", "tight") else None)
            flt = _framed_filter(seg, plan, W, H, max_up)
            seg["framing"] = {k: v for k, v in plan.items() if k != "frames"} | {"detections": plan["frames"]}
            inp, ss = plan["rendition"], seg["src_in"] - plan["offset"]
        else:
            flt = _segment_filter(seg, W, H, sw, sh, fg_aspect=1.0)
            inp, ss = str(src), seg["src_in"]
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-i", inp,
             "-filter_complex", flt, "-map", "[v]", "-r", str(fps), "-frames:v", str(nframes),
             "-an", *enc["args"](12), str(p)])
        listing.append(f"file '{p.name}'")
    (seg_dir / "list.txt").write_text("\n".join(listing) + "\n")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(seg_dir / "list.txt"),
         "-c", "copy", str(out)])
    return {"encoder": enc["name"], "gpu": enc["gpu"], "width": W, "height": H, "fps": fps}


# ------------------------------------------------------------------ subtitles


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk_words(words: list[dict], max_words: int = 3, max_chars: int = 18) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        cand = cur + [w]
        if cur and (len(cand) > max_words or len(" ".join(x["word"] for x in cand)) > max_chars):
            chunks.append(cur)
            cand = [w]
        cur = cand
        if re.search(r"[.,!?;:]$", w["word"]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def write_ass(lines: list[dict], out: Path, W: int, H: int, credit: str, total: float,
              safe: bool = False) -> int:
    # safe=True: smaller type, kept clear of the Shorts UI (right-hand buttons,
    # bottom title/description band) — centred at 47% x / 70% y
    fs = round(H * (0.041 if safe else 0.047))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter ExtraBold,{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{max(2, round(fs * 0.11))},{max(1, round(fs * 0.05))},5,20,20,0,1
Style: Credit,Inter,{round(H * 0.016)},&H50FFFFFF,&H50FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,10,10,{round(H * 0.025)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    cx, cy = (round(W * 0.47), round(H * 0.70)) if safe else (W // 2, round(H * 0.73))
    all_words = [w for ln in lines for w in ln["words"]]
    chunks = [c for ln in lines for c in chunk_words(ln["words"], max_chars=15 if safe else 18)]
    n_words = 0
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else ch[-1]["end"] + 0.5
        end = min(nxt, ch[-1]["end"] + 0.35)
        for wi, w in enumerate(ch):
            w_end = ch[wi + 1]["start"] if wi + 1 < len(ch) else end
            parts = []
            for wj, x in enumerate(ch):
                word = x["word"].upper().replace("{", "").replace("}", "")
                parts.append(r"{\c&H00D7FF&}" + word + r"{\c&HFFFFFF&}" if wj == wi else word)
            pop = r"{\fscx78\fscy78\t(0,90,\fscx100\fscy100)}" if wi == 0 else ""
            ev.append(f"Dialogue: 1,{_ass_time(w['start'])},{_ass_time(w_end)},Cap,,0,0,0,,"
                      + r"{\pos(" + f"{cx},{cy}" + ")}" + pop + " ".join(parts))
            n_words += 1
    ev.append(f"Dialogue: 0,{_ass_time(0)},{_ass_time(total)},Credit,,0,0,0,,{credit}")
    out.write_text(head + "\n".join(ev) + "\n")
    assert n_words == len(all_words)
    return n_words


# ------------------------------------------------------------------ audio


def _decode(path: Path, ss: float | None = None, t: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(path)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-ac", "2", "-ar", str(AR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def _sfx(kind: str) -> np.ndarray:
    """Self-synthesised effects: no third-party licensing involved."""
    rng = np.random.default_rng(7)
    if kind == "hit":
        n = int(1.6 * AR)
        t = np.arange(n) / AR
        f = 38 + 50 * np.exp(-t * 9)
        body = np.sin(2 * np.pi * np.cumsum(f) / AR) * np.exp(-t * 3.2)
        noise = rng.standard_normal(n) * np.exp(-t * 28) * 0.25
        x = 0.8 * body + noise
    else:  # whoosh
        n = int(0.9 * AR)
        t = np.arange(n) / AR
        env = np.sin(np.pi * t / t[-1]) ** 2
        noise = rng.standard_normal(n)
        k = np.exp(-np.arange(300) / 60)
        x = np.convolve(noise, k / k.sum(), mode="same") * env * 1.4
    x = x / (np.abs(x).max() + 1e-9) * 0.5
    return np.stack([x, x], axis=1).astype(np.float32)


def music_cues(story: dict, lines: list[dict], total: float) -> tuple[list[dict], list[float]]:
    """One cue per run of equal moods; each change lands just before the line
    that motivates it. Lines marked sfx=hit get a low braam on their first word."""
    cues = []
    for s, ln in zip(story["sentences"], lines):
        m = s.get("mood", "tension")
        start = 0.0 if not cues else round(ln["start"] - 0.25, 3)
        if cues and cues[-1]["mood"] == m:
            continue
        if cues:
            cues[-1]["end"] = start
        cues.append({"mood": m, "start": start, "end": total, "line": ln["text"]})
    hits = [round(ln["start"], 3) for s, ln in zip(story["sentences"], lines) if s.get("sfx") == "hit"]
    return cues, hits


def _duck_env(voice: np.ndarray, n: int, attack: float = 0.06, release: float = 0.45) -> np.ndarray:
    hop = 480
    lvl = np.abs(voice[:, 0])
    env = np.array([lvl[i:i + hop].max() for i in range(0, n, hop)]) > 0.02
    sm = np.zeros(len(env))
    a, r = 1 - np.exp(-hop / AR / attack), 1 - np.exp(-hop / AR / release)
    for i in range(1, len(env)):
        sm[i] = sm[i - 1] + (a if env[i] > sm[i - 1] else r) * (env[i] - sm[i - 1])
    return np.repeat(sm, hop)[:n]


def mix_score(cfg: Config, timeline: list[dict], lines: list[dict], story: dict,
              total: float, out: Path) -> dict:
    from .music import SR as MSR, compose

    assert MSR == AR
    n = int(total * AR)
    voice = np.zeros((n, 2), np.float32)
    for ln in lines:
        v = _decode(Path(ln["wav"]))
        s0 = int(ln["start"] * AR)
        v = v[: max(0, min(len(v), n - s0))]
        voice[s0:s0 + len(v)] += v
    speech = voice[np.abs(voice[:, 0]) > 0.01]
    v_rms_db = 20 * np.log10(np.sqrt((speech ** 2).mean()) + 1e-9)

    cues, hits = music_cues(story, lines, total)
    score = compose(cues, total, hits)[:n]
    score = np.pad(score, ((0, n - len(score)), (0, 0)))
    s_act = score[np.abs(score).max(1) > 1e-4]
    s_rms_db = 20 * np.log10(np.sqrt((s_act ** 2).mean()) + 1e-9)
    gap_db, under_db = cfg.get("music.gap_db", -7), cfg.get("music.under_voice_db", -17)
    duck = _duck_env(voice, n)
    gain_db = (v_rms_db - s_rms_db) + gap_db + (under_db - gap_db) * duck
    mix = voice + score * (10 ** (gain_db / 20))[:, None]

    fx_cues = []
    for s, ln in zip(story["sentences"], lines):
        if s.get("sfx") == "whoosh":
            fx = _sfx("whoosh")
            at = ln["start"] - 0.45
            s0 = max(0, int(at * AR))
            fx = fx[: max(0, min(len(fx), n - s0))]
            mix[s0:s0 + len(fx)] += fx * 10 ** (-16 / 20)
            fx_cues.append({"kind": "whoosh", "t": round(at, 2)})
    fo = int(1.2 * AR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    raw = out.with_suffix(".raw.wav")
    sf.write(raw, mix, AR, subtype="FLOAT")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
         "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(AR), str(out)])
    raw.unlink()
    stem = out.with_name(out.stem + "_music.wav")
    sf.write(stem, score * 0.9, AR)
    return {"mode": "score", "cues": cues, "hits": hits, "sfx": fx_cues + [{"kind": "braam", "t": h} for h in hits],
            "gap_db": gap_db, "under_voice_db": under_db, "music_stem": str(stem),
            "bed_db": None, "duck_db": under_db - gap_db}


def mix_audio(cfg: Config, src: Path, timeline: list[dict], lines: list[dict], story: dict,
              total: float, out: Path) -> dict:
    if story.get("pipeline", 1) >= 2:
        return mix_score(cfg, timeline, lines, story, total, out)
    n = int(total * AR)
    bed = np.zeros((n, 2), np.float32)
    fade = int(0.015 * AR)
    for seg in timeline:
        a = _decode(src, seg["src_in"], seg["dur"])
        s0 = int(seg["t0"] * AR)
        a = a[: max(0, min(len(a), n - s0))]
        if len(a) > 2 * fade:
            ramp = np.linspace(0, 1, fade)[:, None]
            a[:fade] *= ramp
            a[-fade:] *= ramp[::-1]
        bed[s0:s0 + len(a)] += a

    voice = np.zeros((n, 2), np.float32)
    for ln in lines:
        v = _decode(Path(ln["wav"]))
        s0 = int(ln["start"] * AR)
        v = v[: max(0, min(len(v), n - s0))]
        voice[s0:s0 + len(v)] += v

    # ducking envelope from the voice (attack 40 ms, release 300 ms)
    lvl = np.abs(voice[:, 0])
    hop = 480
    env = np.array([lvl[i:i + hop].max() for i in range(0, n, hop)])
    env = (env > 0.02).astype(float)
    sm = np.zeros_like(env)
    for i in range(1, len(env)):
        coef = 0.6 if env[i] > sm[i - 1] else 0.033
        sm[i] = sm[i - 1] + coef * (env[i] - sm[i - 1])
    duck = np.repeat(sm, hop)[:n]
    base_db, duck_db = cfg.get("edit.source_audio_db"), cfg.get("edit.duck_db")
    gain = 10 ** ((base_db + duck_db * duck) / 20)
    # let the source breathe louder in the tail after the last line
    last = lines[-1]["end"]
    tail_mask = np.arange(n) / AR > last + 0.3
    gain[tail_mask] = np.maximum(gain[tail_mask], 10 ** ((base_db + 6) / 20))
    mix = voice * 1.0 + bed * gain[:, None]

    cues = []
    for s, ln in zip(story["sentences"], lines):
        if kind := s.get("sfx"):
            fx = _sfx(kind)
            at = ln["start"] - (0.05 if kind == "hit" else 0.45)
            s0 = max(0, int(at * AR))
            fx = fx[: max(0, min(len(fx), n - s0))]
            mix[s0:s0 + len(fx)] += fx * 10 ** (-14 / 20)
            cues.append({"kind": kind, "t": round(at, 2)})
    # fade the very end
    fo = int(0.6 * AR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    raw = out.with_suffix(".raw.wav")
    sf.write(raw, mix, AR, subtype="FLOAT")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
         "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(AR), str(out)])
    raw.unlink()
    return {"sfx": cues, "bed_db": base_db, "duck_db": duck_db}


def mux(cfg: Config, video: Path, audio: Path, ass: Path, out: Path, profile: str) -> None:
    enc = detect_video_encoder()
    crf = cfg.get(f"render.{profile}.crf")
    fonts = "/usr/share/fonts"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
         "-vf", f"ass={ass}:fontsdir={fonts}", *enc["args"](crf), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(out)])

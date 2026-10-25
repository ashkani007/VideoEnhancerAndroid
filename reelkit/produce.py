"""Production orchestration: story spec -> voice -> timeline -> preview,
plus the approval gate in front of the final 1440x2560 render."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .analyze import analyze_source
from .edit import build_timeline, build_voice, mux, mix_audio, render_video, write_ass
from .qc import run_qc
from .util import Config, media_duration, read_json, sha256_file, write_json

REPO_PRODUCTIONS = Path(__file__).resolve().parent.parent / "productions"


def _paths(cfg: Config, slug: str) -> tuple[Path, Path]:
    spec_dir = REPO_PRODUCTIONS / slug           # small text deliverables, versioned
    work = cfg.productions_dir / slug            # media, not versioned
    work.mkdir(parents=True, exist_ok=True)
    return spec_dir, work


def _fmt(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def produce(cfg: Config, slug: str, profile: str = "preview", master: Path | None = None) -> dict:
    spec_dir, work = _paths(cfg, slug)
    story = read_json(spec_dir / "story.json")
    src = master or (cfg.workspace / story["source"]["file"])
    analysis = analyze_source(cfg, src)
    if master is not None:
        ref = read_json(spec_dir / "timeline.json")
        if abs(analysis["duration"] - ref["source_duration"]) > 1.0:
            raise SystemExit("master duration differs from the analysed cut; re-plan instead")

    lines = build_voice(cfg, story)
    if master is not None:
        timeline = ref["timeline"]
    else:
        timeline = build_timeline(cfg, story, read_json(Path(analysis["keyframes_dir"]).parent / "shots.json"),
                                  lines)
    total = timeline[-1]["t1"]

    video = work / f"video_{profile}.mp4"
    audio = work / f"mix_{profile}.wav"
    ass = work / f"captions_{profile}.ass"
    out = work / f"{slug}_{profile}.mp4"
    info = render_video(cfg, src, analysis, timeline, video, profile, story)
    sfx = mix_audio(cfg, src, timeline, lines, story, total, audio)
    credit = story["source"].get("credit_short") or story["source"]["credit"]
    v2 = story.get("pipeline", 1) >= 2
    write_ass(lines, ass, info["width"], info["height"], credit, total, safe=v2)
    mux(cfg, video, audio, ass, out, profile)

    qc = run_qc(out, story, lines, timeline, analysis, info, profile,
                cfg.get("discovery.min_source_height_final"), audio_info=sfx,
                max_upscale=cfg.get(f"render.{profile}.max_upscale", 2.2))
    write_json(spec_dir / "timeline.json", {
        "source_duration": analysis["duration"], "total": total, "render": info,
        "audio": sfx, "lines": lines, "timeline": timeline})
    write_json(spec_dir / f"qc_{profile}.json", qc)
    if v2:
        _write_docs_v2(cfg, spec_dir, story, lines, timeline, analysis, qc, sfx, profile)
    else:
        _write_docs(spec_dir, story, lines, timeline, analysis, qc, sfx, profile, out)
    return {"output": str(out), "qc": qc, "render": info}


# ------------------------------------------------------------------ approval gate


def approve(cfg: Config, slug: str, note: str = "") -> dict:
    spec_dir, work = _paths(cfg, slug)
    prev = work / f"{slug}_preview.mp4"
    if not prev.exists():
        raise SystemExit("no preview rendered yet")
    rec = {"approved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "preview_sha256": sha256_file(prev), "note": note}
    write_json(spec_dir / "approval.json", rec)
    return rec


def render_final(cfg: Config, slug: str, master: Path | None = None) -> dict:
    spec_dir, work = _paths(cfg, slug)
    ap = spec_dir / "approval.json"
    if not ap.exists():
        raise SystemExit("final render blocked: preview not approved (run `reelkit approve`)")
    prev = work / f"{slug}_preview.mp4"
    if read_json(ap)["preview_sha256"] != sha256_file(prev):
        raise SystemExit("final render blocked: preview changed since approval")
    story = read_json(spec_dir / "story.json")
    src = master or (cfg.workspace / story["source"]["file"])
    need = cfg.get("discovery.min_source_height_final")
    if story.get("pipeline", 1) >= 2:
        # every clip must come from an HD copy (registered renditions count);
        # 1920-wide scope films (e.g. 1920x818) qualify as 1080p
        from .renditions import choose
        analysis = analyze_source(cfg, src)
        low = [seg["shot"] for seg in read_json(spec_dir / "timeline.json")["timeline"]
               if (r := choose(cfg, src, analysis, seg["src_in"], seg["src_out"]))["width"] < 1920
               and r["height"] < need]
        if low:
            raise SystemExit(f"final render blocked: {len(low)} clips have no HD copy "
                             f"(register one with `reelkit register-rendition`)")
        return produce(cfg, slug, "final")
    h = analyze_source(cfg, src)["height"]
    if h < need:
        raise SystemExit(f"final render blocked: source is {h}p, need >= {need}p master (--master)")
    return produce(cfg, slug, "final", master=master)


# ------------------------------------------------------------------ deliverables


def _write_docs(spec_dir, story, lines, timeline, analysis, qc, sfx, profile, out) -> None:
    beats = {}
    for ln in lines:
        beats.setdefault(ln["beat"], []).append(ln)
    s = [f"# {story['title']}\n", f"Narration for *{story['source']['title']}* — voice: Kokoro `{story['voice']['voice']}` (local TTS).\n"]
    for b in story["beats"]:
        ls = beats.get(b["name"], [])
        if not ls:
            continue
        s.append(f"\n## {b['name'].title()} — target {b['target'][0]}–{b['target'][1]} s, actual {ls[0]['start']:.1f}–{ls[-1]['end']:.1f} s\n")
        for ln in ls:
            s.append(f"- `{_fmt(ln['start'])}` {ln['text']}")
    words = sum(len(ln["text"].split()) for ln in lines)
    s.append(f"\n\n{words} words.\n")
    (spec_dir / "script.md").write_text("\n".join(s))

    src = story["source"]
    (spec_dir / "sources.md").write_text(f"""# Sources and licences

| Asset | Source | Licence | Notes |
|---|---|---|---|
| Footage + original soundtrack/SFX bed | [{src['title']}]({src['official_url']}) — file fetched from {src['fetched_from']} (sha256 `{src['sha256'][:16]}…`) | [{src['license']}]({src['license_url']}) | {analysis['width']}x{analysis['height']}, {analysis['duration']:.0f} s. Attribution required: "{src['credit']}". Shown on screen and must be in the video description. Blender/Sintel logos are excluded from the licence and are not used. |
| Narration voice | Kokoro-82M via kokoro-onnx (local) | Apache-2.0 (model weights) | Generated locally, no per-use cost. |
| Sound effects ({', '.join(c['kind'] for c in sfx['sfx'])}) | Synthesised by ReelKit (numpy) | Own work | No third-party samples. |
| Music | Original film score inside the {src['title']} soundtrack bed | {src['license']} | No separate music track added. |
| Caption font | Inter | SIL OFL 1.1 | |

Suggested description credit:

> Footage: "{src['title']}" {src['credit']} — licensed under {src['license']} ({src['license_url']}). Edited, reframed and narrated; not endorsed by the Blender Foundation.
""")

    rows = ["| # | Time | Dur | Source shot | Source in–out | Reframe | Narration |", "|---|---|---|---|---|---|---|"]
    for i, seg in enumerate(timeline):
        text = lines[seg["sentence"]]["text"] if seg["sentence"] is not None else "(tail — no narration)"
        rf = f"pan {seg['cx0']:.2f}→{seg['cx1']:.2f}" + (" + push-in" if seg["push_in"] else "")
        rows.append(f"| {i+1} | {_fmt(seg['t0'])}–{_fmt(seg['t1'])} | {seg['dur']:.2f} | #{seg['shot']} | "
                    f"{_fmt(seg['src_in'])}–{_fmt(seg['src_out'])} | {rf} | {text} |")
    cues = ", ".join(f"{c['kind']} @ {c['t']:.2f}s" for c in sfx["sfx"])
    (spec_dir / "timeline.md").write_text(
        "# Shot-by-shot timeline\n\nLayout: 9:16 hybrid — square crop of the widescreen frame, "
        "positioned by per-shot saliency tracking, over a blurred fill of the same shot; captions in the lower third.\n\n"
        + "\n".join(rows) + f"\n\nSFX cues: {cues}. Source audio bed {sfx['bed_db']} dB, ducked a further {sfx['duck_db']} dB under narration; master loudness-normalised to -14 LUFS.\n")

    q = [f"# QC report ({profile})\n", f"Overall: **{qc['status'].upper()}** — {qc['duration']:.2f} s, encoder `{qc['encoder']}`.\n",
         "| Check | Status | Detail |", "|---|---|---|"]
    q += [f"| {c['check']} | {c['status']} | {c['detail']} |" for c in qc["checks"]]
    (spec_dir / f"qc_{profile}.md").write_text("\n".join(q) + "\n")


def _write_docs_v2(cfg, spec_dir, story, lines, timeline, analysis, qc, audio, profile) -> None:
    voice = story.get("voice", {}).get("voice") or cfg.get("voice.voice")
    moods = {ln["text"]: s.get("mood", "") for s, ln in zip(story["sentences"], lines)}
    beats = {}
    for ln in lines:
        beats.setdefault(ln["beat"], []).append(ln)
    s = [f"# {story['title']}\n",
         f"Narration for *{story['source']['title']}* — narrator: Kokoro `{voice}` (local, free), "
         f"per-beat pacing {cfg.get('voice.beat_speed')}.\n"]
    for b in story["beats"]:
        ls = beats.get(b["name"], [])
        if ls:
            s.append(f"\n## {b['name'].title()} — target {b['target'][0]}–{b['target'][1]} s, "
                     f"actual {ls[0]['start']:.1f}–{ls[-1]['end']:.1f} s\n")
            s += [f"- `{_fmt(ln['start'])}` {ln['text']}  _(music: {moods[ln['text']]})_" for ln in ls]
    s.append(f"\n\n{sum(len(ln['text'].split()) for ln in lines)} words.\n")
    (spec_dir / "script.md").write_text("\n".join(s))

    src = story["source"]
    rend_rows = []
    used = sorted({seg["framing"]["rendition"] for seg in timeline})
    for r in used:
        n = sum(seg["framing"]["rendition"] == r for seg in timeline)
        w = next(seg["framing"]["rend_w"] for seg in timeline if seg["framing"]["rendition"] == r)
        h = next(seg["framing"]["rend_h"] for seg in timeline if seg["framing"]["rendition"] == r)
        rend_rows.append(f"| `{Path(r).name}` | {w}x{h} | {n} clips |")
    (spec_dir / "sources.md").write_text(f"""# Sources and licences

| Asset | Source | Licence | Notes |
|---|---|---|---|
| Footage | [{src['title']}]({src['official_url']}) | [{src['license']}]({src['license_url']}) | Attribution: "{src['credit']}" (on screen + description). Logos excluded from licence, not used. |
| Narration | Kokoro-82M `{voice}` via kokoro-onnx, run locally | Apache-2.0 | No per-use cost. |
| Music | Original score composed by ReelKit `music.py` for this edit | Own work | Cue sheet in timeline.md. No third-party music. |
| SFX (braam hits, whoosh) | Synthesised by ReelKit | Own work | |
| Face detector | YuNet, OpenCV Zoo | MIT | analysis only |
| Object detector | YOLOX-S, OpenCV Zoo | Apache-2.0 | analysis only |
| Caption font | Inter | SIL OFL 1.1 | |

## Footage copies used (best available per clip)

| File | Resolution | Used for |
|---|---|---|
{chr(10).join(rend_rows)}

Copies: master `sintel.mp4` from {src['fetched_from']}; 720-wide excerpt from
https://raw.githubusercontent.com/iandevlin/iandevlin.github.io/master/mdn/video-player-with-captions/video/sintel-short.mp4
(film 01:28–03:28, auto-aligned to master time). Both are redistributions of the CC BY 3.0 film.
No 1080p+ copy is reachable from this network (blender.org, archive.org, wikimedia blocked).

Suggested description credit:

> Footage: "{src['title']}" {src['credit']} — licensed under {src['license']} ({src['license_url']}). Edited, reframed and narrated; music is original. Not endorsed by the Blender Foundation.
""")

    rows = ["| # | Time | Source | Copy | Framing | Crop | Upscale | Subject kept | Narration |",
            "|---|---|---|---|---|---|---|---|---|"]
    for i, seg in enumerate(timeline):
        fr = seg["framing"]
        text = lines[seg["sentence"]]["text"] if seg["sentence"] is not None else "(tail)"
        by = "+".join(sorted({d["by"] for d in fr["detections"]}))
        rows.append(f"| {i+1} | {_fmt(seg['t0'])}–{_fmt(seg['t1'])} | #{seg['shot']} {_fmt(seg['src_in'])} | "
                    f"{fr['rend_w']}w | {fr['mode']} ({by}) | {fr['crop_w']}px | ×{fr['upscale']} | "
                    f"{fr['subject_coverage']:.0%} | {text} |")
    cue_rows = ["| Cue | Start | End | Mood | Motivated by |", "|---|---|---|---|---|"]
    for i, c in enumerate(audio["cues"]):
        cue_rows.append(f"| {i+1} | {c['start']:.2f} | {c['end']:.2f} | {c['mood']} | \"{c['line']}\" |")
    (spec_dir / "timeline.md").write_text(
        "# Shot-by-shot timeline (v2)\n\nFraming: per clip, faces (YuNet), characters/animals (YOLOX) and "
        "saliency are detected on the real frames; the crop is the narrowest window that keeps every "
        "subject (+12% margin), but never narrower than the 9:16 width or the upscale limit, and the full "
        "frame when the action spans the shot. Height is never cropped. Background: the same shot, blurred and darkened.\n\n"
        + "\n".join(rows)
        + "\n\n## Music cue sheet\n\n" + "\n".join(cue_rows)
        + f"\n\nBraam hits at {', '.join(f'{h:.2f}s' for h in audio['hits'])}. Score sits "
          f"{audio['gap_db']} dB under the narration level between lines and {audio['under_voice_db']} dB "
          "under it while the narrator speaks (60 ms attack / 450 ms release); master -14 LUFS.\n")

    q = [f"# QC report ({profile}, v2)\n",
         f"Overall: **{qc['status'].upper()}** — {qc['duration']:.2f} s, encoder `{qc['encoder']}`.\n",
         "| Check | Status | Detail |", "|---|---|---|"]
    q += [f"| {c['check']} | {c['status']} | {c['detail']} |" for c in qc["checks"]]
    (spec_dir / f"qc_{profile}.md").write_text("\n".join(q) + "\n")

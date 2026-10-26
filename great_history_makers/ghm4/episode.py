#!/usr/bin/env python3
"""Automated v4 episode pipeline: one episode spec -> illustrations (local ComfyUI) -> plates -> storyboard -> video.

  python -m ghm4.episode run <episode_dir>                 # do every step that is possible now, then say what is next
  python -m ghm4.episode jobs <episode_dir>                # queue the illustration job (picked up by the PC worker)
  python -m ghm4.episode status <episode_dir>
  python -m ghm4.episode pick <episode_dir> [--auto | beat=file ...] [--no-upscale]
  python -m ghm4.episode plates <episode_dir>              # plates + automatic metadata + mattes + review sheets
  python -m ghm4.episode sheet <episode_dir> <beat>        # grid overlay for annotating eyes / hands (annotations.json)
  python -m ghm4.episode storyboard <episode_dir>          # storyboard.json (+ timed to the narration)
  python -m ghm4.episode render <episode_dir> [--final]    # picture, narration + captions, verification, visual QC

episode.json
{
  "id": "napoleon_3scene_test", "style": "ghm_cinematic_v1", "workflow": "sdxl_style_face",
  "narration": {"audio": "...", "transcript": "...", "words": "...", "groups": [...], "excerpt_end": 18.2},   optional
  "duration": 18.2,                                            used when there is no narration
  "beats": [
    {"id": "b1_portrait", "type": "portrait|hero_wide|battle|landscape|map", "cue": "exact narration words",
     "duration": 5.0,                                          (no narration)
     "illustration": {"characters": ["napoleon"], "framing": "...", "scene": "...", "lighting": "...", "seeds": [..]},
     "map": "ghm4/data/maps/x.json",                           (type map)
     "matte_hint": {...}, "motion": {"blink_at": 0.45, "sway_at": 0.2}, "text": [ghm4.text items], "puffs": 2}
  ]
}
annotations.json (optional, written after looking at the plates): {"<beat>": {"eyes": [...], "sway": [...], "face": [x, y]}}
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

from . import illustrate, masks, presets

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


class Episode:
    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.spec = load(os.path.join(self.dir, "episode.json"))
        self.state_path = os.path.join(self.dir, "state.json")
        self.state = load(self.state_path, {})
        self.id = self.spec["id"]

    def save_state(self):
        save(self.state_path, self.state)

    def rel(self, ghm_path):
        """GHM-root-relative path -> path relative to the episode folder (for the storyboard)."""
        return os.path.relpath(os.path.join(GHM, ghm_path), self.dir).replace(os.sep, "/")

    def illustrated(self):
        return [b for b in self.spec["beats"] if b.get("illustration")]

    def results(self, job_id):
        return load(os.path.join(GHM, "jobs", "results", job_id, "manifest.json"))


# ------------------------------------------------------------------------------------------- 1. jobs
def next_id(base):
    n = 1
    while os.path.exists(os.path.join(GHM, "jobs", "queue", f"{base}_v{n}.json")) or \
            os.path.exists(os.path.join(GHM, "jobs", "results", f"{base}_v{n}")):
        n += 1
    return f"{base}_v{n}"


def cmd_jobs(ep, a=None):
    if ep.state.get("illustrate_job") and not getattr(a, "force", False):
        print(f"illustration job already queued: {ep.state['illustrate_job']} (use --force for a new version)")
        return
    jid = next_id(ep.id)
    shots = []
    for i, b in enumerate(ep.illustrated()):
        il = b["illustration"]
        shots.append(dict({k: v for k, v in il.items() if k != "seeds"}, id=b["id"], seeds=il.get("seeds", [1000 * (i + 1) + s for s in range(4)])))
    spec = {"job_id": jid, "created": "", "notes": f"illustrations for episode {ep.id}", "style": ep.spec.get("style", "ghm_cinematic_v1"),
            "workflow": ep.spec.get("workflow", "sdxl_style_face"), "shots": shots}
    save(os.path.join(GHM, "jobs", "specs", jid + ".json"), spec)
    job = illustrate.make_job(spec)
    sys.path.insert(0, os.path.join(GHM, "comfyui", "worker"))
    import ghm_worker
    ghm_worker.validate(job, GHM)
    save(os.path.join(GHM, "jobs", "queue", jid + ".json"), job)
    ep.state["illustrate_job"] = jid
    ep.save_state()
    n = sum(len(s["seeds"]) for s in job["shots"])
    print(f"queued jobs/queue/{jid}.json: {len(job['shots'])} illustrations x seeds = {n} images "
          f"(workflow {job['workflow']}). Commit + push, then run run_worker.bat on the PC.")


# ------------------------------------------------------------------------------------------- 2. pick
def score(path):
    """Cheap technical ranking (sharpness, exposure, contrast). Taste stays with the reviewer."""
    im = cv2.imread(path)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    sharp = float(cv2.Laplacian(g, cv2.CV_32F).var()) ** 0.5
    expo = 1 - min(1.0, abs(float(g.mean()) - 0.45) / 0.35)
    contrast = float(g.std())
    return round(4 * sharp + expo + 2 * contrast, 4)


def cmd_status(ep, a=None):
    for key in ("illustrate_job", "upscale_job"):
        jid = ep.state.get(key)
        if not jid:
            print(f"{key}: not queued")
            continue
        m = ep.results(jid)
        print(f"{key} {jid}: " + ("waiting for the PC worker" if not m else
              f"{m['status']}, {len(m['images'])} images, GPU {m.get('system', {}).get('gpu')} "
              f"{m.get('system', {}).get('vram_total_gb')} GB, {sum(i['seconds'] for i in m['images']):.0f} s total"
              + (f", errors {m['errors']}" if m["errors"] else "")))
    print("picks:", ep.state.get("picks", "none"))


def cmd_pick(ep, a):
    jid = ep.state.get("illustrate_job")
    m = ep.results(jid) if jid else None
    if not m or m["status"] != "done":
        sys.exit(f"illustration results for {jid} are not available yet (run the worker on the PC)")
    src = os.path.join(GHM, "jobs", "results", jid)
    picks = {}
    if a.auto:
        for b in ep.illustrated():
            cands = [im["file"] for im in m["images"] if im["shot"] == b["id"]]
            ranked = sorted(cands, key=lambda f: -score(os.path.join(src, f)))
            picks[b["id"]] = ranked[0]
            print(f"{b['id']}: {' > '.join(ranked)}  (technical rank; review the contact sheet before approving)")
    for item in a.picks or []:
        k, v = item.split("=", 1)
        picks[k] = v
    missing = [b["id"] for b in ep.illustrated() if b["id"] not in picks]
    if missing:
        sys.exit(f"no pick for {missing}")
    ep.state["picks"] = picks
    if a.no_upscale:
        ep.state["plate_source"] = "candidates"
    else:
        uid = next_id(ep.id + "_up")
        job = {"job_id": uid, "kind": "upscale", "notes": f"2x RealESRGAN plates for {ep.id}", "workflow": "upscale2x",
               "shots": [{"id": k, "init_image": f"jobs/results/{jid}/{v}", "seeds": [0]} for k, v in picks.items()],
               "output": {"format": "jpg", "quality": 95, "contact_sheet": False}}
        save(os.path.join(GHM, "jobs", "queue", uid + ".json"), job)
        ep.state["upscale_job"] = uid
        ep.state["plate_source"] = "upscale"
        print(f"queued jobs/queue/{uid}.json (2x upscale of the picks)")
    ep.save_state()


# ------------------------------------------------------------------------------------------- 3. plates
def plate_files(ep):
    if ep.state.get("plate_source") == "upscale":
        m = ep.results(ep.state.get("upscale_job", ""))
        if not m or m["status"] != "done":
            return None
        src = os.path.join(GHM, "jobs", "results", ep.state["upscale_job"])
        return {im["shot"]: os.path.join(src, im["file"]) for im in m["images"]}
    src = os.path.join(GHM, "jobs", "results", ep.state["illustrate_job"])
    return {k: os.path.join(src, v) for k, v in ep.state["picks"].items()}


def cmd_plates(ep, a=None):
    files = plate_files(ep) if ep.state.get("picks") else None
    if not files:
        sys.exit("plates are not available yet (pick candidates, then wait for the upscale job)")
    pdir = os.path.join(ep.dir, "plates")
    os.makedirs(pdir, exist_ok=True)
    notes = load(os.path.join(ep.dir, "annotations.json"), {})
    report = {}
    for b in ep.illustrated():
        kind = b["type"]
        ext = os.path.splitext(files[b["id"]])[1]
        dst = os.path.join(pdir, b["id"] + ext)
        shutil.copy2(files[b["id"]], dst)
        img = cv2.cvtColor(cv2.imread(dst), cv2.COLOR_BGR2RGB)
        H, W = img.shape[:2]
        hint = b.get("matte_hint") or presets.default_hint(kind, W, H)
        alpha, qa = None, None
        if hint:
            alpha = masks.make(img, {"ref_width": W, "fg_hint": hint}, "hybrid")
            met, probs = masks.qa(img, alpha)
            qa = dict(metrics=met, problems=probs)
            masks.review_sheet(img, alpha, os.path.join(pdir, b["id"] + "_mask_review.jpg"),
                               f"{b['id']}: " + ("FALLBACK one layer" if probs else "matte ok"))
            if probs:
                alpha = None
        meta = presets.auto_meta(kind, img, alpha, seed=len(report))
        if alpha is not None:
            cv2.imwrite(os.path.join(pdir, b["id"] + "_mask.png"), (alpha * 255).astype(np.uint8))
            meta["mask"] = b["id"] + "_mask.png"
        ann = notes.get(b["id"], {})
        for key in ("eyes", "sway", "face"):
            if key in ann:
                meta[key] = ann[key]
        save(os.path.join(pdir, b["id"] + ".json"), meta)
        subprocess.run([PY, "-m", "ghm4.plate_tool", "overlay", dst, os.path.join(pdir, b["id"] + ".json")], cwd=GHM,
                       capture_output=True)
        todo = []
        if kind == "portrait" and "eyes" not in meta:
            todo.append("eyes (blink)")
        if kind in ("portrait", "hero_wide") and "sway" not in meta:
            todo.append("hand pivot (optional)")
        report[b["id"]] = dict(size=[W, H], matte=bool(alpha is not None), qa=qa, flags=len(meta.get("flags", [])),
                               sky=meta.get("sky", {}).get("y"), annotate=todo)
        print(f"{b['id']}: {W}x{H}, matte {'yes' if alpha is not None else 'no'}, flags {len(meta.get('flags', []))}, "
              f"sky {meta.get('sky', {}).get('y')}" + (f", to annotate: {', '.join(todo)}" if todo else ""))
    ep.state["plates"] = report
    ep.save_state()


def cmd_sheet(ep, a):
    pdir = os.path.join(ep.dir, "plates")
    f = next(os.path.join(pdir, x) for x in os.listdir(pdir) if x.startswith(a.beat + ".") and not x.endswith(".json"))
    im = cv2.imread(f)
    H, W = im.shape[:2]
    step = max(25, int(round(W / 20 / 25)) * 25)
    for x in range(0, W, step):
        cv2.line(im, (x, 0), (x, H), (255, 255, 255), 1)
        cv2.putText(im, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    for y in range(0, H, step):
        cv2.line(im, (0, y), (W, y), (255, 255, 255), 1)
        cv2.putText(im, str(y), (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    out = os.path.join(pdir, a.beat + "_grid.jpg")
    cv2.imwrite(out, im)
    print(out, f"(plate pixels; write eyes / sway / face for '{a.beat}' into annotations.json, then run plates again)")


# ------------------------------------------------------------------------------------------- 4. storyboard
def beat_times(ep):
    beats = ep.spec["beats"]
    nar = ep.spec.get("narration")
    if nar:
        sys.path.insert(0, GHM)
        from mosaic import captions
        tr = open(os.path.join(GHM, nar["transcript"]), encoding="utf-8").read().strip()
        words = captions.map_words(tr, load(os.path.join(GHM, nar["words"])), nar.get("spoken"))
        toks = [w["text"].lower().strip(".,:;!?\"'") for w in words]
        starts = []
        for b in beats:
            q = [x.lower().strip(".,:;!?\"'") for x in b["cue"].split()]
            hit = [i for i in range(len(toks) - len(q) + 1) if toks[i:i + len(q)] == q]
            if len(hit) != 1:
                sys.exit(f"cue {b['cue']!r} found {len(hit)} times in the transcript")
            starts.append(round(max(0.0, words[hit[0]]["start"] - 0.15), 3))
        starts[0] = 0.0
        dur = nar.get("excerpt_end") or round(words[-1]["end"] + 1.2, 3)
    else:
        starts, t = [], 0.0
        for b in beats:
            starts.append(round(t, 3))
            t += b["duration"]
        dur = round(t, 3)
    ends = starts[1:] + [dur]
    return [dict(b, start=s, end=e) for b, s, e in zip(beats, starts, ends)], dur


def cmd_storyboard(ep, a=None):
    timed, dur = beat_times(ep)
    shots, trans = [], []
    prev = None
    for b in timed:
        L = b["end"] - b["start"]
        if b["type"] == "map":
            shot = {"id": b["id"], "type": "map", "start": b["start"], "end": b["end"], "map": ep.rel(b["map"])}
        else:
            pdir = os.path.join(ep.dir, "plates")
            pf = next((x for x in sorted(os.listdir(pdir)) if x.startswith(b["id"] + ".") and not x.endswith(".json")), None) \
                if os.path.isdir(pdir) else None
            if not pf:
                sys.exit(f"plate for {b['id']} missing: run 'plates' first")
            meta = load(os.path.join(pdir, b["id"] + ".json"))
            im = cv2.imread(os.path.join(pdir, pf))
            H, W = im.shape[:2]
            k = W / meta.get("ref_width", W)
            cam = presets.camera(b["type"], W / k, H / k, meta.get("face"))
            shot = {"id": b["id"], "type": "plate", "start": b["start"], "end": b["end"], "plate": f"plates/{pf}",
                    "meta": f"plates/{b['id']}.json", "camera": cam}
            mo = b.get("motion", {})
            if meta.get("eyes"):
                shot["blink"] = [round(mo.get("blink_at", 0.45) * L, 2)]
            if meta.get("sway"):
                for s in meta["sway"]:
                    s.setdefault("at", round(mo.get("sway_at", 0.2) * L, 2))
                save(os.path.join(pdir, b["id"] + ".json"), meta)
            if b["type"] == "battle":
                pts = meta.get("puff_points", [])[: b.get("puffs", 2)]
                shot.update(gains={"flags": 2.0, "bob": 1.6, "battle": 1.0}, haze=0.14,
                            puffs=[[round(0.12 * L + i * 0.38 * L, 2), p[0] / k, p[1] / k] for i, p in enumerate(pts)])
            if b.get("text"):
                shot["scrim"] = [[560, 1280, 0.68]]
        if b.get("text"):
            shot["text"] = b["text"]
        shots.append(shot)
        if prev is not None:
            trans.append({"at": b["start"], "type": b.get("transition", presets.transition(prev["type"], b["type"]))})
        prev = b
    sb = {"id": ep.id, "fps": 30, "duration": dur, "fade_out": 0.5, "shots": shots, "transitions": trans,
          "audio": ep.spec.get("audio") or presets.sound(timed, dur)}
    nar = ep.spec.get("narration")
    if nar:
        sb["excerpt"] = bool(nar.get("excerpt_end"))
        sb["captions"] = {"transcript": ep.rel(nar["transcript"]), "words": ep.rel(nar["words"]), "groups": nar["groups"],
                          "y": 1410, "size": 60, **({"spoken": nar["spoken"]} if nar.get("spoken") else {})}
        sb["audio"]["narration_file"] = ep.rel(nar["audio"])
        sb["audio"].setdefault("bed_under_voice_db", 20)
        sb["audio"].setdefault("bed_in_pauses_db", 11)
    save(os.path.join(ep.dir, "storyboard.json"), sb)
    print(f"storyboard.json: {len(shots)} shots, {dur}s, transitions {[t['type'] for t in trans]}")
    if nar:
        r = subprocess.run([PY, "-m", "ghm4.narrate", os.path.join(ep.dir, "storyboard.json"), "check"], cwd=GHM, capture_output=True, text=True)
        for ln in r.stdout.splitlines():
            if ln.startswith("CONFLICT"):
                print(ln)


# ------------------------------------------------------------------------------------------- 5. render
def cmd_render(ep, a):
    sb = os.path.join(ep.dir, "storyboard.json")
    args = [PY, "-m", "ghm4.render", sb] + (["--final", "--workers", "3"] if a.final else [])
    subprocess.run(args, cwd=GHM, check=True)
    W, H = (1080, 1920) if a.final else (720, 1280)
    pic = os.path.join(ep.dir, "output", f"{ep.id}_{W}x{H}_picture.mp4")
    if ep.spec.get("narration"):
        subprocess.run([PY, "-m", "ghm4.narrate", sb, "finish", pic], cwd=GHM, check=True)
        final = os.path.join(ep.dir, "output", f"{ep.id}_{W}x{H}_final.mp4")
        flags = ["--no-logo"] + (["--excerpt"] if ep.spec["narration"].get("excerpt_end") else [])
        r = subprocess.run([PY, "tools/verify_delivery.py", final, ep.dir, *flags, "--report",
                            os.path.join(ep.dir, "output", f"verify_{W}.json")], cwd=GHM, capture_output=True, text=True)
        print(f"verification: {'PASS' if r.returncode == 0 else 'FAIL'} -> output/verify_{W}.json")
        print(final)
    else:
        final = pic
    q = subprocess.run([PY, "-m", "ghm4.qc", sb, final, "--out", os.path.join(ep.dir, "output", f"qc_{W}")], cwd=GHM,
                       capture_output=True, text=True)
    print("visual QC: " + q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "visual QC: no output")
    for ln in q.stdout.splitlines()[:-1]:
        print("  " + ln)


def cmd_run(ep, a):
    """Every step that can run now; stops with the next human/PC action."""
    if not ep.state.get("illustrate_job"):
        cmd_jobs(ep)
        print("NEXT: commit + push, then on the PC: start ComfyUI and run_worker.bat --once")
        return
    m = ep.results(ep.state["illustrate_job"])
    if not m:
        print(f"NEXT: waiting for {ep.state['illustrate_job']} from the PC worker")
        return
    if m["status"] != "done":
        print(f"illustration job failed on the PC: {m['errors']}")
        return
    if not ep.state.get("picks"):
        print("NEXT: review jobs/results/<job>/contact_sheet.jpg, then: pick <dir> beat=file ... (or --auto)")
        return
    if plate_files(ep) is None:
        print(f"NEXT: waiting for {ep.state.get('upscale_job')} from the PC worker")
        return
    cmd_plates(ep)
    cmd_storyboard(ep)
    cmd_render(ep, argparse.Namespace(final=False))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "jobs", "status", "plates", "storyboard"):
        p = sp.add_parser(name)
        p.add_argument("episode")
        if name == "jobs":
            p.add_argument("--force", action="store_true")
    p = sp.add_parser("pick")
    p.add_argument("episode")
    p.add_argument("picks", nargs="*")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--no-upscale", action="store_true")
    p = sp.add_parser("sheet")
    p.add_argument("episode")
    p.add_argument("beat")
    p = sp.add_parser("render")
    p.add_argument("episode")
    p.add_argument("--final", action="store_true")
    a = ap.parse_args()
    ep = Episode(a.episode)
    {"run": cmd_run, "jobs": cmd_jobs, "status": cmd_status, "pick": cmd_pick, "plates": cmd_plates, "sheet": cmd_sheet,
     "storyboard": cmd_storyboard, "render": cmd_render}[a.cmd](ep, a)


if __name__ == "__main__":
    main()

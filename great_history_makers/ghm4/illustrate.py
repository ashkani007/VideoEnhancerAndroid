#!/usr/bin/env python3
"""Cloud side of the illustration loop: write ComfyUI jobs, review results, pick plates.

  python -m ghm4.illustrate job jobs/specs/napoleon_test3_v1.json        # spec -> jobs/queue/<job_id>.json
  python -m ghm4.illustrate status                                       # queue vs results
  python -m ghm4.illustrate pick <job_id> <shot>=<file> [...] --as <upscale_job_id>
                                                                         # chosen candidates -> 2x upscale job
  python -m ghm4.illustrate place <upscale_job_id> <episode_dir>         # upscaled plates -> <episode>/plates/

Prompts are assembled from the bibles (comfyui/bible/): shot framing + scene + character descriptor + style rendering
+ lighting (shot override or the style default) + the 9:16 composition rule. The negative prompt is the style negative
plus the character negative. The job file contains only data; the local worker validates it before running it.
"""
import argparse
import json
import os
import shutil
import sys

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIBLE = os.path.join(GHM, "comfyui", "bible")
QUEUE = os.path.join(GHM, "jobs", "queue")
RESULTS = os.path.join(GHM, "jobs", "results")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prompt_for(shot, style, chars):
    parts = [shot.get("framing", ""), shot["scene"]]
    negs = [style["negative"]]
    for cid in shot.get("characters", []):
        var = shot.get("variants", {}).get(cid)                      # costume / age variant from the character bible
        parts.append(chars[cid]["variants"][var] if var else chars[cid]["descriptor"])
        negs.append(chars[cid].get("negative", ""))
    parts += [style["positive"], shot.get("lighting", style["lighting_default"]), style.get("composition") or style["composition_9x16"]]
    if shot.get("negative_extra"):
        negs.append(shot["negative_extra"])
    return ", ".join(p.strip().rstrip(",") for p in parts if p), ", ".join(n for n in negs if n)


def make_job(spec):
    style = load(os.path.join(BIBLE, f"style_{spec.get('style', 'ghm_cinematic_v1')}.json"))
    char_ids = {c for s in spec["shots"] for c in s.get("characters", [])}
    chars = {c: load(os.path.join(BIBLE, "characters", f"{c}.json")) for c in char_ids}
    sm, sz, hi, ip = style["sampler"], style["size"], style["hires"], style["ipadapter"]
    wf = spec.get("workflow", "sdxl_style_face")
    face_ref = next((chars[c]["face_reference"] for c in sorted(char_ids) if chars[c].get("face_reference")), None)
    shots = []
    for s in spec["shots"]:
        pos, neg = prompt_for(s, style, chars)
        shot = dict(id=s["id"], positive=pos, negative=neg, seeds=s["seeds"])
        if wf == "sdxl_style_face":                       # face adapter only where the character appears
            shot["ipadapter_face_weight"] = s.get("ipadapter_face_weight", 0.45 if s.get("characters") else 0.0)
        loras = [lo for c in s.get("characters", []) for lo in chars[c].get("loras", [])]
        if loras:
            shot["loras"] = loras
        for k in ("ipadapter_weight", "ipadapter_weight_type", "ipadapter_end_at", "init_image", "denoise", "cfg"):
            if k in s:
                shot[k] = s[k]
        shots.append(shot)
    defaults = dict(width=sz["width"], height=sz["height"], steps=sm["steps"], cfg=sm["cfg"], sampler_name=sm["sampler_name"],
                    scheduler=sm["scheduler"], hires_scale=hi["scale"], hires_steps=hi["steps"], hires_denoise=hi["denoise"],
                    ipadapter_weight=ip["weight"], ipadapter_weight_type=ip["weight_type"], ipadapter_end_at=ip["end_at"])
    refs = {"style": style["reference_image"]} if style.get("reference_image") else {}   # look development: no style ref yet
    if wf == "sdxl_style_face":
        if not face_ref:
            raise SystemExit("sdxl_style_face needs a character with face_reference in its bible")
        refs["face"] = face_ref
    if wf == "flux_schnell":                              # distilled model: 4 steps, CFG 1, no negative, no IP-Adapter
        defaults = dict(width=sz["width"], height=sz["height"], steps=4, cfg=1.0, sampler_name="euler", scheduler="simple",
                        hires_scale=hi["scale"], hires_steps=6, hires_denoise=0.4)
        refs = {}
        for sh in shots:
            sh.pop("ipadapter_weight", None)
    return {
        "job_id": spec["job_id"], "kind": "illustrate", "created": spec.get("created", ""),
        "notes": spec.get("notes", ""), "workflow": wf,
        "defaults": defaults,
        "references": refs,
        "shots": shots,
        "output": {"format": "jpg", "quality": 92, "contact_sheet": True},
    }


def cmd_job(a):
    job = make_job(load(a.spec))
    sys.path.insert(0, os.path.join(GHM, "comfyui", "worker"))
    import ghm_worker
    ghm_worker.validate(job, GHM)                       # same checks the local worker will run
    os.makedirs(QUEUE, exist_ok=True)
    out = os.path.join(QUEUE, job["job_id"] + ".json")
    if os.path.exists(out) and not a.force:
        raise SystemExit(f"{out} exists; job ids are immutable (use a new id, or --force before the worker picked it up)")
    json.dump(job, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n = sum(len(s["seeds"]) for s in job["shots"])
    print(f"queued {out}: {len(job['shots'])} shots, {n} images")


def cmd_status(a):
    for f in sorted(os.listdir(QUEUE)):
        jid = f[:-5]
        m = os.path.join(RESULTS, jid, "manifest.json")
        if os.path.exists(m):
            mm = load(m)
            sysinfo = mm.get("system", {})
            print(f"{jid}: {mm['status']}, {len(mm['images'])} images, GPU {sysinfo.get('gpu')} "
                  f"({sysinfo.get('vram_total_gb')} GB)" + (f", errors: {mm['errors']}" if mm["errors"] else ""))
        else:
            print(f"{jid}: waiting for the local worker")


def cmd_pick(a):
    src = os.path.join(RESULTS, a.job_id)
    shots = []
    for item in a.picks:
        sid, fname = item.split("=", 1)
        path = os.path.join(src, fname)
        if not os.path.exists(path):
            raise SystemExit(f"missing {path}")
        shots.append(dict(id=sid, init_image=os.path.relpath(path, GHM).replace(os.sep, "/"), seeds=[0]))
    job = {"job_id": a.as_id, "kind": "upscale", "notes": f"2x RealESRGAN of picks from {a.job_id}", "workflow": "upscale2x",
           "shots": shots, "output": {"format": "jpg", "quality": 95, "contact_sheet": False}}
    sys.path.insert(0, os.path.join(GHM, "comfyui", "worker"))
    import ghm_worker
    ghm_worker.validate(job, GHM)
    out = os.path.join(QUEUE, a.as_id + ".json")
    json.dump(job, open(out, "w", encoding="utf-8"), indent=1)
    print(f"queued {out}")


def cmd_place(a):
    src = os.path.join(RESULTS, a.job_id)
    m = load(os.path.join(src, "manifest.json"))
    dst = os.path.join(a.episode, "plates")
    os.makedirs(dst, exist_ok=True)
    for im in m["images"]:
        ext = os.path.splitext(im["file"])[1]
        shutil.copy2(os.path.join(src, im["file"]), os.path.join(dst, im["shot"] + ext))
        print(f"{im['shot']}{ext} -> {dst}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    j = sp.add_parser("job")
    j.add_argument("spec")
    j.add_argument("--force", action="store_true")
    sp.add_parser("status")
    p = sp.add_parser("pick")
    p.add_argument("job_id")
    p.add_argument("picks", nargs="+")
    p.add_argument("--as", dest="as_id", required=True)
    pl = sp.add_parser("place")
    pl.add_argument("job_id")
    pl.add_argument("episode")
    a = ap.parse_args()
    {"job": cmd_job, "status": cmd_status, "pick": cmd_pick, "place": cmd_place}[a.cmd](a)


if __name__ == "__main__":
    main()
